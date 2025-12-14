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
from config import (
    TELEGRAM_BOT_TOKEN, WEBHOOK_URL, WEBHOOK_PORT, WEBHOOK_PATH, WEBHOOK_SECRET_TOKEN,
    COMMAND_PROBABILITY_HIGH_THRESHOLD, COMMAND_PROBABILITY_LOW_THRESHOLD
)
from chatgpt_client import ChatGPTClient
from command_handler import CommandHandler as BotCommandHandler
from message_storage import message_storage
from user_ignore_list import user_ignore_list
from redis_client import redis_client
from datetime import datetime

from tools.state_machine import state_machine


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


def is_name_called(message_text: str) -> tuple[bool, str]:
    """
    Check if bot's name (Альфред/Alfred) is explicitly called at the start of the message.
    
    Args:
        message_text: The message text to check
        
    Returns:
        Tuple of (is_called, extracted_message)
        If name is called, returns (True, message_without_name)
        Otherwise returns (False, "")
    """
    if not message_text:
        return False, ""
    
    # Bot name variations (case insensitive)
    name_patterns = [
        r"^альфред\s*[,:]\s*",  # "Альфред, " or "Альфред: "
        r"^альфред\s+",  # "Альфред " (with space)
        r"^alfred\s*[,:]\s*",  # "Alfred, " or "Alfred: " (English)
        r"^alfred\s+",  # "Alfred " (English, with space)
    ]
    
    message_lower = message_text.lower()
    
    for pattern in name_patterns:
        match = re.match(pattern, message_lower, re.IGNORECASE)
        if match:
            # Extract message after the name
            extracted = message_text[match.end():].strip()
            if extracted:  # Only return True if there's content after the name
                return True, extracted
    
    return False, ""


def should_process_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> tuple[bool, str]:
    """
    Determine if message should be processed and extract user message.
    Bot responds when:
    1. Explicitly mentioned (@botname)
    2. Replying to bot's message
    3. Bot's name is explicitly called (Альфред/Alfred)
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
        
        # Check if bot's name is explicitly called
        is_called, extracted_message = is_name_called(message_text)
        if is_called:
            return True, extracted_message
        
        # Don't process messages where bot is not mentioned or called
        return False, ""
    
    elif update.channel_post:
        message_text = update.channel_post.text
        bot_username = context.bot.username
        
        # Check if bot is mentioned
        if is_bot_mentioned(message_text, bot_username):
            user_message = re.sub(f"@{re.escape(bot_username)}", "", message_text, flags=re.IGNORECASE).strip()
            return True, user_message
        
        # Check if bot's name is explicitly called
        is_called, extracted_message = is_name_called(message_text)
        if is_called:
            return True, extracted_message
        
        # Only process if mentioned or called by name
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
1. Упомяните меня (@имя_бота) с вашим запросом
2. Ответьте на мое сообщение с вашим запросом
3. Назовите меня по имени: "Альфред, [ваш запрос]" (например, "Альфред, назови число от 1 до 1000")

Я буду вежливо спрашивать подтверждение перед выполнением любой команды, как и подобает хорошему помощнику."""
    
    # Handle both private chats and channels
    if update.message:
        await update.message.reply_text(welcome_message)
    elif update.channel_post:
        await update.channel_post.reply_text(welcome_message)

async def generate_random_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    chat_id = update.message.chat.id
    try:
        min, max = map(int, update.message.text.split()[1:])
        if min > max:
            min, max  = max, min
        parameters = {"min": min, "max": max}
        user_id = update.message.from_user.id if update.message and update.message.from_user else None
        response = await command_handler.execute_command("random_number", parameters, bot=bot, chat_id=chat_id, user_id=user_id)
    except Exception as e:
        response = f"Произошла досадная ошибка: ({e})"

    if update.message:
        await update.message.reply_text(response)
    elif update.channel_post:
        await update.channel_post.reply_text(response)

