# G4Gate 审查报告 — module7_announcements 公告数据管道

**模块**: P0 第4周 | module7_announcements  
**审查日期**: 2026-04-03  
**代码路径**: `impl/module7_announcements/`  
**审查人**: G4Gate Agent

---

## G4Gate结论：**有异议**（需修复后通过）

---

## 一、公告类型识别：⚠️ 基本OK，有改进空间

**评分: 72/100**

### 优点
- YJYG 关键词覆盖较全：业绩预告扭亏/首亏/续亏/增亏/减亏均有匹配
- YJGG 修正类型（更正/修正/差异/调整/补充更正/差错更正/会计差错）覆盖充分
- 置信度权重设计合理（YJGG 95%, YJYG 90%, YJKB 90%）
- 有独立的 `extract_yjyg_fields()` 做金额/变动百分比/报告期提取

### 问题

**问题1：正则 `首亏|续亏|增亏|减亏` 为单条 OR，正向匹配效率低**
```python
# 当前（有问题）
re.compile(r"首亏|续亏|增亏|减亏", re.I)

# 建议（更精准）
re.compile(r"(?:首亏|续亏|增亏|减亏)", re.I)
```
非捕获组不影响功能，但当前写法语义不够清晰，建议统一。

**问题2：漏掉"业绩预减"、"业绩预增"**
这是最常见的业绩预告表述之一，当前规则未覆盖。补充：
```python
re.compile(r"业绩预(?!告)", re.I),  # 预减/预增，但不匹配"预告"
```
实际应分两条：
```python
re.compile(r"业绩预减", re.I),
re.compile(r"业绩预增", re.I),
```

**问题3：漏掉"预计"开头的业绩表述**
部分公告标题格式为"预计2024年度归母净利润同比增长XX%"，当前规则未覆盖。

**问题4：`column_name` 字段在 cninfo 返回为空时降级为 `category`**
```python
"column_name": item.get("categoryName", "") or item.get("category", ""),
```
但分类器只用 `column_name`，category 未参与分类，可能丢失分类机会。

**改进建议优先级**：
- P0: 增加"业绩预减/业绩预增"匹配（最常见漏识别项）
- P1: 增加"预计"开头匹配 + column_name/category 双轨参与分类
- P2: 非捕获组规范化

---

## 二、三级降级机制：⚠️ 架构合理，实现有缺陷

**评分: 55/100**

### 优点
- CNINFO → EM → AKShare 三级降级架构清晰
- 结果按 `art_code` 去重合并，不会重复
- 有分页和礼貌延迟（0.2~0.5s），不容易触发限流

### 严重问题

**问题1：EM 根本无法作为有效备选（14天限制是硬伤）**

东方财富 np-anotice API 声明只返回**最近约14天**、总量5万条上限。

```python
# 当前代码将 begin_time 设为 2020-01-01
if not begin_time:
    begin_time = "2020-01-01"  # 但这不work！
```

begin_time 参数被发送，但 EM API 根本不理会，**始终只返回最近14天**。这意味着：

- 如果 CNINFO 挂了，只有14天内有公告的公司才能被 EM 补充
- 永新002014近14天无新公告 → EM 返回 0 条（完全失效）
- 降级设计在统计99%的股票上是**形同虚设**

**CNINFO 成功率已经很高**（永新测试中 CNINFO 单独拿到了150条），所以这个缺陷暂未暴露。但若 CNINFO 限流/维护，**整个降级机制将静默失效**。

**问题2：AKShare Brotli 问题无解，当前设计无法降级**

AKShare 用 `akshare as ak` 直接调用，内部使用 `requests` + `brotli` 解码器。东窗资讯服务器返回 Brotli 压缩，但解码器报状态异常。

当前代码对这个异常 `except` 住后返回空列表：
```python
except Exception as e:
    logger.warning("[AKShare] 失败: %s", e)
    return []  # 静默失败
```

这不是真正的"降级"，是"降级失败"。且 AKShare 依赖本地安装的 akshare 包，版本不一致也会导致问题。

**问题3：fetch_notice_detail 在 __all__ 中导出但不存在**
```python
# api.py __all__ 包含：
"fetch_notice_detail",  # ← fetcher.py 中不存在！
```
运行时 import 会报 `ImportError`。

### 改进建议

| 优先级 | 问题 | 建议方案 |
|--------|------|---------|
| P0 | EM 14天限制 | 移除 EM 作为全量备选，改为"近期补充"；或明确标注 EM 仅用于最近7天 |
| P0 | fetch_notice_detail 不存在 | 从 `__all__` 删除，或实现一个 stub |
| P1 | AKShare 静默失败 | 增加 fallback 到 `curl`（手动发 HTTP 请求）；增加明确日志标记"降级失败" |
| P2 | 降级时无明确状态码 | 返回结构应包含 `degraded: bool, degraded_reason: str`，让调用方感知降级 |

