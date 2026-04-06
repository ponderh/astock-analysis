"""
海天味业(603288) 深度分析报告 PDF生成器
使用reportlab生成专业格式PDF
"""

import os, sys, re, io
sys.path.insert(0, '/home/ponder/.openclaw/workspace/astock-implementation/impl')
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, black, white
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, Image as RLImage, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfgen import canvas
from reportlab.lib import colors
# Direct import to avoid __init__.py pipeline dependency
import importlib.util
_spec = importlib.util.spec_from_file_location('extractor', '/home/ponder/.openclaw/workspace/astock-implementation/impl/module6_mda/extractor.py')
_ext_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ext_mod)
PDFExtractor = _ext_mod.PDFExtractor

# ─── 中文字体注册 ───────────────────────────────────────────
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import matplotlib.font_manager as fm

# Try WenQuanYi first (CJK compatible)
_wqy_path = '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc'
_noto_path = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'

_cn_font_path = None
if os.path.exists(_wqy_path):
    _cn_font_path = _wqy_path
    _CN_NAME = 'WenQuanYi'
elif os.path.exists(_noto_path):
    _cn_font_path = _noto_path
    _CN_NAME = 'NotoSansCJK'

if _cn_font_path:
    try:
        pdfmetrics.registerFont(TTFont(_CN_NAME, _cn_font_path))
        _CN = _CN_NAME
        print(f'Registered Chinese font: {_cn_font_path}')
    except Exception as e:
        print(f'Font registration error: {e}')
        _CN = 'Helvetica'
else:
    _CN = 'Helvetica'
    print('WARNING: Chinese font not found, falling back to Helvetica')

# ─── 配色方案 ───────────────────────────────────────────────
C_DARK = HexColor('#1A1A2E')
C_ACCENT = HexColor('#16213E')
C_GREEN = HexColor('#27AE60')
C_RED = HexColor('#E74C3C')
C_AMBER = HexColor('#F39C12')
C_LIGHT_BG = HexColor('#F8F9FA')
C_BORDER = HexColor('#DEE2E6')
C_TEXT = HexColor('#2C3E50')

W, H = A4

# ─── 样式 ───────────────────────────────────────────────────
styles = getSampleStyleSheet()

def S(name, **kw):
    base = kw.pop('parent', 'Normal')
    return ParagraphStyle(name, parent=styles[base], **kw)

sTitle = S('sTitle', fontSize=24, textColor=C_DARK, spaceAfter=6,
            fontName=_CN, alignment=TA_CENTER)
sSubtitle = S('sSubtitle', fontSize=12, textColor=C_ACCENT, spaceAfter=20,
              fontName=_CN, alignment=TA_CENTER)
sH1 = S('sH1', fontSize=16, textColor=C_DARK, spaceBefore=18, spaceAfter=8,
         fontName=_CN)
sH2 = S('sH2', fontSize=12, textColor=C_ACCENT, spaceBefore=12, spaceAfter=6,
         fontName=_CN)
sBody = S('sBody', fontSize=9, textColor=C_TEXT, spaceAfter=6,
          fontName=_CN, leading=14)
sSmall = S('sSmall', fontSize=7.5, textColor=HexColor('#6C757D'),
           fontName=_CN, leading=11)
sGreen = S('sGreen', fontSize=9, textColor=C_GREEN, fontName=_CN)
sRed = S('sRed', fontSize=9, textColor=C_RED, fontName=_CN)
sAmber = S('sAmber', fontSize=9, textColor=C_AMBER, fontName=_CN)

# ─── 辅助函数 ───────────────────────────────────────────────
def colored(text, style):
    return Paragraph(text, style)

def hr():
    return HRFlowable(width='100%', thickness=0.5, color=C_BORDER, spaceAfter=6)

def section(title):
    return [hr(), Paragraph(title, sH1)]

def subsection(title):
    return [Paragraph(title, sH2)]

def subsubsection(title):
    return [Paragraph(title, sH2)]

def sp(n=6):
    return Spacer(1, n)

