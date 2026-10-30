import { BIN, PEN, GEAR, FOLDER } from './icons.jsx';
import logo from '../../../Logo.png';

export default function Sidebar({ chats, current, projectList, onNew, onOpen, onDelete, onOpenSettings, updateAvailable }) {
  const groups = new Map();
  for (const chat of chats) {
    if (!groups.has(chat.project)) groups.set(chat.project, []);
    groups.get(chat.project).push(chat);
  }
  const order = [...new Set([...projectList.map((p) => p.path), ...groups.keys()])];

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <img src={logo} alt="Pascal Code" className="sidebar-logo" />
        <span className="sidebar-title">Pascal Code</span>
      </div>
      <button type="button" className="new-chat" onClick={onNew}>
        {PEN}
        New chat
      </button>
      {updateAvailable && (
        <button type="button" className="new-chat" onClick={onOpenSettings} style={{ fontSize: 12, color: 'var(--muted)' }}>
          new update available →
        </button>
      )}
      <nav className="chats" aria-label="Chats">
        {order.map((path) => {
          if (!groups.has(path)) return null;
          const name = projectList.find((p) => p.path === path)?.name ?? path;
          return (
            <div key={path}>
              <div className="group-name" title={path}>
                {FOLDER}
                <span className="group-title">{name}</span>
              </div>
              {groups.get(path).map(({ id, title }) => (
                <div key={id} className="chat" aria-current={String(id === current)}>
                  <button
                    type="button"
                    className="chat-open"
                    title={title}
                    onClick={() => onOpen(id)}
                  >
                    {title}
                  </button>
                  <button
                    type="button"
                    className="chat-delete"
                    aria-label={`Delete chat: ${title}`}
                    onClick={() => onDelete(id, title, id === current)}
                  >
                    {BIN}
                  </button>
                </div>
              ))}
            </div>
          );
        })}
      </nav>
      <div className="sidebar-foot">
        <div className="menu-separator" />
        <button type="button" className="new-chat" onClick={onOpenSettings}>
          {GEAR}
          Settings
        </button>
      </div>
    </aside>
  );
}
