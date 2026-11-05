import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tool_registry import ToolRegistry, ToolSpec


class ToolRegistryTests(unittest.TestCase):
    def test_rejects_unknown_and_extra_arguments(self):
        registry = ToolRegistry()
        registry.register(
            ToolSpec(
                name="echo",
                description="Echo a value.",
                parameters={
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"value": {"type": "string", "maxLength": 10}},
                    "required": ["value"],
                },
                handler=lambda value: value,
            )
        )
        self.assertEqual(registry.execute("missing", {})["code"], "unknown_tool")
        self.assertEqual(
            registry.execute("echo", {"value": "ok", "extra": True})["code"],
            "invalid_arguments",
        )

    def test_confirmation_is_a_hard_gate(self):
        registry = ToolRegistry()
        called = []
        registry.register(
            ToolSpec(
                name="delete_item",
                description="Delete one item.",
                parameters={"type": "object", "properties": {"item": {"type": "string"}}, "required": ["item"]},
                handler=lambda item: called.append(item),
                permission="destructive",
                requires_confirmation=True,
            )
        )
        result = registry.execute("delete_item", {"item": "record"})
        self.assertEqual(result["code"], "confirmation_required")
        self.assertEqual(called, [])
        self.assertTrue(registry.execute("delete_item", {"item": "record"}, confirmation_granted=True)["ok"])

    def test_timeout_and_cancellation_are_structured(self):
        registry = ToolRegistry()
        registry.register(
            ToolSpec(
                name="slow",
                description="Slow operation.",
                parameters={"type": "object", "properties": {}},
                handler=lambda: time.sleep(0.2),
                timeout_seconds=0.01,
            )
        )
        self.assertEqual(registry.execute("slow", {})["code"], "timeout")
        cancel = threading.Event()
        cancel.set()
        self.assertEqual(registry.execute("slow", {}, cancel_event=cancel)["code"], "cancelled")

    def test_approved_folder_workflow(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "brief.txt"
            path.write_text("Trojan workflow complete.", encoding="utf-8")
            previous = os.environ.get("TROJAN_APPROVED_FOLDERS")
            os.environ["TROJAN_APPROVED_FOLDERS"] = folder
            try:
                from trojanassiastant import read_approved_file, search_approved_files

                matches = search_approved_files("brief")
                self.assertEqual(matches[0]["name"], "brief.txt")
                result = read_approved_file(str(path))
                self.assertEqual(result["content"], "Trojan workflow complete.")
            finally:
                if previous is None:
                    os.environ.pop("TROJAN_APPROVED_FOLDERS", None)
                else:
                    os.environ["TROJAN_APPROVED_FOLDERS"] = previous

    def test_model_receives_actual_tool_feedback_before_final_answer(self):
        import trojanassiastant as assistant

        class FakeMessage:
            def __init__(self, content="", tool_calls=None):
                self.content = content
                self.tool_calls = tool_calls or []

            def model_dump(self, exclude_none=True):
                return {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {"name": call.function.name, "arguments": call.function.arguments},
                        }
                        for call in self.tool_calls
                    ],
                }

        class Call:
            id = "call-1"
            function = type("Function", (), {"name": "echo", "arguments": '{"value":"real"}'})()

        class FakeClient:
            def __init__(self):
                self.requests = []
                self.chat = self
                self.completions = self
                self.responses = [
                    type("Response", (), {"choices": [type("Choice", (), {"message": FakeMessage(tool_calls=[Call()]), "finish_reason": "tool_calls"})()]})(),
                    type("Response", (), {"choices": [type("Choice", (), {"message": FakeMessage("The tool returned real, sir."), "finish_reason": "stop"})()]})(),
                ]

            def create(self, **kwargs):
                self.requests.append(list(kwargs["messages"]))
                return self.responses.pop(0)

        registry = ToolRegistry()
        registry.register(
            ToolSpec(
                name="echo",
                description="Echo a value.",
                parameters={"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]},
                handler=lambda value: {"echoed": value},
            )
        )
        fake = FakeClient()
        spoken = []
        with patch.object(assistant, "client", fake), patch.object(
            assistant, "tool_registry", registry
        ), patch.object(
            assistant, "pc_control_tools", registry.declarations()
        ), patch.object(
            assistant, "speak", spoken.append
        ):
            answer = assistant.process_user_input([], "use the echo tool", speak_response=True)

        self.assertEqual(answer, "The tool returned real, sir.")
        self.assertEqual(spoken, ["The tool returned real, sir."])
        self.assertEqual(len(fake.requests), 2)
        feedback = fake.requests[1][-1]
        self.assertEqual(feedback["role"], "tool")
        self.assertIn('"echoed": "real"', feedback["content"])


if __name__ == "__main__":
    unittest.main()
