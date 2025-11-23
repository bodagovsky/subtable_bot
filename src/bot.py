"""Main Telegram bot application."""
import sys
import os
# Add parent directory to path to allow imports when running as module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
import re
import asyncio
from aiohttp import web
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from config import TELEGRAM_BOT_TOKEN, WEBHOOK_URL, WEBHOOK_PORT, WEBHOOK_PATH, WEBHOOK_SECRET_TOKEN
from chatgpt_client import ChatGPTClient
from command_handler import CommandHandler as BotCommandHandler
from message_storage import message_storage
from datetime import datetime

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize clients
chatgpt = ChatGPTClient()
command_handler = BotCommandHandler()


def is_bot_mentioned(message_text: str, bot_username: str) -> bool:
    """Check if bot is mentioned in the message."""
    if not bot_username or not message_text:
        return False
    # Check for @username mention
    mention_pattern = f"@{re.escape(bot_username)}"
    return bool(re.search(mention_pattern, message_text, re.IGNORECASE))


def is_reply_to_bot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if message is a reply to bot's message."""
    if not update.message or not update.message.reply_to_message:
        return False
    
    replied_message = update.message.reply_to_message
    # Check if the replied message is from the bot
    return replied_message.from_user and replied_message.from_user.id == context.bot.id


def should_process_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> tuple[bool, str]:
    """
    Determine if message should be processed and extract user message.
    Bot only responds when explicitly mentioned or when replying to bot's message.
    Returns: (should_process, user_message)
    """
    if update.message:
        message_text = update.message.text
        bot_username = context.bot.username
        
        # Check if it's a reply to bot's message
        if is_reply_to_bot(update, context):
            return True, message_text
        
        # Check if bot is mentioned
        if is_bot_mentioned(message_text, bot_username):
            # Remove mention from message
            user_message = re.sub(f"@{re.escape(bot_username)}", "", message_text, flags=re.IGNORECASE).strip()
            return True, user_message
        
        # Don't process messages where bot is not mentioned
        return False, ""
    
    elif update.channel_post:
        message_text = update.channel_post.text
        bot_username = context.bot.username
        
        # Check if bot is mentioned
        if is_bot_mentioned(message_text, bot_username):
            user_message = re.sub(f"@{re.escape(bot_username)}", "", message_text, flags=re.IGNORECASE).strip()
            return True, user_message
        
        # Only process if mentioned
        return False, ""
    
    return False, ""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    welcome_message = """Добро пожаловать, сэр/мадам. Я Альфред, ваш помощник-бот на базе ChatGPT.
    
Я к вашим услугам и готов выполнить команды на естественном языке. Просто обратитесь ко мне, и я постараюсь понять и выполнить вашу просьбу.

Доступные команды:
- Получить текущее время
- Сгенерировать случайные числа
- Повторить сообщение
- Найти самых активных пользователей

Как обратиться:
1. Упомяните меня (@имя_бота) с вашим запросом - я отвечаю только при явном упоминании
2. Ответьте на мое сообщение с вашим запросом

Я буду вежливо спрашивать подтверждение перед выполнением любой команды, как и подобает хорошему помощнику."""
    
    # Handle both private chats and channels
    if update.message:
        await update.message.reply_text(welcome_message)
    elif update.channel_post:
        await update.channel_post.reply_text(welcome_message)


