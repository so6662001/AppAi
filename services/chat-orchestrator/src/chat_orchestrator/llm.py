"""LLM 客户端 - 兼容 OpenAI 协议 (DeepSeek/通义千问/本地 Qwen vLLM 全兼容)。

调用场景:
  1) intent_fallback: 规则未命中指标时, 让 LLM 抽取槽位
  2) summarize: 把 rows + dsl 生成自然中文总结
  3) drill_analysis: 复杂归因 (TODO)

无 API Key 时所有方法返回 None, 调用方走规则路径作为兜底.
"""
from __future__ import annotations
import json
import logging
import os
from typing import Optional
import httpx

log = logging.getLogger("chat.llm")


class LLMClient:

    def __init__(self, provider: str = "rule", api_key: str | None = None,
                 base_url: str | None = None, model: str | None = None):
        self.provider = provider
        self.api_key = api_key or os.environ.get("LLM_API_KEY")
        self.base_url = base_url or self._default_base()
        self.model = model or self._default_model()
        self.enabled = bool(self.api_key) and provider != "rule"
        if self.enabled:
            log.info("LLM enabled provider=%s model=%s", provider, self.model)

    def _default_base(self) -> str:
        return {
            "deepseek": "https://api.deepseek.com/v1",
            "qwen":     "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "openai":   "https://api.openai.com/v1",
            "local":    os.environ.get("LLM_LOCAL_URL", "http://localhost:8000/v1"),
        }.get(self.provider, "https://api.deepseek.com/v1")

    def _default_model(self) -> str:
        return {
            "deepseek": "deepseek-chat",
            "qwen":     "qwen-plus",
            "openai":   "gpt-4o-mini",
            "local":    "Qwen2.5-7B-Instruct",
        }.get(self.provider, "deepseek-chat")

    def chat(self, messages: list[dict], temperature: float = 0.3,
             max_tokens: int = 800, timeout: float = 15) -> Optional[str]:
        if not self.enabled:
            return None
        try:
            r = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}",
                         "Content-Type": "application/json"},
                json={"model": self.model, "messages": messages,
                      "temperature": temperature, "max_tokens": max_tokens},
                timeout=timeout)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            log.warning("LLM call failed: %s", e)
            return None

    def intent_extract(self, text: str, available_metrics: list[str]) -> dict | None:
        """让 LLM 抽出: {metrics, time, dimensions, compare, top_n}.
        返回 None 表示失败/未启用, 调用方走规则路径."""
        if not self.enabled:
            return None
        sys = (
            "你是钢铁经营分析意图抽取助手. 用户问题中可能包含: 指标(销售额/库存/达交率等)、"
            "时间(yesterday/last_week/last_month/mtd/ytd)、维度(customer/origin/grade/region/product_type)、"
            "比较(yoy/mom/wow)、topN. 严格输出 JSON, 不要解释."
        )
        usr = (
            f"问题: {text}\n可选指标列表(部分): {', '.join(available_metrics[:30])}\n"
            "输出格式: {\"metrics\":[\"name\"], \"time_preset\":\"\", \"dimensions\":[\"\"], "
            "\"compare\":null|\"yoy\"|\"mom\"|\"wow\", \"top_n\":null|5}"
        )
        out = self.chat(
            [{"role": "system", "content": sys}, {"role": "user", "content": usr}],
            temperature=0.0, max_tokens=300)
        if not out:
            return None
        try:
            # 模型可能返回带 ```json 包裹的内容
            txt = out.strip()
            if txt.startswith("```"):
                txt = txt.strip("`")
                if txt.startswith("json"): txt = txt[4:]
            return json.loads(txt)
        except Exception as e:
            log.warning("LLM intent JSON parse failed: %s; raw=%s", e, out[:200])
            return None

    def summarize(self, rows: list[dict], dsl: dict, base_summary: str) -> str:
        """生成更自然的中文总结. 失败返回 base_summary."""
        if not self.enabled or not rows:
            return base_summary
        sys = "你是钢铁经营分析助手. 用一句不超过 50 字的中文总结结果, 数字保留 2 位小数."
        usr = (
            f"DSL: {json.dumps(dsl, ensure_ascii=False)}\n"
            f"结果(前5行): {json.dumps(rows[:5], ensure_ascii=False, default=str)}"
        )
        out = self.chat([{"role": "system", "content": sys},
                         {"role": "user", "content": usr}],
                        temperature=0.3, max_tokens=120)
        return out.strip() if out else base_summary