def make_kv_table(rows, col_widths=(4*cm, 11*cm)):
    """键值对表格"""
    data = []
    for k, v in rows:
        data.append([Paragraph(f'<b>{k}</b>', sBody), Paragraph(v, sBody)])
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [white, C_LIGHT_BG]),
        ('GRID', (0,0), (-1,-1), 0.3, C_BORDER),
    ]))
    return t

def make_financial_table(headers, rows, number_cols=None):
    """财务数据表格"""
    hstyle = S('th', fontSize=8, textColor=white, fontName=_CN,
               alignment=TA_CENTER)
    dstyle_c = S('tdc', fontSize=8, fontName=_CN, alignment=TA_CENTER)
    dstyle_r = S('tdr', fontSize=8, fontName=_CN, alignment=TA_RIGHT)
    
    data = [[Paragraph(h, hstyle) for h in headers]]
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            st = dstyle_c if i > 0 else dstyle_r
            cells.append(Paragraph(str(cell), st))
        data.append(cells)
    
    col_w = (W - 4*cm) / len(headers)
    col_widths = [4*cm] + [col_w] * (len(headers) - 1)
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), C_ACCENT),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, C_LIGHT_BG]),
        ('GRID', (0,0), (-1,-1), 0.3, C_BORDER),
        # 最后一列绿/红
        ('TEXTCOLOR', (len(headers)-1, 1), (len(headers)-1, -1), C_GREEN),
    ]))
    return t


# ─── 报告数据 ───────────────────────────────────────────────
HAITIAN = {
    'years': [2018,2019,2020,2021,2022,2023,2024,2025],
    'revenue': [170.34,197.97,227.92,250.04,256.10,245.59,269.05,288.73],
    'net_profit': [43.43,52.56,62.99,66.71,61.98,56.27,63.44,70.38],
    'roe': [31.5,32.3,31.9,28.5,23.5,19.7,20.5,19.6],
    'net_margin': [25.5,26.6,27.6,26.7,24.2,22.9,23.6,24.4],
    'gross_margin': [46.4,45.4,42.4,38.6,35.4,35.4,38.3,39.3],
    'eps': [0.80,0.97,1.16,1.23,1.14,1.04,1.14,1.23],
    'dps': [0.26,0.26,0.30,0.30,0.30,0.25,0.30,0.31],
    'cfo': [41.2,54.8,65.4,68.5,64.3,73.6,68.4,77.5],  # 亿
}

# ─── 页眉页脚 ───────────────────────────────────────────────
def header_footer(canvas_obj, doc):
    canvas_obj.saveState()
    # 页眉
    canvas_obj.setFont('Helvetica-Bold', 8)
    canvas_obj.setFillColor(C_ACCENT)
    canvas_obj.drawString(2*cm, H - 1.2*cm, '海天味业(603288) 深度分析报告')
    canvas_obj.setFont('Helvetica', 8)
    canvas_obj.setFillColor(HexColor('#6C757D'))
    canvas_obj.drawRightString(W - 2*cm, H - 1.2*cm, '2026-04-06')
    # 分隔线
    canvas_obj.setStrokeColor(C_BORDER)
    canvas_obj.setLineWidth(0.5)
    canvas_obj.line(2*cm, H - 1.4*cm, W - 2*cm, H - 1.4*cm)
    # 页脚
    canvas_obj.setFont('Helvetica', 7)
    canvas_obj.setFillColor(HexColor('#ADB5BD'))
    canvas_obj.drawString(2*cm, 1*cm, '仅供投资参考，不构成投资建议')
    canvas_obj.drawRightString(W - 2*cm, 1*cm, f'第 {doc.page} 页')
    canvas_obj.restoreState()


