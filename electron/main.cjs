/* Electron main process: frameless window + Python backend sidecar.
 *
 * Dev:     vite on http://localhost:5173, backend from `python -m backend.app`.
 * Packaged: backend from the PyInstaller bundle in resources/backend/,
 *           frontend from frontend/dist/. No browser, no localhost tabs.
 *
 * The renderer reaches the backend over HTTP (see frontend/src/api.js; the
 * port arrives via --backend-port, exposed synchronously by preload.cjs) and
 * reaches Electron-only features (folder dialog, window controls) through
 * window.electron.
 */

const { app, BrowserWindow, dialog, ipcMain } = require('electron');
const { spawn } = require('node:child_process');
const path = require('node:path');
const net = require('node:net');
const fs = require('node:fs');

const isDev = !app.isPackaged;

// Single instance, like any real desktop app: a second launch just
// focuses the existing window instead of spawning a second backend.
if (!app.requestSingleInstanceLock()) app.quit();

let backendProc = null;
let backendPort = Number(process.env.PASCAL_PORT || 8000);
let mainWindow = null;

function backendBin() {
  if (process.env.BACKEND_BIN) return process.env.BACKEND_BIN;
  if (!app.isPackaged) return null; // dev: use `python -m backend.app`
  const exe = process.platform === 'win32' ? 'pascal-backend.exe' : 'pascal-backend';
  const bundled = path.join(process.resourcesPath, 'backend', exe);
  if (fs.existsSync(bundled)) return bundled;
  // Fallback for unpacked/portable layouts.
  const sibling = path.join(path.dirname(app.getPath('exe')), 'backend', exe);
  if (fs.existsSync(sibling)) return sibling;
  return null;
}

function findFreePort(start) {
  return new Promise((resolve) => {
    const tryPort = (port) => {
      const srv = net.createServer();
      srv.once('error', () => tryPort(port + 1));
      srv.once('listening', () => srv.close(() => resolve(port)));
      srv.listen(port, '127.0.0.1');
    };
    tryPort(start);
  });
}

function backendHealth(port) {
  return fetch(`http://127.0.0.1:${port}/api/health`)
    .then((r) => r.ok)
    .catch(() => false);
}

async function waitForBackend(port, timeoutMs = 45000) {
  const start = Date.now();
  for (;;) {
    if (await backendHealth(port)) return true;
    if (Date.now() - start > timeoutMs) return false;
    await new Promise((r) => setTimeout(r, 300));
  }
}

function startBackend(port) {
  const projectRoot = path.join(__dirname, '..');
  const env = { ...process.env, PASCAL_PORT: String(port) };
  const bin = backendBin();
  if (bin) {
    console.log(`starting backend: ${bin}`);
    backendProc = spawn(bin, [], { env, stdio: 'ignore' });
  } else {
    const py = process.platform === 'win32' ? 'python' : 'python3';
    console.log(`starting backend: ${py} -m backend.app`);
    backendProc = spawn(py, ['-m', 'backend.app'], { cwd: projectRoot, env, stdio: 'inherit' });
  }
  backendProc.on('exit', (code) => console.log(`backend exited with code ${code}`));
  backendProc.on('error', (err) => console.error('backend failed to start:', err));
}

function createWindow(port) {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    frame: false, // custom title bar in React (TopBar.jsx)
    backgroundColor: '#ffffff',
    show: false, // show when ready, no white flash
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      // Sync channel for the backend port; preload parses this. Keeps the
      // file:// renderer working with zero race (no executeJavaScript timing).
      additionalArguments: [`--backend-port=${port}`],
    },
  });

  // Legacy hook: some renderer code still reads window.__BACKEND_PORT.
  mainWindow.webContents.on('did-finish-load', () => {
    mainWindow.webContents
      .executeJavaScript(`window.__BACKEND_PORT = ${port};`)
      .catch(() => {});
  });
  mainWindow.once('ready-to-show', () => mainWindow.show());

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'frontend', 'dist', 'index.html'));
  }

  mainWindow.on('maximize', () => mainWindow.webContents.send('window:maximized', true));
  mainWindow.on('unmaximize', () => mainWindow.webContents.send('window:maximized', false));
}

ipcMain.handle('window:minimize', () => mainWindow?.minimize());
ipcMain.handle('window:toggle-maximize', () => {
  if (!mainWindow) return false;
  if (mainWindow.isMaximized()) {
    mainWindow.unmaximize();
    return false;
  }
  mainWindow.maximize();
  return true;
});
ipcMain.handle('window:close', () => mainWindow?.close());
ipcMain.handle('backend:port', () => backendPort);
ipcMain.handle('dialog:open-folder', async () => {
  const res = await dialog.showOpenDialog(mainWindow, { properties: ['openDirectory'] });
  if (res.canceled || res.filePaths.length === 0) return null;
  return res.filePaths[0];
});

app.on('second-instance', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  }
});

app.whenReady().then(async () => {
  backendPort = await findFreePort(backendPort);
  const alreadyUp = await backendHealth(backendPort);
  if (!alreadyUp) {
    startBackend(backendPort);
    const ok = await waitForBackend(backendPort);
    if (!ok) console.error('backend did not become healthy in time');
  } else {
    console.log(`reusing backend on port ${backendPort}`);
  }
  process.env.PASCAL_PORT = String(backendPort);
  createWindow(backendPort);

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow(backendPort);
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  if (backendProc) backendProc.kill();
});
