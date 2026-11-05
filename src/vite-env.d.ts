interface Window {
  trojan: {
    chat(prompt: string): Promise<{ ok: boolean; answer?: string; error?: string }>;
    cancelChat(): Promise<{ ok: boolean; cancelled?: boolean; error?: string }>;
    listen(): Promise<{ ok: boolean; transcript?: string; error?: string }>;
    speak(text: string): Promise<{ ok: boolean; spoken?: boolean; error?: string }>;
    stopSpeaking(): Promise<{ ok: boolean; stopped?: boolean; error?: string }>;
    getSettings(): Promise<{ ok: boolean; settings?: Record<string, unknown>; error?: string }>;
    saveSettings(settings: Record<string, unknown>): Promise<{ ok: boolean; error?: string }>;
    backendStatus(): Promise<{ running: boolean; starting?: boolean; error?: string | null }>;
    activityStatus(): Promise<{ ok: boolean; state?: string; tool?: string | null; progress?: number; error?: string }>;
    getLoginItemSettings(): Promise<{ openAtLogin: boolean }>;
    setOpenAtLogin(enabled: boolean): Promise<{ openAtLogin: boolean }>;
    getConversation(): Promise<{ ok: boolean; conversation?: Array<{ role: string; content: string }>; error?: string }>;
    getHistory(): Promise<{ ok: boolean; history?: Array<{ id: string; role: string; content: string; created_at: string }>; error?: string }>;
    clearConversation(): Promise<{ ok: boolean; error?: string }>;
    getMemories(): Promise<{ ok: boolean; memories?: Array<{ id: string; content: string; category: string }>; error?: string }>;
    addMemory(content: string, category: string): Promise<{ ok: boolean; memory?: { id: string; content: string; category: string }; error?: string }>;
    deleteMemory(id: string): Promise<{ ok: boolean; deleted?: boolean; error?: string }>;
    clearMemories(category?: string): Promise<{ ok: boolean; error?: string }>;
    getProjects(): Promise<{ ok: boolean; projects?: Array<{ id: string; name: string; content: string; created_at: string; updated_at: string }>; error?: string }>;
    saveProject(name: string, content: string): Promise<{ ok: boolean; project?: { id: string; name: string; content: string; created_at: string; updated_at: string }; error?: string }>;
    deleteProject(id: string): Promise<{ ok: boolean; deleted?: boolean; error?: string }>;
    getDesktopPreferences(): Promise<{ minimizeToTray: boolean; openAtLogin: boolean }>;
    setMinimizeToTray(enabled: boolean): Promise<{ minimizeToTray: boolean }>;
    windowControl(action: "minimize" | "maximize" | "restore" | "close"): Promise<{ ok: boolean; maximized?: boolean }>;
    onBackendCrashed(callback: (message: string) => void): () => void;
  };
}
