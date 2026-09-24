"""MCP server that gives an agent a deliberately small Telegram tool surface.

Run locally (stdio):
    python src/telegram_mcp.py

Run remotely (Streamable HTTP):
    python src/telegram_mcp.py --transport streamable-http

Telegram delivers new updates to a bot, but MCP is request/response.  A separate
webhook worker must start an agent run when a new Telegram update should trigger
proactive behaviour.  This server is the agent's read/write interface for that
run.
"""
import argparse
import asyncio
import os
from datetime import datetime
from typing import Any

from mcp.server.fastmcp import FastMCP
from telegram import Bot

from mtproto_client import get_mtproto_client
from message_storage import message_storage
from redis_client import redis_client


MAX_MESSAGE_LENGTH = 4096
MAX_HISTORY_LIMIT = 100
_telegram_lock = asyncio.Lock()


def _required_bot_token() -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    return token


def _allowed_chat_ids() -> set[int]:
    """Read the optional allow-list once per tool call.

    An empty variable is convenient for local development.  A deployed HTTP
    server should always set TELEGRAM_MCP_ALLOWED_CHAT_IDS.
    """
    raw_ids = os.getenv("TELEGRAM_MCP_ALLOWED_CHAT_IDS", "").strip()
    if not raw_ids:
        return set()
    try:
        return {int(value.strip()) for value in raw_ids.split(",") if value.strip()}
    except ValueError as exc:
        raise RuntimeError("TELEGRAM_MCP_ALLOWED_CHAT_IDS must contain comma-separated integers") from exc


def _assert_chat_allowed(chat_id: int) -> None:
    allowed = _allowed_chat_ids()
    if allowed and chat_id not in allowed:
        raise RuntimeError(f"Chat {chat_id} is not in TELEGRAM_MCP_ALLOWED_CHAT_IDS")


def _assert_can_send(chat_id: int, text: str) -> None:
    _assert_chat_allowed(chat_id)
    if os.getenv("TELEGRAM_MCP_READ_ONLY", "").lower() in {"1", "true", "yes"}:
        raise RuntimeError("Sending is disabled because TELEGRAM_MCP_READ_ONLY is enabled")
    if not text or not text.strip():
        raise ValueError("text must not be empty")
    if len(text) > MAX_MESSAGE_LENGTH:
        raise ValueError(f"text must be at most {MAX_MESSAGE_LENGTH} characters")


async def _send_telegram_message(
    chat_id: int,
    text: str,
    reply_to_message_id: int | None = None,
    thread_id: int | None = None,
) -> dict[str, Any]:
    """Perform the send operation shared by the two MCP tool wrappers."""
    _assert_can_send(chat_id, text)
    async with Bot(token=_required_bot_token()) as bot:
        sent = await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_to_message_id=reply_to_message_id,
            message_thread_id=thread_id,
        )
    return {"chat_id": sent.chat_id, "message_id": sent.message_id, "sent_at": sent.date.isoformat()}


def _message_to_dict(message: Any) -> dict[str, Any]:
    """Return only stable, agent-useful fields instead of a Telethon object."""
    sender_id = getattr(message, "sender_id", None)
    sent_at = getattr(message, "date", None)
    return {
        "message_id": message.id,
        "text": message.message or "",
        "sender_id": sender_id,
        "sent_at": sent_at.isoformat() if isinstance(sent_at, datetime) else None,
        "reply_to_message_id": getattr(getattr(message, "reply_to", None), "reply_to_msg_id", None),
    }


async def _read_recent_messages(chat_id: int, limit: int) -> list[dict[str, Any]]:
    _assert_chat_allowed(chat_id)
    if not 1 <= limit <= MAX_HISTORY_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_HISTORY_LIMIT}")

    # The existing project already authenticates Telethon as this bot.  A lock
    # keeps a shared session from being stopped while another HTTP request uses it.
    async with _telegram_lock:
        client = get_mtproto_client()
        await client.start()
        try:
            messages = await client.get_recent_messages(chat_id, limit)
            return [_message_to_dict(message) for message in messages]
        finally:
            await client.stop()


async def _read_messages_by_ids(chat_id: int, message_ids: list[int]) -> list[dict[str, Any]]:
    messages = await _get_messages_by_ids(chat_id, message_ids)
    return [_message_to_dict(message) for message in messages if message is not None]


async def _get_messages_by_ids(chat_id: int, message_ids: list[int]) -> list[Any]:
    _assert_chat_allowed(chat_id)
    if not message_ids:
        return []
    if len(message_ids) > MAX_HISTORY_LIMIT:
        raise ValueError(f"at most {MAX_HISTORY_LIMIT} message IDs can be requested")
    async with _telegram_lock:
        client = get_mtproto_client()
        await client.start()
        try:
            return await client.get_messages(chat_id, message_ids)
        finally:
            await client.stop()


def _parse_timestamp(value: str) -> datetime:
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamps must be ISO 8601 strings") from exc
    if timestamp.tzinfo is None:
        raise ValueError("timestamps must include a timezone offset")
    return timestamp


def _delivery(delivery_id: str) -> dict[str, Any]:
    """Resolve a webhook-derived delivery capability without exposing chat IDs."""
    delivery = redis_client.get_agent_delivery(delivery_id)
    if not delivery:
        raise RuntimeError("delivery_id is unknown, expired, or already used")
    return delivery


