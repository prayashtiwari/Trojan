import { memo, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { motion, useReducedMotion } from "framer-motion";

type Message = { role: "user" | "assistant"; content: string };
type View = "command" | "history" | "voice" | "provider" | "settings";
type CoreState = "idle" | "listening" | "transcribing" | "thinking" | "executing" | "speaking" | "error";

const nav: Array<[View, string, string]> = [
  ["command", "Command Center", "◈"], ["history", "History", "◷"], ["voice", "Voice", "◉"],
  ["provider", "Provider", "◇"], ["settings", "Settings", "⚙"],
];

const stateCopy: Record<CoreState, { label: string; detail: string }> = {
  idle: { label: "READY", detail: "Awaiting your instruction" },
  listening: { label: "LISTENING", detail: "Microphone capture is active" },
  transcribing: { label: "TRANSCRIBING", detail: "Converting captured speech to text" },
  thinking: { label: "THINKING", detail: "The local bridge is processing your request" },
  executing: { label: "EXECUTING", detail: "A verified Trojan tool is running" },
  speaking: { label: "SPEAKING", detail: "Voice playback is active" },
  error: { label: "ATTENTION", detail: "The last operation could not be completed" },
};

function useMicrophoneLevel(active: boolean) {
  const [available, setAvailable] = useState(false);
  const stageRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!active || !navigator.mediaDevices?.getUserMedia) {
      stageRef.current?.style.setProperty("--mic-level", "0");
      setAvailable(false);
      return;
    }
    let frame = 0;
    let stream: MediaStream | undefined;
    let context: AudioContext | undefined;
    let analyser: AnalyserNode | undefined;
    let data: Uint8Array<ArrayBuffer> | undefined;
    let cancelled = false;
    navigator.mediaDevices.getUserMedia({ audio: true }).then((nextStream) => {
      if (cancelled) { nextStream.getTracks().forEach((track) => track.stop()); return; }
      stream = nextStream;
      context = new AudioContext();
      analyser = context.createAnalyser();
      analyser.fftSize = 256;
      data = new Uint8Array(new ArrayBuffer(analyser.fftSize));
      context.createMediaStreamSource(stream).connect(analyser);
      setAvailable(true);
      const sample = () => {
        if (!analyser || !data) return;
        analyser.getByteTimeDomainData(data);
        let sum = 0;
        for (const value of data) { const normalized = (value - 128) / 128; sum += normalized * normalized; }
        const level = Math.min(1, Math.sqrt(sum / data.length) * 3.2);
        stageRef.current?.style.setProperty("--mic-level", String(level));
        frame = requestAnimationFrame(sample);
      };
      sample();
    }).catch(() => setAvailable(false));
    return () => {
      cancelled = true;
      cancelAnimationFrame(frame);
      stream?.getTracks().forEach((track) => track.stop());
      void context?.close();
      stageRef.current?.style.setProperty("--mic-level", "0");
    };
  }, [active]);
  return { stageRef, available };
}

const AICore = memo(function AICore({ state, tool, progress }: { state: CoreState; tool: string | null; progress: number }) {
  const reducedMotion = useReducedMotion();
  const listening = state === "listening";
  const { stageRef, available } = useMicrophoneLevel(listening);
  const active = state !== "idle" && state !== "error";
  const rings = [0, 1, 2];
  return (
    <div ref={stageRef} className={`core-stage state-${state}`} aria-label={`Assistant state: ${stateCopy[state].label}`}>
      <motion.div
        className="core-aura"
        animate={reducedMotion ? undefined : { opacity: active ? [0.25, 0.52, 0.25] : [0.18, 0.28, 0.18], scale: active ? [0.96, 1.04, 0.96] : [0.98, 1, 0.98] }}
        transition={{ duration: active ? 2.4 : 5, repeat: Infinity, ease: "easeInOut" }}
      />
      {rings.map((ring) => (
        <motion.div
          className={`mechanical-ring ring-${ring}`}
          key={ring}
          animate={reducedMotion || (state === "idle" && ring !== 0) ? undefined : { rotate: ring % 2 ? -360 : 360 }}
          transition={{ duration: 22 + ring * 9, repeat: Infinity, ease: "linear" }}
        />
      ))}
      {listening && <div className="waveform" aria-label={available ? "Live microphone amplitude" : "Microphone state animation"}>
        {Array.from({ length: 18 }, (_, index) => <i key={index} style={{ "--bar": (index % 5) / 5 } as CSSProperties} />)}
      </div>}
      <div className="core-emblem">
        <img src="./trojan-horse.png" alt="Trojan horse emblem" />
        <span className="core-scan" />
      </div>
      <div className="core-ticks" aria-hidden="true">{Array.from({ length: 18 }, (_, index) => <i key={index} />)}</div>
      {state === "executing" && <div className="execution-readout"><b>{progress || 50}%</b><span>{tool || "TOOL RUNNING"}</span></div>}
    </div>
  );
});

