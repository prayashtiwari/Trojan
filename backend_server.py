"""Loopback API for the Trojan desktop application.

The server deliberately binds to localhost only. Electron supplies an
ephemeral bearer token so another local process cannot use the control API
without access to the Electron child-process environment.
"""

from __future__ import annotations

import argparse
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trojan local desktop API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--token", required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    os.environ["TROJAN_API_TOKEN"] = args.token

    assistant = None
    speak = None
    stop_speaking = None
    messages: list[dict[str, Any]] = []
    messages_lock = threading.Lock()
    chat_lock = threading.Lock()
    activity_lock = threading.Lock()
    activity: dict[str, Any] = {"state": "idle", "tool": None, "progress": 0}
    cancel_event = threading.Event()
    settings_path = Path(os.getenv("APPDATA", Path.home())) / "Trojan AI" / "settings.json"
    saved_settings: dict[str, Any] = {}
    try:
        saved_settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass

    def ensure_assistant() -> Any:
        nonlocal assistant, speak, stop_speaking, messages
        if assistant is None:
            import trojanassiastant
            from voice import speak as voice_speak, stop_speaking as voice_stop_speaking

            assistant = trojanassiastant
            speak = voice_speak
            stop_speaking = voice_stop_speaking
            saved_model = saved_settings.get("model")
            if isinstance(saved_model, str) and saved_model.strip():
                assistant.MODEL_NAME = saved_model.strip()
            messages = assistant.create_conversation()
        return assistant

    class Handler(BaseHTTPRequestHandler):
        server_version = "TrojanBackend/1.0"

        def log_message(self, format: str, *args: Any) -> None:
            print("[Backend] " + (format % args))

        def _authorized(self) -> bool:
            return self.headers.get("Authorization", "") == f"Bearer {args.token}"

        def _send(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 1_000_000:
                raise ValueError("Request body is too large.")
            raw = self.rfile.read(length)
            value = json.loads(raw or b"{}")
            if not isinstance(value, dict):
                raise ValueError("Request body must be a JSON object.")
            return value

        def do_GET(self) -> None:
            if not self._authorized():
                self._send(401, {"error": "Unauthorized."})
                return
            path = urlparse(self.path).path
            if path == "/health":
                loaded_assistant = ensure_assistant()
                self._send(200, {"ok": True, "model": loaded_assistant.MODEL_NAME})
            elif path == "/status":
                with activity_lock:
                    self._send(200, dict(activity))
            elif path == "/conversation":
                loaded_assistant = ensure_assistant()
                self._send(200, {"conversation": loaded_assistant.context_store.conversation()})
            elif path == "/history":
                loaded_assistant = ensure_assistant()
                self._send(200, {"history": loaded_assistant.context_store.history()})
            elif path == "/memories":
                loaded_assistant = ensure_assistant()
                self._send(200, {"memories": loaded_assistant.context_store.memories()})
            elif path == "/projects":
                loaded_assistant = ensure_assistant()
                self._send(200, {"projects": loaded_assistant.context_store.projects()})
            elif path == "/settings":
                try:
                    settings = json.loads(settings_path.read_text(encoding="utf-8"))
                except (FileNotFoundError, json.JSONDecodeError):
                    settings = {}
                self._send(200, {"settings": settings})
            else:
                self._send(404, {"error": "Not found."})

        def do_POST(self) -> None:
            if not self._authorized():
                self._send(401, {"error": "Unauthorized."})
                return
            path = urlparse(self.path).path
            try:
                payload = self._read_json()
                if path == "/chat":
                    loaded_assistant = ensure_assistant()
                    prompt = payload.get("prompt")
                    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 20_000:
                        raise ValueError("prompt must be a non-empty string under 20,000 characters.")
                    if not chat_lock.acquire(blocking=False):
                        self._send(409, {"error": "A request is already in progress."})
                        return
                    def on_activity(state: str, tool: str | None = None, progress: int = 0) -> None:
                        with activity_lock:
                            activity.update({"state": state, "tool": tool, "progress": progress})

                    cancel_event.clear()
                    on_activity("thinking")
                    try:
                        with messages_lock:
                            answer = loaded_assistant.process_user_input(
                                messages,
                                prompt.strip(),
                                speak_response=True,
                                on_activity=on_activity,
                                cancel_event=cancel_event,
                            )
                    finally:
                        on_activity("idle")
                        chat_lock.release()
                    if answer is None:
                        self._send(502, {"error": "The assistant did not return a response."})
                    else:
                        self._send(200, {"answer": answer})
                elif path == "/chat/cancel":
                    cancel_event.set()
                    with activity_lock:
                        activity.update({"state": "idle", "tool": None, "progress": 0})
                    self._send(200, {"cancelled": True})
                elif path == "/conversation/clear":
                    loaded_assistant = ensure_assistant()
                    with messages_lock:
                        loaded_assistant.context_store.clear_conversation()
                        messages[:] = loaded_assistant.create_conversation()
                    self._send(200, {"cleared": True})
                elif path == "/memories":
                    loaded_assistant = ensure_assistant()
                    content = payload.get("content")
                    category = payload.get("category", "preference")
                    if not isinstance(content, str) or not isinstance(category, str):
                        raise ValueError("content and category must be strings.")
                    memory = loaded_assistant.context_store.add_memory(content, category)
                    with messages_lock:
                        messages[:] = loaded_assistant.create_conversation()
                    self._send(200, {"memory": memory})
                elif path == "/memories/clear":
                    loaded_assistant = ensure_assistant()
                    category = payload.get("category")
                    if category is not None and not isinstance(category, str):
                        raise ValueError("category must be a string.")
                    loaded_assistant.context_store.clear_memories(category)
                    with messages_lock:
                        messages[:] = loaded_assistant.create_conversation()
                    self._send(200, {"cleared": True})
                elif path == "/memories/delete":
                    loaded_assistant = ensure_assistant()
                    memory_id = payload.get("id")
                    if not isinstance(memory_id, str) or not memory_id.strip():
                        raise ValueError("id must be a non-empty string.")
                    deleted = loaded_assistant.context_store.delete_memory(memory_id)
                    with messages_lock:
                        messages[:] = loaded_assistant.create_conversation()
                    self._send(200, {"deleted": deleted})
                elif path == "/projects":
                    loaded_assistant = ensure_assistant()
                    name = payload.get("name")
                    content = payload.get("content")
                    if not isinstance(name, str) or not isinstance(content, str):
                        raise ValueError("name and content must be strings.")
                    project = loaded_assistant.context_store.save_project(name, content)
                    self._send(200, {"project": project})
                elif path == "/projects/delete":
                    loaded_assistant = ensure_assistant()
                    project_id = payload.get("id")
                    if not isinstance(project_id, str) or not project_id.strip():
                        raise ValueError("id must be a non-empty string.")
                    self._send(200, {"deleted": loaded_assistant.context_store.delete_project(project_id)})
                elif path == "/voice/listen":
                    with activity_lock:
                        activity.update({"state": "listening", "tool": None, "progress": 0})
                    try:
                        transcript = ensure_assistant().listen_command()
                        with activity_lock:
                            activity.update({"state": "transcribing", "tool": None, "progress": 0})
                        self._send(200, {"transcript": transcript})
                    finally:
                        with activity_lock:
                            activity.update({"state": "idle", "tool": None, "progress": 0})
                elif path == "/voice/speak":
                    ensure_assistant()
                    text = payload.get("text")
                    if not isinstance(text, str) or not text.strip() or len(text) > 20_000:
                        raise ValueError("text must be a non-empty string under 20,000 characters.")
                    with activity_lock:
                        activity.update({"state": "speaking", "tool": None, "progress": 0})
                    try:
                        spoken = bool(speak(text.strip()))
                        self._send(200, {"spoken": spoken})
                    finally:
                        with activity_lock:
                            activity.update({"state": "idle", "tool": None, "progress": 0})
                elif path == "/voice/stop":
                    ensure_assistant()
                    stop_speaking()
                    with activity_lock:
                        activity.update({"state": "idle", "tool": None, "progress": 0})
                    self._send(200, {"stopped": True})
                elif path == "/settings":
                    settings = payload.get("settings")
                    if not isinstance(settings, dict):
                        raise ValueError("settings must be a JSON object.")
                    model = settings.get("model")
                    if model is not None:
                        if not isinstance(model, str) or not model.strip() or len(model) > 200:
                            raise ValueError("model must be a non-empty string under 200 characters.")
                        if assistant is not None:
                            assistant.MODEL_NAME = model.strip()
                    settings_path.parent.mkdir(parents=True, exist_ok=True)
                    settings_path.write_text(
                        json.dumps(settings, indent=2), encoding="utf-8"
                    )
                    self._send(200, {"saved": True})
                else:
                    self._send(404, {"error": "Not found."})
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                self._send(400, {"error": str(exc)})
            except Exception as exc:
                print(f"[Backend error] {exc}")
                self._send(500, {"error": "The backend could not complete the request."})

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(json.dumps({"ready": True, "port": server.server_address[1]}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