def create_server(host: str = "127.0.0.1", port: int = 8000) -> FastMCP:
    """Create the server separately so it can be imported by an ASGI host/tests."""
    server = FastMCP(
        "Telegram",
        instructions=(
            "Every tool call needs the current delivery_id supplied by the task. "
            "It identifies one webhook conversation and cannot select a chat."
        ),
        host=host,
        port=port,
        stateless_http=True,
        json_response=True,
    )

    @server.tool()
    async def telegram_get_recent_messages(delivery_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """Read up to 100 newest messages in the current webhook chat.

        Uses the project's existing Telethon/MTProto credentials.  The result is
        newest first.  It contains text and metadata, not media files.
        """
        return await _read_recent_messages(_delivery(delivery_id)["chat_id"], limit)

    @server.tool()
    async def telegram_get_messages_by_ids(delivery_id: str, message_ids: list[int]) -> list[dict[str, Any]]:
        """Read specific Telegram messages previously seen by this bot.

        Use this to inspect the message the user replied to, or the IDs returned
        by a time-range query. Text is retrieved from Telegram only on demand.
        """
        return await _read_messages_by_ids(_delivery(delivery_id)["chat_id"], message_ids)

    @server.tool()
    async def telegram_get_messages_in_time_range(
        delivery_id: str, start_time: str, end_time: str | None = None
    ) -> list[dict[str, Any]]:
        """Read indexed chat messages in an ISO-8601 time range, oldest first.

        The bot retains a compact seven-day index. This tool retrieves the text
        for its message IDs from Telegram and is the preferred tool for a
        question such as 'what did we discuss in the last two hours?'.
        """
        chat_id = _delivery(delivery_id)["chat_id"]
        start = _parse_timestamp(start_time)
        end = _parse_timestamp(end_time) if end_time else None
        indexed = message_storage.get_messages_in_period(chat_id, start, end)
        return await _read_messages_by_ids(chat_id, [message_id for _, message_id, _ in indexed])

    @server.tool()
    async def telegram_get_top_speakers_by_reactions(delivery_id: str, hours: float = 168) -> list[dict[str, Any]]:
        """Rank the top three authors by reactions received on their messages.

        The default period is seven days. Counts are read from Telegram at query
        time for messages indexed during that period.
        """
        chat_id = _delivery(delivery_id)["chat_id"]
        _assert_chat_allowed(chat_id)
        if not 0 < hours <= 24 * 7:
            raise ValueError("hours must be greater than 0 and at most 168")
        from datetime import timedelta, timezone

        end = datetime.now(timezone.utc)
        indexed = message_storage.get_messages_in_period(chat_id, end - timedelta(hours=hours), end)
        messages = await _get_messages_by_ids(chat_id, [message_id for _, message_id, _ in indexed])
        author_by_message = {message_id: user_id for user_id, message_id, _ in indexed}
        totals: dict[int, int] = {}
        for message in messages:
            if message is None:
                continue
            reactions = getattr(getattr(message, "reactions", None), "results", []) or []
            reaction_count = sum(getattr(reaction, "count", 0) for reaction in reactions)
            author_id = author_by_message.get(message.id)
            if author_id is not None:
                totals[author_id] = totals.get(author_id, 0) + reaction_count
        return [
            {"user_id": user_id, "reaction_count": reaction_count}
            for user_id, reaction_count in sorted(totals.items(), key=lambda item: item[1], reverse=True)[:3]
        ]

    @server.tool()
    async def telegram_send_message(
        chat_id: int,
        text: str,
        reply_to_message_id: int | None = None,
    ) -> dict[str, Any]:
        """Send one text message, optionally as a reply, to an allowed chat.

        This has an external side effect. Never use it for a draft: send only
        text that the user has requested or explicitly approved.
        """
        return await _send_telegram_message(chat_id, text, reply_to_message_id)

    @server.tool()
    async def telegram_reply(delivery_id: str, text: str) -> dict[str, Any]:
        """Reply once to the current Telegram request.

        The server resolves and consumes delivery_id to obtain the chat, original
        message, and optional forum topic. This is the only message-delivery tool
        exposed to the remote agent.
        """
        delivery = redis_client.consume_agent_delivery(delivery_id)
        if not delivery:
            raise RuntimeError("delivery_id is unknown, expired, or already used")
        return await _send_telegram_message(
            delivery["chat_id"],
            text,
            delivery["message_id"],
            delivery.get("thread_id"),
        )

    @server.tool()
    async def telegram_get_bot_identity() -> dict[str, Any]:
        """Return the identity of the bot configured for this MCP server."""
        async with Bot(token=_required_bot_token()) as bot:
            bot_user = await bot.get_me()
        return {"id": bot_user.id, "username": bot_user.username, "name": bot_user.full_name}

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="Telegram MCP server")
    parser.add_argument("--transport", choices=("stdio", "streamable-http"), default="stdio")
    parser.add_argument("--host", default=os.getenv("TELEGRAM_MCP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("TELEGRAM_MCP_PORT", "8000")))
    args = parser.parse_args()
    create_server(host=args.host, port=args.port).run(transport=args.transport)


if __name__ == "__main__":
    main()