export default function App() {
  const [view, setView] = useState<View>("command");
  const [messages, setMessages] = useState<Message[]>([]);
  const [prompt, setPrompt] = useState("");
  const [state, setState] = useState<CoreState>("idle");
  const [activityTool, setActivityTool] = useState<string | null>(null);
  const [activityProgress, setActivityProgress] = useState(0);
  const [error, setError] = useState("");
  const [settings, setSettings] = useState<Record<string, unknown>>({});
  const [openAtLogin, setOpenAtLogin] = useState(false);
  const [minimizeToTray, setMinimizeToTray] = useState(false);
  const [backendOnline, setBackendOnline] = useState(false);
  const [memories, setMemories] = useState<Array<{ id: string; content: string; category: string }>>([]);
  const [memoryDraft, setMemoryDraft] = useState("");
  const [projects, setProjects] = useState<Array<{ id: string; name: string; content: string; created_at: string; updated_at: string }>>([]);
  const [projectName, setProjectName] = useState("");
  const [projectDraft, setProjectDraft] = useState("");
  const promptRef = useRef<HTMLInputElement>(null);
  const stateRef = useRef(state);
  stateRef.current = state;
  const status = stateCopy[state];

  useEffect(() => {
    Promise.all([window.trojan.getSettings(), window.trojan.getLoginItemSettings(), window.trojan.backendStatus(), window.trojan.getDesktopPreferences(), window.trojan.getConversation()])
      .then(([settingsResult, loginResult, backendResult, desktopResult, conversationResult]) => {
        setSettings(settingsResult.settings || {});
        setOpenAtLogin(loginResult.openAtLogin);
        setBackendOnline(backendResult.running);
        setMinimizeToTray(desktopResult.minimizeToTray);
        setMessages((conversationResult.conversation || []).filter((item) => item.role === "user" || item.role === "assistant") as Message[]);
      })
      .catch(() => setBackendOnline(false));
  }, []);

  useEffect(() => {
    const removeCrashListener = window.trojan.onBackendCrashed((message) => {
      setBackendOnline(false);
      setError(message || "The local backend stopped unexpectedly.");
      setState("error");
    });
    const shortcut = (event: KeyboardEvent) => {
      if (event.ctrlKey && event.key.toLowerCase() === "l") {
        event.preventDefault();
        promptRef.current?.focus();
      } else if (event.ctrlKey && event.key.toLowerCase() === "m") {
        event.preventDefault();
        void listen();
      } else if (event.key === "Escape" && (stateRef.current === "thinking" || stateRef.current === "speaking" || stateRef.current === "listening")) {
        event.preventDefault();
        if (stateRef.current === "thinking") void cancelChat();
        else void stopVoice();
      }
    };
    window.addEventListener("keydown", shortcut);
    return () => {
      removeCrashListener();
      window.removeEventListener("keydown", shortcut);
    };
  }, []);

  useEffect(() => {
    const poll = window.setInterval(() => {
      window.trojan.backendStatus().then((result) => {
        setBackendOnline((current) => current === result.running ? current : result.running);
        if (!result.running && result.error && state !== "error") {
          setError(result.error);
          setState("error");
        }
      }).catch(() => setBackendOnline(false));
    }, 3000);
    return () => window.clearInterval(poll);
  }, []);

  useEffect(() => {
    if (!backendOnline) return;
    let stopped = false;
    let timer = 0;
    const poll = () => {
      window.trojan.activityStatus().then((result) => {
        if (stopped) return;
        if (result.state && ["idle", "thinking", "executing", "speaking"].includes(result.state)) {
          setState((current) => current === "listening" || current === "transcribing" || current === "error" ? current : result.state as CoreState);
          setActivityTool((current) => current === (result.tool || null) ? current : result.tool || null);
          setActivityProgress((current) => current === (result.progress || 0) ? current : result.progress || 0);
        }
        timer = window.setTimeout(poll, result.state === "idle" ? 3000 : 250);
      }).catch(() => {
        if (!stopped) timer = window.setTimeout(poll, 3000);
      });
    };
    poll();
    return () => { stopped = true; window.clearTimeout(timer); };
  }, [backendOnline]);

  useEffect(() => {
    if (view === "settings") Promise.all([window.trojan.getMemories(), window.trojan.getProjects()])
      .then(([memoryResult, projectResult]) => {
        setMemories(memoryResult.memories || []);
        setProjects(projectResult.projects || []);
      });
  }, [view]);

  async function send(text = prompt, fromVoice = false) {
    const clean = text.trim();
    if (!clean || ["thinking", "listening", "executing", "speaking"].includes(state) || (state === "transcribing" && !fromVoice)) return;
    setPrompt(""); setError(""); setState("thinking");
    setMessages((current) => [...current, { role: "user", content: clean }]);
    try {
      const result = await window.trojan.chat(clean);
      if (result.ok && result.answer) {
        setMessages((current) => [...current, { role: "assistant", content: result.answer! }]);
        setState("idle");
      } else {
        setError(result.error || "The backend did not respond.");
        setState("error");
      }
    } catch {
      setError("The local bridge is unavailable.");
      setState("error");
    }
  }

  async function listen() {
    if (state === "listening" || state === "transcribing" || state === "thinking") return;
    setError(""); setState("listening");
    try {
      const result = await window.trojan.listen();
      if (result.ok && result.transcript) {
        setState("transcribing");
        setPrompt(result.transcript);
        await send(result.transcript, true);
      } else {
        setError(result.error || "No speech was recognized.");
        setState("idle");
      }
    } catch {
      setError("The microphone service is unavailable.");
      setState("error");
    }
  }

  async function speak(text: string) {
    if (!text.trim()) return;
    setError(""); setState("speaking");
    try {
      const result = await window.trojan.speak(text);
      if (!result.ok || !result.spoken) { setError(result.error || "Voice playback could not start."); setState("error"); return; }
      setState("idle");
    } catch {
      setError("The voice service is unavailable.");
      setState("error");
    }

  }

  async function stopVoice() {
    await window.trojan.stopSpeaking();
    setState("idle");
    setActivityTool(null);
    setActivityProgress(0);
  }

  async function cancelChat() {
    await window.trojan.cancelChat();
    setState("idle");
    setActivityTool(null);
    setActivityProgress(0);
  }

  async function saveSettings() {
    const result = await window.trojan.saveSettings(settings);
    if (!result.ok) { setError(result.error || "Could not save settings."); setState("error"); }
  }

  const title = useMemo(() => nav.find(([key]) => key === view)?.[1] || "Command Center", [view]);
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><img src="./trojan-horse.png" alt="Trojan horse emblem" /></div><div><strong>TROJAN</strong><span>AI COMMAND</span></div></div>
      <div className={`system-pill ${backendOnline ? "online" : "offline"}`}><span className="dot" /> BRIDGE {backendOnline ? "ONLINE" : "CONNECTING"}</div>
      <nav>{nav.map(([key, label, icon]) => <button className={view === key ? "active" : ""} onClick={() => setView(key)} key={key}><span>{icon}</span>{label}</button>)}</nav>
      <div className="sidebar-footer">SECURE LOCAL BRIDGE<br /><small>OpenRouter stays in Python</small></div>
    </aside>
    <main className="main">
      <header><div><p className="eyebrow">TROJAN AI / {view.toUpperCase()}</p><h1>{title}</h1></div><div className="header-status"><span className="status-led" /> {backendOnline ? "LOCAL BACKEND" : "BRIDGE STARTING"} <b>127.0.0.1</b></div></header>
      {view === "command" && <section className="command-grid">
        <div className="core-panel">
          <AICore state={state} tool={activityTool} progress={activityProgress} />
          <p className="core-state">{status.label}</p><p className="core-detail">{status.detail}</p>
          <button className="mic-button" onClick={state === "listening" ? stopVoice : listen} disabled={["thinking", "transcribing", "executing", "speaking"].includes(state)}>{state === "listening" ? "Stop listening" : "Activate microphone"}</button>
          <div className="state-legend"><span><i className="legend-dot" /> {state === "listening" && activityTool === null ? "Live input when permission is granted" : "State-linked motion"}</span><span>{state === "executing" ? `${activityProgress || 50}% complete` : "Local bridge telemetry"}</span></div>
        </div>
        <div className="chat-panel"><div className="messages">{messages.length === 0 && <div className="empty"><span>Τ</span><p>Good evening, sir.<br />Your command center is ready.</p></div>}{messages.map((message, index) => <div className={`message ${message.role}`} key={index}><span>{message.role === "user" ? "YOU" : "TROJAN"}</span><p>{message.content}</p></div>)}</div>{error && <div className="error">{error}</div>}<form onSubmit={(event) => { event.preventDefault(); send(); }}><input ref={promptRef} value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Speak or type a command..." disabled={state === "thinking"} /><button type={state === "thinking" ? "button" : "submit"} onClick={state === "thinking" ? cancelChat : undefined}>{state === "thinking" ? "CANCEL" : "SEND ↗"}</button></form></div>
      </section>}
      {view === "history" && <section className="card"><h2>Conversation history</h2><button className="gold-button" onClick={async () => { const result = await window.trojan.clearConversation(); if (result.ok) setMessages([]); else setError(result.error || "Could not clear conversation."); }}>Clear conversation</button>{messages.length ? messages.map((message, i) => <div className="history-row" key={i}><b>{message.role}</b><span>{message.content}</span></div>) : <p className="muted">Current conversation context is empty.</p>}<p className="muted">Conversation history is bounded and separate from approved preferences and projects.</p></section>}
      {view === "voice" && <section className="card"><h2>Voice controls</h2><p className="muted">Listening and transcription states use the existing Python microphone endpoint. The core only shows live amplitude when the renderer receives microphone permission; otherwise it remains explicitly state-driven.</p><button className="gold-button" onClick={() => speak(messages.filter((message) => message.role === "assistant").at(-1)?.content || "Trojan is ready.")}>Speak latest response</button><button className="gold-button" onClick={() => window.trojan.stopSpeaking()}>Stop speaking</button></section>}
      {view === "provider" && <section className="card"><h2>AI provider</h2><label>Model<input value={String(settings.model || "meta-llama/llama-3.3-70b-instruct")} onChange={(e) => setSettings({...settings, model: e.target.value})} /></label><p className="muted">API credentials are never sent to the renderer or bundled into the frontend.</p><button className="gold-button" onClick={saveSettings}>Save provider settings</button></section>}
      {view === "settings" && <section className="card"><h2>Application settings</h2><label>Voice enabled<select value={String(settings.voiceEnabled ?? "true")} onChange={(e) => setSettings({...settings, voiceEnabled: e.target.value === "true"})}><option value="true">Enabled</option><option value="false">Disabled</option></select></label><label>Launch at Windows startup<select value={String(openAtLogin)} onChange={async (e) => { const result = await window.trojan.setOpenAtLogin(e.target.value === "true"); setOpenAtLogin(result.openAtLogin); }}><option value="false">Disabled</option><option value="true">Enabled</option></select></label><label>Close to system tray<select value={String(minimizeToTray)} onChange={async (e) => { const result = await window.trojan.setMinimizeToTray(e.target.value === "true"); setMinimizeToTray(result.minimizeToTray); }}><option value="false">Close the app</option><option value="true">Keep Trojan in tray</option></select></label><p className="muted">Keyboard: Ctrl+L focuses chat, Ctrl+M activates the microphone, Escape cancels active work.</p><button className="gold-button" onClick={saveSettings}>Save settings</button><h2>Approved preferences</h2><p className="muted">Only information you explicitly save is retained. Credential-like content is rejected.</p><form onSubmit={async (event) => { event.preventDefault(); if (!memoryDraft.trim()) return; const result = await window.trojan.addMemory(memoryDraft, "preference"); if (result.ok && result.memory) { setMemories((current) => [...current, result.memory!]); setMemoryDraft(""); } else setError(result.error || "Could not save preference."); }}><input value={memoryDraft} onChange={(event) => setMemoryDraft(event.target.value)} placeholder="I prefer concise answers" /><button className="gold-button" type="submit">Save preference</button></form>{memories.map((memory) => <div className="history-row" key={memory.id}><span>{memory.content}</span><button onClick={async () => { const result = await window.trojan.deleteMemory(memory.id); if (result.ok) setMemories((current) => current.filter((item) => item.id !== memory.id)); }}>Forget</button></div>)}<button className="gold-button" onClick={async () => { const result = await window.trojan.clearMemories("preference"); if (result.ok) setMemories([]); }}>Forget all preferences</button><h2>Saved projects</h2><p className="muted">Store project context separately from preferences and conversation history.</p><form onSubmit={async (event) => { event.preventDefault(); if (!projectName.trim() || !projectDraft.trim()) return; const result = await window.trojan.saveProject(projectName, projectDraft); if (result.ok && result.project) { setProjects((current) => [...current.filter((item) => item.id !== result.project!.id), result.project!]); setProjectName(""); setProjectDraft(""); } else setError(result.error || "Could not save project."); }}><input value={projectName} onChange={(event) => setProjectName(event.target.value)} placeholder="Project name" /><input value={projectDraft} onChange={(event) => setProjectDraft(event.target.value)} placeholder="Approved project details" /><button className="gold-button" type="submit">Save project</button></form>{projects.map((project) => <div className="history-row" key={project.id}><span><b>{project.name}</b> {project.content}</span><button onClick={async () => { const result = await window.trojan.deleteProject(project.id); if (result.ok) setProjects((current) => current.filter((item) => item.id !== project.id)); }}>Forget</button></div>)}</section>}
    </main>
  </div>;
}
