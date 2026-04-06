"""
质量评分器
评估MD&A提取质量，输出A/B/C/D等级
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class QualityScorer:
    """
    质量评分器

    评分维度:
    - 字数完整度 (25%): 目标≥3000字
    - 结构完整度 (30%): 包含战略/风险/经营子节
    - 关键段落覆盖 (35%): 关键词覆盖率
    - 语义一致性 (10%): LLM输出的结构化程度
    """

    # 关键词清单（来自监管要求）
    MDA_KEYWORDS = [
        '营业收入', '净利润', '经营现金流', '总资产', '净资产',
        '主营业务', '核心竞争力', '发展战略', '风险因素',
        '行业状况', '产品结构', '市场地位', '产能',
        '毛利率', '净利率', 'ROE', '资产负债率'
    ]

    # 战略子节关键词
    STRATEGY_KEYWORDS = [
        '战略', '产品', '市场', '技术', '产能', '竞争',
        '优势', '规划', '目标', '布局', '发展'
    ]

    def score(self, mda_text: str, subsections: Dict[str, str],
               strategic_data: Optional[Dict] = None,
               location_method: str = 'unknown') -> Dict:
        """
        综合质量评分

        Returns: {
            'overall_score': float,  # 0-1
            'grade': str,  # A/B/C/D
            'char_count_score': float,
            'structure_score': float,
            'key_paragraph_score': float,
            'semantic_score': float,
            'details': dict
        }
        """
        # === 1. 字数完整度 ===
        char_count_score = self._score_char_count(mda_text)

        # === 2. 结构完整度 ===
        structure_score = self._score_structure(subsections)

        # === 3. 关键段落覆盖 ===
        key_paragraph_score = self._score_keyword_coverage(mda_text)

        # === 4. 语义一致性（LLM输出结构化程度）===
        semantic_score = self._score_semantic(strategic_data)

        # === 综合评分 ===
        overall = (
            0.25 * char_count_score +
            0.30 * structure_score +
            0.35 * key_paragraph_score +
            0.10 * semantic_score
        )

        # === 等级 ===
        if overall >= 0.90:
            grade = 'A'
        elif overall >= 0.75:
            grade = 'B'
        elif overall >= 0.60:
            grade = 'C'
        else:
            grade = 'D'

        details = {
            'char_count': len(mda_text),
            'subsection_count': len(subsections),
            'keyword_hits': self._count_keyword_hits(mda_text),
            'location_method': location_method,
            'strategic_fields_count': strategic_data and len(strategic_data) or 0
        }

        result = {
            'overall_score': overall,
            'grade': grade,
            'char_count_score': char_count_score,
            'structure_score': structure_score,
            'key_paragraph_score': key_paragraph_score,
            'semantic_score': semantic_score,
            'details': details
        }

        logger.info(f"质量评分: {overall:.2f} ({grade}) | "
                     f"字数={char_count_score:.2f} 结构={structure_score:.2f} "
                     f"关键词={key_paragraph_score:.2f} 语义={semantic_score:.2f}")

        return result

    def _score_char_count(self, text: str) -> float:
        """
        字数完整度评分
        标准: ≥3000字得满分，<500字得0分
        """
        length = len(text)
        if length >= 3000:
            return 1.0
        elif length >= 2000:
            return 0.75
        elif length >= 1000:
            return 0.5
        elif length >= 500:
            return 0.3
        elif length >= 200:
            return 0.15
        else:
            return 0.0

    def _score_structure(self, subsections: Dict[str, str]) -> float:
        """
        结构完整度评分
        检查是否包含主要子节
        """
        required_subsections = ['strategy', 'risk', 'operation']
        found_subs = [s for s in required_subsections if s in subsections and len(subsections[s]) > 100]

        if len(found_subs) >= 3:
            return 1.0
        elif len(found_subs) == 2:
            return 0.7
        elif len(found_subs) == 1:
            return 0.4
        else:
            # 检查是否有其他有意义的子节
            non_empty = [k for k, v in subsections.items() if len(v) > 50]
            if len(non_empty) >= 2:
                return 0.5
            elif len(non_empty) == 1:
                return 0.25
            else:
                return 0.0

    def _score_keyword_coverage(self, text: str) -> float:
        """
        关键词覆盖率
        检查MD&A文本是否覆盖监管要求的关键词
        """
        hits = self._count_keyword_hits(text)
        total = len(self.MDA_KEYWORDS)

        coverage = hits / total
        return min(coverage * 1.5, 1.0)  # 权重放大，最多1.0

    def _count_keyword_hits(self, text: str) -> int:
        """统计关键词命中数"""
        hits = 0
        for kw in self.MDA_KEYWORDS:
            if kw in text:
                hits += 1
        return hits

    def _score_semantic(self, strategic_data: Optional[Dict]) -> float:
        """
        语义一致性评分
        基于LLM/规则引擎提取的结构化程度
        G3修复：不再锁死0.3，根据实际提取内容的具体程度评估。
        """
        if not strategic_data:
            return 0.3  # 没有输出，给个基础分

        # G3修复：根据提取到的结构化字段数量和质量打分
        # 目标字段（与RuleBasedAnalyzer输出结构对齐）
        target_fields = [
            'strategic_commitments',
            'key_strategic_themes',
            'risk_factors',
            'operating_highlights'
        ]

        filled = sum(
            1 for field in target_fields
            if strategic_data.get(field) and len(strategic_data[field]) > 0
        )
        ratio = filled / len(target_fields)

        # 有结构化字段但需要检查内容质量
        score = 0.0

        if strategic_data.get('strategic_commitments'):
            score += 0.3
        if strategic_data.get('key_strategic_themes'):
            score += 0.3
        if strategic_data.get('risk_factors'):
            score += 0.2
        if strategic_data.get('operating_highlights'):
            score += 0.2

        # 检查是否有"NONE"以外的有效内容
        valid_content = False
        for field_name in ['strategic_commitments', 'key_strategic_themes', 'risk_factors']:
            items = strategic_data.get(field_name, [])
            if items and any(
                (isinstance(item, dict) and any(v and 'NONE' not in str(v) for v in item.values()))
                for item in items
            ):
                valid_content = True
                break

        if valid_content:
            score = min(score + 0.2, 1.0)

        # G3修复：不锁死，而是根据填充比例在0.5-0.8之间浮动
        # 0.5基础 + 最多0.3（基于ratio）
        base_from_ratio = 0.5 + ratio * 0.3
        # 如果有有效内容，可以给到0.8
        if valid_content:
            base_from_ratio = max(base_from_ratio, 0.6)

        # 综合：使用计算出的score，但不低于base_from_ratio
        return max(score, base_from_ratio)

    def adaptive_sampling(self, results: List[Dict]) -> List[int]:
        """
        动态抽样（用于人工审核）
        正常10% + 异常20% + 变更后20%
        返回: 需要人工审核的结果索引列表
        """
        indices = []

        grades = [r.get('grade', 'D') for r in results]

        for i, grade in enumerate(grades):
            if grade in ['C', 'D']:
                indices.append(i)  # 异常全量

        # 从A/B中随机抽10%
        normal_indices = [i for i, g in enumerate(grades) if g in ['A', 'B']]
        import random
        sample_size = max(1, int(len(normal_indices) * 0.1))
        sampled = random.sample(normal_indices, min(sample_size, len(normal_indices)))
        indices.extend(sampled)

        return sorted(list(set(indices)))
