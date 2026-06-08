"""AgentNet 轻量内存 — 最近一次执行记录."""
from typing import Any, Dict, List, Optional

_last_execution: Optional[Dict[str, Any]] = None
_history: List[Dict[str, Any]] = []


def save_execution(result: Dict[str, Any]) -> None:
    global _last_execution
    _last_execution = result
    _history.append(result)
    if len(_history) > 20:
        _history.pop(0)


def get_last_execution() -> Optional[Dict[str, Any]]:
    return _last_execution


def get_history(limit: int = 5) -> List[Dict[str, Any]]:
    return _history[-limit:]
