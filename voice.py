"""Offline text-to-speech support for the assistant."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import threading
import time
from typing import Any


def _load_local_env() -> None:
    """Load simple KEY=VALUE entries without requiring python-dotenv."""
    env_path = os.getenv("TROJAN_ENV_FILE")
    candidates = [env_path] if env_path else []
    candidates.append(os.path.join(os.path.dirname(__file__), ".env"))
    for candidate in candidates:
        if not candidate or not os.path.isfile(candidate):
            continue
        try:
            with open(candidate, encoding="utf-8") as environment_file:
                for raw_line in environment_file:
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    name, value = line.split("=", 1)
                    name = name.strip()
                    value = value.strip().strip("\"'")
                    if name and name not in os.environ:
                        os.environ[name] = value
        except OSError as exc:
            print(f"[Voice configuration error: could not read {candidate}: {exc}]")
        return


_load_local_env()

try:
    import requests
except ImportError:
    requests = None

try:
    import numpy as np
except ImportError:
    np = None

try:
    import msvcrt
except ImportError:
    msvcrt = None

try:
    import winreg
except ImportError:
    winreg = None

try:
    import pyttsx3
except ImportError:  # Keep the assistant usable when optional TTS is absent.
    pyttsx3 = None

try:
    import sounddevice as sd
    from scipy.io.wavfile import read as read_wav
except ImportError:  # Keep text-only operation possible without audio packages.
    sd = None
    read_wav = None


_engine: Any = None
_engine_lock = threading.Lock()
_speaking_lock = threading.Lock()
_initialization_attempted = False
_stop_requested = threading.Event()
_active_process: subprocess.Popen[str] | None = None
ELEVENLABS_VOICE_ID = "8UI98YksGHW9FvROsnJ6"
ELEVENLABS_OUTPUT_FORMAT = "pcm_22050"
ELEVENLABS_SAMPLE_RATE = 22050


def _setting(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value:
        return value.strip()
    if winreg is None:
        return default
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _ = winreg.QueryValueEx(key, name)
            return str(value).strip()
    except (FileNotFoundError, OSError, TypeError):
        return default


def _preferred_voice_id(voices: list[Any]) -> str | None:
    requested = os.getenv("TROJAN_VOICE_ID", "").strip().lower()
    if requested:
        for voice in voices:
            if requested in str(getattr(voice, "id", "")).lower():
                return voice.id

    for voice in voices:
        languages = " ".join(str(language).lower() for language in voice.languages)
        if "en-us" in languages or "en-gb" in languages or "english" in languages:
            return voice.id
    return None


def _is_enabled() -> bool:
    return os.getenv("TROJAN_VOICE_ENABLED", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _clean_text(text: str) -> str:
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[*#_`>\[\]()]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _get_engine() -> Any:
    global _engine, _initialization_attempted

    if _initialization_attempted:
        return _engine

    _initialization_attempted = True
    if pyttsx3 is None:
        print("[Voice disabled: install pyttsx3 to enable speech.]")
        return None

    try:
        _engine = pyttsx3.init()
        voice_id = _preferred_voice_id(_engine.getProperty("voices"))
        if voice_id:
            _engine.setProperty("voice", voice_id)
        _engine.setProperty("rate", int(os.getenv("TROJAN_VOICE_RATE", "175")))
        _engine.setProperty("volume", float(os.getenv("TROJAN_VOICE_VOLUME", "1.0")))
    except Exception as exc:
        _engine = None
        print(f"[Voice initialization error: {exc}]")
    return _engine


def _reset_engine() -> None:
    global _engine, _initialization_attempted

    _engine = None
    _initialization_attempted = False


def stop_speaking() -> None:
    """Stop the current utterance, if one is playing."""
    global _active_process

    _stop_requested.set()
    if _active_process is not None and _active_process.poll() is None:
        _active_process.terminate()
    if sd is not None:
        sd.stop()


def _skip_key_pressed() -> bool:
    if msvcrt is None or not msvcrt.kbhit():
        return False
    key = msvcrt.getwch().lower()
    if key == "s":
        stop_speaking()
        print("\n[Speech skipped]")
        return True
    return False


def _play_pcm_audio(audio: Any, sample_rate: int) -> bool:
    if sd is None:
        print("[Voice error: sounddevice is unavailable.]")
        return False

    sd.play(audio, sample_rate)
    while True:
        if _skip_key_pressed() or _stop_requested.is_set():
            sd.stop()
            return False
        if not sd.get_stream().active:
            return True
        time.sleep(0.05)


def _speak_with_elevenlabs(text: str) -> bool:
    """Generate English speech with Trojan's ElevenLabs voice and play it."""
    api_key = _setting("ELEVENLABS_API_KEY")
    if not api_key or requests is None or np is None:
        return False

    voice_id = _setting("ELEVENLABS_VOICE_ID", ELEVENLABS_VOICE_ID)
    endpoint = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    payload = {
        "text": text,
        "model_id": _setting(
            "ELEVENLABS_MODEL_ID",
            "eleven_multilingual_v2",
        ),
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.85,
            "style": 0.2,
            "use_speaker_boost": True,
        },
    }

    try:
        response = requests.post(
            endpoint,
            params={"output_format": ELEVENLABS_OUTPUT_FORMAT},
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "audio/pcm",
            },
            json=payload,
            timeout=30,
        )
        if response.status_code != 200:
            detail = response.text[:300].replace("\n", " ")
            print(
                f"[ElevenLabs voice error: HTTP {response.status_code}. "
                f"{detail or 'Check ELEVENLABS_API_KEY and account quota.'}]"
            )
            return False
        if _stop_requested.is_set():
            return False

        audio = np.frombuffer(response.content, dtype=np.int16)
        if audio.size == 0:
            print("[ElevenLabs voice error: received empty audio.]")
            return False
        return _play_pcm_audio(audio, ELEVENLABS_SAMPLE_RATE)
    except requests.RequestException as exc:
        print(f"[ElevenLabs voice error: {exc}]")
        return False
    except (OSError, ValueError) as exc:
        print(f"[ElevenLabs playback error: {exc}]")
        return False


