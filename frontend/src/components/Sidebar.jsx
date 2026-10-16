import { BIN, SLIDERS } from './icons.jsx';

export default function Sidebar({ chats, current, projectList, onNew, onOpen, onDelete, onOpenSettings }) {
  const groups = new Map();
  for (const chat of chats) {
    if (!groups.has(chat.project)) groups.set(chat.project, []);
    groups.get(chat.project).push(chat);
  }
  const order = [...new Set([...projectList.map((p) => p.path), ...groups.keys()])];

  return (
    <aside className="sidebar">
      <button type="button" className="new-chat" onClick={onNew}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
          <path d="M12 5v14M5 12h14" />
        </svg>
        New chat
      </button>
      <nav className="chats" aria-label="Chats">
        {order.map((path) => {
          if (!groups.has(path)) return null;
          const name = projectList.find((p) => p.path === path)?.name ?? path;
          return (
            <div key={path}>
              <div className="group-name" title={path}>
                {name}
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
          {SLIDERS}
          Settings
        </button>
      </div>
    </aside>
  );
}
