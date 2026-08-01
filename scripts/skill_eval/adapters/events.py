"""Codex event-stream parsing kept inside the Codex adapter boundary."""

from __future__ import annotations

import json
from typing import Any

from ..evidence import _all_strings


class CodexEventParser:
    """Parse Codex JSONL and extract adapter-native execution signals."""

    @staticmethod
    def load(text: str) -> tuple[list[dict[str, Any]], list[str]]:
        events: list[dict[str, Any]] = []
        errors: list[str] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_number}: {exc}")
                continue
            if isinstance(value, dict):
                events.append(value)
        return events, errors

    @staticmethod
    def summarize(
        events: list[dict[str, Any]],
        *,
        activation_marker: str | None,
        activation_name: str | None,
    ) -> dict[str, Any]:
        final_messages: list[str] = []
        tool_calls = 0
        usage: dict[str, int] = {}
        activated = False
        marker_suffix = activation_marker.replace("\\", "/") if activation_marker else None

        for event in events:
            item = event.get("item")
            if isinstance(item, dict):
                item_type = str(item.get("type", ""))
                if item_type == "agent_message" and isinstance(item.get("text"), str):
                    final_messages.append(item["text"])
                if event.get("type") == "item.completed" and item_type not in {
                    "agent_message",
                    "reasoning",
                }:
                    tool_calls += 1
                if item_type in {"skill_call", "skill"} and activation_name:
                    activated = activated or any(
                        value == activation_name or value.endswith(f"/{activation_name}")
                        for value in _all_strings(item)
                    )
                if marker_suffix and item_type not in {"agent_message", "reasoning"}:
                    activated = activated or any(
                        marker_suffix in value.replace("\\", "/") for value in _all_strings(item)
                    )
            if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
                usage = {
                    key: int(value)
                    for key, value in event["usage"].items()
                    if isinstance(value, (int, float)) and not isinstance(value, bool)
                }
        return {
            "final_response": final_messages[-1] if final_messages else "",
            "tool_calls": tool_calls,
            "usage": usage,
            "activated": activated,
        }
