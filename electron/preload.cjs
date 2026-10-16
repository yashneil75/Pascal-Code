// Preload bridge: safe Electron APIs exposed to the React renderer as
// window.electron. The renderer never gets full node access.
const { contextBridge, ipcRenderer } = require('electron');

// Passed by main.cjs via webPreferences.additionalArguments. Synchronous, so
// the file:// renderer knows the backend port before its first fetch.
function backendPortFromArgv() {
  const arg = (process.argv || []).find((a) => a.startsWith('--backend-port='));
  const port = arg ? Number(arg.split('=')[1]) : NaN;
  return Number.isFinite(port) && port > 0 ? port : null;
}

const backendPort = backendPortFromArgv();

contextBridge.exposeInMainWorld('electron', {
  backendPort,
  getBackendPort: () => ipcRenderer.invoke('backend:port'),
  minimize: () => ipcRenderer.invoke('window:minimize'),
  toggleMaximize: () => ipcRenderer.invoke('window:toggle-maximize'),
  snap: (zone) => ipcRenderer.invoke('window:snap', zone),
  close: () => ipcRenderer.invoke('window:close'),
  openFolder: () => ipcRenderer.invoke('dialog:open-folder'),
  onMaximized: (cb) => {
    const listener = (_event, value) => cb(value);
    ipcRenderer.on('window:maximized', listener);
    return () => ipcRenderer.removeListener('window:maximized', listener);
  },
});
