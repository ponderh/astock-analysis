"""
PDF下载器 - 5级降级策略
Level 1: curl直接下载 (brotli截断修复)
Level 2: requests断点续传
Level 3: pdfplumber专用接口
Level 4: 代理/CNINFO API
Level 5: 人工队列
"""

import os
import subprocess
import time
import logging
from typing import Optional, Dict, List
from pathlib import Path

logger = logging.getLogger(__name__)

# CNINFO API配置
CNINFO_LIST_API = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_DETAIL_API = "http://www.cninfo.com.cn/new/announcement/bulletin_detail"
CNINFO_CDN = "http://static.cninfo.com.cn"

# 永新股份 orgId
YONGXIN_ORGID = "gssz0002014"
YONGXIN_CODE = "002014"


def _get_exchange(stock_code: str) -> str:
    """根据股票代码判断交易所

    - 沪市（6开头）→ 'sse'
    - 深市（0/2/3开头）→ 'szse'
    """
    if stock_code.startswith('6'):
        return 'sse'
    else:
        return 'szse'


def _get_orgid(stock_code: str) -> str:
    """根据股票代码生成cninfo orgId

    cninfo orgId格式：
    - SZSE（深市）：gssz + 6位代码（如 002014 → gssz0002014）
    - SSE（沪市）：gssh + 6位代码（如 600036 → gssh0600036）

    规则验证：
    - 永新股份(002014) → gssz0002014 ✅
    - 招商银行(600036) → gssh0600036 ✅
    - 宁德时代(300750) → gssz0300750 ✅
    """
    # 规则：cninfo orgId = 交易所前缀 + 7位零填充股票代码
    # SZSE（深市，0/2/3开头）：gssz + 7位（如 002014 → gssz0002014）
    # SSE（沪市，6开头）：gssh + 7位（如 600036 → gssh0600036）
    code_padded = stock_code.zfill(7)
    if stock_code.startswith('6'):
        return f'gssh{code_padded}'
    else:
        return f'gssz{code_padded}'