---

## 三、业绩预告0条分析：✅ 合理

**评分: 90/100**

### 分析结论：**0条是正常的，无需归为问题**

#### 法规背景

根据沪深交易所规定：
- **业绩预告**（强制披露）：适用于归母净利润同比变动≥50% 或亏损/扭亏的公司
- **业绩快报**（自愿披露）：适用于所有公司
- 主板公司预计净利润为正但同比变动<50%，**不强制披露预告**

#### 永新002014的情况推断

永新包装行业（塑料软包装）多年盈利稳定，属于**业绩平稳型公司**。测试结果中"最近10条全为董事会换届/股东会决议"，说明：
1. 公司已进入正常年报披露季（4月初）
2. 无强制业绩预告，说明归母净利润变动在 ±50% 以内（平稳）
3. 真正的业绩数据会在 **2024年报全文**（4月发布）中体现

#### 当前时间2026年4月的问题

题目假设"2024年报业绩预告预计2025年1-4月发布"，但当前是2026年4月。

- 永新2024年报：应于 **2025年2-4月** 披露（已过）
- 业绩预告：应于 **2025年1-2月** 发布（已过）
- 如果公司没发预告 = 业绩平稳，不需要强制预告 → **完全正常**

### 建议

- 将 `get_yjyg_notices()` 的 years 默认范围从 `[2023, 2024, 2025]` 改为 `[2024, 2025, 2026]`，并用系统当前年份动态计算
- 增加日志提示：若 years 参数对应年份早于去年，自动给出"已过披露期"提示

---

## 四、增量抓取支持：❌ 不支持

**评分: 0/100**

### 问题

- `fetch_announcements()` 无 `last_fetch_time` / `since` 参数
- `get_announcements()` 无增量接口
- 无基于 `notice_date` 或 `art_code` 的去重/跳过逻辑

### 影响

每次调用都从 `begin_time` 重新拉取，无法：
- 实现"只拉新公告"的增量管道
- 支持 cron 定时抓取（会重复拉取）
- 节省 API 调用配额

### 建议

```python
def fetch_announcements(
    stock_code: str,
    begin_time: Optional[str] = None,
    end_time: Optional[str] = None,
    max_notices: int = 50,
    last_fetch_time: Optional[str] = None,  # 新增：增量参数
    skip_art_codes: Optional[set[str]] = None,  # 新增：已知ID去重
) -> list[dict]:
```

在结果返回前过滤：
```python
if last_fetch_time:
    results = [r for r in results if r['notice_date'] > last_fetch_time]
if skip_art_codes:
    results = [r for r in results if r['art_code'] not in skip_art_codes]
```

---

## 问题汇总

| # | 严重度 | 模块 | 问题 | 状态 |
|---|--------|------|------|------|
| 1 | 🔴 P0 | fetcher | `fetch_notice_detail` 在 `__all__` 导出但不存在，运行时报 ImportError | 需修复 |
| 2 | 🔴 P0 | fetcher | EM 降级是无效降级（14天硬限制），降级机制形同虚设 | 需修复 |
| 3 | 🟡 P1 | parser | "业绩预减/业绩预增"关键词缺失，最常见漏识别项 | 建议修复 |
| 4 | 🟡 P1 | fetcher | AKShare 静默失败，无 curl 兜底 | 建议修复 |
| 5 | 🟡 P1 | fetcher | 增量抓取不支持，无法实现增量管道 | 需修复 |
| 6 | 🟢 P2 | parser | `首亏\|续亏\|增亏\|减亏` 建议改非捕获组 | 可选 |
| 7 | 🟢 P2 | parser | `column_name` 为空时 `category` 未参与分类 | 可选 |

---

## 总体评价

**架构设计：良好** — 三级降级思路清晰，parser 结构良好（类型枚举、正则规则、置信度、字段提取），分类体系完整，代码可读性高。

**实现质量：不合格** — 三级降级只有 CNINFO 一级真正可用；ImportError bug 会导致生产事故；增量抓取缺失使管道无法实际生产运行。

**关键风险**：
1. CNINFO 一旦限流/故障，整个管道静默返回空数据（EM 无法兜底）
2. 增量抓取不支持，无法作为可靠的数据管道在 cron 场景下使用

**建议行动**：
1. 立即修复 `fetch_notice_detail` ImportError
2. 重新评估 EM 定位——要么明确标注"仅用于补充最近7天"，要么引入真正的第二数据源（如 Tushare、Wind）
3. 增加增量抓取参数 `last_fetch_time`
4. 增加"业绩预减/业绩预增"关键词
