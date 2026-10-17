import { useCallback, useEffect, useRef, useState } from 'react';
import Sidebar from './components/Sidebar.jsx';
import TopBar from './components/TopBar.jsx';
import ProjectMenu from './components/ProjectMenu.jsx';
import ModelMenu from './components/ModelMenu.jsx';
import ChatThread from './components/ChatThread.jsx';
import Composer from './components/Composer.jsx';
import ConfirmDialog from './components/ConfirmDialog.jsx';
import SettingsPopup from './components/SettingsPopup.jsx';
import { modelLabel } from './components/icons.jsx';
import { api, desktop, streamChat } from './api.js';

export default function App() {
  const [messages, setMessages] = useState([]);
  const [chats, setChats] = useState([]);
  const [currentChat, setCurrentChat] = useState(null);
  const [projects, setProjects] = useState([]);
  const [currentProject, setCurrentProject] = useState('');
  const [workspace, setWorkspace] = useState('');
  const [tiers, setTiers] = useState([]);
  const [model, setModel] = useState('');
  const [modelMock, setModelMock] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(true);
  const [ask, setAsk] = useState(null);
  const [projectOpen, setProjectOpen] = useState(false);
  const [modelOpen, setModelOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [streamingText, setStreamingText] = useState(null);
  const [error, setError] = useState('');
  const abort = useRef(null);
  const askResolve = useRef(null);

  const closeMenus = useCallback(() => {
    setProjectOpen(false);
    setModelOpen(false);
  }, []);

  const refreshNav = useCallback(async () => {
    try {
      const [proj, conv] = await Promise.all([api.projects(), api.conversations()]);
      setProjects(proj.projects);
      setCurrentProject(proj.current);
      setWorkspace(proj.workspace);
      setChats(conv.chats);
      setCurrentChat(conv.current);
    } catch (err) {
      console.error('Could not refresh nav:', err);
    }
  }, []);

  const loadHistory = useCallback(async () => {
    try {
      const data = await api.history();
      setMessages(data.messages);
    } catch (err) {
      console.error('Could not load history:', err);
    }
  }, []);

  // Wait for the backend (Electron may still be spawning Python).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      // Resolve the backend port (Electron exposes it synchronously via
      // preload, but fall back to the async IPC channel just in case).
      if (typeof window !== 'undefined' && window.electron && !window.electron.backendPort && typeof window.electron.getBackendPort === 'function') {
        try {
          const p = await window.electron.getBackendPort();
          if (p) window.__BACKEND_PORT = p;
        } catch {}
      }
      for (let i = 0; i < 60 && !cancelled; i++) {
        try {
          await api.health();
          const [settings, models] = await Promise.all([api.settings(), api.models()]);
          if (cancelled) return;
          setConfirmDelete(settings.confirm_delete);
          setTiers(models.tiers);
          setModel(models.current);
          setModelMock(models.mock);
          await loadHistory();
          await refreshNav();
          return;
        } catch {
          await new Promise((r) => setTimeout(r, 500));
        }
      }
      if (!cancelled) setError('Could not reach the Python backend on /api. Is it running?');
    })();
    return () => {
      cancelled = true;
    };
  }, [loadHistory, refreshNav]);

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') {
        closeMenus();
        setSettingsOpen(false);
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [closeMenus]);

  const stopStream = useCallback(() => {
    abort.current?.abort();
  }, []);

  const send = useCallback(
    async (text) => {
      setError('');
      setMessages((m) => [...m, { role: 'user', content: text }]);
      setInput('');
      setStreaming(true);
      setStreamingText('');
      refreshNav(); // a brand-new chat (or title) shows up in the sidebar

      const controller = new AbortController();
      abort.current = controller;
      let full = '';
      try {
        full = await streamChat(text, {
          signal: controller.signal,
          onToken: (_tok, assembled) => setStreamingText(assembled),
        });
      } catch (err) {
        if (err.name !== 'AbortError') {
          console.error('Chat failed:', err);
          setError(String(err.message || err));
        }
      } finally {
        abort.current = null;
        setStreaming(false);
        setStreamingText(null);
        // The backend persisted both messages; re-read for the canonical state.
        await loadHistory();
        await refreshNav();
      }
      return full;
    },
    [loadHistory, refreshNav],
  );

  const newChat = useCallback(async () => {
    stopStream();
    setMessages([]);
    setInput('');
    try {
      await api.newChat();
    } catch (err) {
      console.error('new_chat failed:', err);
    }
    await refreshNav();
  }, [refreshNav, stopStream]);

  const openChat = useCallback(
    async (id) => {
      stopStream();
      try {
        await api.openChat(id);
      } catch (err) {
        console.error('open_chat failed:', err);
      }
      await loadHistory();
      await refreshNav();
    },
    [loadHistory, refreshNav, stopStream],
  );

  const confirm = useCallback(
    (title, body) =>
      new Promise((resolve) => {
        if (!confirmDelete) return resolve(true);
        askResolve.current = resolve;
        setAsk({ title, body });
      }),
    [confirmDelete],
  );

  const resolveAsk = useCallback(
    (ok, never) => {
      setAsk(null);
      if (ok && never) {
        setConfirmDelete(false);
        api.setSetting('confirm_delete', false).catch((err) => console.error(err));
      }
      askResolve.current?.(ok);
      askResolve.current = null;
    },
    [],
  );

  const deleteChat = useCallback(
    async (id, title, isCurrent) => {
      if (!(await confirm('Delete this chat?', `"${title}" and its messages will be deleted permanently.`)))
        return;
      stopStream();
      try {
        await api.deleteChat(id);
      } catch (err) {
        console.error('delete_chat failed:', err);
      }
      if (isCurrent) await loadHistory();
      await refreshNav();
    },
    [confirm, loadHistory, refreshNav, stopStream],
  );

  const openProject = useCallback(
    async (path) => {
      stopStream();
      setProjectOpen(false);
      try {
        await api.openProject(path);
      } catch (err) {
        console.error('open_project failed:', err);
      }
      await loadHistory();
      await refreshNav();
    },
    [loadHistory, refreshNav, stopStream],
  );

  const browseForFolder = useCallback(async () => {
    setProjectOpen(false);
    stopStream();
    try {
      const path = await desktop.openFolder();
      if (!path) return; // dialog dismissed
      await api.openProject(path);
      await loadHistory();
      await refreshNav();
    } catch (err) {
      console.error('Could not open the folder picker:', err);
    }
  }, [loadHistory, refreshNav, stopStream]);

  const deleteProject = useCallback(
    async (path, name) => {
      if (
        !(await confirm(
          'Delete this project?',
          `"${name}" and its chats will be deleted permanently. The folder itself is left on disk.`,
        ))
      )
        return;
      stopStream();
      try {
        await api.deleteProject(path);
      } catch (err) {
        console.error('delete_project failed:', err);
      }
      await loadHistory();
      await refreshNav();
    },
    [confirm, loadHistory, refreshNav, stopStream],
  );

  const selectModel = useCallback(async (name) => {
    setModelOpen(false);
    setModel(name);
    try {
      const status = await api.selectModel(name);
      setModel(status.current ?? name);
      setModelMock(status.mock ?? false);
    } catch (err) {
      console.error('Could not switch model:', err);
    }
  }, []);

  // Called by the settings popup after switching; keeps the composer badge honest.
  const handleUsed = useCallback((status) => {
    setModel(status.current ?? '');
    setModelMock(status.mock ?? false);
  }, []);

  const projectName =
    projects.find((p) => p.path === currentProject)?.name ?? currentProject;
  const isHero = messages.length === 0 && streamingText === null;

  return (
    <div className="app" onClick={(e) => {
      if (!e.target.closest('.model') && !e.target.closest('.project')) closeMenus();
    }}>
      <Sidebar
        chats={chats}
        current={currentChat}
        projectList={projects}
        onNew={newChat}
        onOpen={openChat}
        onDelete={deleteChat}
        onOpenSettings={() => setSettingsOpen(true)}
      />

      <div className={`pane${isHero ? ' is-hero' : ''}`}>
        <TopBar
          projectName={projectName}
          projectPath={currentProject}
          menuOpen={projectOpen}
          onToggleMenu={() => {
            setModelOpen(false);
            setProjectOpen((v) => !v);
          }}
          onCloseMenus={closeMenus}
          menu={
            <ProjectMenu
              open={projectOpen}
              projects={projects}
              current={currentProject}
              workspace={workspace}
              onOpen={openProject}
              onBrowse={browseForFolder}
              onDelete={deleteProject}
            />
          }
        />

        {!isHero && <ChatThread messages={messages} streamingText={streamingText} />}
        {error && (
          <div className="dock" style={{ paddingBottom: 0 }}>
            <div className="error-bubble">{error}</div>
          </div>
        )}

        <div className="dock">
          <h1 className="hero">What next?</h1>
          <Composer
            value={input}
            onChange={setInput}
            onSend={send}
            streaming={streaming}
            onStop={stopStream}
          />
          <div className="meta">
            {modelMock && (
              <span className="mock-badge" title="Model weights are not downloaded; replies are canned placeholders">
                mock model
              </span>
            )}
            <div className="model">
              <button
                type="button"
                className="model-trigger"
                aria-haspopup="menu"
                aria-expanded={modelOpen}
                hidden={!model}
                onClick={() => {
                  setProjectOpen(false);
                  setModelOpen((v) => !v);
                }}
              >
                <span>{modelLabel(model)}</span>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="m6 9 6 6 6-6" />
                </svg>
              </button>
              <ModelMenu open={modelOpen} tiers={tiers} current={model} onSelect={selectModel} />
            </div>
          </div>
        </div>
      </div>

      <ConfirmDialog ask={ask} onResolve={resolveAsk} />
      <SettingsPopup
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        confirm={confirm}
        onUsed={handleUsed}
      />
    </div>
  );
}
