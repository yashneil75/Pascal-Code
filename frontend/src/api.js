// Backend access.
// Packaged app (file://): Electron passes --backend-port, exposed synchronously
// by preload.cjs as window.electron.backendPort. No localhost tabs involved.
// Dev (Vite): same-origin /api, proxied to Python. Browser fallback: build-time
// VITE_BACKEND_URL.
function baseUrl() {
  if (typeof window !== 'undefined') {
    const port = window.electron?.backendPort || window.__BACKEND_PORT;
    if (port) return `http://127.0.0.1:${port}`;
  }
  return (import.meta.env.VITE_BACKEND_URL || '').replace(/\/$/, '');
}

const url = (path) => `${baseUrl()}${path}`;

async function req(path, options = {}) {
  const res = await fetch(url(path), {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => '');
    throw new Error(`${options.method || 'GET'} ${path} failed (${res.status}): ${detail}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  health: () => req('/api/health'),
  models: () => req('/api/models'),
  selectModel: (name) =>
    req('/api/models/select', { method: 'POST', body: JSON.stringify({ name }) }),
  projects: () => req('/api/projects'),
  openProject: (path) =>
    req('/api/projects/open', { method: 'POST', body: JSON.stringify({ path }) }),
  deleteProject: (path) =>
    req('/api/projects/delete', { method: 'POST', body: JSON.stringify({ path }) }),
  history: () => req('/api/history'),
  conversations: () => req('/api/conversations'),
  newChat: () => req('/api/conversations/new', { method: 'POST' }),
  openChat: (id) => req(`/api/conversations/${id}/open`, { method: 'POST' }),
  deleteChat: (id) => req(`/api/conversations/${id}`, { method: 'DELETE' }),
  settings: () => req('/api/settings'),
  setSetting: (key, value) =>
    req(`/api/settings/${key}`, { method: 'PUT', body: JSON.stringify({ value }) }),
  chat: (content) =>
    req('/api/chat', { method: 'POST', body: JSON.stringify({ content }) }),
};

/**
 * POST to /api/chat/stream and invoke onToken for each SSE token.
 * Returns the full assembled reply. Abort via AbortController signal.
 */
export async function streamChat(content, { onToken, signal } = {}) {
  const res = await fetch(url('/api/chat/stream'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ content }),
    signal,
  });
  if (!res.ok) throw new Error(`stream failed (${res.status})`);
  if (!res.body) throw new Error('streaming not supported in this browser');

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  let full = '';

  const handleLine = (line) => {
    const text = line.trim();
    if (!text.startsWith('data:')) return false;
    const payload = text.slice(5).trim();
    if (payload === '[DONE]') return true;
    try {
      const data = JSON.parse(payload);
      if (data.token) {
        full += data.token;
        onToken?.(data.token, full);
      } else if (data.error) {
        throw new Error(data.error);
      }
    } catch (err) {
      if (err.message && !err.message.startsWith('{')) throw err;
      // ignore malformed keep-alive lines
    }
    return false;
  };

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, idx);
      buf = buf.slice(idx + 1);
      if (handleLine(line)) return full;
    }
  }
  // trailing fragment
  if (buf.trim() && handleLine(buf)) return full;
  return full;
}

// Electron bridge (preload.cjs). In a plain browser these are no-ops except
// openFolder, which falls back to a manual prompt.
export const desktop = {
  isElectron: !!window.electron,
  minimize: () => window.electron?.minimize(),
  toggleMaximize: () => window.electron?.toggleMaximize(),
  close: () => window.electron?.close(),
  onMaximized: (cb) => window.electron?.onMaximized(cb),
  openFolder: async () => {
    if (window.electron?.openFolder) return window.electron.openFolder();
    const path = window.prompt('Project folder path:');
    return path || null;
  },
};
