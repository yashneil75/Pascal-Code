import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import backend.config as config
from backend.store import Store

# The schema as it stood before project folders existed.
OLD_SCHEMA = """
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE messages (
    id INTEGER PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
    payload TEXT NOT NULL
);
"""


class StoreTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.store = Store(self.root / "conversations.db")
        self.project = str(self.root / "project")
        self.conversation = self.store.new_conversation(self.project)

    def tearDown(self):
        self._tmp.cleanup()

    def test_round_trip_keeps_llama_cpp_message_shape(self):
        messages = [
            {"role": "system", "content": "You are Simply."},
            {"role": "user", "content": "list the files"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "ls", "arguments": '{"path": "."}'},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "config.py"},
        ]
        for message in messages:
            self.store.append(self.conversation, message)

        self.assertEqual(self.store.load(self.conversation), messages)

    def test_append_order_is_preserved(self):
        for text in ("first", "second", "third"):
            self.store.append(self.conversation, {"role": "user", "content": text})

        contents = [m["content"] for m in self.store.load(self.conversation)]
        self.assertEqual(contents, ["first", "second", "third"])

    def test_conversations_are_isolated(self):
        other = self.store.new_conversation(self.project)
        self.store.append(self.conversation, {"role": "user", "content": "mine"})
        self.store.append(other, {"role": "user", "content": "theirs"})

        self.assertEqual(len(self.store.load(self.conversation)), 1)
        self.assertEqual(self.store.load(other)[0]["content"], "theirs")

    def test_projects_are_registered_once(self):
        first = self.store.ensure_project(self.project)
        second = self.store.ensure_project(self.project)

        self.assertEqual(first, second)
        self.assertEqual(self.store.projects(), [self.project])

    def test_newest_chat_is_per_project(self):
        other_project = str(self.root / "other")
        other = self.store.new_conversation(other_project)

        self.assertEqual(self.store.newest(self.project), self.conversation)
        self.assertEqual(self.store.newest(other_project), other)
        self.assertIsNone(self.store.newest(str(self.root / "unused")))

    def test_project_of_a_chat(self):
        other_project = str(self.root / "other")
        other = self.store.new_conversation(other_project)

        self.assertEqual(self.store.project_of(other), other_project)
        self.assertEqual(self.store.project_of(self.conversation), self.project)
        self.assertIsNone(self.store.project_of(999))

    def test_summaries_are_titled_by_the_first_prompt_newest_first(self):
        self.store.append(self.conversation, {"role": "user", "content": "first chat"})
        second = self.store.new_conversation(self.project)
        self.store.append(second, {"role": "system", "content": "a system prompt"})
        self.store.append(second, {"role": "user", "content": "second chat"})
        self.store.append(second, {"role": "assistant", "content": "a reply"})
        self.store.append(second, {"role": "user", "content": "a follow up"})

        summaries = self.store.summaries()
        self.assertEqual([s["id"] for s in summaries], [second, self.conversation])
        self.assertEqual([s["title"] for s in summaries], ["second chat", "first chat"])
        self.assertEqual({s["project"] for s in summaries}, {self.project})

    def test_summaries_skip_chats_with_nothing_said(self):
        self.store.new_conversation(self.project)
        self.assertEqual(self.store.summaries(), [])

    def test_delete_conversation_takes_the_chats_messages_with_it(self):
        self.store.append(self.conversation, {"role": "user", "content": "keep"})
        doomed = self.store.new_conversation(self.project)
        self.store.append(doomed, {"role": "user", "content": "gone"})

        self.store.delete_conversation(doomed)

        self.assertEqual(self.store.load(doomed), [])
        self.assertEqual([s["id"] for s in self.store.summaries()], [self.conversation])
        self.assertEqual(self.store.load(self.conversation)[0]["content"], "keep")

    def test_deleting_a_chat_that_is_already_gone_is_harmless(self):
        self.store.delete_conversation(999)

    def test_delete_project_takes_its_chats_and_messages_with_it(self):
        self.store.append(self.conversation, {"role": "user", "content": "one"})
        other_project = str(self.root / "other")
        other = self.store.new_conversation(other_project)
        self.store.append(other, {"role": "user", "content": "two"})

        self.store.delete_project(self.project)

        self.assertEqual(self.store.projects(), [other_project])
        self.assertIsNone(self.store.newest(self.project))
        self.assertEqual([s["title"] for s in self.store.summaries()], ["two"])
        # the rows are gone, not merely detached from a deleted project
        self.assertEqual(self.store.load(self.conversation), [])
        self.assertEqual(self.store.load(other)[0]["content"], "two")

    def test_settings_round_trip(self):
        self.assertIsNone(self.store.setting("confirm_delete"))

        self.store.set_setting("confirm_delete", "false")
        self.assertEqual(self.store.setting("confirm_delete"), "false")

        self.store.set_setting("confirm_delete", "true")
        self.assertEqual(self.store.setting("confirm_delete"), "true")

    def test_a_database_from_before_projects_lands_in_the_workspace(self):
        path = self.root / "old.db"
        with closing(sqlite3.connect(path)) as conn, conn:
            conn.executescript(OLD_SCHEMA)
            conn.execute("INSERT INTO conversations DEFAULT VALUES")
            conn.execute(
                "INSERT INTO messages (conversation_id, payload) VALUES (1, ?)",
                (json.dumps({"role": "user", "content": "from before"}),),
            )

        old = Store(path)
        reopened = Store(path)  # migrating is idempotent

        self.assertEqual(old.projects(), [str(config.WORKSPACE)])
        self.assertEqual(reopened.newest(config.WORKSPACE), 1)
        (chat,) = reopened.summaries()
        self.assertEqual(chat["title"], "from before")
        self.assertEqual(chat["project"], str(config.WORKSPACE))

    def test_rejects_a_message_without_a_known_role(self):
        with self.assertRaises(ValueError):
            self.store.append(self.conversation, {"role": "wizard", "content": "hi"})

    def test_rejects_non_string_content(self):
        with self.assertRaises(ValueError):
            self.store.append(self.conversation, {"role": "user", "content": 42})


if __name__ == "__main__":
    unittest.main()
