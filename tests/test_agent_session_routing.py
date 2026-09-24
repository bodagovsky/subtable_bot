"""Unit tests for selecting an Agents API conversation after a Telegram reply."""
import importlib
import sys
import types
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class FakeRedisClient:
    def __init__(self):
        self.reply_sessions = {}
        self.topic_sessions = {}

    def get_agents_api_session_id_for_message(self, chat_id, message_id):
        return self.reply_sessions.get((chat_id, message_id))

    def get_agents_api_session_id(self, chat_id, thread_id):
        return self.topic_sessions.get((chat_id, thread_id))


fake_redis = FakeRedisClient()
sys.modules["redis_client"] = types.SimpleNamespace(redis_client=fake_redis)
sys.modules.setdefault("dotenv", types.SimpleNamespace(load_dotenv=lambda: None))
worker = importlib.import_module("agent_worker")


class AgentSessionRoutingTests(unittest.TestCase):
    def setUp(self):
        fake_redis.reply_sessions.clear()
        fake_redis.topic_sessions.clear()

    def test_reply_uses_session_of_replied_message(self):
        fake_redis.reply_sessions[(42, 100)] = "sess_original"
        fake_redis.topic_sessions[(42, None)] = "sess_chat_default"

        self.assertEqual(
            worker._preferred_session_id({"chat_id": 42, "thread_id": None, "reply_to_message_id": 100}),
            "sess_original",
        )

    def test_non_reply_uses_chat_topic_default(self):
        fake_redis.topic_sessions[(42, None)] = "sess_chat_default"

        self.assertEqual(
            worker._preferred_session_id({"chat_id": 42, "thread_id": None}),
            "sess_chat_default",
        )

    def test_reply_without_mapping_falls_back_to_chat_topic_default(self):
        fake_redis.topic_sessions[(42, None)] = "sess_chat_default"

        self.assertEqual(
            worker._preferred_session_id({"chat_id": 42, "thread_id": None, "reply_to_message_id": 999}),
            "sess_chat_default",
        )
