import { useEffect, useState } from 'react';
import ProjectMenu from './ProjectMenu.jsx';
import { desktop } from '../api.js';

export default function TopBar({
  projectName,
  projectPath,
  menuOpen,
  onToggleMenu,
  onCloseMenus,
  menu,
}) {
  const [maximized, setMaximized] = useState(false);

  useEffect(() => desktop.onMaximized?.(setMaximized), []);

  const toggleMaximize = async () => {
    if (!desktop.isElectron) return;
    const next = await desktop.toggleMaximize();
    if (typeof next === 'boolean') setMaximized(next);
  };

  return (
    <header className="bar">
      <div className="project">
        <button
          type="button"
          className="project-trigger"
          aria-haspopup="menu"
          aria-expanded={menuOpen}
          hidden={!projectName}
          onClick={onToggleMenu}
        >
          <svg className="folder" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 6a2 2 0 0 1 2-2h3.6l2 2.5H19a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
          </svg>
          <span id="project-name" title={projectPath}>
            {projectName}
          </span>
          <svg className="caret" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="m6 9 6 6 6-6" />
          </svg>
        </button>
        {menu}
      </div>

      <div className={`bar-drag${desktop.isElectron ? ' draggable' : ''}`} onClick={onCloseMenus} />

      <div className="window-controls">
        <button type="button" className="win" title="Minimize" aria-label="Minimize window" onClick={() => desktop.minimize()}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
            <path d="M7 12h10" />
          </svg>
        </button>
        <button
          type="button"
          className="win"
          title={maximized ? 'Restore' : 'Maximize'}
          aria-label={`${maximized ? 'Restore' : 'Maximize'} window`}
          aria-pressed={String(maximized)}
          onClick={toggleMaximize}
        >
          <svg className="glyph-max" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round">
            <rect x="7.25" y="7.25" width="9.5" height="9.5" rx="1.6" />
          </svg>
          <svg className="glyph-restore" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10 7.25h5.25a1.5 1.5 0 0 1 1.5 1.5V14" />
            <rect x="7.25" y="9.75" width="8" height="8" rx="1.6" />
          </svg>
        </button>
        <button type="button" className="win win-close" title="Close" aria-label="Close window" onClick={() => desktop.close()}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
            <path d="m7.5 7.5 9 9" />
            <path d="m16.5 7.5-9 9" />
          </svg>
        </button>
      </div>
    </header>
  );
}

export { ProjectMenu };
