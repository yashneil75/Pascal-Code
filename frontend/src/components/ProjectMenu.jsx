import { BIN, CHECK, FOLDER } from './icons.jsx';

export default function ProjectMenu({
  open,
  projects,
  current,
  workspace,
  onOpen,
  onBrowse,
  onDelete,
}) {
  if (!open) return null;
  return (
    <div className="project-menu menu" role="menu" aria-label="Project folder">
      {projects.map(({ path, name }) => (
        <div key={path} className="menu-row">
          <button
            type="button"
            className="menu-option"
            role="menuitemradio"
            aria-checked={String(path === current)}
            onClick={() => onOpen(path)}
          >
            <span className="opt-text">
              <span className="opt-name">{name}</span>
              <span className="opt-path">{path}</span>
            </span>
            {CHECK}
          </button>
          {path !== workspace && (
            <button
              type="button"
              className="menu-delete"
              aria-label={`Delete project: ${name}`}
              onClick={() => onDelete(path, name)}
            >
              {BIN}
            </button>
          )}
        </div>
      ))}
      <div className="menu-separator" />
      <button type="button" className="menu-option" onClick={onBrowse}>
        <span className="opt-text">
          <span className="opt-name">Add a new workspace…</span>
        </span>
        {FOLDER}
      </button>
    </div>
  );
}
