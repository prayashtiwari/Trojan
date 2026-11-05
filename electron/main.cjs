const { app, BrowserWindow, Tray, Menu, ipcMain, nativeImage, screen } = require("electron");
const { spawn } = require("child_process");
const crypto = require("crypto");
const path = require("path");
const http = require("http");
const fs = require("fs");

let backend;
let backendPort;
let backendStartupError;
let backendReady;
let backendStarting = false;
let mainWindow;
let tray;
let isQuitting = false;
let preferences = { minimizeToTray: false, openAtLogin: false, bounds: null, maximized: false };
const token = crypto.randomBytes(32).toString("hex");
const preferencesPath = path.join(app.getPath("userData"), "desktop-preferences.json");
const allowedBackendPaths = new Set([
  "/chat", "/chat/cancel", "/voice/listen", "/voice/speak", "/voice/stop",
  "/status", "/settings", "/conversation", "/history", "/conversation/clear",
  "/memories", "/memories/clear", "/memories/delete", "/projects", "/projects/delete",
]);

function appIconPath() {
  return app.isPackaged
    ? path.join(process.resourcesPath, "trojan-icon.ico")
    : path.join(__dirname, "..", "build", "icon.ico");
}

function loadPreferences() {
  try {
    const saved = JSON.parse(fs.readFileSync(preferencesPath, "utf8"));
    if (saved && typeof saved === "object") preferences = { ...preferences, ...saved };
  } catch (error) {
    if (error.code !== "ENOENT") console.error("[Trojan preferences]", error);
  }
}

function savePreferences() {
  fs.mkdirSync(path.dirname(preferencesPath), { recursive: true });
  fs.writeFileSync(preferencesPath, JSON.stringify(preferences, null, 2), "utf8");
}

function backendCommand() {
  const packagedPython = path.join(process.resourcesPath, "python-runtime", "Scripts", "python.exe");
  if (app.isPackaged) return [packagedPython, [path.join(process.resourcesPath, "backend_server.py")]];
  return [process.env.TROJAN_PYTHON || "python", [path.join(__dirname, "..", "backend_server.py")]];
}

function startBackend() {
  backendStarting = true;
  backendReady = new Promise((resolve, reject) => {
    const [command, args] = backendCommand();
    backend = spawn(command, [...args, "--token", token, "--port", "0"], {
      cwd: app.isPackaged ? process.resourcesPath : path.join(__dirname, ".."),
      windowsHide: true,
      env: { ...process.env, PYTHONUNBUFFERED: "1" },
    });
    let output = "";
    backend.stdout.on("data", (chunk) => {
      output += chunk.toString();
      if (output.length > 16_384) output = output.slice(-16_384);
      const line = output.split(/\r?\n/).find((item) => item.includes('"ready": true'));
      if (line && !backendPort) {
        try {
          backendPort = JSON.parse(line).port;
          backendStarting = false;
          resolve();
        } catch (error) {
          backendStartupError = error;
          backendStarting = false;
          reject(error);
        }
      }
    });
    backend.stderr.on("data", (chunk) => console.error(`[Trojan backend] ${chunk}`));
    backend.on("error", (error) => {
      backendStartupError = error;
      reject(error);
    });
    backend.on("exit", (code, signal) => {
      backendPort = undefined;
      backendStarting = false;
      if (!isQuitting) {
        backendStartupError = new Error(`Backend exited${code == null ? ` by ${signal}` : ` with code ${code}`}.`);
        if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send("backend:crashed", backendStartupError.message);
        reject(backendStartupError);
      }
    });
  });
  return backendReady;
}

function validatedRequest(request) {
  if (!request || typeof request !== "object") throw new TypeError("Invalid backend request.");
  if (!["GET", "POST"].includes(request.method) || typeof request.path !== "string") {
    throw new TypeError("Invalid backend method or path.");
  }
  if (!allowedBackendPaths.has(request.path)) throw new Error("Backend path is not allowed.");
  if (request.method === "POST" && request.body !== undefined && (!request.body || typeof request.body !== "object" || Array.isArray(request.body))) {
    throw new TypeError("Backend body must be an object.");
  }
  return request;
}

async function requestBackend(request) {
  const validated = validatedRequest(request);
  if (!backendPort) await backendReady;
  return new Promise((resolve, reject) => {
    const req = http.request({
      host: "127.0.0.1", port: backendPort, path: validated.path, method: validated.method,
      timeout: 30_000,
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    }, (response) => {
      let data = "";
      response.on("data", (chunk) => { data += chunk; });
      response.on("end", () => {
        let parsed;
        try { parsed = JSON.parse(data); } catch { parsed = { error: "Invalid backend response." }; }
        resolve({ ok: response.statusCode >= 200 && response.statusCode < 300, ...parsed });
      });
    });
    req.on("timeout", () => req.destroy(new Error("Backend request timed out.")));
    req.on("error", reject);
    req.end(validated.method === "GET" ? undefined : JSON.stringify(validated.body || {}));
  });
}

function splashMarkup() {
  return `<!doctype html><html><body style="margin:0;background:#08090b;color:#d8bd8a;font-family:Segoe UI,sans-serif;display:grid;place-items:center;height:100vh"><div style="text-align:center;letter-spacing:4px"><div style="font-size:28px">TROJAN</div><div style="font-size:10px;color:#82745f;margin-top:12px">ESTABLISHING LOCAL BRIDGE</div><div style="height:1px;width:180px;background:#6e512d;margin:24px auto;position:relative;overflow:hidden"><i style="display:block;height:100%;width:45%;background:#d0a365;animation:s 1.3s infinite"></i></div></div><style>@keyframes s{to{transform:translateX(400%)}}</style></body></html>`;
}