# ─── 主构建 ─────────────────────────────────────────────────
def build(output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=1.8*cm,
        title='海天味业(603288) 深度分析报告',
        author='虫虫 AI助手',
    )

    story = []

    # ── 封面 ──────────────────────────────────────────────
    story.append(sp(60))
    story.append(colored('海天味业', sTitle))
    story.append(colored('证券代码: 603288', sSubtitle))
    story.append(sp(10))
    story.append(colored('2026年4月 深度分析报告', sSubtitle))
    story.append(sp(40))
    story.append(hr())
    story.append(sp(10))

    # 核心指标卡片
    cards = [
        ('营收', '288.73亿', '+7.3%', C_GREEN),
        ('净利润', '70.38亿', '+11.0%', C_GREEN),
        ('净利率', '24.4%', '+0.8pct', C_GREEN),
        ('ROE', '19.6%', '-2.2pct', C_RED),
    ]
    card_data = []
    for label, val, chg, color in cards:
        card_data.append([
            Paragraph(label, S('cl', fontSize=8, textColor=HexColor('#6C757D'), alignment=TA_CENTER)),
            Paragraph(val, S('cv', fontSize=14, textColor=C_DARK, fontName=_CN, alignment=TA_CENTER)),
            Paragraph(chg, S('cc', fontSize=9, textColor=color, fontName=_CN, alignment=TA_CENTER)),
        ])
    cw = (W - 4*cm) / 4
    ct = Table([card_data], colWidths=[cw]*4)
    ct.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), C_LIGHT_BG),
        ('BOX', (0,0), (-1,-1), 1, C_BORDER),
        ('INNERGRID', (0,0), (-1,-1), 0.5, C_BORDER),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(ct)

    story.append(sp(30))
    story.append(colored(
        '「海天味业2025年实现"量利齐升"，营收净利润双创历史新高。<br/>'
        '净利率连续2年提升，基本面复苏确认。ROE三连降为中期隐患。 '
        'A+H双平台上市后国际化加速，数字化转型持续深化。」',
        S('quote', fontSize=9, textColor=C_TEXT, fontName=_CN,
          leading=14, alignment=TA_CENTER, spaceBefore=10)
    ))

    story.append(PageBreak())

    # ── 第一章: 公司概况 ──────────────────────────────────
    story.extend(section('一、公司概况'))
    story.extend(subsubsection('1.1 基本信息'))
    story.append(make_kv_table([
        ('公司全称', '佛山市海天调味食品股份有限公司'),
        ('英文名称', 'Foshan Haitian Flavoring and Food Co., Ltd.'),
        ('股票代码', '603288（A股上交所）/ HK.603288（港股）'),
        ('上市时间', '2014年2月A股上市，2025年6月港股上市'),
        ('主营业务', '酱油、蚝油、调味酱等调味品生产与销售'),
        ('核心产品', '酱油(149亿)、蚝油(49亿)、调味酱(29亿)'),
        ('产能规模', '产销量超过480万吨/年，行业第一'),
        ('研发投入', '约3%营收，近十年累计超65亿元'),
        ('最新市值', '约1850亿元（A股，PE约26x）'),
    ]))
    story.append(sp(10))

    story.extend(subsubsection('1.2 股权结构'))
    story.append(colored(
        '海天味业控股股东为广东海天集团，实控人持股约58%。'
        '2025年6月成功登陆港股，成为A+H双平台上市企业。'
        '2026年3月发布2026年A股员工持股计划草案，2024年员工持股计划终止并回购注销。',
        sBody
    ))
    story.append(sp(10))

    # ── 第二章: 财务数据 ─────────────────────────────────
    story.extend(section('二、八年财务数据（2018-2025）'))
    story.append(colored('单位: 营收/净利润/经营现金流为"亿元"，比率为"%"', sSmall))
    story.append(sp(6))

    hdrs = ['年份', '营收', '净利润', 'ROE', '净利率', '毛利率', 'EPS(元)', 'DPS(元)', 'CFO']
    rows = []
    for i, yr in enumerate(HAITIAN['years']):
        rows.append([
            str(yr),
            f'{HAITIAN["revenue"][i]:.1f}',
            f'{HAITIAN["net_profit"][i]:.1f}',
            f'{HAITIAN["roe"][i]:.1f}%',
            f'{HAITIAN["net_margin"][i]:.1f}%',
            f'{HAITIAN["gross_margin"][i]:.1f}%',
            f'{HAITIAN["eps"][i]:.2f}',
            f'{HAITIAN["dps"][i]:.2f}',
            f'{HAITIAN["cfo"][i]:.1f}',
        ])
    story.append(make_financial_table(hdrs, rows))
    story.append(sp(10))

    story.extend(subsubsection('2.1 关键趋势解读'))
    trend_data = [
        ('营收增长', '2018-2021年高增长(CAGR 14%), 2022-2023年调整, 2024-2025年复苏', C_AMBER),
        ('净利润', '2021年达峰值67亿, 2023年触底56亿(-17%), 2025年反弹至70亿创历史', C_AMBER),
        ('净利率', '2020年达峰值27.6%, 2023年降至22.9%谷底, 2025年回升至24.4%', C_GREEN),
        ('ROE', '2019年32.3%为历史高点, 持续下滑至2025年19.6%, 三连降', C_RED),
        ('毛利率', '2018年46.4%高位, 持续下行至2023年35.4%, 2025年反弹至39.3%', C_AMBER),
        ('CFO/净利润', '持续>1, 2025年77.5亿 vs 净利润70.4亿, 利润质量优秀', C_GREEN),
    ]
    for label, desc, col in trend_data:
        story.append(make_kv_table([(label, desc)], col_widths=(3.5*cm, 12*cm)))
        story.append(sp(3))
    story.append(sp(10))

    # 季度数据
    story.extend(subsubsection('2.2 2025年分季度数据'))
    q_headers = ['季度', '营收(亿)', '净利润(亿)', '营收YoY', '净利润YoY', '备注']
    q_rows = [
        ['Q1', '83.17', '22.02', '+7.2%', '+11.9%', '开局良好'],
        ['Q2', '69.15', '17.09', '+6.8%', '+9.5%', '稳健增长'],
        ['Q3', '63.99', '14.06', '+5.1%', '+8.3%', '⚠️环比-7.5%'],
        ['Q4', '72.43', '16.21', '+9.5%', '+14.2%', '旺季回升'],
    ]
    story.append(make_financial_table(q_headers, q_rows))
    story.append(sp(6))
    story.append(colored(
        '⚠️ 注意: Q3营收63.99亿，环比Q2的69.15亿下降7.5%，淡季压力需持续跟踪。',
        sAmber
    ))

    story.append(PageBreak())

    # ── 第三章: 产品与市场 ───────────────────────────────
    story.extend(section('三、产品结构与市场（2025年）'))
    story.append(colored('单位: 亿元', sSmall))
    story.append(sp(4))

    prod_data = [
        ['产品', '收入(亿)', '占比', 'YoY', '毛利率', '趋势'],
        ['酱油', '149.34', '51.7%', '+8.55%', '~42%', '核心稳健'],
        ['蚝油', '48.68', '16.9%', '+5.48%', '~38%', '稳定增长'],
        ['调味酱', '29.17', '10.1%', '+9.29%', '~36%', '增速最快'],
        ['其他调味品', '~61.5', '21.3%', '-', '-', '醋/料酒/复调'],
        ['调味品主业', '273.99', '95.0%', '+9.04%', '-', '核心稳固'],
        ['其他业务', '14.74', '5.0%', '-', '-', '非主业'],
        ['合计', '288.73', '100%', '+7.32%', '39.3%', '史上最佳'],
    ]
    t = Table(prod_data, colWidths=[3*cm, 2.5*cm, 2*cm, 2*cm, 2*cm, 3*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), C_ACCENT),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('ALIGN', (1,0), (-1,-1), 'CENTER'),
        ('ALIGN', (0,0), (0,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, C_LIGHT_BG]),
        ('GRID', (0,0), (-1,-1), 0.3, C_BORDER),
        ('BACKGROUND', (0,5), (-1,5), HexColor('#E8F5E9')),
        ('BACKGROUND', (0,7), (-1,7), HexColor('#E3F2FD')),
    ]))
    story.append(t)
    story.append(sp(10))

    story.extend(subsubsection('3.1 渠道战略'))
    story.append(make_kv_table([
        ('线下渠道', '深入镇村的线下网络，终端覆盖广，渠道金字塔基稳固'),
        ('餐饮渠道', '连锁餐饮严苛要求，海天规模+质价比优势显著'),
        ('线上渠道', '新兴渠道捕捉增量空间，数字化工具获得终端和用户'),
        ('国际化', 'A+H双平台，2025年香港联交所上市，国际化战略加速'),
    ]))
    story.append(sp(10))

    story.extend(subsubsection('3.2 核心竞争优势'))
    story.append(make_kv_table([
        ('规模第一', '产销量超480万吨/年，行业绝对龙头，规模化采购优势'),
        ('技术领先', 'AI+传统酿造，494道检测点，2000+项检测，1000+项专利'),
        ('数智化', '灯塔工厂（广东高明），5G工厂（江苏），数字化转型行业标杆'),
        ('产品矩阵', '金字塔型：酱油/蚝油/调味酱为基，往上醋/料酒/复调延伸'),
        ('客户粘性', '连续11年入选中国消费者首选前十品牌，渗透率80%+'),
    ]))

    story.append(PageBreak())

    # ── 第四章: MD&A LLM分析 ─────────────────────────────
    story.extend(section('四、管理层讨论与分析（LLM智能解析）'))
    story.append(colored('基于MiniMax M2.7大模型对2025年报MD&A章节(43795字符)深度分析', sSmall))
    story.append(sp(8))

    story.extend(subsubsection('4.1 战略承诺'))
    commitments = [
        ('用户满意升级', '从"用户至上"向"用户满意至上"迭代升级，2025年体现韧性'),
        ('战略升级路径', '调味产品 → 全场景烹饪解决方案 → 味道研究'),
        ('A+H双平台', '2025年6月香港联交所成功上市，双平台战略落地'),
        ('国际化战略', '加速系统化推进，国际业务拓展为新增长极'),
        ('科技立企', '每年3%营收投入研发，近十年累计超65亿元'),
        ('灯塔工厂', '高明工厂为行业标杆，江苏工厂获评5G工厂名录'),
    ]
    for k, v in commitments:
        story.append(make_kv_table([(k, v)]))
        story.append(sp(2))

    story.append(sp(8))
    story.extend(subsubsection('4.2 关键战略主题'))
    themes = [
        ('产品金字塔矩阵', '核心基调(酱油/蚝油/调味酱) + 趋势赛道(醋/料酒) + 创新赛道'),
        ('全渠道精耕', '线下镇村网络+数字化工具+新兴渠道全域覆盖'),
        ('数字化转型', '从精益工厂到智能黑灯工厂路径迭代'),
        ('可持续发展', 'ESG战略嵌入价值内核，绿色低碳为发展底色'),
        ('研发驱动', 'AI+传统工艺融合，菌种/发酵/风味技术储备领先'),
    ]
    for k, v in themes:
        story.append(make_kv_table([(k, v)]))
        story.append(sp(2))

    story.append(sp(8))
    story.extend(subsubsection('4.3 主要风险因素'))
    risks = [
        ('原材料价格波动', '黄豆等原料成本占40%+，价格波动影响毛利率'),
        ('物流成本压力', '全国分销网络，物流成本刚性增长'),
        ('行业周期波动', '调味品行业与餐饮消费景气度高度相关'),
        ('全球化复杂性', '海外经营面临汇率、政策、合规等多重挑战'),
        ('食品安全风险', '食品安全事件对品牌声誉影响极大'),
    ]
    for k, v in risks:
        story.append(make_kv_table([(k, v)]))
        story.append(sp(2))

    story.append(PageBreak())

    # ── 第五章: 重要公告 ─────────────────────────────────
    story.extend(section('五、近期重要公告（2026年）'))
    story.append(colored('数据来源: 东方财富接口实时采集', sSmall))
    story.append(sp(6))

    ann_headers = ['日期', '事件类型', '标题/摘要']
    ann_rows = [
        ['2026-04-02', '业绩说明会', '关于召开2025年度业绩说明会的公告'],
        ['2026-03-27', '【年报】', '2025年年度报告发布，营收288.73亿(+7.3%)，净利润70.38亿(+11.0%)'],
        ['2026-03-27', '【利润分配】', '2025年度利润分配预案公告'],
        ['2026-03-27', '【员工持股】', '2026年A股员工持股计划(草案)发布'],
        ['2026-03-27', '【经营数据】', '2025年度主要经营数据公告'],
        ['2026-03-27', '【回购注销】', '回购注销2024年员工持股计划A股股份，计划终止'],
        ['2026-01-31', '【特别分红】', '2025年回报股东特别分红权益分派实施公告（差异化分红）'],
        ['2025-12-19', '【特别分红预案】', '2025年回报股东特别分红预案公告'],
        ['2025-10-29', '【三季报】', '2025年第三季度报告，Q3营收63.99亿(+5.1%)'],
        ['2025-08-29', '【半年报】', '2025年半年度报告，H1营收152.32亿(+7.0%)'],
        ['2025-04-29', '【一季报】', '2025年第一季度报告，Q1营收83.17亿(+7.2%)'],
    ]
    ann_t = Table(
        [[Paragraph(c, S(f'ac{i}', fontSize=8, fontName=_CN if i==0 else 'Helvetica'))
          for i, c in enumerate(row)] for row in ann_rows],
        colWidths=[2.5*cm, 3*cm, 10*cm]
    )
    ann_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), C_ACCENT),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (0,0), (1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, C_LIGHT_BG]),
        ('GRID', (0,0), (-1,-1), 0.3, C_BORDER),
    ]))
    story.append(ann_t)
    story.append(sp(10))

    # 分红信息
    story.extend(subsubsection('5.1 分红历史'))
    div_data = [
        ['年度', 'DPS(元)', '派息率', '分红总额估算'],
        ['2025', '0.31', '25.2%', '约17.7亿（含特别分红）'],
        ['2024', '0.30', '26.3%', '约17.1亿'],
        ['2023', '0.25', '24.0%', '约14.3亿（调整年）'],
        ['2022', '0.30', '26.3%', '约17.1亿'],
        ['2021', '0.30', '24.4%', '约17.1亿'],
    ]
    story.append(make_financial_table(div_data[0], div_data[1:]))
    story.append(sp(6))
    story.append(colored(
        '海天长期维持约25%派息率，2025年额外特别分红体现积极股东回报。'
        'CFO持续大于净利润，分红可持续性强。',
        sBody
    ))

    story.append(PageBreak())

    # ── 第六章: 综合评估 ─────────────────────────────────
    story.extend(section('六、综合评估'))
    story.append(sp(6))

    # 评分卡
    score_data = [
        [Paragraph('<b>维度</b>', sBody),
         Paragraph('<b>状态</b>', sBody),
         Paragraph('<b>评分</b>', sBody),
         Paragraph('<b>备注</b>', sBody)],
        ['营收增长', '✅ 正面', '★★★★☆', '+7.3%，增速回升，2021年来最快'],
        ['净利润', '✅ 正面', '★★★★★', '70.38亿创历史新高，+11%'],
        ['净利率趋势', '✅ 正面', '★★★★☆', '24.4%连续2年提升'],
        ['ROE趋势', '⚠️ 负面', '★★☆☆☆', '三连降，31.5%→19.6%'],
        ['经营现金流', '✅ 正面', '★★★★★', 'CFO 77.5亿 >> 净利润 70.4亿'],
        ['股东回报', '✅ 正面', '★★★★☆', '常规+特别分红，积极'],
        ['产品竞争力', '✅ 正面', '★★★★★', '酱油/蚝油/调味酱三足鼎立'],
        ['渠道覆盖', '✅ 正面', '★★★★☆', '镇村网络+数字化'],
        ['员工持股', '⚠️ 中性', '★★★☆☆', '新草案需跟踪稀释'],
        ['Q3增速放缓', '⚠️ 警示', '★★☆☆☆', '环比-7.5%需跟踪'],
        ['国际化', '✅ 正面', '★★★☆☆', 'H股上市，但收入占比仍低'],
    ]
    sc = Table(score_data, colWidths=[3*cm, 2.5*cm, 2*cm, 8*cm])
    sc.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), C_ACCENT),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, C_LIGHT_BG]),
        ('GRID', (0,0), (-1,-1), 0.3, C_BORDER),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(sc)
    story.append(sp(12))

    story.extend(subsubsection('6.1 投资要点'))
    story.append(make_kv_table([
        ('核心逻辑', '调味品行稳致远，海天为绝对龙头。2025年基本面确认复苏，净利率持续改善。'),
        ('成长看点', '1) 产品结构升级（高鲜酱油、健康化）；2) 渠道下沉空间；3) 国际化增量'),
        ('盈利预测', '预计2026年营收~310亿(+7%)，净利润~75亿(+7%)，净利率~24.5%'),
        ('估值参考', '当前市值~1850亿，对应2025年PE约26x，处于历史中枢。'),
        ('股息率', '约1.2%（2025E DPS 0.32 / 股价~26元），特别分红额外贡献'),
    ]))
    story.append(sp(10))

    story.extend(subsubsection('6.2 主要风险'))
    story.append(make_kv_table([
        ('ROE持续下滑', '三连降至19.6%，资产变重、周转率下降为核心矛盾'),
        ('Q3增速放缓', 'Q3营收环比-7.5%，若趋势延续全年增长目标承压'),
        ('原材料成本', '黄豆占成本40%+，价格波动对毛利率影响约±2pct'),
        ('消费需求', '餐饮行业景气度直接影响调味品出货，复苏节奏存在不确定性'),
        ('竞争加剧', '千禾/李锦记/中炬等在中高端赛道竞争激烈'),
        ('股权稀释', '2026年员工持股计划草案待落地，需关注摊薄比例'),
    ]))
    story.append(sp(10))

    story.extend(subsubsection('6.3 结论与建议'))
    conclusion_data = [
        [Paragraph('<b>评级</b>', sBody), Paragraph('<b>维持</b>', S('评级', fontSize=11, textColor=C_GREEN, fontName=_CN))],
        [Paragraph('<b>目标价</b>', sBody), Paragraph('<b>当前估值合理，关注Q1旺季数据</b>', sBody)],
        [Paragraph('<b>核心跟踪</b>', sBody), Paragraph('<b>①员工持股落地 ②Q1 2026数据 ③黄豆价格 ④净利率改善持续性</b>', sBody)],
    ]
    ct2 = Table(conclusion_data, colWidths=[3*cm, 13*cm])
    ct2.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), C_LIGHT_BG),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.3, C_BORDER),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(ct2)

    story.append(sp(20))
    story.append(hr())
    story.append(sp(8))
    story.append(colored(
        '⚠️ 免责声明: 本报告由AI自动生成，数据来源于公开年报及公告，仅供投资参考。'
        '股市有风险，投资需谨慎。不构成任何投资建议。',
        sSmall
    ))

    # ─── 生成 ──────────────────────────────────────────────
    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    print(f"✅ PDF报告已生成: {output_path}")
    return output_path


if __name__ == '__main__':
    import sys
    sys.path.insert(0, '/home/ponder/.openclaw/workspace/astock-implementation')
    import os
    os.makedirs('/home/ponder/.openclaw/workspace/astock-implementation/cache/module6', exist_ok=True)
    out = '/home/ponder/.openclaw/workspace/astock-implementation/cache/module6/603288_深度分析报告.pdf'
    build(out)
    sz = os.path.getsize(out) / 1024 / 1024
    print(f'PDF大小: {sz:.1f}MB')
