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


class AlfredInvocationTests(unittest.TestCase):
    def test_cyrillic_name_with_comma(self):
        self.assertEqual(extract_alfred_request("Альфред, что нового?"), "что нового?")

    def test_cyrillic_name_with_space(self):
        self.assertEqual(extract_alfred_request("Альфред это правда?"), "это правда?")

    def test_english_name_with_colon(self):
        self.assertEqual(extract_alfred_request("Alfred: summarize"), "summarize")

    def test_does_not_accept_name_as_a_prefix_of_a_word(self):
        self.assertIsNone(extract_alfred_request("Альфредовна, привет"))


if __name__ == "__main__":
    unittest.main()
