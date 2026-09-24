"""Fast webhook-side routing for Alfred requests.

This module deliberately does not classify the user's intent.  Its only job is
to persist enough Telegram metadata and put valid invocations on the Redis
queue for the agent worker.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from telegram import Update

from message_storage import message_storage
from redis_client import redis_client

MAX_REPLIED_CONTEXT_CHARS = 12_000


def extract_alfred_request(text: str | None) -> str | None:
    """Return text after an initial 'Alfred/Альфред' invocation, if present."""
    if not text:
        return None
    stripped = text.lstrip()
    lowered = stripped.lower()
    for name in ("альфред", "alfred"):
        if not lowered.startswith(name):
            continue
        remainder = stripped[len(name):]
        if not remainder or not (remainder[0].isspace() or remainder[0] in ",:"):
            continue
        return remainder.lstrip(" \t,:").strip() or None
    return None


def _is_reply_to_bot(message: Any, bot_id: int) -> bool:
    replied = getattr(message, "reply_to_message", None)
    return bool(replied and replied.from_user and replied.from_user.id == bot_id)


def extract_replied_context(message: Any) -> str | None:
    """Return bounded text/caption from the message quoted by a Telegram reply."""
    replied = getattr(message, "reply_to_message", None)
    if not replied:
        return None
    text = getattr(replied, "text", None) or getattr(replied, "caption", None)
    if not text:
        return None
    text = str(text)
    if len(text) > MAX_REPLIED_CONTEXT_CHARS:
        return f"{text[:MAX_REPLIED_CONTEXT_CHARS]}\n[цитата обрезана]"
    return text


async def enqueue_update(update: Update, bot_id: int) -> bool:
    """Index an update and enqueue it only when it invokes Alfred."""
    if not redis_client.claim_update(update.update_id):
        return False
    try:
        # python-telegram-bot 20.7 does not expose reaction fields on every
        # Update object, even when Telegram has enabled these update types.
        reaction_count = getattr(update, "message_reaction_count", None)
        if reaction_count:
            reaction = reaction_count
            total = sum(item.total_count for item in reaction.reactions)
            message_storage.record_reaction_count(reaction.chat.id, reaction.message_id, total)
            return False

        reaction_change = getattr(update, "message_reaction", None)
        if reaction_change:
            reaction = reaction_change
            delta = len(reaction.new_reaction) - len(reaction.old_reaction)
            message_storage.adjust_reaction_count(reaction.chat.id, reaction.message_id, delta)
            return False

        message = update.effective_message
        if not message or not message.from_user:
            return False

        timestamp = message.date or datetime.now().astimezone()
        message_storage.add_message(
            chat_id=message.chat_id,
            user_id=message.from_user.id,
            message_id=message.message_id,
            timestamp=timestamp,
            thread_id=message.message_thread_id,
        )

        requested_text = extract_alfred_request(message.text)
        is_reply = _is_reply_to_bot(message, bot_id)
        if not requested_text and not is_reply:
            return False

        # A reply can be a natural continuation, so retain its complete text.
        user_text = requested_text or (message.text or "")
        if not user_text:
            return False

        replied_message_id = message.reply_to_message.message_id if message.reply_to_message else None
        replied_context = extract_replied_context(message)
        delivery_id = redis_client.create_agent_delivery(
            chat_id=message.chat_id,
            message_id=message.message_id,
            thread_id=message.message_thread_id,
        )
        redis_client.enqueue_agent_job(
            {
                "chat_id": message.chat_id,
                "user_id": message.from_user.id,
                "thread_id": message.message_thread_id,
                "message_id": message.message_id,
                "reply_to_message_id": replied_message_id,
                "reply_to_message_text": replied_context,
                "delivery_id": delivery_id,
                "text": user_text,
                "timestamp": timestamp.isoformat(),
            }
        )
        return True
    except Exception:
        # Let Telegram retry the update if indexing or enqueuing was incomplete.
        redis_client.release_update_claim(update.update_id)
        raise
