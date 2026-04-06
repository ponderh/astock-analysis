# 模块8：投资结论引擎 - 配置

# 多因子权重配置
WEIGHTS = {
    'financial_health': 0.30,      # 财务健康（模块2）
    'risk_score': 0.25,            # 风险评分（模块5红旗）
    'quality_score': 0.20,         # 质地评分（模块6 MD&A）
    'momentum_score': 0.15,        # 动量评分（模块7公告）
    'governance_score': 0.10,      # 治理评分（模块9）
}

# 投资建议阈值
RECOMMENDATION_THRESHOLDS = {
    'strongly_buy': 80,    # >=80
    'buy': 65,              # >=65
    'hold': 45,             # >=45
    'sell': 30,             # >=30
    'strongly_sell': 0,   # <30
}

# 置信度阈值
CONFIDENCE_THRESHOLDS = {
    'high': 75,            # 高置信度
    'medium': 50,          # 中置信度
    'low': 25,             # 低置信度
}

# 默认值配置（缺失数据时使用）
DEFAULT_SCORES = {
    'financial_health': 50,      # 财务数据缺失时的默认值
    'risk_score': 50,              # 红旗缺失时的默认值
    'quality_score': 50,           # MD&A缺失时的默认值
    'momentum_score': 50,          # 公告缺失时的默认值
    'governance_score': 50,         # 治理缺失时的默认值
}

# 缺失容错配置
MISSING_STRATEGY = {
    'module2_financial': {
        'default': 50,
        'confidence_penalty': 50,  # 财务数据缺失，置信度上限50%
    },
    'module5_red_flag': {
        'default': 50,
    },
    'module6_mda': {
        'default': 50,
    },
    'module7_announcements': {
        'default': 50,
    },
    'module9_governance': {
        'default': 50,
    },
}

# 红旗优先级（越高越优先）
RED_FLAG_PRIORITY = {
    'EXTREME': 4,      # 最高优先级
    'HIGH': 3,
    'MEDIUM': 2,
    'LOW': 1,
    'NONE': 0,
}

# 投资建议映射
RECOMMENDATION_MAP = {
    (80, 100): '强烈买入',
    (65, 80): '买入',
    (45, 65): '持有',
    (30, 45): '卖出',
    (0, 30): '强烈卖出',
}
