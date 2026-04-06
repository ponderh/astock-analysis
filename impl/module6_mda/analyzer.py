"""
MD&A分析器 - LLM + 规则双引擎
三层幻觉保障: 约束性Prompt + Schema校验 + 后处理一致性检查

Provider优先级:
  1. MiniMax M2.7-highspeed（主用）
  2. MiniMax M2.5-highspeed（降级）
  3. DeepSeek（多LLM验证）
"""

import os, re, json
from typing import Dict, List, Any, Optional

# ============================================================================
# Provider配置（API Key 通过环境变量注入，不硬编码）
# ============================================================================

LLM_PROVIDERS = [
    # 主用：MiniMax M2.7-highspeed
    {
        'id': 'minimax_primary',
        'name': 'MiniMax M2.7',
        'model': 'MiniMax-M2.7-highspeed',
        'api_key_env': 'MINIMAX_API_KEY',
        'base_url': 'https://api.minimaxi.com/anthropic/v1',
        'api_style': 'anthropic',
        'enabled': True,
    },
    # 降级：MiniMax M2.5-highspeed
    {
        'id': 'minimax_fallback',
        'name': 'MiniMax M2.5',
        'model': 'MiniMax-M2.5-highspeed',
        'api_key_env': 'MINIMAX_API_KEY',
        'base_url': 'https://api.minimaxi.com/anthropic/v1',
        'api_style': 'anthropic',
        'enabled': True,
    },
    # 多LLM验证：DeepSeek
    {
        'id': 'deepseek',
        'name': 'DeepSeek',
        'model': 'deepseek-chat',
        'api_key_env': 'DEEPSEEK_API_KEY',
        'base_url': 'https://api.deepseek.com/v1',
        'api_style': 'openai',
        'enabled': True,
    },
]


def _get_provider_api_key(provider: Dict) -> Optional[str]:
    """从环境变量获取 API Key"""
    key_env = provider.get('api_key_env', '')
    return os.environ.get(key_env) if key_env else None


