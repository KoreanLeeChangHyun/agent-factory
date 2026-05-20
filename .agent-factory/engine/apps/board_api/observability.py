"""Board API observability helpers."""

from __future__ import annotations

import datetime
import functools
import json
import os
from collections.abc import Callable
from typing import Any


def server_debug_log(tag: str, data: object) -> None:
    """Append a server-side debug event when board debug logging is enabled."""
    try:
        log_dir = os.path.join(os.getcwd(), ".agent-factory", "runs", "bg")
        if not os.path.exists(os.path.join(log_dir, "debug.enabled")):
            return
        entry = {
            "ts": datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z"),
            "tag": "server." + str(tag),
            "data": data,
        }
        with open(os.path.join(log_dir, "debug.log"), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except (OSError, TypeError, ValueError):
        pass


def api_endpoint(domain: str, verb: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorate board API endpoint handlers with standard debug log events."""
    base_tag = f"api.{domain}.{verb}"

    def _decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def _wrapped(*args: Any, **kwargs: Any) -> Any:
            server_debug_log(
                base_tag + ".entry",
                {"args_count": len(args), "kwargs_keys": list(kwargs.keys())},
            )
            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                server_debug_log(
                    base_tag + ".error",
                    {"type": type(exc).__name__, "msg": str(exc)},
                )
                raise
            server_debug_log(base_tag + ".exit", {"result_type": type(result).__name__})
            return result

        return _wrapped

    return _decorator
