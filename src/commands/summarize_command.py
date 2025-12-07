"""Summarize command implementation."""
from .base import BaseCommand
from typing import Optional, List
import logging
import sys
import os
from datetime import datetime, timedelta
import pytz

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.state_machine import Event
from redis_client import redis_client
from mtproto_client import get_mtproto_client
from chatgpt_client import ChatGPTClient

utc = pytz.UTC
logger = logging.getLogger(__name__)


class SummarizeCommand(BaseCommand):
    """Command to summarize recent chat messages."""
    
    def __init__(self):
        super().__init__(
            name="summarize",
            description="Суммаризировать обсуждения за указанный период или количество сообщений (минимум: 15 сообщений или 30 минут, максимум: 1000 сообщений или 24 часа)"
        )
        self.chatgpt = ChatGPTClient()
    
    def validate_parameters(self, parameters: dict = None) -> tuple[bool, str | None]:
        """Validate parameters (message_count or time_window_hours).
        
        Note: This method allows missing parameters - extraction will happen in execute().
        """
        params = parameters or {}
        
        message_count = params.get("message_count")
        time_window_hours = params.get("time_window_hours")
        
        # Allow missing parameters - they will be extracted in execute() if user_message is provided
        # Only validate if parameters are already provided
        
        # Validate message_count if provided
        if message_count is not None:
            try:
                message_count = int(message_count)
                if message_count < 15:
                    return False, "Минимальное количество сообщений для анализа: 15. Пожалуйста, укажите не менее 15 сообщений."
                if message_count > 1000:
                    return False, "Максимальное количество сообщений для анализа: 1000. Пожалуйста, укажите не более 1000 сообщений."
                # Update params with converted value
                params["message_count"] = message_count
            except (ValueError, TypeError):
                return False, "Количество сообщений должно быть целым числом."
        
        # Validate time_window_hours if provided
        if time_window_hours is not None:
            try:
                time_window_hours = float(time_window_hours)
                if time_window_hours < 0.5:  # 30 minutes
                    return False, "Минимальный временной период для анализа: 30 минут. Пожалуйста, укажите период не менее 30 минут."
                if time_window_hours > 24:
                    return False, "Максимальный временной период для анализа: 24 часа. Пожалуйста, укажите период не более 24 часов."
                # Update params with converted value
                params["time_window_hours"] = time_window_hours
            except (ValueError, TypeError):
                return False, "Временной период должен быть числом."
        
        return True, None
    
    async def execute(
        self, 
        parameters: dict = None, 
        update=None,
        context=None,
        chatgpt_client=None
    ) -> Event:
        """
        Execute the summarize command.
        
        Args:
            parameters: Dictionary with 'message_count' (int) or 'time_window_hours' (float)
            update: Telegram Update object
            context: Bot context
            chatgpt_client: ChatGPT client instance
            
        Returns:
            Event enum
        """
        message_obj = update.message if update.message else update.channel_post
        if not message_obj:
            return Event.COMMAND_EXECUTED
        
        chat_id = message_obj.chat.id
        user_message = message_obj.text if message_obj.text else None
        
        if not chat_id:
            await message_obj.reply_text("Прошу прощения, сэр/мадам, но контекст чата недоступен для этой команды.")
            return Event.COMMAND_EXECUTED
        
        params = parameters or {}
        message_count = params.get("message_count")
        time_window_hours = params.get("time_window_hours")
        
        # Step 1: If parameters are not provided, try to extract from user message
        if not message_count and not time_window_hours and user_message and chatgpt_client:
            logger.info(f"Attempting to extract summarize parameters from user message: {user_message}")
            extraction_result = chatgpt_client.extract_summarize_parameters(user_message)
            
            if extraction_result.get("success"):
                # Parameters extracted successfully
                if extraction_result.get("message_count"):
                    message_count = extraction_result["message_count"]
                    params["message_count"] = message_count
                elif extraction_result.get("time_window_hours"):
                    time_window_hours = extraction_result["time_window_hours"]
                    params["time_window_hours"] = time_window_hours
                logger.info(f"Extracted parameters: message_count={message_count}, time_window_hours={time_window_hours}")
            else:
                # Extraction failed - ask user to provide explicitly
                reasoning = extraction_result.get("reasoning", "Не удалось определить параметры")
                logger.info(f"Parameter extraction failed: {reasoning}")
                await message_obj.reply_text(
                    "Прошу прощения, сэр/мадам. Я не смог определить параметры для суммирования из вашего сообщения.\n\n"
                    "Пожалуйста, укажите явно:\n"
                    "- Либо количество сообщений (например, 'последние 300 сообщений', минимум 15, максимум 1000)\n"
                    "- Либо временной период (например, 'за последний час', 'за последние 3 часа', минимум 30 минут, максимум 24 часа)"
                )
                return Event.PARAMETERS_UNCLEAR
        
        # Step 2: Validate parameters (convert types and check constraints)
        if message_count is not None:
            try:
                message_count = int(message_count)
                if message_count < 15:
                    await message_obj.reply_text("Минимальное количество сообщений для анализа: 15. Пожалуйста, укажите не менее 15 сообщений.")
                    return Event.PARAMETERS_UNCLEAR
                if message_count > 1000:
                    await message_obj.reply_text("Максимальное количество сообщений для анализа: 1000. Пожалуйста, укажите не более 1000 сообщений.")
                    return Event.PARAMETERS_UNCLEAR
                params["message_count"] = message_count
            except (ValueError, TypeError):
                await message_obj.reply_text("Количество сообщений должно быть целым числом. Пожалуйста, укажите корректное количество (например, '300 сообщений').")
                return Event.PARAMETERS_UNCLEAR
        
        if time_window_hours is not None:
            try:
                time_window_hours = float(time_window_hours)
                if time_window_hours < 0.5:
                    await message_obj.reply_text("Минимальный временной период для анализа: 30 минут. Пожалуйста, укажите период не менее 30 минут.")
                    return Event.PARAMETERS_UNCLEAR
                if time_window_hours > 24:
                    await message_obj.reply_text("Максимальный временной период для анализа: 24 часа. Пожалуйста, укажите период не более 24 часов.")
                    return Event.PARAMETERS_UNCLEAR
                params["time_window_hours"] = time_window_hours
            except (ValueError, TypeError):
                await message_obj.reply_text("Временной период должен быть числом. Пожалуйста, укажите корректный период (например, 'за последний час' или 'за последние 3 часа').")
                return Event.PARAMETERS_UNCLEAR
        
        # Step 3: If still no parameters, ask user to provide explicitly
        if not message_count and not time_window_hours:
            await message_obj.reply_text(
                "Прошу прощения, сэр/мадам. Для суммирования необходимо указать параметры.\n\n"
                "Пожалуйста, укажите:\n"
                "- Либо количество сообщений (например, 'последние 300 сообщений', минимум 15, максимум 1000)\n"
                "- Либо временной период (например, 'за последний час', 'за последние 3 часа', минимум 30 минут, максимум 24 часа)"
            )
            return Event.PARAMETERS_UNCLEAR
        
        # Step 4: Update local variables from validated params
        message_count = params.get("message_count")
        time_window_hours = params.get("time_window_hours")
        
        try:
            # Get messages from Redis
            if message_count is not None:
                # Get by count
                redis_messages = redis_client.get_messages_by_count(chat_id, message_count)
            else:
                # Get by time range
                end_time = datetime.now(utc)
                start_time = end_time - timedelta(hours=time_window_hours)
                redis_messages = redis_client.get_messages_by_time_range(chat_id, start_time, end_time)
            
            if not redis_messages:
                if message_count:
                    await message_obj.reply_text(f"Прошу прощения, сэр/мадам, но не найдено сообщений для анализа (запрошено: {message_count}).")
                else:
                    hours_text = "часов" if time_window_hours >= 2 else "часа" if time_window_hours >= 1 else "минут"
                    await message_obj.reply_text(f"Прошу прощения, сэр/мадам, но не найдено сообщений за последние {int(time_window_hours * 60) if time_window_hours < 1 else int(time_window_hours)} {hours_text}.")
                return Event.COMMAND_EXECUTED
            
            # Parse message IDs from Redis format: "{user_id}:{message_id}"
            message_data = []
            for msg_value, timestamp in redis_messages:
                try:
                    user_id_str, message_id_str = msg_value.split(":", 1)
                    message_data.append({
                        "user_id": int(user_id_str),
                        "message_id": int(message_id_str),
                        "timestamp": timestamp
                    })
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not parse message value '{msg_value}': {e}")
                    continue
            
            if not message_data:
                await message_obj.reply_text("Прошу прощения, сэр/мадам, но не удалось обработать сообщения.")
                return Event.COMMAND_EXECUTED
            
            # Get full message content from MTProto
            mtproto = get_mtproto_client()
            await mtproto.start()
            
            try:
                # Extract message IDs
                message_ids = [msg["message_id"] for msg in message_data]
                
                # Get messages from Telegram
                # Note: chat_id might need to be negative for groups/channels
                # Try both positive and negative
                telegram_messages = await mtproto.get_messages(chat_id, message_ids)
                
                # Check if we got any valid messages
                valid_messages = [m for m in telegram_messages if m is not None]
                
                # Also try with negative chat_id (for groups/channels) if no messages found
                if not valid_messages:
                    telegram_messages = await mtproto.get_messages(-abs(chat_id), message_ids)
                
                # Build messages list for OpenAI
                messages_for_openai = []
                message_dict = {msg["message_id"]: msg for msg in message_data}
                
                # Collect all unique user IDs
                unique_user_ids = set()
                for msg_data in message_data:
                    user_id = msg_data.get("user_id")
                    if user_id:
                        unique_user_ids.add(user_id)
                
                # Fetch user names for all unique user IDs
                user_id_to_name = {}
                bot = context.bot if context else None
                
                if bot:
                    for user_id in unique_user_ids:
                        try:
                            chat_member = await bot.get_chat_member(chat_id, user_id)
                            user = chat_member.user
                            user_name = user.first_name or ""
                            if user.last_name:
                                user_name += f" {user.last_name}" if user_name else user.last_name
                            if user.username:
                                user_name += f" (@{user.username})" if user_name else f"@{user.username}"
                            if not user_name:
                                user_name = f"User {user_id}"
                            user_id_to_name[user_id] = user_name
                        except Exception as e:
                            logger.warning(f"Could not get user info for {user_id}: {e}")
                            user_id_to_name[user_id] = f"User {user_id}"
                else:
                    # Fallback if bot is not available
                    for user_id in unique_user_ids:
                        user_id_to_name[user_id] = f"User {user_id}"
                
                for i, tg_msg in enumerate(telegram_messages):
                    if tg_msg is None:
                        continue
                    
                    msg_id = tg_msg.id
                    msg_data = message_dict.get(msg_id, {})
                    
                    # Get message text
                    text = ""
                    if hasattr(tg_msg, 'message') and tg_msg.message:
                        text = tg_msg.message
                    elif hasattr(tg_msg, 'text') and tg_msg.text:
                        text = tg_msg.text
                    
                    if not text:
                        continue
                    
                    user_id = msg_data.get("user_id", 0)
                    user_name = user_id_to_name.get(user_id, f"User {user_id}")
                    
                    messages_for_openai.append({
                        "user_id": user_name,  # Use user name instead of user_id
                        "message_id": msg_id,
                        "text": text,
                        "timestamp": msg_data.get("timestamp", 0)
                    })
                
                if not messages_for_openai:
                    await message_obj.reply_text("Прошу прощения, сэр/мадам, но не удалось получить содержимое сообщений.")
                    return Event.COMMAND_EXECUTED
                
                # Summarize using OpenAI
                summary_result = chatgpt_client.summarize_messages(messages_for_openai)
                topics = summary_result.get("topics", [])
                
                if not topics:
                    await message_obj.reply_text("Прошу прощения, сэр/мадам, но не удалось определить темы обсуждения.")
                    return Event.COMMAND_EXECUTED
                
                # Cache topics in Redis
                for topic in topics:
                    topic_handle = topic.get("topic_handle")
                    if topic_handle:
                        redis_client.cache_topic_summary(chat_id, topic_handle, topic)
                
                # Build response - always show topics list (no breakdown)
                response = self._format_topics_list_response(topics, chat_id, message_count, time_window_hours)
                await message_obj.reply_text(response, parse_mode="Markdown")
                return Event.COMMAND_EXECUTED
                    
            finally:
                await mtproto.stop()
                
        except Exception as e:
            logger.error(f"Error in Summarize command: {e}")
            await message_obj.reply_text(f"Прошу прощения, сэр/мадам, но произошла ошибка при выполнении команды: {str(e)}")
            return Event.COMMAND_EXECUTED
    
    def _format_topics_list_response(
        self, 
        topics: List[dict], 
        chat_id: int,
        message_count: Optional[int],
        time_window_hours: Optional[float]
    ) -> str:
        """Format response showing list of topics (no breakdown)."""
        # Build time/message count text
        if message_count:
            time_text = f"последние {message_count} сообщений"
        else:
            hours = int(time_window_hours) if time_window_hours else 0
            if hours == 1:
                time_text = "последний час"
            elif hours in [2, 3, 4]:
                time_text = f"последние {hours} часа"
            else:
                time_text = f"последние {hours} часов"
        
        response = f"Конечно, сэр/мадам. За {time_text} обсуждалось несколько тем:\n\n"
        
        for i, topic in enumerate(topics, 1):
            description = topic.get("description", topic.get("topic_handle", "Тема"))
            message_count_topic = topic.get("message_count", 0)
            response += f"{i}. {description} ({message_count_topic} сообщений)\n"
        
        response += "\nЕсли вы хотите разобрать какую-то тему подробнее, просто попросите меня об этом."
        
        return response

