# Trojan AI

**Your desktop. Your assistant. Your command center.**

Trojan AI is an open-source Windows desktop AI assistant designed to bring intelligent conversations, voice interaction, local memory, and desktop controls into one unified interface.

Built with Python, React, and Electron, Trojan combines an AI-powered backend with a modern desktop experience.

<img width="512" height="512" alt="greek" src="https://github.com/user-attachments/assets/d9d0105d-ec1a-415c-92d9-ac40683ecb44" />


---

## Overview

Trojan AI aims to make interacting with artificial intelligence feel like interacting with a personal desktop assistant.

Instead of being limited to a browser-based chatbot, Trojan connects AI conversations with desktop functionality through a dedicated Windows application.

## Features

- **AI-powered conversations** — Interact with AI models through OpenRouter.
- **Voice interaction** — Speak to Trojan and receive spoken responses.
- **Persistent memory** — Store and manage user-approved memories locally.
- **Conversation history** — Retain and manage previous conversations.
- **Desktop controls** — Execute supported desktop commands.
- **Modern interface** — A dedicated Electron and React desktop interface.
- **Tool integration** — A structured tool system with validation, permissions, and execution timeouts.

## Screenshots

<img width="1920" height="1080" alt="Screenshot (1)" src="https://github.com/user-attachments/assets/ce64de8f-6321-4186-b965-7e8f33e32e5a" />

<img width="1920" height="1080" alt="Screenshot (2)" src="https://github.com/user-attachments/assets/3ab9adcb-4ae2-474f-9329-42df6a9b211d" />

<img width="1920" height="1080" alt="Screenshot (3)" src="https://github.com/user-attachments/assets/00734fa6-1f40-4385-911c-bf0588fa2232" />

<img width="1920" height="1080" alt="Screenshot (4)" src="https://github.com/user-attachments/assets/f1b964ca-3a0e-49eb-97df-a90243477222" />

<img width="1920" height="1080" alt="Screenshot (5)" src="https://github.com/user-attachments/assets/40b0aa2d-0e84-4ff0-8071-ee493fd56734" />


## Technology Stack

| Technology | Purpose |
|---|---|
| Python | AI backend and assistant logic |
| React | User interface |
| Electron | Desktop application framework |
| OpenRouter API | AI model connectivity |
| ElevenLabs | Voice generation |
| SpeechRecognition | Speech transcription |
| SQLite | Local conversation and memory storage |

## Architecture

Trojan uses a Python backend and an Electron-based desktop frontend.

- **Python backend:** Handles AI requests, conversation context, tools, speech recognition, and text-to-speech.
- **Electron main process:** Manages the desktop application and starts the local backend.
- **React renderer:** Displays the user interface.
- **Preload bridge:** Exposes restricted application methods to the renderer.

The local backend listens on `127.0.0.1` and uses an ephemeral bearer token for authenticated communication.

## Installation and Development

### Prerequisites

- Windows
- Python
- Node.js 20 or newer
- An OpenRouter API key

### 1. Clone the repository

```bash
git clone https://github.com/prayashtiwari/Trojan.git
cd Trojan
```

### 2. Set up Python

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy `.env.example` to `.env` and configure your API key:

```env
OPENROUTER_API_KEY=your_api_key_here
```

Never commit your actual `.env` file or expose API credentials in frontend code.

### 4. Install Node dependencies

```bash
npm install
```

### 5. Launch Trojan

```bash
npm run dev
```

## Voice Configuration

Trojan supports microphone input through its SpeechRecognition pipeline.

For spoken responses, it can use:

1. ElevenLabs
2. Windows SAPI
3. pyttsx3 fallback

Voice functionality can be disabled by setting:

```env
TROJAN_VOICE_ENABLED=0
```

Typed conversations remain available when microphone or audio devices are unavailable.

## Building for Windows

To build the application:

```powershell
npm run build
npm run dist
```

The configured packaging process produces an NSIS installer and a portable executable in the `release/` directory.

For a packaged Python backend, prepare the executable using:

```powershell
.venv\Scripts\pyinstaller.exe Trojan-AI.spec
```

Test packaged builds on a clean Windows machine before distributing them.

## Project Structure

```text
Trojan/
├── electron/          # Electron main process and preload
├── public/            # Static assets
├── src/               # React frontend
├── tests/             # Automated tests
├── build/              # Packaging assets
├── backend_server.py  # Local backend server
├── context_store.py   # Conversation and memory storage
├── tool_registry.py   # Tool registration and validation
├── voice.py           # Voice functionality
├── requirements.txt   # Python dependencies
├── package.json       # Node dependencies and scripts
└── README.md
```

## Roadmap

Planned improvements:

- [ ] Improve voice interaction and reliability.
- [ ] Expand desktop automation capabilities.
- [ ] Improve memory and context management.
- [ ] Expand automated testing.
- [ ] Improve documentation and onboarding.
- [ ] Publish stable Windows releases.

## Contributing

Contributions, bug reports, and feature suggestions are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Make your changes.
4. Test your changes.
5. Submit a pull request.

## Security

Do not publish API keys, passwords, personal data, or other sensitive credentials.

If you discover a security vulnerability, report it responsibly rather than publishing exploit details.

## License

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.

---

**Trojan AI** — An open-source experiment in building a more capable desktop assistant.