function createSplash() {
  const splash = new BrowserWindow({ width: 420, height: 260, frame: false, resizable: false, movable: false, center: true, show: true, backgroundColor: "#08090b", webPreferences: { sandbox: true } });
  splash.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(splashMarkup())}`);
  return splash;
}

function validBounds(bounds) {
  return bounds && Number.isFinite(bounds.x) && Number.isFinite(bounds.y)
    && Number.isFinite(bounds.width) && Number.isFinite(bounds.height)
    && bounds.width >= 1000 && bounds.height >= 700;
}

async function createWindow() {
  const display = screen.getPrimaryDisplay().workArea;
  const savedBounds = validBounds(preferences.bounds) ? preferences.bounds : {
    width: Math.min(1440, display.width), height: Math.min(900, display.height),
  };
  mainWindow = new BrowserWindow({
    ...savedBounds,
    minWidth: 1000,
    minHeight: 700,
    show: false,
    backgroundColor: "#08090b",
    icon: appIconPath(),
    webPreferences: { preload: path.join(__dirname, "preload.cjs"), contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  mainWindow.on("resize", persistBounds);
  mainWindow.on("move", persistBounds);
  mainWindow.on("maximize", () => { preferences.maximized = true; savePreferences(); });
  mainWindow.on("unmaximize", () => { preferences.maximized = false; savePreferences(); });
  mainWindow.on("close", (event) => {
    if (!isQuitting && preferences.minimizeToTray) {
      event.preventDefault();
      mainWindow.hide();
    }
  });
  mainWindow.webContents.on("did-fail-load", (_event, code, description) => {
    console.error(`[Trojan renderer] ${code}: ${description}`);
  });
  if (app.isPackaged || process.env.TROJAN_PRODUCTION === "1") await mainWindow.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  else await mainWindow.loadURL("http://localhost:5173");
  if (preferences.maximized) mainWindow.maximize();
  mainWindow.show();
  mainWindow.focus();
}

function persistBounds() {
  if (!mainWindow || mainWindow.isDestroyed() || mainWindow.isMinimized()) return;
  preferences.bounds = mainWindow.getBounds();
  savePreferences();
}

function createTray() {
  tray = new Tray(nativeImage.createFromPath(appIconPath()));
  tray.setToolTip("Trojan AI");
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: "Show Trojan", click: () => { mainWindow.show(); mainWindow.focus(); } },
    { label: "Start with Windows", type: "checkbox", checked: Boolean(preferences.openAtLogin), click: (item) => {
      preferences.openAtLogin = item.checked;
      app.setLoginItemSettings({ openAtLogin: item.checked });
      savePreferences();
    } },
    { type: "separator" },
    { label: "Exit Trojan", click: () => { isQuitting = true; app.quit(); } },
  ]));
  tray.on("double-click", () => { mainWindow.show(); mainWindow.focus(); });
}

ipcMain.handle("backend:request", (_event, request) => requestBackend(request));
ipcMain.handle("backend:status", () => ({ running: Boolean(backendPort), starting: backendStarting, error: backendStartupError?.message || null }));
ipcMain.handle("app:desktop-preferences", () => ({ ...preferences }));
ipcMain.handle("app:set-minimize-to-tray", (_event, enabled) => {
  if (typeof enabled !== "boolean") throw new TypeError("minimizeToTray must be boolean.");
  preferences.minimizeToTray = enabled;
  savePreferences();
  return { minimizeToTray: enabled };
});
ipcMain.handle("app:window-control", (_event, action) => {
  if (!mainWindow || mainWindow.isDestroyed()) return { ok: false };
  if (action === "minimize") mainWindow.minimize();
  else if (action === "maximize") mainWindow.maximize();
  else if (action === "restore") mainWindow.unmaximize();
  else if (action === "close") mainWindow.close();
  else throw new TypeError("Unknown window action.");
  return { ok: true, maximized: mainWindow.isMaximized() };
});
ipcMain.handle("app:login-item-settings", () => app.getLoginItemSettings());
ipcMain.handle("app:set-login-item-settings", (_event, openAtLogin) => {
  if (typeof openAtLogin !== "boolean") throw new TypeError("openAtLogin must be a boolean.");
  preferences.openAtLogin = openAtLogin;
  app.setLoginItemSettings({ openAtLogin });
  savePreferences();
  return app.getLoginItemSettings();
});

app.whenReady().then(async () => {
  app.setAppUserModelId("com.trojan.ai");
  loadPreferences();
  const splash = createSplash();
  startBackend().catch((error) => console.error("[Trojan backend startup]", error));
  try { await createWindow(); } catch (error) { console.error("[Trojan window startup]", error); app.quit(); return; }
  if (!backendPort) {
    await Promise.race([
      backendReady.catch(() => undefined),
      new Promise((resolve) => setTimeout(resolve, 8000)),
    ]);
  }
  if (!splash.isDestroyed()) splash.close();
  createTray();
}).catch((error) => { console.error(error); app.quit(); });

app.on("before-quit", () => {
  isQuitting = true;
  persistBounds();
  if (backend && !backend.killed) backend.kill();
});
app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });
