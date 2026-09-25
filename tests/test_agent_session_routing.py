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
        self.active_sessions = {}
        self.bound_jobs = []

    def get_agents_api_session_id_for_message(self, chat_id, message_id):
        return self.reply_sessions.get((chat_id, message_id))

    def get_active_agents_api_session_id_for_user(self, chat_id, user_id):
        return self.active_sessions.get((chat_id, user_id))

    def set_agents_api_session_id_for_message(self, chat_id, message_id, session_id):
        self.reply_sessions[(chat_id, message_id)] = session_id

    def set_agent_delivery_session_id(self, delivery_id, session_id):
        self.bound_jobs.append(("delivery", delivery_id, session_id))

    def add_agents_api_session_participant(self, chat_id, session_id, user_id):
        self.bound_jobs.append(("participant", chat_id, session_id, user_id))


fake_redis = FakeRedisClient()
sys.modules["redis_client"] = types.SimpleNamespace(redis_client=fake_redis)
sys.modules.setdefault("dotenv", types.SimpleNamespace(load_dotenv=lambda: None))
worker = importlib.import_module("agent_worker")


class AgentSessionRoutingTests(unittest.TestCase):
    def setUp(self):
        fake_redis.reply_sessions.clear()
        fake_redis.active_sessions.clear()
        fake_redis.bound_jobs.clear()

    def test_reply_uses_session_of_replied_message(self):
        fake_redis.reply_sessions[(42, 100)] = "sess_original"
        fake_redis.active_sessions[(42, 7)] = "sess_user_default"

        self.assertEqual(
            worker._preferred_session_id({"chat_id": 42, "user_id": 7, "thread_id": None, "reply_to_message_id": 100}),
            "sess_original",
        )

    def test_non_reply_uses_users_active_session(self):
        fake_redis.active_sessions[(42, 7)] = "sess_user_active"

        self.assertEqual(
            worker._preferred_session_id({"chat_id": 42, "user_id": 7, "thread_id": None}),
            "sess_user_active",
        )

    def test_reply_without_mapping_falls_back_to_users_active_session(self):
        fake_redis.active_sessions[(42, 7)] = "sess_user_active"

        self.assertEqual(
            worker._preferred_session_id({"chat_id": 42, "user_id": 7, "thread_id": None, "reply_to_message_id": 999}),
            "sess_user_active",
        )

    def test_reply_adds_sender_to_session_participants(self):
        job = {"chat_id": 42, "user_id": 8, "message_id": 101, "delivery_id": "delivery_1"}

        worker._bind_job_to_session(job, "sess_original")

        self.assertEqual(fake_redis.reply_sessions[(42, 101)], "sess_original")
        self.assertIn(("participant", 42, "sess_original", 8), fake_redis.bound_jobs)