# ============================================================================
# MultiProvider LLM分析器
# ============================================================================
class MultiProviderLLMAnalyzer:
    def __init__(self):
        self._providers = self._build_provider_list()
        self._enabled_providers = [p for p in self._providers if p.get('enabled') and _get_provider_api_key(p)]

    def _build_provider_list(self) -> List[Dict]:
        providers = []
        for p in LLM_PROVIDERS:
            key = _get_provider_api_key(p)
            if key:
                providers.append({**p, 'api_key': key, 'enabled': True})
        return providers

    def _call_llm_provider(self, text: str, prompt_template: str,
                           provider: Dict, max_tokens: int) -> Optional[str]:
        """统一调用入口，根据 api_style 分发到不同协议"""
        prompt = prompt_template.replace('{text}', text[:8000])
        api_style = provider.get('api_style', 'openai')

        try:
            if api_style == 'anthropic':
                return self._call_anthropic(prompt, provider, max_tokens)
            else:
                return self._call_openai(prompt, provider, max_tokens)
        except Exception:
            return None

    def _call_openai(self, prompt: str, provider: Dict, max_tokens: int) -> Optional[str]:
        """OpenAI /chat/completions 协议（DeepSeek 等）"""
        import requests
        resp = requests.post(
            f"{provider['base_url']}/chat/completions",
            headers={
                'Authorization': f"Bearer {provider['api_key']}",
                'Content-Type': 'application/json'
            },
            json={
                'model': provider['model'],
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': max_tokens,
                'temperature': 0.1
            },
            timeout=60
        )
        if resp.status_code == 200:
            return resp.json()['choices'][0]['message']['content']
        return None

    def _call_anthropic(self, prompt: str, provider: Dict, max_tokens: int) -> Optional[str]:
        """Anthropic /messages 协议（MiniMax 等）"""
        import requests
        resp = requests.post(
            f"{provider['base_url']}/messages",
            headers={
                'x-api-key': provider['api_key'],
                'Content-Type': 'application/json',
                'anthropic-version': '2023-06-01',
                'anthropic-dangerous-direct-browser-access': 'true'
            },
            json={
                'model': provider['model'],
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': max_tokens
            },
            timeout=60
        )
        if resp.status_code == 200:
            data = resp.json()
            # 找 type=text 的 block（跳过 thinking）
            for block in data.get('content', []):
                if block.get('type') == 'text':
                    return block['text']
            # fallback: 直接返回第一个非-thinking block
            for block in data.get('content', []):
                if block.get('type') != 'thinking':
                    return block.get('text', '') or block.get('content', '')
            return ''
        return None

    def analyze(self, text: str, prompt_template: str,
                output_schema: Optional[Dict] = None,
                max_tokens: int = 4096) -> Dict[str, Any]:
        """入口：尝试多Provider，自动降级（优先级顺序）"""
        for provider in self._enabled_providers:
            raw = self._call_llm_provider(text, prompt_template, provider, max_tokens)
            if raw:
                parsed = self._parse_json_response(raw)
                flags = self._check_hallucination(text, parsed, raw)
                return {
                    'raw_response': raw,
                    'structured_data': parsed,
                    'model_used': f"{provider['id']}/{provider['model']}",
                    'hallucination_flags': flags,
                    'error': None
                }
        return {
            'raw_response': '', 'structured_data': {},
            'model_used': 'none', 'hallucination_flags': ['api_call_failed'],
            'error': 'api_call_failed'
        }

    def analyze_with_fallback(self, text: str, prompt_template: str,
                              max_tokens: int = 8192) -> Dict[str, Any]:
        """
        单路调用，自动降级。
        顺序：MiniMax M2.7 → MiniMax M2.5 → DeepSeek
        """
        # 只取 MiniMax 相关 provider
        minimax_providers = [p for p in self._enabled_providers
                             if p['id'].startswith('minimax')]
        all_fallback = minimax_providers + [p for p in self._enabled_providers
                                             if p['id'] == 'deepseek']
        for provider in all_fallback:
            raw = self._call_llm_provider(text, prompt_template, provider, max_tokens)
            if raw:
                parsed = self._parse_json_response(raw)
                flags = self._check_hallucination(text, parsed, raw)
                return {
                    'raw_response': raw,
                    'structured_data': parsed,
                    'model_used': f"{provider['id']}/{provider['model']}",
                    'hallucination_flags': flags,
                    'error': None
                }
        return {
            'raw_response': '', 'structured_data': {},
            'model_used': 'none', 'hallucination_flags': ['api_call_failed'],
            'error': 'api_call_failed'
        }

    def analyze_with_validation(self, text: str, prompt_template: str,
                                 max_tokens: int = 8192) -> Dict[str, Any]:
        """
        多LLM验证：MiniMax + DeepSeek 同时调用，对比结果一致性。
        返回两个结果 + 一致性分析。
        """
        # 找 MiniMax 主用和 DeepSeek
        minimax_p = next((p for p in self._enabled_providers
                          if p['id'] == 'minimax_primary'), None)
        deepseek_p = next((p for p in self._enabled_providers
                           if p['id'] == 'deepseek'), None)

        results = {}
        if minimax_p:
            raw = self._call_llm_provider(text, prompt_template, minimax_p, max_tokens)
            if raw:
                results['minimax'] = {
                    'raw': raw,
                    'parsed': self._parse_json_response(raw),
                    'model': f"{minimax_p['id']}/{minimax_p['model']}"
                }

        if deepseek_p:
            raw = self._call_llm_provider(text, prompt_template, deepseek_p, max_tokens)
            if raw:
                results['deepseek'] = {
                    'raw': raw,
                    'parsed': self._parse_json_response(raw),
                    'model': f"{deepseek_p['id']}/{deepseek_p['model']}"
                }

        if not results:
            return {
                'validation_status': 'failed',
                'results': {},
                'consistency': {},
                'error': 'all_providers_failed'
            }

        # 一致性检查：对比关键字段
        consistency = self._check_consistency(results)
        return {
            'validation_status': 'completed',
            'results': results,
            'consistency': consistency,
            'error': None
        }

    def _check_consistency(self, results: Dict) -> Dict[str, Any]:
        """检查 MiniMax 和 DeepSeek 结果的一致性"""
        if 'minimax' not in results or 'deepseek' not in results:
            return {'status': 'single_provider_only', 'disagreements': []}

        m_data = results['minimax']['parsed']
        d_data = results['deepseek']['parsed']

        disagreements = []

        # 对比战略性承诺数量
        m_commits = len(m_data.get('strategic_commitments', []))
        d_commits = len(d_data.get('strategic_commitments', []))
        if abs(m_commits - d_commits) > 3:
            disagreements.append(f"strategic_commitments count diff: minimax={m_commits}, deepseek={d_commits}")

        # 对比主题数量
        m_themes = len(m_data.get('key_strategic_themes', []))
        d_themes = len(d_data.get('key_strategic_themes', []))
        if abs(m_themes - d_themes) > 3:
            disagreements.append(f"key_strategic_themes count diff: minimax={m_themes}, deepseek={d_themes}")

        # 对比风险因素数量
        m_risks = len(m_data.get('risk_factors', []))
        d_risks = len(d_data.get('risk_factors', []))
        if abs(m_risks - d_risks) > 3:
            disagreements.append(f"risk_factors count diff: minimax={m_risks}, deepseek={d_risks}")

        return {
            'status': 'disagreement' if disagreements else 'consistent',
            'disagreements': disagreements,
            'counts': {
                'minimax': {'commitments': m_commits, 'themes': m_themes, 'risks': m_risks},
                'deepseek': {'commitments': d_commits, 'themes': d_themes, 'risks': d_risks}
            }
        }

    def _parse_json_response(self, raw_response: str) -> Dict[str, Any]:
        if not raw_response:
            return {}
        # 尝试从markdown代码块提取
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        # 尝试直接解析
        try:
            return json.loads(raw_response)
        except json.JSONDecodeError:
            pass
        # 提取纯文本内容
        cleaned = re.sub(r'^```.*?```$', '', raw_response, flags=re.DOTALL).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {'raw_text': cleaned}

    def _check_hallucination(self, original_text: str,
                              structured_data: Dict[str, Any],
                              raw_response: str) -> list:
        flags = []
        vague_words = ['大约', '约', '基本', '可能', '或许', '大概', '估计', '差不多']
        if any(word in raw_response for word in vague_words):
            flags.append('vague_words_detected')

        required_fields = ['strategic_commitments', 'key_strategic_themes', 'risk_factors']
        missing = [f for f in required_fields if f not in structured_data]
        if missing:
            flags.append(f'missing_fields:{",".join(missing)}')

        if structured_data.get('strategic_commitments'):
            for item in structured_data['strategic_commitments']:
                if not isinstance(item, dict):
                    flags.append('schema_violation:strategic_commitments_not_dict')
                    continue
                quant = item.get('quantitative_target', '')
                if quant and quant != 'NONE' and quant != 'NONE-原文未提及':
                    if not re.search(r'[\d\.%十百千万亿]', quant):
                        flags.append('suspicious_quantitative_target')

        for field in ['key_strategic_themes', 'risk_factors']:
            items = structured_data.get(field, [])
            if items:
                for item in items:
                    if not isinstance(item, dict):
                        flags.append(f'schema_violation:{field}_not_dict')
                        break

        return flags

    def analyze_mda_full(self, mda_text: str) -> Dict[str, Any]:
        """完整MD&A章节分析"""
        from .prompts import MDA_EXTRACTION_PROMPT
        return self.analyze(text=mda_text, prompt_template=MDA_EXTRACTION_PROMPT,
                           max_tokens=8192)


