"""Permissioned, bounded tool execution for Trojan.

The model only receives declarations from this registry. Handlers are ordinary
Python callables, but argument validation, permission checks, time limits, and
result shaping are centralized here.
"""

from __future__ import annotations

import json
import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger("trojan.tools")


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]
    permission: str = "safe"
    requires_confirmation: bool = False
    timeout_seconds: float = 30.0


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if not spec.name or not callable(spec.handler):
            raise ValueError("A tool needs a name and callable handler.")
        if spec.timeout_seconds <= 0:
            raise ValueError("Tool timeout must be positive.")
        self._tools[spec.name] = spec

    def declarations(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.parameters,
                },
            }
            for spec in self._tools.values()
        ]

    def execute(
        self,
        name: str,
        arguments: str | dict[str, Any],
        *,
        cancel_event: threading.Event | None = None,
        confirmation_granted: bool = False,
    ) -> dict[str, Any]:
        spec = self._tools.get(name)
        if spec is None:
            return self._failure(name, "unknown_tool", "Unknown tool requested.")
        try:
            values = json.loads(arguments or "{}") if isinstance(arguments, str) else arguments
            if not isinstance(values, dict):
                raise ValueError("Tool arguments must be a JSON object.")
            self._validate(spec.parameters, values)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            return self._failure(name, "invalid_arguments", str(exc))

        if spec.requires_confirmation and not confirmation_granted:
            logger.info("Tool %s blocked pending confirmation.", name)
            return {
                "ok": False,
                "tool": name,
                "code": "confirmation_required",
                "permission": spec.permission,
                "message": "User confirmation is required before this action can run.",
            }
        if cancel_event is not None and cancel_event.is_set():
            return self._failure(name, "cancelled", "Tool execution was cancelled.")

        logger.info("Executing tool %s (permission=%s).", name, spec.permission)
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="trojan-tool")
        future: Future[Any] = executor.submit(spec.handler, **values)
        try:
            result = future.result(timeout=spec.timeout_seconds)
            if cancel_event is not None and cancel_event.is_set():
                return self._failure(name, "cancelled", "Tool execution was cancelled.")
            return {
                "ok": True,
                "tool": name,
                "permission": spec.permission,
                "result": result if isinstance(result, (dict, list, str, int, float, bool)) else str(result),
            }
        except FutureTimeoutError:
            future.cancel()
            return self._failure(
                name,
                "timeout",
                f"Tool timed out after {spec.timeout_seconds:g} seconds.",
            )
        except Exception:
            logger.exception("Tool %s failed.", name)
            return self._failure(name, "execution_failed", "The tool failed without exposing internal details.")
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    @staticmethod
    def _failure(name: str, code: str, message: str) -> dict[str, Any]:
        return {"ok": False, "tool": name, "code": code, "error": message}

    @staticmethod
    def _validate(schema: dict[str, Any], values: dict[str, Any]) -> None:
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        missing = [key for key in required if key not in values]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")
        if schema.get("additionalProperties") is False:
            unexpected = [key for key in values if key not in properties]
            if unexpected:
                raise ValueError(f"Unexpected field: {unexpected[0]}")
        for key, value in values.items():
            definition = properties.get(key)
            if not definition:
                raise ValueError(f"Unexpected field: {key}")
            declared = definition.get("type", [])
            allowed = declared if isinstance(declared, list) else [declared]
            if value is None and "null" in allowed:
                continue
            matches = {
                "string": isinstance(value, str),
                "integer": isinstance(value, int) and not isinstance(value, bool),
                "boolean": isinstance(value, bool),
                "number": isinstance(value, (int, float)) and not isinstance(value, bool),
                "array": isinstance(value, list),
                "object": isinstance(value, dict),
            }
            if not any(matches.get(item, False) for item in allowed):
                raise ValueError(f"Field {key} has an invalid type.")
            if isinstance(value, str) and "maxLength" in definition and len(value) > definition["maxLength"]:
                raise ValueError(f"Field {key} is too long.")
            if "enum" in definition and value not in definition["enum"]:
                raise ValueError(f"Field {key} must be one of: {', '.join(definition['enum'])}")
