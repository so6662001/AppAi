"""多模型路由 - 按任务类型 + 复杂度选择模型.

任务:
  intent        : 意图分类 / 槽位抽取  → 便宜小模型 (qwen-7b 本地 / deepseek-chat)
  summarize     : 一句话总结           → 便宜小模型
  drill         : 复杂归因             → 强模型 (deepseek-v3 / qwen-max)
  embedding     : 文本 embedding       → bge-m3 本地

策略:
  - 同 task_type 内长度 < 100 字 → 便宜模型
  - > 500 字或包含"为什么/原因/归因" → 强模型
  - 失败自动 fallback 到下一档
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

TaskType = Literal["intent", "summarize", "drill", "embedding"]


@dataclass
class ModelChoice:
    provider: str
    model: str
    why: str = ""


PROVIDERS = {
    "deepseek": {"chat": "deepseek-chat", "strong": "deepseek-reasoner"},
    "qwen":     {"chat": "qwen-plus",     "strong": "qwen-max"},
    "local":    {"chat": "Qwen2.5-7B-Instruct"},
}


def route(task: TaskType, text_length: int = 0, complex_hint: bool = False) -> ModelChoice:
    is_complex = complex_hint or text_length > 500
    if task == "drill" or is_complex:
        # 强模型
        return ModelChoice("deepseek", "deepseek-reasoner", "complex/drill needs strong model")
    if task in ("intent", "summarize"):
        return ModelChoice("local", "Qwen2.5-7B-Instruct", "simple task → cheap local")
    if task == "embedding":
        return ModelChoice("local", "bge-m3", "always local embed")
    return ModelChoice("deepseek", "deepseek-chat", "default")