async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle confirmation responses (yes/no) from users."""
    if not update.message or not update.message.text:
        return
    
    user_message = update.message.text.lower().strip()
    
    # Check if there's a pending command confirmation
    pending_command = context.user_data.get("pending_command")
    if not pending_command:
        return False
    
    # Check if this is a reply to bot's message (confirmation should be a reply)
    if not is_reply_to_bot(update, context):
        # If there's a pending command but not a reply, might be a new request
        # Clear the old pending command and process as new message
        del context.user_data["pending_command"]
        return False
    
    # Check if user confirmed
    if user_message in ["yes", "y", "да", "ok", "okay", "confirm", "execute", "верно", "ага"]:
        # Execute the pending command
        command_name = pending_command["command"]
        parameters = pending_command.get("parameters", {})
        
        logger.info(f"User confirmed command: {command_name} with parameters: {parameters}")
        
        # Get bot and chat_id for commands that need them
        bot = context.bot
        chat_id = update.message.chat.id
        
        # Execute the command
        response = command_handler.execute_command(command_name, parameters, bot=bot, chat_id=chat_id)
        
        # Clear pending command
        del context.user_data["pending_command"]
        
        # Reply to user's confirmation message
        await update.message.reply_text(response)
        return True
    else:
        # User declined or said something else
        logger.info(f"User did not confirm: {user_message}")
        
        # Clear pending command
        del context.user_data["pending_command"]
        
        await update.message.reply_text("Как вам будет угодно, сэр/мадам. Команда отменена. Я готов к вашим дальнейшим распоряжениям.")
        return True


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages."""
    # Store message for tracking (if it's a regular message)
    message_obj = update.message if update.message else update.channel_post
    if message_obj and message_obj.from_user and message_obj.chat:
        try:
            message_timestamp = datetime.utcnow()
            if message_obj.date:
                message_timestamp = message_obj.date
            message_storage.add_message(
                chat_id=message_obj.chat.id,
                user_id=message_obj.from_user.id,
                message_id=message_obj.message_id,
                timestamp=message_timestamp
            )
        except Exception as e:
            logger.debug(f"Could not store message: {e}")
    
    # Check if this is a time window extraction retry
    if context.user_data.get("pending_time_window"):
        pending_tw = context.user_data["pending_time_window"]
        command_name = pending_tw["command"]
        attempt = pending_tw.get("attempt", 1)
        
        # Check if this is a reply to bot's message
        if is_reply_to_bot(update, context) and update.message:
            user_message = update.message.text
            
            # Try to extract time window again
            time_window_result = chatgpt.extract_time_window(user_message)
            
            if time_window_result.get("success") and time_window_result.get("time_window_hours"):
                # Success - store as pending command
                parameters = {"time_window_hours": time_window_result["time_window_hours"]}
                context.user_data["pending_command"] = {
                    "command": command_name,
                    "parameters": parameters
                }
                del context.user_data["pending_time_window"]
                
                # Ask for confirmation
                time_window_hours = parameters["time_window_hours"]
                confirmation_message = "Понял вас, сэр/мадам. Вы желаете выполнить: **Самые активные пользователи**\n\n"
                confirmation_message += f"Временной период: {time_window_hours} часов\n\n"
                confirmation_message += "Верно ли я вас понял? Пожалуйста, подтвердите, ответив 'да'."
                
                await update.message.reply_text(confirmation_message, parse_mode="Markdown")
                return
            else:
                # Failed again
                if attempt >= 2:
                    # Second attempt failed - give up
                    del context.user_data["pending_time_window"]
                    await update.message.reply_text(
                        "Прошу прощения, сэр/мадам, но я не смог понять указанный вами временной период. "
                        "Будьте так любезны, попробуйте еще раз с более конкретным периодом (например, 'за последний день', 'за последние 3 часа')."
                    )
                    return
                else:
                    # First attempt failed - try once more
                    context.user_data["pending_time_window"]["attempt"] = 2
                    await update.message.reply_text(
                        "Прошу прощения, сэр/мадам, но я всё ещё не смог определить временной период. "
                        "Будьте так любезны, попробуйте ещё раз с более понятным форматом, "
                        "например: 'за последний день', 'за последние 3 часа', 'за прошлую неделю' (максимум одна неделя)."
                    )
                    return
    
    # Check if this is a confirmation response
    if context.user_data.get("pending_command"):
        handled = await handle_confirmation(update, context)
        if handled:
            return
    
    # Check if message should be processed (mention or reply)
    should_process, user_message = should_process_message(update, context)
    
    if not should_process or not user_message:
        return
    
    # Determine which message object to use for replies
    message_obj = update.message if update.message else update.channel_post
    if not message_obj:
        return
    
    logger.info(f"Processing request: {user_message}")
    
    # Get available commands
    available_commands = command_handler.get_available_commands()
    
    # Analyze message with ChatGPT
    analysis = chatgpt.analyze_message(user_message, available_commands)
    
    logger.info(f"ChatGPT analysis: {analysis}")
    
    # Check if a command was identified
    command_name = analysis.get("command")
    # Handle case where JSON returns string "null" instead of actual null
    if command_name in [None, "null", ""]:
        command_name = None
    
    if command_name and command_name in command_handler.commands:
        # Command found - handle special case for most_active_user
        if command_name == "most_active_user":
            # Extract time window from the message
            time_window_result = chatgpt.extract_time_window(user_message)
            
            if time_window_result.get("success") and time_window_result.get("time_window_hours"):
                # Time window extracted successfully
                parameters = {"time_window_hours": time_window_result["time_window_hours"]}
                reasoning = time_window_result.get("reasoning", "")
                
                # Store pending command
                context.user_data["pending_command"] = {
                    "command": command_name,
                    "parameters": parameters
                }
                
                # Get command description for confirmation message
                cmd_info = next((c for c in available_commands if c["name"] == command_name), None)
                cmd_description = cmd_info["description"] if cmd_info else command_name
                
                time_window_hours = parameters["time_window_hours"]
                confirmation_message = f"Понял вас, сэр/мадам. Вы желаете выполнить: **{cmd_description}**\n\n"
                confirmation_message += f"Временной период: {time_window_hours} часов\n\n"
                if reasoning:
                    confirmation_message += f"Мое понимание: {reasoning}\n\n"
                confirmation_message += "Верно ли я вас понял? Пожалуйста, подтвердите, ответив 'да'."
                
                await message_obj.reply_text(confirmation_message, parse_mode="Markdown")
            else:
                # Time window extraction failed - ask user for time window
                context.user_data["pending_time_window"] = {
                    "command": command_name,
                    "attempt": 1
                }
                await message_obj.reply_text(
                    "Понял вас, сэр/мадам. Вы желаете найти самых активных пользователей, однако я не смог определить временной период из вашего сообщения.\n\n"
                    "Будьте так любезны, укажите временной период (например, 'за последний день', 'за последние 3 часа', 'за прошлую неделю'). "
                    "Максимально допустимый период составляет одну неделю."
                )
        else:
            # Regular command - ask for confirmation
            parameters = analysis.get("parameters", {})
            reasoning = analysis.get("reasoning", "")
            
            # Store pending command
            context.user_data["pending_command"] = {
                "command": command_name,
                "parameters": parameters
            }
            
            # Get command description for confirmation message
            cmd_info = next((c for c in available_commands if c["name"] == command_name), None)
            cmd_description = cmd_info["description"] if cmd_info else command_name
            
            confirmation_message = f"Понял вас, сэр/мадам. Вы желаете выполнить: **{cmd_description}**\n\n"
            if parameters:
                confirmation_message += f"Параметры: {parameters}\n\n"
            if reasoning:
                confirmation_message += f"Мое понимание: {reasoning}\n\n"
            confirmation_message += "Верно ли я вас понял? Пожалуйста, подтвердите, ответив 'да'."
            
            # Reply to user's message asking for confirmation
            await message_obj.reply_text(confirmation_message, parse_mode="Markdown")
    else:
        # No command found - ask for clarification
        clarification_message = chatgpt.generate_clarification(user_message, available_commands)
        
        # Reply to user's message asking for clarification
        await message_obj.reply_text(clarification_message)




