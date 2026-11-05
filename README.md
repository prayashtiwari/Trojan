# Trojan AI

Trojan AI is a Windows desktop command center around the existing Python
assistant. The Python module remains the owner of OpenRouter requests,
conversation context, tools, speech recognition, and text-to-speech. Electron
only renders the interface and calls a short-lived, authenticated loopback
bridge.

## Context and tools

Conversation turns and user-approved memories are stored locally in
`%APPDATA%\Trojan AI\context.db` (or the path in `TROJAN_CONTEXT_PATH`).
The assistant sends only the bounded recent conversation window, plus approved
memories, to OpenRouter. The desktop Settings screen can add/delete memories;
History can clear the conversation. The local backend also exposes authenticated
`GET /conversation`, `POST /conversation/clear`, `GET /memories`,
`POST /memories`, `POST /memories/delete`, `POST /memories/clear`,
`GET /history`, `GET /projects`, `POST /projects`, and
`POST /projects/delete`.

Tools are registered with a validated JSON schema, permission label, and
execution timeout. Tool failures are returned to the model as explicit results
instead of being presented as successful actions. Configure the context window
with `TROJAN_CONTEXT_HISTORY_LIMIT` (default: 40 turns).

Common desktop commands are handled locally before an AI request is made:
`open YouTube`, `open Notepad`, `increase volume`, `decrease volume`,
`increase brightness`, and `decrease brightness`. Relative volume and
brightness changes use a 10 percent step by default, or the percentage spoken
by the user. Website targets are normalized before being opened so malformed
tool-call formatting cannot be passed to the browser.

Apple Music is launched through its registered Windows AppsFolder identity
(`AppleInc.AppleMusicWin_nzyj5cx40ttqa!App`) instead of fuzzy matching an
executable or unrelated shortcut.

## Development

1. Create and activate a Python virtual environment.
2. Install Python dependencies:

   ```powershell
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and set `OPENROUTER_API_KEY` locally. Never
   commit `.env` or put a real key in frontend code.
4. Install Node.js 20 or newer, then install frontend dependencies:

   ```powershell
   npm install
   npm run dev
   ```

The Electron main process starts `backend_server.py` on `127.0.0.1` with an
ephemeral bearer token. The renderer receives only the restricted methods in
`electron/preload.cjs`; it has no Node.js or filesystem access.

## Voice

The microphone endpoint uses the existing `sounddevice` capture and
SpeechRecognition transcription path. Response speech uses the existing
ElevenLabs configuration when available, then Windows SAPI and pyttsx3
fallbacks. Set `TROJAN_VOICE_ENABLED=0` for text-only operation. If a device
is unavailable, typed chat remains usable. Optional diagnostics and microphone
selection are documented in `.env.example`.

Desktop chat responses are spoken by the backend by default. If ElevenLabs
fails, Trojan logs the failure and falls back to Windows SAPI and then
pyttsx3. Simple `KEY=VALUE` entries are loaded from the project `.env` file
(or `TROJAN_ENV_FILE`) when those variables are not already present in the
process environment.

## Packaging

The checked-in builder targets are:

```powershell
npm run build
npm run dist
```

This produces an NSIS installer and a portable executable in `release/`.
The Python runtime used for a packaged build must be prepared on Windows with
the same architecture as the target. For a self-contained backend executable,
build `Trojan-AI.spec` first:

```powershell
.venv\Scripts\pyinstaller.exe Trojan-AI.spec
```

Do not treat a development virtual environment as a release artifact unless
it has been built specifically for the target machine. A release checklist
must verify the installer and portable executable on a clean Windows machine,
including backend startup, API errors, voice fallback, and shutdown cleanup.

## Verification boundaries

- Windows microphone and SAPI behavior requires a real microphone and audio
  device; automated voice tests cover playback coordination and fallbacks
  without fabricating microphone input.
- API credentials are intentionally external configuration; they are never
  bundled in the frontend.