def _speak_with_powershell(text: str) -> bool:
    """Use Windows' built-in SAPI voice and play its WAV through the default device."""
    if os.name != "nt":
        return False

    file_descriptor, audio_path = tempfile.mkstemp(
        prefix="trojan_voice_",
        suffix=".wav",
    )
    os.close(file_descriptor)
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$synth.Volume = 100; "
        "$synth.Rate = 0; "
        "$requested = $env:TROJAN_VOICE_ID; "
        "$voice = $synth.GetInstalledVoices() | Where-Object { "
        "($requested -and ($_.VoiceInfo.Id -like ('*' + $requested + '*') -or "
        "$_.VoiceInfo.Name -like ('*' + $requested + '*'))) -or "
        "$_.VoiceInfo.Culture.Name -in @('en-US', 'en-GB') -or "
        "$_.VoiceInfo.Name -match 'English' } | Select-Object -First 1; "
        "if ($voice) { $synth.SelectVoice($voice.VoiceInfo.Name) }; "
        "$synth.SetOutputToWaveFile($env:TROJAN_SPEECH_FILE); "
        "$synth.Speak($env:TROJAN_SPEECH_TEXT); "
        "$synth.SetOutputToDefaultAudioDevice(); "
        "$synth.Dispose()"
    )
    environment = os.environ.copy()
    environment["TROJAN_SPEECH_TEXT"] = text
    environment["TROJAN_SPEECH_FILE"] = audio_path
    environment["TROJAN_VOICE_ID"] = _setting("TROJAN_VOICE_ID")

    try:
        global _active_process
        _active_process = subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        if _stop_requested.is_set():
            _active_process.terminate()
        started_at = time.monotonic()
        while _active_process.poll() is None:
            if time.monotonic() - started_at > 30:
                _active_process.terminate()
                raise TimeoutError("speech synthesis timed out")
            if _stop_requested.is_set():
                _active_process.terminate()
            _skip_key_pressed()
            time.sleep(0.05)
        result = _active_process
        _active_process = None
    except (OSError, TimeoutError) as exc:
        print(f"[Windows voice fallback error: {exc}]")
        try:
            os.remove(audio_path)
        except OSError:
            pass
        return False
    try:
        if _stop_requested.is_set():
            return False
        if result.returncode != 0:
            print("[Windows voice fallback error: PowerShell speech command failed.]")
            return False
        if sd is None or read_wav is None:
            print("[Windows voice fallback error: audio playback packages are unavailable.]")
            return False

        sample_rate, audio = read_wav(audio_path)
        if len(audio) == 0:
            print("[Windows voice fallback error: SAPI produced an empty WAV.]")
            return False
        sd.play(audio, sample_rate)
        while True:
            if _skip_key_pressed() or _stop_requested.is_set():
                sd.stop()
                return False
            if not sd.get_stream().active:
                return True
            time.sleep(0.05)
    except Exception as exc:
        print(f"[Windows voice playback error: {exc}]")
        return False
    finally:
        _active_process = None
        try:
            os.remove(audio_path)
        except OSError:
            pass


def speak(text: str) -> bool:
    """Speak non-empty text once, returning whether speech was attempted."""
    if not _is_enabled() or not isinstance(text, str):
        return False

    speech = _clean_text(text)
    if not speech:
        return False

    if not _speaking_lock.acquire(blocking=False):
        print("[Voice] Playback already active; ignoring duplicate request.")
        return False

    try:
        with _engine_lock:
            _stop_requested.clear()
            elevenlabs_configured = bool(_setting("ELEVENLABS_API_KEY"))
            if elevenlabs_configured and _speak_with_elevenlabs(speech):
                return True
            if elevenlabs_configured:
                print("[Voice] ElevenLabs failed; trying Windows/local voice fallback.")
            if _speak_with_powershell(speech):
                return True
            if _stop_requested.is_set():
                return False

            engine = _get_engine()
            if engine is not None:
                try:
                    engine.say(speech)
                    engine.runAndWait()
                    return not _stop_requested.is_set()
                except Exception as exc:
                    print(f"[Voice error: {exc}]")
                    _reset_engine()

            return False
    finally:
        _speaking_lock.release()