async def webhook_handler(request: web.Request) -> web.Response:
    """Handle incoming webhook requests from Telegram."""
    # Verify secret token if configured
    if WEBHOOK_SECRET_TOKEN:
        token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if token != WEBHOOK_SECRET_TOKEN:
            logger.warning("Webhook request with invalid secret token")
            return web.Response(status=403, text="Forbidden")
    
    application = request.app["application"]
    
    # Get the update from the request
    update_data = await request.json()
    update = Update.de_json(update_data, application.bot)
    
    # Process the update
    await application.process_update(update)
    
    return web.Response(text="OK")


async def setup_webhook(application: Application) -> None:
    """Set up the webhook with Telegram."""
    if not WEBHOOK_URL:
        raise ValueError("WEBHOOK_URL not set in environment variables")
    
    webhook_url = f"{WEBHOOK_URL.rstrip('/')}{WEBHOOK_PATH}"
    
    # Set webhook
    await application.bot.set_webhook(
        url=webhook_url,
        secret_token=WEBHOOK_SECRET_TOKEN if WEBHOOK_SECRET_TOKEN else None,
        allowed_updates=Update.ALL_TYPES
    )
    
    logger.info(f"Webhook set to: {webhook_url}")


async def remove_webhook(application: Application) -> None:
    """Remove the webhook from Telegram."""
    await application.bot.delete_webhook(drop_pending_updates=True)
    logger.info("Webhook removed")


async def create_app() -> web.Application:
    """Create and configure the aiohttp web application."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in environment variables")
    
    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start))
    
    # Handle all text messages (private chats, groups, channels)
    # The handler will check for mentions and replies internally
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Initialize application (this will call initialize() on all handlers)
    await application.initialize()
    
    # Set up webhook
    await setup_webhook(application)
    
    # Create aiohttp app
    app = web.Application()
    app["application"] = application
    
    # Add webhook route
    app.router.add_post(WEBHOOK_PATH, webhook_handler)
    
    # Add health check route
    async def health_check(request: web.Request) -> web.Response:
        return web.Response(text="Bot is running")
    
    app.router.add_get("/health", health_check)
    
    # Cleanup on shutdown
    async def on_shutdown(app: web.Application) -> None:
        await remove_webhook(app["application"])
        await app["application"].shutdown()
    
    app.on_shutdown.append(on_shutdown)
    
    return app


async def main_async():
    """Async main function to set up and run the webhook server."""
    logger.info("Bot starting with webhook...")
    logger.info(f"Webhook URL: {WEBHOOK_URL}")
    logger.info(f"Webhook port: {WEBHOOK_PORT}")
    logger.info(f"Webhook path: {WEBHOOK_PATH}")
    logger.info("Bot supports both private chats and channels!")
    logger.info("For channels: Add bot as admin OR mention the bot in messages")
    
    # Create the web application
    app = await create_app()
    
    # Start the web server
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEBHOOK_PORT)
    await site.start()
    
    logger.info(f"Webhook server started on port {WEBHOOK_PORT}")
    logger.info(f"Waiting for updates at {WEBHOOK_URL}{WEBHOOK_PATH}")
    
    # Keep the server running
    try:
        await asyncio.Event().wait()  # Wait indefinitely
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await runner.cleanup()


def main():
    """Start the bot with webhook."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()

