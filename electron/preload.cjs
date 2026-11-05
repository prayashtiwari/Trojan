const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("trojan", {
  chat: (prompt) => ipcRenderer.invoke("backend:request", { method: "POST", path: "/chat", body: { prompt } }),
  cancelChat: () => ipcRenderer.invoke("backend:request", { method: "POST", path: "/chat/cancel", body: {} }),
  listen: () => ipcRenderer.invoke("backend:request", { method: "POST", path: "/voice/listen", body: {} }),
  speak: (text) => ipcRenderer.invoke("backend:request", { method: "POST", path: "/voice/speak", body: { text } }),
  stopSpeaking: () => ipcRenderer.invoke("backend:request", { method: "POST", path: "/voice/stop", body: {} }),
  getSettings: () => ipcRenderer.invoke("backend:request", { method: "GET", path: "/settings" }),
  saveSettings: (settings) => ipcRenderer.invoke("backend:request", { method: "POST", path: "/settings", body: { settings } }),
  backendStatus: () => ipcRenderer.invoke("backend:status"),
  activityStatus: () => ipcRenderer.invoke("backend:request", { method: "GET", path: "/status" }),
  getLoginItemSettings: () => ipcRenderer.invoke("app:login-item-settings"),
  setOpenAtLogin: (enabled) => ipcRenderer.invoke("app:set-login-item-settings", enabled),
  getConversation: () => ipcRenderer.invoke("backend:request", { method: "GET", path: "/conversation" }),
  getHistory: () => ipcRenderer.invoke("backend:request", { method: "GET", path: "/history" }),
  clearConversation: () => ipcRenderer.invoke("backend:request", { method: "POST", path: "/conversation/clear", body: {} }),
  getMemories: () => ipcRenderer.invoke("backend:request", { method: "GET", path: "/memories" }),
  addMemory: (content, category) => ipcRenderer.invoke("backend:request", { method: "POST", path: "/memories", body: { content, category } }),
  deleteMemory: (id) => ipcRenderer.invoke("backend:request", { method: "POST", path: "/memories/delete", body: { id } }),
  clearMemories: (category) => ipcRenderer.invoke("backend:request", { method: "POST", path: "/memories/clear", body: category ? { category } : {} }),
  getProjects: () => ipcRenderer.invoke("backend:request", { method: "GET", path: "/projects" }),
  saveProject: (name, content) => ipcRenderer.invoke("backend:request", { method: "POST", path: "/projects", body: { name, content } }),
  deleteProject: (id) => ipcRenderer.invoke("backend:request", { method: "POST", path: "/projects/delete", body: { id } }),
  getDesktopPreferences: () => ipcRenderer.invoke("app:desktop-preferences"),
  setMinimizeToTray: (enabled) => ipcRenderer.invoke("app:set-minimize-to-tray", enabled),
  windowControl: (action) => ipcRenderer.invoke("app:window-control", action),
  onBackendCrashed: (callback) => {
    if (typeof callback !== "function") throw new TypeError("callback must be a function.");
    const listener = (_event, message) => callback(message);
    ipcRenderer.on("backend:crashed", listener);
    return () => ipcRenderer.removeListener("backend:crashed", listener);
  },
});
