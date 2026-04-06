"""
多来源年报PDF下载器
支持: 东方财富(cn/ext)、巨潮(cninfo备选)
作者: 虫虫 @ 2026-04-06
"""

import re, time, os
import urllib.request
import json

CACHE_DIR = '/home/ponder/.openclaw/workspace/astock-implementation/cache/module6'
os.makedirs(CACHE_DIR, exist_ok=True)


# ─────────────────────────────────────────────────────────────
# 东方财富接口（主）
# ─────────────────────────────────────────────────────────────
def get_eastmoney_announcements(stock_code, page=1, page_size=100):
    """东方财富公告列表"""
    url = (
        f"http://np-anotice-stock.eastmoney.com/api/security/ann"
        f"?cb=jQuery&sr=-1&page_size={page_size}&page_index={page}"
        f"&ann_type=A&stock_list={stock_code}"
    )
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'http://data.eastmoney.com/'
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read().decode('utf-8')
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if m:
        return json.loads(m.group()).get('data', {}).get('list', []) or []
    return []


def get_pdf_url_eastmoney(art_code):
    """东方财富PDF URL解析"""
    url = (
        f"http://np-cnotice-stock.eastmoney.com/api/content/ann"
        f"?art_code={art_code}&client_source=web&page=1"
    )
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://data.eastmoney.com/'
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        d = json.loads(resp.read().decode('utf-8'))
    attach = (d.get('data', {}).get('attach_list', []) or
              d.get('data', {}).get('attach_list_ch', []) or [])
    for a in attach:
        u = a.get('attach_url', '')
        if u and '.pdf' in u.lower():
            return u
    return None


# ─────────────────────────────────────────────────────────────
# 巨潮备用接口（cninfo同集团，部分可用）
# ─────────────────────────────────────────────────────────────
def get_chaoxian_announcements(stock_code, max_pages=3):
    """巨潮资讯网公告列表（cninfo同集团，IP限速更友好）"""
    # 巨潮不需要登录即可获取列表
    results = []
    for page in range(1, max_pages + 1):
        url = (
            f"http://www.cninfo.com.cn/new/hisAnnouncement/query"
            f"?pageNum={page}&pageSize=30&column=szse"
            f"&tabName=fulltext&plate=&stock={stock_code}"
            f"&searchkey=&secid=&category=&trade=&seDate=&sortName="
            f"announcementTime&sortType=desc&isHLtitle=true"
        )
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Accept': 'application/json',
            'Referer': 'http://www.cninfo.com.cn/'
        })
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                d = json.loads(resp.read().decode('utf-8'))
            items = d.get('announcements') or []
            if not items:
                break
            results.extend(items)
            if len(items) < 30:
                break
            time.sleep(2)  # 巨潮限速2秒
        except Exception as e:
            print(f"  巨潮第{page}页失败: {e}")
            break
    return results


def get_pdf_url_chaoxian(announcement_id):
    """巨潮PDF URL（需要另一个API）"""
    url = f"http://www.cninfo.com.cn/new/disclosure/detail?announcement_id={announcement_id}&orgId=gssz0603288"
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'http://www.cninfo.com.cn/'
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            d = json.loads(resp.read().decode('utf-8'))
        # 巨潮返回的PDF在 attach files 字段
        attachments = d.get('data', {}).get('attachments', []) or []
        for a in attachments:
            u = a.get('adjunctUrl', '')
            if u and '.pdf' in u.lower():
                if not u.startswith('http'):
                    u = 'http://www.cninfo.com.cn' + u
                return u
    except Exception as e:
        print(f"  巨潮PDF URL失败: {e}")
    return None


# ─────────────────────────────────────────────────────────────
# 主下载器（多来源优先）
# ─────────────────────────────────────────────────────────────
def download_annual_report(stock_code, year, save_dir=None):
    """
    下载年报PDF，尝试多个来源
    返回: (local_path, source) 或 (None, error_msg)
    """
    if save_dir is None:
        save_dir = CACHE_DIR
    os.makedirs(save_dir, exist_ok=True)

    local_path = os.path.join(save_dir, f"{stock_code}_{year}年报.pdf")

    # 已在缓存
    if os.path.exists(local_path) and os.path.getsize(local_path) > 100_000:
        return local_path, 'cache'

    targets = [
        ('东方财富', _download_via_eastmoney),
        ('巨潮', _download_via_chaoxian),
    ]

    for source_name, fn in targets:
        try:
            result = fn(stock_code, year, local_path)
            if result:
                print(f"  ✅ [{source_name}] -> {local_path}")
                return result, source_name
        except Exception as e:
            print(f"  ⚠️ [{source_name}] 失败: {e}")
        time.sleep(1)

    return None, 'all_failed'


def _download_via_eastmoney(stock_code, year, local_path):
    """东方财富下载"""
    target_title = f"{year}年年度报告"
    for page in range(1, 4):
        items = get_eastmoney_announcements(stock_code, page=page)
        for it in items:
            title = it.get('title', '')
            art_code = it.get('art_code', '')
            notice_date = it.get('notice_date', '')[:10]
            if target_title in title and '摘要' not in title:
                print(f"  东方财富找到: {notice_date} {title[:40]}")
                pdf_url = get_pdf_url_eastmoney(art_code)
                if pdf_url:
                    urllib.request.urlretrieve(pdf_url, local_path)
                    if os.path.getsize(local_path) > 50_000:
                        return local_path
        time.sleep(0.5)
    return None


def _download_via_chaoxian(stock_code, year, local_path):
    """巨潮下载"""
    target_title = f"{year}年年度报告"
    items = get_chaoxian_announcements(stock_code, max_pages=3)
    for it in items:
        title = it.get('announcementTitle', '')
        aid = it.get('announcementId', '')
        notice_date = it.get('announcementTime', '')[:10]
        if target_title in title and '摘要' not in title:
            print(f"  巨潮找到: {notice_date} {title[:40]}")
            pdf_url = get_pdf_url_chaoxian(aid)
            if pdf_url:
                urllib.request.urlretrieve(pdf_url, local_path)
                if os.path.getsize(local_path) > 50_000:
                    return local_path
        time.sleep(0.5)
    return None


# ─────────────────────────────────────────────────────────────
# 批量下载
# ─────────────────────────────────────────────────────────────
def download_reports_batch(stock_code, years=None, report_types=None):
    """
    批量下载多种报告
    report_types: ['年报', '三季报', '半年报', '一季报']
    """
    if years is None:
        years = [2025, 2024]
    if report_types is None:
        report_types = ['年报', '三季报', '半年报', '一季报']

    type_map = {
        '年报': f"{year}年年度报告",
        '三季报': f"{year}年第三季度报告",
        '半年报': f"{year}年半年度报告",
        '一季报': f"{year}年第一季度报告",
    }

    results = {}
    for year in years:
        for rtype in report_types:
            target_title = type_map[rtype].replace(f"{year}", str(year))
            print(f"\n▶ 下载 {stock_code} {year}{rtype}...")
            path, src = download_annual_report(stock_code, year, CACHE_DIR)
            results[f"{year}{rtype}"] = (path, src)
            time.sleep(2)
    return results


# 兼容旧pipeline.py的占位类（pipeline.py已在重构中，如不需要可删除）
class PDFDownloader:
    """年报PDF下载器占位类，由多来源下载函数替代"""
    def __init__(self, stock_code=None):
        self.stock_code = stock_code

YONGXIN_CODE = ''  # 永信API停用，保留占位
YONGXIN_ORGID = ''

if __name__ == '__main__':
    # CLI test
    print('多来源下载器 - 请使用 download_reports_batch() 函数')
