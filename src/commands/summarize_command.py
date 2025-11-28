"""Summarize command implementation."""
from .base import BaseCommand
from typing import Optional, List, Dict
from telegram import Bot
import logging
import sys
import os
from datetime import datetime, timedelta
import pytz

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from redis_client import redis_client
from mtproto_client import get_mtproto_client
from chatgpt_client import ChatGPTClient
from config import COMMAND_PROBABILITY_HIGH_THRESHOLD, COMMAND_PROBABILITY_LOW_THRESHOLD

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
        """Validate parameters (message_count or time_window_hours)."""
        params = parameters or {}
        
        message_count = params.get("message_count")
        time_window_hours = params.get("time_window_hours")
        
        # Must have either message_count or time_window_hours
        if not message_count and not time_window_hours:
            return False, "Пожалуйста, укажите либо количество сообщений (например, 'последние 300 сообщений'), либо временной период (например, 'за последний час')."
        
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
        bot: Optional[Bot] = None, 
        chat_id: Optional[int] = None
    ) -> str:
        """
        Execute the summarize command.
        
        Args:
            parameters: Dictionary with 'message_count' (int) or 'time_window_hours' (float)
            bot: Telegram bot instance
            chat_id: Chat ID
            
        Returns:
            Response message with summary or topic list
        """
        if not chat_id:
            return "Прошу прощения, сэр/мадам, но контекст чата недоступен для этой команды."
        
        params = parameters or {}
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
                    return f"Прошу прощения, сэр/мадам, но не найдено сообщений для анализа (запрошено: {message_count})."
                else:
                    hours_text = "часов" if time_window_hours >= 2 else "часа" if time_window_hours >= 1 else "минут"
                    return f"Прошу прощения, сэр/мадам, но не найдено сообщений за последние {int(time_window_hours * 60) if time_window_hours < 1 else int(time_window_hours)} {hours_text}."
            
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
                return "Прошу прощения, сэр/мадам, но не удалось обработать сообщения."
            
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
                    
                    messages_for_openai.append({
                        "user_id": msg_data.get("user_id", 0),
                        "message_id": msg_id,
                        "text": text,
                        "timestamp": msg_data.get("timestamp", 0)
                    })
                
                if not messages_for_openai:
                    return "Прошу прощения, сэр/мадам, но не удалось получить содержимое сообщений."
                
                # Summarize using OpenAI
                summary_result = self.chatgpt.summarize_messages(messages_for_openai)
                topics = summary_result.get("topics", [])
                
                if not topics:
                    return "Прошу прощения, сэр/мадам, но не удалось определить темы обсуждения."
                
                # Cache topics in Redis
                for topic in topics:
                    topic_handle = topic.get("topic_handle")
                    if topic_handle:
                        redis_client.cache_topic_summary(chat_id, topic_handle, topic)
                
                # Build response
                if len(topics) == 1:
                    # Single topic - show breakdown directly
                    topic = topics[0]
                    return self._format_single_topic_response(topic, chat_id, message_count, time_window_hours)
                else:
                    # Multiple topics - ask user to choose
                    return self._format_multiple_topics_response(topics, chat_id, message_count, time_window_hours)
                    
            finally:
                await mtproto.stop()
                
        except Exception as e:
            logger.error(f"Error in Summarize command: {e}")
            return f"Прошу прощения, сэр/мадам, но произошла ошибка при выполнении команды: {str(e)}"
    
    def _format_single_topic_response(
        self, 
        topic: dict, 
        chat_id: int, 
        message_count: Optional[int],
        time_window_hours: Optional[float]
    ) -> str:
        """Format response for single topic."""
        description = topic.get("description", topic.get("topic_handle", "Тема"))
        message_count_topic = topic.get("message_count", 0)
        summary = topic.get("summary", "")
        start_message_id = topic.get("start_message", {}).get("message_id", 0)
        
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
        
        # Build message link
        # Telegram links use channel ID without the -100 prefix for groups/channels
        # For example: -1001234567890 becomes 1234567890 in the link
        link_chat_id = str(abs(chat_id))
        if len(link_chat_id) > 10 and link_chat_id.startswith("100"):
            link_chat_id = link_chat_id[3:]  # Remove -100 prefix for groups/channels
        message_link = f"https://t.me/c/{link_chat_id}/{start_message_id}" if start_message_id else ""
        
        response = f"Конечно, сэр/мадам. За {time_text} обсуждалась тема **{description}** ({message_count_topic} сообщений).\n\n"
        
        if message_link:
            response += f"[Начало обсуждения]({message_link})\n\n"
        
        # Format summary points
        if summary:
            # Split summary by newlines or numbers
            points = summary.split("\n")
            formatted_points = []
            for point in points:
                point = point.strip()
                if point:
                    # Remove leading numbers if present
                    if point and point[0].isdigit():
                        point = point.split(".", 1)[-1].strip()
                    if point:
                        formatted_points.append(point)
            
            if formatted_points:
                for i, point in enumerate(formatted_points, 1):
                    response += f"{i}. {point}\n"
        
        return response
    
    def _format_multiple_topics_response(
        self, 
        topics: List[dict], 
        chat_id: int,
        message_count: Optional[int],
        time_window_hours: Optional[float]
    ) -> str:
        """Format response for multiple topics - ask user to choose."""
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
        
        response += "\nКакую тему вы хотите, чтобы я разобрал подробнее?"
        
        return response

