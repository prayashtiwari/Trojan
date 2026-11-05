import tempfile
import unittest
from pathlib import Path

from context_store import ContextStore


class ContextStoreTests(unittest.TestCase):
    def test_approved_memories_and_projects_survive_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "trojan.db"
            first = ContextStore(path=path)
            memory = first.add_memory("I prefer concise answers", "preference")
            project = first.save_project("Apollo", "Use the bronze interface.")

            restarted = ContextStore(path=path)
            self.assertEqual(restarted.memories()[0]["content"], "I prefer concise answers")
            self.assertEqual(restarted.projects()[0]["name"], "Apollo")
            self.assertEqual(restarted.conversation(), [])
            self.assertEqual(memory["category"], "preference")
            self.assertEqual(project["name"], "Apollo")
            first.close()
            restarted.close()

    def test_clear_controls_remove_only_the_requested_records(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ContextStore(path=Path(folder) / "trojan.db")
            store.add_memory("Dark mode", "preference")
            store.add_memory("Apollo uses Python", "project")
            store.append_turn("user", "Hello")
            store.clear_memories("preference")
            self.assertEqual(store.memories("preference"), [])
            self.assertEqual(len(store.memories("project")), 1)
            self.assertEqual(len(store.conversation()), 1)
            store.clear_conversation()
            self.assertEqual(store.conversation(), [])
            store.close()

    def test_secret_like_content_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ContextStore(path=Path(folder) / "trojan.db")
            with self.assertRaises(ValueError):
                store.add_memory("api_key=do-not-save")
            with self.assertRaises(ValueError):
                store.save_project("Secrets", "password: do-not-save")
            store.close()


if __name__ == "__main__":
    unittest.main()