# ============================================================================
# LLM分析器（兼容接口）
# ============================================================================
class LLMAnalyzer:
    def __init__(self, api_key: Optional[str] = None, model: str = "deepseek-chat"):
        if api_key or model != "deepseek-chat":
            self._delegate = None
            self._single_mode = True
            self.api_key = api_key or os.environ.get('DEEPSEEK_API_KEY', '')
            self.model = model
            self.base_url = 'https://api.deepseek.com/v1'
            self.api_style = 'openai'
        else:
            self._delegate = MultiProviderLLMAnalyzer()
            self._single_mode = False
        self._rule_analyzer = None  # lazy init

    @property
    def rule_analyzer(self):
        if self._rule_analyzer is None:
            self._rule_analyzer = RuleBasedAnalyzer()
        return self._rule_analyzer

    def analyze(self, text: str, prompt_template: str,
                output_schema: Optional[Dict] = None,
                max_tokens: int = 4096) -> Dict[str, Any]:
        if self._single_mode:
            return self._analyze_single(text, prompt_template, max_tokens)
        return self._delegate.analyze(text, prompt_template, output_schema, max_tokens)

    def analyze_with_fallback(self, text: str, prompt_template: str,
                               max_tokens: int = 8192) -> Dict[str, Any]:
        """单路调用，自动降级（MiniMax M2.7 → M2.5 → DeepSeek）"""
        if self._single_mode:
            return self._analyze_single(text, prompt_template, max_tokens)
        return self._delegate.analyze_with_fallback(text, prompt_template, max_tokens)

    def analyze_with_validation(self, text: str, prompt_template: str,
                                 max_tokens: int = 8192) -> Dict[str, Any]:
        """多LLM验证：MiniMax + DeepSeek 同时调用"""
        if self._single_mode:
            return self._analyze_single(text, prompt_template, max_tokens)
        return self._delegate.analyze_with_validation(text, prompt_template, max_tokens)

    def _analyze_single(self, text: str, prompt_template: str, max_tokens: int) -> Dict[str, Any]:
        if len(text) < 50:
            return {'error': 'text_too_short', 'structured_data': {}, 'hallucination_flags': []}

        prompt = prompt_template.replace('{text}', text[:8000])

        if self.api_style == 'anthropic':
            import requests
            resp = requests.post(
                f"{self.base_url}/messages",
                headers={
                    'x-api-key': self.api_key,
                    'Content-Type': 'application/json',
                    'anthropic-version': '2023-06-01',
                    'anthropic-dangerous-direct-browser-access': 'true'
                },
                json={
                    'model': self.model,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'max_tokens': max_tokens
                },
                timeout=60
            )
            if resp.status_code == 200:
                data = resp.json()
                for block in data.get('content', []):
                    if block.get('type') == 'text':
                        raw = block['text']
                        break
                else:
                    raw = ''
            else:
                return {'raw_response': '', 'structured_data': {},
                        'model_used': 'failed', 'hallucination_flags': ['api_call_failed'],
                        'error': f'status_{resp.status_code}'}
        else:
            import requests
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    'Authorization': f"Bearer {self.api_key}",
                    'Content-Type': 'application/json'
                },
                json={
                    'model': self.model,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'max_tokens': max_tokens,
                    'temperature': 0.1
                },
                timeout=60
            )
            if resp.status_code == 200:
                raw = resp.json()['choices'][0]['message']['content']
            else:
                return {'raw_response': '', 'structured_data': {},
                        'model_used': 'failed', 'hallucination_flags': ['api_call_failed'],
                        'error': f'status_{resp.status_code}'}

        parsed = self._parse_json_response(raw)
        flags = self._check_hallucination(text, parsed, raw)
        return {
            'raw_response': raw,
            'structured_data': parsed,
            'model_used': f"single/{self.model}",
            'hallucination_flags': flags,
            'error': None
        }

    def _parse_json_response(self, raw_response: str) -> Dict[str, Any]:
        if not raw_response:
            return {}
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        try:
            return json.loads(raw_response)
        except json.JSONDecodeError:
            return {'raw_text': raw_response}

    def _check_hallucination(self, original_text: str,
                              structured_data: Dict[str, Any],
                              raw_response: str) -> list:
        flags = []
        vague_words = ['大约', '约', '基本', '可能', '或许', '大概', '估计', '差不多']
        if any(word in raw_response for word in vague_words):
            flags.append('vague_words_detected')

        required_fields = ['strategic_commitments', 'key_strategic_themes', 'risk_factors']
        missing = [f for f in required_fields if f not in structured_data]
        if missing:
            flags.append(f'missing_fields:{",".join(missing)}')

        if structured_data.get('strategic_commitments'):
            for item in structured_data['strategic_commitments']:
                if not isinstance(item, dict):
                    flags.append('schema_violation:strategic_commitments_not_dict')
                    continue
                quant = item.get('quantitative_target', '')
                if quant and quant != 'NONE' and quant != 'NONE-原文未提及':
                    if not re.search(r'[\d\.%十百千万亿]', quant):
                        flags.append('suspicious_quantitative_target')

        for field in ['key_strategic_themes', 'risk_factors']:
            items = structured_data.get(field, [])
            if items:
                for item in items:
                    if not isinstance(item, dict):
                        flags.append(f'schema_violation:{field}_not_dict')
                        break

        return flags

    def analyze_strategy_section(self, strategy_text: str) -> Dict[str, Any]:
        """
        分析战略子节
        【G7修复】统一使用 MDA_EXTRACTION_PROMPT（Schema A）
        """
        try:
            from .prompts import MDA_EXTRACTION_PROMPT
        except ImportError:
            from prompts import MDA_EXTRACTION_PROMPT

        return self.analyze(
            text=strategy_text,
            prompt_template=MDA_EXTRACTION_PROMPT,
            output_schema={},
            max_tokens=8192
        )

    def analyze_mda_full(self, mda_text: str) -> Dict[str, Any]:
        """完整MD&A分析"""
        try:
            from .prompts import MDA_EXTRACTION_PROMPT
        except ImportError:
            from prompts import MDA_EXTRACTION_PROMPT
        return self.analyze(text=mda_text, prompt_template=MDA_EXTRACTION_PROMPT, max_tokens=8192)

    def analyze_with_rules(self, text: str) -> Dict[str, Any]:
        result = {
            'raw_response': '[RuleBasedAnalyzer - fallback]',
            'structured_data': {},
            'model_used': 'rule_based',
            'hallucination_flags': [],
            'error': None
        }
        try:
            structured = {
                'strategic_commitments': self._extract_commitments(text),
                'key_strategic_themes': self._extract_themes(text),
                'risk_factors': self._extract_risks(text),
                'operating_highlights': [],
            }
            result['structured_data'] = structured
        except Exception:
            result['hallucination_flags'].append('rule_analysis_error')
        return result

    def _extract_commitments(self, text: str) -> list:
        patterns = [
            r'((?:将|拟|计划|致力于|聚焦|坚持|秉承)[^。]{10,100}?。)',
            r'((?:目标|力争|预计|将实现)[^。]{5,50}?。)',
        ]
        results = []
        for p in patterns:
            for m in re.finditer(p, text):
                t = m.group(1).strip()
                if t and len(t) > 5:
                    results.append({
                        'commitment': t, 'time_horizon': 'UNKNOWN',
                        'quantitative_target': 'NONE', 'source_quote': ''
                    })
        return results[:20]

    def _extract_themes(self, text: str) -> list:
        patterns = [
            r'((?:技术|研发|创新)[^。]{5,30}?。)',
            r'((?:市场|客户|品牌)[^。]{5,30}?。)',
            r'((?:产能|生产|制造)[^。]{5,30}?。)',
        ]
        results = []
        for p in patterns:
            for m in re.finditer(p, text):
                t = m.group(1).strip()
                if t and len(t) > 5:
                    results.append({'theme': t[:20], 'description': t, 'evidence_quote': ''})
        return results[:10]

    def _extract_risks(self, text: str) -> list:
        patterns = [
            r'((?:风险|挑战|不利因素|潜在风险)[^。]{5,50}?。)',
        ]
        results = []
        for p in patterns:
            for m in re.finditer(p, text):
                t = m.group(1).strip()
                if t and len(t) > 5:
                    results.append({'risk': t, 'mitigation': 'NONE', 'source_quote': ''})
        return results[:10]


