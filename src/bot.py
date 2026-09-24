"""Telegram webhook bridge for the Alfred agent.

The bridge does no intent classification: every valid invocation is queued for
the single agent worker.  Keeping this request path short prevents Telegram
webhook retries while the agent performs MCP or web-search work.
"""
import asyncio
import logging

from aiohttp import web
from telegram import Update
from telegram.ext import Application

from agent_bridge import enqueue_update
from config import TELEGRAM_BOT_TOKEN, WEBHOOK_PATH, WEBHOOK_PORT, WEBHOOK_SECRET_TOKEN, WEBHOOK_URL


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
# httpx logs full request URLs. Telegram Bot API embeds the token in that URL,
# so never emit its INFO-level request logs in a hosted environment.
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

ALLOWED_UPDATES = [
    "message",
    "edited_message",
    "channel_post",
    "edited_channel_post",
    "message_reaction",
    "message_reaction_count",
]


async def webhook_handler(request: web.Request) -> web.Response:
    """Authenticate, deserialize, index, and enqueue one Telegram update."""
    if WEBHOOK_SECRET_TOKEN:
        token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if token != WEBHOOK_SECRET_TOKEN:
            logger.warning("Webhook request with invalid secret token")
            return web.Response(status=403, text="Forbidden")

    try:
        update = Update.de_json(await request.json(), request.app["application"].bot)
        queued = await enqueue_update(update, request.app["bot_id"])
        logger.debug("Telegram update %s queued=%s", update.update_id, queued)
    except Exception:
        # Return a retryable error: the deduplication key is written only after
        # Redis accepts it, and the producer can safely redeliver an update.
        logger.exception("Could not process Telegram webhook")
        return web.Response(status=500, text="Retry later")
    return web.Response(text="OK")


async def create_app() -> web.Application:
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in environment variables")
    if not WEBHOOK_URL:
        raise ValueError("WEBHOOK_URL not set in environment variables")

    telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    await telegram_app.initialize()
    bot_identity = await telegram_app.bot.get_me()
    await telegram_app.bot.set_webhook(
        url=f"{WEBHOOK_URL.rstrip('/')}{WEBHOOK_PATH}",
        secret_token=WEBHOOK_SECRET_TOKEN or None,
        allowed_updates=ALLOWED_UPDATES,
    )

    app = web.Application()
    app["application"] = telegram_app
    app["bot_id"] = bot_identity.id
    app.router.add_post(WEBHOOK_PATH, webhook_handler)
    async def health(_: web.Request) -> web.Response:
        return web.Response(text="Alfred bridge is running")

    app.router.add_get("/health", health)

    async def shutdown(_: web.Application) -> None:
        await telegram_app.bot.delete_webhook(drop_pending_updates=False)
        await telegram_app.shutdown()

    app.on_shutdown.append(shutdown)
    return app


async def main_async() -> None:
    app = await create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEBHOOK_PORT)
    await site.start()
    logger.info("Alfred webhook bridge is listening on port %s", WEBHOOK_PORT)
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
