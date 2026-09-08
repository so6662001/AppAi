"""DSL → SQL 编译器。

只对外暴露以下高层 API：
    - load_registry(metrics_dir)
    - compile(dsl, context)
    - execute_dsl(...) (在 app.py 中暴露为 FastAPI 端点)
"""
from .registry import MetricRegistry, load_registry
from .compiler import DSLCompiler, CompileResult, CompileError
from .models import DSL, CompileContext, MetricDef

__all__ = [
    "MetricRegistry",
    "load_registry",
    "DSLCompiler",
    "CompileResult",
    "CompileError",
    "DSL",
    "CompileContext",
    "MetricDef",
]