# ============================================================================
# RuleBasedAnalyzer（降级fallback）
# ============================================================================
class RuleBasedAnalyzer:
    """纯规则MD&A分析器，用于LLM不可用时的降级方案"""

    def __init__(self):
        pass

    def analyze_strategy_section(self, text: str) -> Dict[str, Any]:
        try:
            from .prompts import MDA_EXTRACTION_PROMPT
        except ImportError:
            from prompts import MDA_EXTRACTION_PROMPT
        return self.analyze(text)

    def analyze(self, text: str) -> Dict[str, Any]:
        if len(text) < 30:
            return {
                'raw_response': '[RuleBasedAnalyzer - text_too_short]',
                'structured_data': {'strategic_commitments': [], 'key_strategic_themes': [],
                                   'risk_factors': [], 'operating_highlights': []},
                'model_used': 'rule_based',
                'hallucination_flags': [],
                'error': 'text_too_short'
            }
        commitments = self._extract_commitments(text)
        themes = self._extract_themes(text)
        risks = self._extract_risks(text)
        return {
            'raw_response': '[RuleBasedAnalyzer]',
            'structured_data': {
                'strategic_commitments': commitments,
                'key_strategic_themes': themes,
                'risk_factors': risks,
                'operating_highlights': []
            },
            'model_used': 'rule_based',
            'hallucination_flags': [],
            'error': None
        }

    def _extract_commitments(self, text: str) -> list:
        patterns = [
            r'((?:将|拟|计划|致力于|聚焦)[^。]{10,100}?。)',
            r'((?:目标|力争|预计)[^。]{5,50}?。)',
        ]
        results = []
        for p in patterns:
            for m in re.finditer(p, text):
                t = m.group(1).strip()
                if t and len(t) > 5:
                    results.append({
                        'commitment': t, 'time_horizon': 'UNKNOWN',
                        'quantitative_target': 'NONE', 'source_quote': ''
                    })
        return results[:20]

    def _extract_themes(self, text: str) -> list:
        patterns = [
            r'((?:技术|研发|创新)[^。]{5,30}?。)',
            r'((?:市场|客户|品牌)[^。]{5,30}?。)',
            r'((?:产能|生产|制造)[^。]{5,30}?。)',
        ]
        results = []
        for p in patterns:
            for m in re.finditer(p, text):
                t = m.group(1).strip()
                if t and len(t) > 5:
                    results.append({'theme': t[:20], 'description': t, 'evidence_quote': ''})
        return results[:10]

    def _extract_risks(self, text: str) -> list:
        patterns = [
            r'((?:风险|挑战|不利因素|潜在风险)[^。]{5,50}?。)',
        ]
        results = []
        for p in patterns:
            for m in re.finditer(p, text):
                t = m.group(1).strip()
                if t and len(t) > 5:
                    results.append({'risk': t, 'mitigation': 'NONE', 'source_quote': ''})
        return results[:10]
