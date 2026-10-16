import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { capitalize } from './icons.jsx';

// Model library popup: download tiers, warm up / switch / delete weights.
// Progress polls while open; the backend caches remote sizes so polling is cheap.
function fmtSize(bytes) {
  if (bytes == null) return 'size unknown';
  if (bytes < 1e9) return `${Math.round(bytes / 1e6)} MB`;
  return `${(bytes / 1e9).toFixed(1)} GB`;
}

function pct(d) {
  if (!d || !d.total) return null;
  return Math.min(100, Math.round((100 * d.downloaded) / d.total));
}

export default function SettingsPopup({ open, onClose, confirm, onUsed }) {
  const [lib, setLib] = useState(null);
  const [progress, setProgress] = useState({});
  const [busy, setBusy] = useState(null);

  const refresh = async () => {
    try {
      setLib(await api.library());
    } catch (err) {
      console.error('library failed:', err);
    }
  };

  useEffect(() => {
    if (!open) return;
    refresh();
    const t = setInterval(async () => {
      try {
        setProgress((await api.downloadProgress()).downloads);
        await refresh();
      } catch (err) {
        console.error('progress poll failed:', err);
      }
    }, 1000);
    return () => clearInterval(t);
  }, [open ]);

  if (!open) return null;

  const run = async (id, fn) => {
    setBusy(id);
    try {
      await fn();
    } catch (err) {
      console.error(err);
    } finally {
      setBusy(null);
      await refresh();
    }
  };

  const useModel = (id) =>
    run(id, async () => {
      const status = await api.selectModel(id);
      onUsed?.(status);
    });

  const deleteModel = (id, label) =>
    run(id, async () => {
      const ok = await confirm(
        'Delete this model?',
        `"${label}" (${fmtSize(lib.models.find((m) => m.id === id)?.size_bytes)}) will be deleted from disk and must be re-downloaded to use again.`,
      );
      if (ok) await api.deleteModel(id);
    });

  return (
    <div className="settings-backdrop" onClick={onClose}>
      <div className="settings-modal" role="dialog" aria-label="Model settings" onClick={(e) => e.stopPropagation()}>
        <div className="settings-head">
          <h2>Models</h2>
          <button type="button" className="settings-close" aria-label="Close settings" onClick={onClose}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
              <path d="m7 7 10 10M17 7 7 17" />
            </svg>
          </button>
        </div>
        <p className="settings-sub">
          Weights live in <code>~/.pascal_code</code>. Download a tier, warm it up, or delete what you
          don&rsquo;t need.
        </p>
        <div className="settings-list">
          {!lib && <p className="settings-sub">Loading…</p>}
          {lib?.models.map((m) => {
            const isCurrent = m.id === lib.current;
            const dl = progress[m.id];
            const downloading = dl?.status === 'downloading' || dl?.status === 'queued';
            const failed = dl?.status === 'error';
            const p = pct(dl);
            const size = fmtSize(m.size_bytes ?? m.remote_bytes);
            const state = isCurrent
              ? lib.running
                ? 'Active'
                : lib.loading
                  ? 'Loading…'
                  : 'Selected'
              : m.downloaded
                ? 'Downloaded'
                : 'Not downloaded';
            return (
              <div className="settings-row" key={m.id}>
                <div className="settings-info">
                  <div className="settings-name">
                    {capitalize(m.label)}
                    <span className={`settings-state${isCurrent ? ' is-current' : ''}`}>{state}</span>
                  </div>
                  <div className="settings-desc">{m.description} · {size}</div>
                  {downloading && (
                    <>
                      <div className="progress" role="progressbar" aria-valuenow={p ?? 0} aria-valuemin="0" aria-valuemax="100">
                        <div className="progress-fill" style={{ width: `${p ?? 0}%` }} />
                      </div>
                      <div className="progress-label">
                        {failed || p == null ? 'Starting…' : `${p}% · ${fmtSize(dl.downloaded)} of ${fmtSize(dl.total)}`}
                      </div>
                    </>
                  )}
                  {failed && <div className="progress-error">{dl.error || 'Download failed'}</div>}
                </div>
                <div className="settings-actions">
                  {!m.downloaded && !downloading && (
                    <button type="button" className="btn" disabled={busy === m.id}
                      onClick={() => run(m.id, () => api.startDownload(m.id))}>
                      Download
                    </button>
                  )}
                  {m.downloaded && !isCurrent && (
                    <>
                      <button type="button" className="btn" disabled={busy === m.id} onClick={() => useModel(m.id)}>
                        Use
                      </button>
                      <button type="button" className="btn btn-danger" disabled={busy === m.id}
                        onClick={() => deleteModel(m.id, capitalize(m.label))}>
                        Delete
                      </button>
                    </>
                  )}
                  {isCurrent && m.downloaded && !lib.running && !lib.loading && (
                    <button type="button" className="btn" disabled={busy === m.id}
                      onClick={() => run(m.id, () => api.loadModel())}>
                      Load
                    </button>
                  )}
                  {isCurrent && lib.loading && (
                    <button type="button" className="btn" disabled>Loading…</button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
