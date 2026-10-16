import json
import sqlite3
from contextlib import closing
from pathlib import Path

from backend import config

DB_PATH = config.MODEL_DIR / "conversations.db"

# llama.cpp chat completion roles.
ROLES = ("system", "user", "assistant", "tool")

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects (id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# Created after migrations, since these may index migrated columns.
INDEXES = """
CREATE INDEX IF NOT EXISTS messages_by_conversation ON messages (conversation_id, id);
CREATE INDEX IF NOT EXISTS conversations_by_project ON conversations (project_id, id);
"""


class Store:
    """Conversations, grouped into project folders, in SQLite.

    Each message row holds the whole llama.cpp message dict as JSON -- role,
    content, and any tool_calls or tool_call_id -- so a conversation reloads
    straight into create_chat_completion(messages=...). Tool calls therefore
    need no columns of their own; they ride along inside the payload.
    """

    def __init__(self, path: Path = DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.executescript(SCHEMA)
            self._migrate(conn)
            conn.executescript(INDEXES)

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """Bring a database written before projects existed up to date."""
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(conversations)")}
        if "project_id" in columns:
            return

        conn.execute(
            "ALTER TABLE conversations ADD COLUMN project_id INTEGER "
            "REFERENCES projects (id) ON DELETE CASCADE"
        )
        # Chats that predate projects belong to the default workspace.
        conn.execute(
            "INSERT OR IGNORE INTO projects (path) VALUES (?)", (str(config.WORKSPACE),)
        )
        conn.execute(
            "UPDATE conversations SET project_id = (SELECT id FROM projects WHERE path = ?)",
            (str(config.WORKSPACE),),
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def ensure_project(self, path: str | Path) -> int:
        """Register a project folder if it is new; return its id either way."""
        path = str(path)
        with closing(self._connect()) as conn, conn:
            conn.execute("INSERT OR IGNORE INTO projects (path) VALUES (?)", (path,))
            row = conn.execute("SELECT id FROM projects WHERE path = ?", (path,)).fetchone()
            return row["id"]

    def projects(self) -> list[str]:
        """Registered project folders, in the order they were added."""
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT path FROM projects ORDER BY id").fetchall()
        return [row["path"] for row in rows]

    def new_conversation(self, project: str | Path) -> int:
        project_id = self.ensure_project(project)
        with closing(self._connect()) as conn, conn:
            cursor = conn.execute(
                "INSERT INTO conversations (project_id) VALUES (?)", (project_id,)
            )
            return cursor.lastrowid

    def newest(self, project: str | Path) -> int | None:
        """The most recent chat in a project folder."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT c.id
                FROM conversations AS c
                JOIN projects AS p ON p.id = c.project_id
                WHERE p.path = ?
                ORDER BY c.id DESC
                LIMIT 1
                """,
                (str(project),),
            ).fetchone()
            return row["id"] if row else None

    def project_of(self, conversation_id: int) -> str | None:
        """The folder a chat lives in."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT p.path
                FROM conversations AS c
                JOIN projects AS p ON p.id = c.project_id
                WHERE c.id = ?
                """,
                (conversation_id,),
            ).fetchone()
            return row["path"] if row else None

    def summaries(self) -> list[dict]:
        """Every chat with a prompt in it, newest first, with its project folder."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT c.id, c.created_at, p.path AS project,
                       (
                           SELECT json_extract(m.payload, '$.content')
                           FROM messages AS m
                           WHERE m.conversation_id = c.id
                             AND json_extract(m.payload, '$.role') = 'user'
                           ORDER BY m.id
                           LIMIT 1
                       ) AS title
                FROM conversations AS c
                JOIN projects AS p ON p.id = c.project_id
                ORDER BY c.id DESC
                """
            ).fetchall()
        return [
            {
                "id": row["id"],
                "title": row["title"],
                "created_at": row["created_at"],
                "project": row["project"],
            }
            for row in rows
            if row["title"]
        ]

    def delete_conversation(self, conversation_id: int) -> None:
        """Drop a chat; its messages go with it through the foreign key."""
        with closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))

    def delete_project(self, path: str | Path) -> None:
        """Forget a project, its chats and their messages. The folder stays put."""
        with closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM projects WHERE path = ?", (str(path),))

    def append(self, conversation_id: int, message: dict) -> None:
        if message.get("role") not in ROLES:
            raise ValueError(
                f"Unknown role {message.get('role')!r}, expected one of {ROLES}"
            )
        content = message.get("content")
        if content is not None and not isinstance(content, str):
            raise ValueError("Message content must be a string or null")
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO messages (conversation_id, payload) VALUES (?, ?)",
                (conversation_id, json.dumps(message)),
            )

    def load(self, conversation_id: int) -> list[dict]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT payload FROM messages WHERE conversation_id = ? ORDER BY id",
                (conversation_id,),
            ).fetchall()
            return [json.loads(row["payload"]) for row in rows]

    # Preferences, kept in the same file so they outlive a session.
    def setting(self, key: str) -> str | None:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else None

    def set_setting(self, key: str, value: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
            )