async def silence(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id if update.message and update.message.from_user else None
    response = await command_handler.execute_command("silence", {}, bot=bot, chat_id=chat_id, user_id=user_id)

    if update.message:
        await update.message.reply_text(response)
    elif update.channel_post:
        await update.channel_post.reply_text(response)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages using state machine."""
    from tools.state_machine import UserState, Event
    
    # Determine which message object to use
    message_obj = update.message if update.message else update.channel_post
    if not message_obj or not message_obj.chat:
        return
    
    chat_id = message_obj.chat.id
    user_id = message_obj.from_user.id if message_obj.from_user else None

    if message_obj.from_user:
        try:
            message_timestamp = datetime.now()
            if message_obj.date:
                message_timestamp = message_obj.date
            is_new_message = message_storage.add_message(
                chat_id=chat_id,
                user_id=message_obj.from_user.id,
                message_id=message_obj.message_id,
                timestamp=message_timestamp
            )
            # If message already stored, return early (idempotency)
            if not is_new_message:
                return
        except Exception as e:
            logger.debug(f"Could not store message: {e}")
    
    # Step 1: Check if bot is silenced (using Redis)
    is_silenced = redis_client.is_bot_silenced(chat_id)
    if is_silenced:
        # Check if this is an unsilence request
        should_process, user_message = should_process_message(update, context)
        if should_process and user_message:
            # Check if it's a silence command (which will unsilence if called by the right user)
            available_commands = command_handler.get_available_commands()
            analysis = chatgpt.analyze_message(user_message, available_commands)
            commands_with_probs = analysis.get("commands", [])
            
            # Find silence command
            silence_cmd = None
            for cmd in commands_with_probs:
                if cmd.get("name") == "silence":
                    silence_cmd = cmd
                    break
            
            # Check if user is the one who silenced
            silence_user_id = redis_client.get_silence_user_id(chat_id)
            if silence_cmd and silence_cmd.get("probability", 0) >= COMMAND_PROBABILITY_HIGH_THRESHOLD:
                if silence_user_id == user_id:
                    # User who silenced is trying to unsilence - execute command
                    event = await command_handler.execute_command(
                        "silence", {}, update=update, context=context, chatgpt_client=chatgpt
                    )
                    # Update state based on event
                    current_state = context.user_data.get("user_state", UserState.INIT)
                    new_state = state_machine.perform_transition(current_state, event) or current_state
                    context.user_data["user_state"] = new_state
                    return
                else:
                    # Different user trying to unsilence - ignore
                    logger.info(f"Bot is silenced in chat {chat_id}, ignoring message from user {user_id}")
                    return
            else:
                # Not an unsilence request - ignore
                logger.info(f"Bot is silenced in chat {chat_id}, ignoring message")
                return
        else:
            # Not a message that should be processed - ignore
                    return
        
    # Step 2: Check if user is ignored (but allow unsilence requests)
    if user_id and user_ignore_list.is_ignored(user_id):
        should_process, user_message = should_process_message(update, context)
        if should_process and user_message:
            # Check if it's a silence_me command (unsilence request)
            available_commands = command_handler.get_available_commands()
            analysis = chatgpt.analyze_message(user_message, available_commands)
            commands_with_probs = analysis.get("commands", [])
            
            silence_me_cmd = None
            for cmd in commands_with_probs:
                if cmd.get("name") == "silence_me":
                    silence_me_cmd = cmd
                    break
            
            silence_me_prob = silence_me_cmd.get("probability", 0) if silence_me_cmd else 0
            if silence_me_prob >= COMMAND_PROBABILITY_HIGH_THRESHOLD:
                # Execute silence_me to unsilence
                
                event = await command_handler.execute_command(
                    "silence_me", {}, update=update, context=context, chatgpt_client=chatgpt
                )
                # Update state based on event
                current_state = context.user_data.get("user_state", UserState.INIT)
                new_state = state_machine.perform_transition(current_state, event) or current_state
                context.user_data["user_state"] = new_state
                return
        
        # User is ignored and it's not an unsilence request - ignore
        logger.info(f"User {user_id} is in ignore list, ignoring message")
        return
    
    # Step 3: Check if message should be processed (mention or reply)
    should_process, user_message = should_process_message(update, context)
    if not should_process:
        # Store message for tracking if not silenced
        if message_obj.from_user:
            try:
                message_timestamp = datetime.now()
                if message_obj.date:
                    message_timestamp = message_obj.date
                is_new_message = message_storage.add_message(
                    chat_id=chat_id,
                    user_id=message_obj.from_user.id,
                    message_id=message_obj.message_id,
                    timestamp=message_timestamp
                )
                # If message already stored, return early (idempotency)
                if not is_new_message:
                    return
            except Exception as e:
                logger.debug(f"Could not store message: {e}")
            return
    
    logger.info(f"Processing request: {user_message}")
    
    # Step 4: Get current user state from context
    current_state = context.user_data.get("user_state", UserState.INIT)
    current_command = context.user_data.get("current_command")

    
    # Step 5: Handle based on current state
    if current_state == UserState.PENDING_COMMAND_CLARIFICATION:
        # Perform commands extraction
        available_commands = command_handler.get_available_commands()
        analysis = chatgpt.analyze_message(user_message, available_commands)
        commands_with_probs = analysis.get("commands", [])

        high_threshold_commands = [
            cmd for cmd in commands_with_probs
            if cmd.get("probability", 0) >= COMMAND_PROBABILITY_HIGH_THRESHOLD
        ]
        
        if len(high_threshold_commands) == 1:
            # Command clarified - execute it
            cmd_data = high_threshold_commands[0]
            command_name = cmd_data.get("name")
            
            # Check if command requires parameters and extract them separately
            parameters = {}
            command = command_handler.commands.get(command_name)
            if command and command.requires_parameters():
                # Extract parameters separately using ChatGPT
                parameters_description = command.human_readable_parameters()
                extraction_result = chatgpt.extract_parameters_for_command(
                    command_name, user_message, parameters_description
                )
                if extraction_result.get("success"):
                    parameters = extraction_result.get("parameters", {})
                else:
                    # Parameters extraction failed - will be handled by command execution
                    parameters = {}
            
            event = await command_handler.execute_command(
                command_name, parameters, update=update, context=context, chatgpt_client=chatgpt
            )
            
            # Update state
            new_state = state_machine.perform_transition(current_state, event) or current_state
            context.user_data["user_state"] = new_state
            if event == Event.COMMAND_EXECUTED:
                context.user_data["current_command"] = None
            else:
                context.user_data["current_command"] = command_name
        else:
            # Still unclear - return COMMAND_UNCLEAR event
            event = Event.COMMAND_UNCLEAR
            # Command execute should have sent clarification message
            # But if no command was found, send generic clarification
            if not high_threshold_commands:
                clarification_message = chatgpt.generate_clarification(user_message, available_commands)
                await message_obj.reply_text(clarification_message)
            
            new_state = state_machine.perform_transition(current_state, event) or current_state
            context.user_data["user_state"] = new_state
    
    elif current_state == UserState.PENDING_PARAMETERS_CLARIFICATION:
        # User is clarifying parameters - extract parameters for current command
        if current_command:
            # Get the command and extract parameters from user message
            command = command_handler.commands.get(current_command)
            if command:
                parameters = {}
                if command.requires_parameters():
                    # Extract parameters separately using ChatGPT
                    parameters_description = command.human_readable_parameters()
                    extraction_result = chatgpt.extract_parameters_for_command(
                        current_command, user_message, parameters_description
                    )
                    if extraction_result.get("success"):
                        parameters = extraction_result.get("parameters", {})
                    # If extraction failed, parameters will be empty and command will handle it
                
                event = await command_handler.execute_command(
                    current_command, parameters, update=update, context=context, chatgpt_client=chatgpt
                )
                
                # Update state
                new_state = state_machine.perform_transition(current_state, event) or current_state
                context.user_data["user_state"] = new_state
                if event == Event.COMMAND_EXECUTED:
                    context.user_data["current_command"] = None
            else:
                # Command not found - this shouldn't happen, but treat as parameter clarification failure
                event = Event.PARAMETERS_UNCLEAR
                new_state = state_machine.perform_transition(current_state, event) or current_state
                context.user_data["user_state"] = new_state
        else:
            # No current command - reset to INIT
            context.user_data["user_state"] = UserState.INIT
    
    else:  # INIT or other states
        # New request - analyze commands first
        available_commands = command_handler.get_available_commands()
        analysis = chatgpt.analyze_message(user_message, available_commands)
        commands_with_probs = analysis.get("commands", [])
        
        high_threshold_commands = [
            cmd for cmd in commands_with_probs
            if cmd.get("probability", 0) >= COMMAND_PROBABILITY_HIGH_THRESHOLD
        ]
        low_threshold_commands = [
            cmd for cmd in commands_with_probs
            if cmd.get("probability", 0) >= COMMAND_PROBABILITY_LOW_THRESHOLD
        ]
        
        # Sort by probability
        high_threshold_commands.sort(key=lambda x: x.get("probability", 0), reverse=True)
        low_threshold_commands.sort(key=lambda x: x.get("probability", 0), reverse=True)
        
        if len(high_threshold_commands) == 1:
            # Single high probability command - execute directly
            cmd_data = high_threshold_commands[0]
            command_name = cmd_data.get("name")
            
            # Check if command requires parameters and extract them separately
            parameters = {}
            command = command_handler.commands.get(command_name)
            if command and command.requires_parameters():
                # Extract parameters separately using ChatGPT
                parameters_description = command.human_readable_parameters()
                extraction_result = chatgpt.extract_parameters_for_command(
                    command_name, user_message, parameters_description
                )
                if extraction_result.get("success"):
                    parameters = extraction_result.get("parameters", {})
                # If extraction failed, parameters will be empty and command will handle it
            
            event = await command_handler.execute_command(
                command_name, parameters, update=update, context=context, chatgpt_client=chatgpt
            )
            
            # Update state and store command
            new_state = state_machine.perform_transition(current_state, event) or current_state
            context.user_data["user_state"] = new_state
            if event == Event.COMMAND_EXECUTED:
                context.user_data["current_command"] = None
            else:
                context.user_data["current_command"] = command_name
        
        elif len(high_threshold_commands) > 1:
            # Multiple high probability commands - unclear
            event = Event.COMMAND_UNCLEAR
            new_state = state_machine.perform_transition(current_state, event) or current_state
            context.user_data["user_state"] = new_state
            
            # Send clarification message
            cmd_list = "\n".join([
                f"{i+1}. {cmd.get('name')} (вероятность: {cmd.get('probability', 0):.0f}%)"
                for i, cmd in enumerate(high_threshold_commands)
            ])
            await message_obj.reply_text(
                f"Понял вас, сэр/мадам. Я определил несколько команд, которые могут соответствовать вашему запросу:\n\n"
                f"{cmd_list}\n\n"
                f"Будьте так любезны, уточните и повторите ваш запрос."
            )
        
        elif len(low_threshold_commands) > 0:
            # Some low probability commands - unclear
            event = Event.COMMAND_UNCLEAR
            new_state = state_machine.perform_transition(current_state, event) or current_state
            context.user_data["user_state"] = new_state
            
            # Send clarification message
            cmd_list = "\n".join([
                f"{i+1}. {cmd.get('name')} (вероятность: {cmd.get('probability', 0):.0f}%)"
                for i, cmd in enumerate(low_threshold_commands)
            ])
            await message_obj.reply_text(
                f"Понял вас, сэр/мадам. Я определил несколько возможных команд, которые могут соответствовать вашему запросу:\n\n"
                f"{cmd_list}\n\n"
                f"Будьте так любезны, уточните и повторите ваш запрос."
            )
        
        else:
            # No commands found - unclear
            event = Event.COMMAND_UNCLEAR
            new_state = state_machine.perform_transition(current_state, event) or current_state
            context.user_data["user_state"] = new_state
            
            # Check if it's conversational
            intent_analysis = chatgpt.analyze_message_intent(user_message)
            is_command_request = intent_analysis.get("is_command_request", True)
            should_respond = intent_analysis.get("should_respond", False)
            intent_type = intent_analysis.get("intent_type", "other")
            
            if not is_command_request and should_respond:
                # Conversational - respond
                response = chatgpt.generate_conversational_response(user_message, intent_type)
                await message_obj.reply_text(response)
            else:
                # Command request that wasn't understood - ask for clarification
                clarification_message = chatgpt.generate_clarification(user_message, available_commands)
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
    application.add_handler(CommandHandler("random_number", generate_random_number))
    application.add_handler(CommandHandler("silence", silence))
    
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
