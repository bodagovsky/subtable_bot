"""Unit tests for invocation parsing; they do not require Telegram credentials."""
import importlib
import sys
import types
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.modules.setdefault("telegram", types.SimpleNamespace(Update=object))
sys.modules.setdefault("message_storage", types.SimpleNamespace(message_storage=object()))
sys.modules.setdefault("redis_client", types.SimpleNamespace(redis_client=object()))
extract_alfred_request = importlib.import_module("agent_bridge").extract_alfred_request
extract_replied_context = importlib.import_module("agent_bridge").extract_replied_context


class AlfredInvocationTests(unittest.TestCase):
    def test_cyrillic_name_with_comma(self):
        self.assertEqual(extract_alfred_request("Альфред, что нового?"), "что нового?")

    def test_cyrillic_name_with_space(self):
        self.assertEqual(extract_alfred_request("Альфред это правда?"), "это правда?")

    def test_english_name_with_colon(self):
        self.assertEqual(extract_alfred_request("Alfred: summarize"), "summarize")

    def test_does_not_accept_name_as_a_prefix_of_a_word(self):
        self.assertIsNone(extract_alfred_request("Альфредовна, привет"))

    def test_replied_message_text_becomes_context(self):
        message = types.SimpleNamespace(reply_to_message=types.SimpleNamespace(text="Проверяемое утверждение"))
        self.assertEqual(extract_replied_context(message), "Проверяемое утверждение")

    def test_selected_quote_replaces_full_replied_message(self):
        message = types.SimpleNamespace(
            quote=types.SimpleNamespace(text="Только это утверждение"),
            reply_to_message=types.SimpleNamespace(text="Длинное сообщение, включающее только это утверждение и другой контекст."),
        )
        self.assertEqual(extract_replied_context(message), "Только это утверждение")

    def test_replied_context_is_bounded(self):
        source = importlib.import_module("agent_bridge")
        message = types.SimpleNamespace(reply_to_message=types.SimpleNamespace(text="x" * (source.MAX_REPLIED_CONTEXT_CHARS + 1)))
        context = extract_replied_context(message)
        self.assertTrue(context.endswith("[цитата обрезана]"))
        self.assertLessEqual(len(context), source.MAX_REPLIED_CONTEXT_CHARS + len("\n[цитата обрезана]"))


if __name__ == "__main__":
    unittest.main()
