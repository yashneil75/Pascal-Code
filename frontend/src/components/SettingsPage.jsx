import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { capitalize } from './icons.jsx';

function fmtSize(bytes) {
  if (bytes == null) return 'unknown';
  if (bytes < 1e9) return `${Math.round(bytes / 1e6)} MB`;
  return `${(bytes / 1e9).toFixed(1)} GB`;
}

function pct(d) {
  if (!d || !d.total) return null;
  return Math.min(100, Math.round((100 * d.downloaded) / d.total));
}

const TABS = ['General', 'Models'];

function compat(model, system) {
  const vram = system?.vram_available_gb ?? system?.vram_total_gb;
  const ram = system?.ram_available_gb ?? system?.ram_total_gb;
  if (vram != null && vram >= (model.min_vram_gb || 0)) return 'Compatible';
  if (ram != null && ram >= (model.min_ram_gb || 0)) return 'May be slow';
  return 'Insufficient memory';
}

export default function SettingsPage({ onClose, confirm, onUsed, confirmDelete, onToggleConfirmDelete, updateAvailable, updateDownloaded, updateVersion, updateProgress }) {
  const [tab, setTab] = useState('General');
  const [lib, setLib] = useState(null);
  const [progress, setProgress] = useState({});
  const [busy, setBusy] = useState(null);
  const [system, setSystem] = useState(null);
  const [expanded, setExpanded] = useState({});

  const refresh = async () => {
    try { setLib(await api.library()); } catch (e) { console.error(e); }
  };

  useEffect(() => {
    api.system().then(setSystem).catch(() => {});
  }, []);

  useEffect(() => {
    if (tab !== 'Models') return;
    refresh();
    const t = setInterval(async () => {
      try {
        setProgress((await api.downloadProgress()).downloads);
        await refresh();
      } catch (e) { console.error(e); }
    }, 1000);
    return () => clearInterval(t);
  }, [tab]);

  const run = async (id, fn) => {
    setBusy(id);
    try { await fn(); } catch (e) { console.error(e); }
    finally { setBusy(null); await refresh(); }
  };

  const useModel = (id) => run(id, async () => {
    const status = await api.selectModel(id);
    onUsed?.(status);
  });

  const deleteModel = (id, label) => run(id, async () => {
    const ok = await confirm('Delete this model?', `"${label}" will be deleted from disk.`);
    if (ok) await api.deleteModel(id);
  });

  const cancelDownload = (id) => run(id, async () => {
    await api.cancelDownload(id);
  });

  // Recommended: highest tier that is compatible
  let recommendedId = null;
  if (lib && system) {
    const compatible = lib.models.filter((m) => compat(m, system) === 'Compatible');
    if (compatible.length) recommendedId = compatible[compatible.length - 1].id;
  }

  return (
    <div className="settings-page">
      <div className="settings-page-head">
        <div>
          <h2>Model Settings</h2>
          <div className="settings-sub">Choose, download and manage local models.</div>
        </div>
      </div>
      <div className="settings-tabs">
        {TABS.map((t) => (
          <button key={t} type="button" className={`settings-tab${tab === t ? ' is-active' : ''}`} onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
      </div>
      <div className="settings-page-body">
        {tab === 'Models' && (
          <>
            {system && (
              <div className="hw-panel">
                {system.gpu_type === 'integrated' ? (
                  <span>System RAM: {system.ram_available_gb}/{system.ram_total_gb} GB available</span>
                ) : (
                  <>
                    <span>System RAM: {system.ram_available_gb}/{system.ram_total_gb} GB available</span>
                    {system.vram_total_gb != null && (
                      <span>GPU: {system.vram_available_gb}/{system.vram_total_gb} GB</span>
                    )}
                  </>
                )}
              </div>
            )}
            <div className="settings-list">
              {!lib && <div className="settings-sub">Loading…</div>}
              {lib?.models.map((m) => {
                const isCurrent = m.id === lib.current;
                const dl = progress[m.id];
                const downloading = dl?.status === 'downloading' || dl?.status === 'queued';
                const failed = dl?.status === 'error';
                const cancelled = dl?.status === 'cancelled';
                const p = pct(dl);
                const size = fmtSize(m.size_bytes ?? m.remote_bytes);
                const state = isCurrent
                  ? (lib.running ? 'Active' : lib.loading ? 'Loading…' : 'Selected')
                  : (m.downloaded ? 'Downloaded' : 'Not downloaded');
                const c = compat(m, system);
                const isRecommended = m.id === recommendedId;
                const expandedOpen = !!expanded[m.id];
                return (
                  <div key={m.id} className={`model-card${isCurrent ? ' is-current' : ''}`}>
                    <div className="model-card-head">
                      <div>
                        <div className="model-card-title">
                          {capitalize(m.label)}
                          {isRecommended && <span className="recommended">Recommended</span>}
                        </div>
                        <div className="model-card-desc">{m.performance}</div>
                      </div>
                      <div className="model-card-status">
                        {lib.loading && isCurrent && <span className="spinner" />}
                        <span className="status-text">{state}</span>
                      </div>
                    </div>
                    <div className="model-meta">
                      {m.ctx != null && <span>{Math.round(m.ctx / 1000)}K context</span>}
                      {m.min_vram_gb != null && <span>{m.min_vram_gb}GB GPU</span>}
                      {m.min_ram_gb != null && <span>{m.min_ram_gb}GB RAM</span>}
                      <span>{size}</span>
                      <span className={`compat ${c.toLowerCase().replace(' ', '-')}`}>{c}</span>
                    </div>
                    {downloading && (
                      <div className="progress-block">
                        <div className="progress" role="progressbar" aria-valuenow={p ?? 0} aria-valuemin="0" aria-valuemax="100">
                          <div className="progress-fill" style={{ width: `${p ?? 0}%` }} />
                        </div>
                        <div className="progress-label">
                          {p == null ? 'Starting…' : `${p}% · ${fmtSize(dl.downloaded)} of ${fmtSize(dl.total)}`}
                          {dl?.total && dl?.downloaded != null && (
                            <span> · {fmtSize(dl.total - dl.downloaded)} remaining</span>
                          )}
                        </div>
                      </div>
                    )}
                    {failed && <div className="progress-error">{dl.error || 'Download failed'}</div>}
                    {cancelled && <div className="progress-error">Cancelled</div>}
                    <div className="model-actions">
                      {!m.downloaded && !downloading && (
                        <button type="button" className="btn" disabled={busy === m.id} onClick={() => run(m.id, () => api.startDownload(m.id))}>
                          Download
                        </button>
                      )}
                      {m.downloaded && !isCurrent && (
                        <>
                          <button type="button" className="btn" disabled={busy === m.id} onClick={() => useModel(m.id)}>Use</button>
                          <button type="button" className="btn btn-danger" disabled={busy === m.id} onClick={() => deleteModel(m.id, capitalize(m.label))}>Delete</button>
                        </>
                      )}
                      {isCurrent && m.downloaded && !lib.running && !lib.loading && (
                        <button type="button" className="btn" disabled={busy === m.id} onClick={() => run(m.id, () => api.loadModel())}>Load</button>
                      )}
                      {isCurrent && lib.loading && (
                        <button type="button" className="btn" disabled>Loading…</button>
                      )}
                      {downloading && (
                        <button type="button" className="btn btn-danger" disabled={busy === m.id} onClick={() => cancelDownload(m.id)}>Cancel</button>
                      )}
                      <button type="button" className="btn btn-ghost" onClick={() => setExpanded((e) => ({ ...e, [m.id]: !e[m.id] }))}>
                        {expandedOpen ? 'Hide details' : 'Details'}
                      </button>
                    </div>
                    {expandedOpen && (
                      <div className="model-details">
                        <div>Architecture: {m.arch}</div>
                        <div>Quantization: {m.quant}</div>
                        {m.ctx != null && <div>Context: {m.ctx.toLocaleString()} tokens</div>}
                        <div>Expected memory: ~{m.min_ram_gb} GB</div>
                        <div>Repo: {m.repo || '—'}</div>
                        {m.path && <div>Path: {m.path}</div>}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </>
        )}
        {tab === 'General' && (
          <div className="settings-general">
            <label className="ask-opt">
              <input type="checkbox" checked={!confirmDelete} onChange={() => onToggleConfirmDelete?.(confirmDelete)} />
              Don't ask before deleting chats/projects
            </label>
            <div style={{ marginTop: 16 }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>Updates</div>
              {updateAvailable && <div style={{ marginBottom: 6 }}>New update available {updateVersion}</div>}
              {updateDownloaded && <div style={{ marginBottom: 6 }}>Update downloaded and ready to install.</div>}
              {updateProgress > 0 && updateProgress < 100 && <div style={{ marginBottom: 6 }}>Downloading update: {updateProgress}%</div>}
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button type="button" className="btn" onClick={() => window.electron?.checkForUpdates?.()}>Check for updates</button>
                {updateDownloaded && (
                  <button type="button" className="btn" onClick={() => window.electron?.installUpdate?.()}>Install update</button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}