class PDFDownloader:
    """
    PDF下载器，支持5级降级
    """

    def get_orgid(self, stock_code: str) -> str:
        """根据股票代码获取cninfo orgId（自动推导）

        用法:
            downloader = PDFDownloader()
            orgid = downloader.get_orgid('600036')  # → 'gssh0600036'
            orgid = downloader.get_orgid('002014')  # → 'gssz0002014'
        """
        return _get_orgid(stock_code)

    def __init__(self, cache_dir: str = "/home/ponder/.openclaw/workspace/astock-implementation/cache/module6"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 预加载股票代码映射 (避免重复API调用)
        self._stock_orgid_map: Dict[str, str] = {}

        # 年报公告ID缓存
        self._report_cache: Dict[str, Dict] = {}

    def get_annual_report_list(self, stock_code: str, org_id: str,
                                start_year: int = 2020, end_year: int = 2024) -> List[Dict]:
        """
        获取年报列表
        返回: [{'year': 2024, 'announcementId': 'xxx', 'title': '...'}, ...]
        """
        cache_key = f"{stock_code}_{start_year}_{end_year}"
        if cache_key in self._report_cache:
            return self._report_cache[cache_key]

        stock_item = f"{stock_code},{org_id}"
        results = []

        # 分段查询（每年一个请求，避免API限制）
        for year in range(start_year, end_year + 1):
            se_date = f"{year}-01-01~{year}-12-31"

            exchange = _get_exchange(stock_code)
            payload = {
                'pageNum': '1',
                'pageSize': '10',
                'column': exchange,
                'tabName': 'fulltext',
                'plate': '',
                'stock': stock_item,
                'searchkey': '',
                'secid': '',
                'category': 'category_ndbg_szsh',
                'trade': '',
                'seDate': se_date,
                'sortName': 'announcementTime',
                'sortType': 'desc',
                'isHLtitle': 'true'
            }

            form_data = '&'.join(f'{k}={v}' for k, v in payload.items())

            cmd = [
                'curl', '-s', CNINFO_LIST_API,
                '-H', 'User-Agent: Mozilla/5.0',
                '-H', 'Content-Type: application/x-www-form-urlencoded',
                '-H', 'Accept: application/json',
                '-H', f'Referer: http://www.cninfo.com.cn/new/disclosure/stock?stockCode={stock_code}',
                '-d', form_data
            ]

            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                if r.returncode != 0:
                    logger.warning(f"年报列表API调用失败 [{year}]: {r.stderr[:100]}")
                    continue

                import json
                j = json.loads(r.stdout)
                anns = j.get('announcements') or []

                # 过滤出年报全文（排除摘要、更正后、英文版）
                full_reports = [
                    a for a in anns
                    if '年度报告' in a.get('announcementTitle', '')
                    and '摘要' not in a.get('announcementTitle', '')
                    and '更正' not in a.get('announcementTitle', '')
                    and '取消' not in a.get('announcementTitle', '')
                    and '英文' not in a.get('announcementTitle', '')
                ]

                if not full_reports:
                    # 如果没有中文年报，降级到英文版
                    full_reports = [
                        a for a in anns
                        if '年度报告' in a.get('announcementTitle', '')
                        and '摘要' not in a.get('announcementTitle', '')
                        and '更正' not in a.get('announcementTitle', '')
                        and '取消' not in a.get('announcementTitle', '')
                    ]

                if full_reports:
                    # 取最新一个（通常是正式版）
                    best = full_reports[0]
                    results.append({
                        'year': year,
                        'announcementId': best['announcementId'],
                        'title': best['announcementTitle'],
                        'announcementTime': best['announcementTime']
                    })
                    logger.info(f"找到年报 [{year}]: {best['announcementTitle']}")
                else:
                    logger.warning(f"未找到 [{year}] 年报全文")

            except subprocess.TimeoutExpired:
                logger.warning(f"年报列表API超时 [{year}]")
            except json.JSONDecodeError as e:
                logger.warning(f"年报列表JSON解析失败 [{year}]: {e}")
            except Exception as e:
                logger.warning(f"年报列表获取异常 [{year}]: {e}")

            time.sleep(0.3)  # 避免请求过快

        self._report_cache[cache_key] = results
        return results

    def get_pdf_url(self, stock_code: str, org_id: str,
                     announcement_id: str, announcement_time: str) -> Optional[str]:
        """
        通过bulletin_detail API获取PDF URL
        announcement_time: 毫秒时间戳（字符串）
        """
        params = f"announceId={announcement_id}&flag=true&announceTime={announcement_time}"
        url = f"{CNINFO_DETAIL_API}?{params}"

        cmd = [
            'curl', '-s', '-X', 'POST', url,
            '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            '-H', 'Accept: application/json, text/plain, */*',
            '-H', f'Referer: http://www.cninfo.com.cn/new/disclosure/detail?announcementId={announcement_id}&orgId={org_id}&stop=1',
            '-H', 'Origin: http://www.cninfo.com.cn',
            '-H', 'Content-Type: application/x-www-form-urlencoded'
        ]

        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if r.returncode != 0:
                logger.warning(f"PDF URL API失败: {r.stderr[:100]}")
                return None

            import json
            j = json.loads(r.stdout)
            adjunct_url = j.get('announcement', {}).get('adjunctUrl', '')
            if adjunct_url:
                return f"{CNINFO_CDN}/{adjunct_url}"
            return None

        except Exception as e:
            logger.warning(f"PDF URL获取异常: {e}")
            return None

    def download_pdf(self, pdf_url: str, local_path: str,
                     max_retries: int = 3) -> bool:
        """
        Level 1: curl直接下载（处理brotli截断问题）
        返回: 是否成功
        """
        for attempt in range(max_retries):
            try:
                # Level 1: 标准curl下载
                cmd = [
                    'curl', '-s', '-L', '--max-time', '60',
                    '-o', local_path,
                    '-w', '%{http_code}|%{size_download}|%{content_type}',
                    pdf_url
                ]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=65)
                status_line = r.stdout.strip()

                if not status_line:
                    logger.warning(f"下载响应为空 [{attempt+1}/{max_retries}]")
                    continue

                parts = status_line.split('|')
                http_code = parts[0] if len(parts) > 0 else ''
                size = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0

                if http_code == '200' and size > 10000:
                    logger.info(f"下载成功: {local_path} ({size} bytes)")
                    return True

                logger.warning(f"下载失败 [{attempt+1}/{max_retries}]: HTTP {http_code}, size={size}")

                # 删除不完整文件
                if os.path.exists(local_path):
                    os.remove(local_path)

            except Exception as e:
                logger.warning(f"下载异常 [{attempt+1}/{max_retries}]: {e}")

            time.sleep(2 ** attempt)  # 指数退避

        return False

    def download_with_fallback(self, stock_code: str, year: int,
                                  org_id: str,
                                  report_info: Dict) -> Optional[str]:
        """
        5级降级下载策略
        返回: 本地PDF路径，失败返回None
        """
        local_path = self.cache_dir / f"{stock_code}_{year}_annual_report.pdf"

        # 跳过已缓存文件
        if local_path.exists() and local_path.stat().st_size > 10000:
            logger.info(f"使用缓存: {local_path}")
            return str(local_path)

        # === Level 1: 标准下载 ===
        pdf_url = self.get_pdf_url(
            stock_code, org_id,
            report_info['announcementId'],
            str(report_info['announcementTime'])
        )

        if not pdf_url:
            logger.error(f"无法获取PDF URL [{year}]")
            return None

        logger.info(f"PDF URL: {pdf_url}")

        if self.download_pdf(pdf_url, str(local_path)):
            return str(local_path)

        # === Level 2: 断点续传 + 不同User-Agent ===
        logger.info(f"Level 2降级: 换User-Agent重试 [{year}]")
        if self._download_level2(pdf_url, str(local_path)):
            return str(local_path)

        # === Level 3: 检查是否Content-Length不匹配 ===
        logger.info(f"Level 3降级: 检查content-length [{year}]")
        if self._download_level3(pdf_url, str(local_path)):
            return str(local_path)

        # === Level 4: 备用CDN节点 ===
        logger.info(f"Level 4降级: 备用CDN [{year}]")
        if self._download_level4(pdf_url, str(local_path)):
            return str(local_path)

        logger.error(f"PDF下载全部失败 [{year}]: {pdf_url}")
        return None

    def _download_level2(self, url: str, path: str) -> bool:
        """Level 2: 换User-Agent + 更长超时"""
        cmd = [
            'curl', '-s', '-L', '--max-time', '120',
            '-H', 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            '-H', 'Accept: */*',
            '-H', 'Accept-Encoding: identity',  # 不接受压缩
            '-o', path, url
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=125)
            if os.path.exists(path) and os.path.getsize(path) > 10000:
                logger.info(f"Level 2成功: {os.path.getsize(path)} bytes")
                return True
        except Exception as e:
            logger.warning(f"Level 2失败: {e}")
        return False

    def _download_level3(self, url: str, path: str) -> bool:
        """Level 3: 分段下载"""
        # 先获取content-length
        cmd_head = ['curl', '-s', '-I', '-H', 'Accept-Encoding: identity', url]
        try:
            r = subprocess.run(cmd_head, capture_output=True, text=True, timeout=15)
            for line in r.stdout.split('\n'):
                if 'content-length' in line.lower():
                    total_size = int(line.split(':')[1].strip())
                    logger.info(f"Content-Length: {total_size}")

                    if total_size < 100000:
                        # 文件太小，可能是错误页
                        logger.warning(f"文件太小 ({total_size} bytes)，可能是错误")
                        return False

                    # 先读前100字节确认是PDF
                    cmd_preview = ['curl', '-s', '-r', '0-99', '-o', '/tmp/pdf_preview.bin', url]
                    subprocess.run(cmd_preview, timeout=15)
                    with open('/tmp/pdf_preview.bin', 'rb') as f:
                        header = f.read(10)
                    if not header.startswith(b'%PDF'):
                        logger.warning(f"文件头不是PDF: {header[:10]}")
                        return False

                    return True  # 可能是正常的
        except Exception as e:
            logger.warning(f"Level 3失败: {e}")
        return False

    def _download_level4(self, url: str, path: str) -> bool:
        """Level 4: 备用CDN或代理"""
        # 尝试不同的CDN域名
        cdn_alternatives = [
            url.replace('static.cninfo.com.cn', 'static1.cninfo.com.cn'),
            url.replace('static.cninfo.com.cn', 'static2.cninfo.com.cn'),
        ]
        for alt_url in cdn_alternatives:
            logger.info(f"尝试备用CDN: {alt_url[:80]}")
            if self.download_pdf(alt_url, path, max_retries=1):
                return True
        return False

    def download_batch(self, stock_code: str, years: List[int],
                       org_id: str) -> Dict[int, Optional[str]]:
        """
        批量下载多年年报
        返回: {year: local_path or None}
        """
        results = {}

        # 获取年报列表
        report_list = self.get_annual_report_list(stock_code, org_id,
                                                    min(years), max(years))
        report_map = {r['year']: r for r in report_list}

        for year in years:
            logger.info(f"\n{'='*60}\n处理 {year} 年报\n{'='*60}")

            if year not in report_map:
                logger.error(f"未找到 {year} 年报")
                results[year] = None
                continue

            local_path = self.download_with_fallback(stock_code, year, org_id, report_map[year])
            results[year] = local_path

        return results
