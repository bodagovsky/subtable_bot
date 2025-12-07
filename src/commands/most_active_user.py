"""MostActiveUser command implementation."""
from .base import BaseCommand
from typing import Optional
from telegram import Bot
from collections import Counter
import logging
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from message_storage import message_storage
from tools.state_machine import Event

logger = logging.getLogger(__name__)


class MostActiveUserCommand(BaseCommand):
    """Command to find the most active users in a chat within a time window."""
    
    def __init__(self):
        super().__init__(
            name="most_active_user",
            description="Найти топ-3 самых активных пользователей в чате за указанный временной период (максимум 1 неделя)"
        )
    
    def validate_parameters(self, parameters: dict = None) -> tuple[bool, str | None]:
        """Validate that time_window_hours is a valid positive number <= 168 hours."""
        params = parameters or {}
        time_window_hours = params.get("time_window_hours")
        
        if not time_window_hours:
            return False, "Временной период не был указан. Пожалуйста, укажите временной период (например, 'за последний день', 'за последние 3 часа')."
        
        try:
            time_window_hours = float(time_window_hours)
        except (ValueError, TypeError):
            return False, "Временной период должен быть числом. Пожалуйста, укажите корректный временной период (например, 'за последний день', 'за последние 3 часа')."
        
        # Validate time window (max 1 week = 168 hours)
        if time_window_hours > 168:
            return False, "Временной период не может превышать одну неделю (168 часов). Пожалуйста, укажите период не более одной недели."
        
        if time_window_hours <= 0:
            return False, "Временной период должен быть положительным числом. Пожалуйста, укажите корректный временной период."
        
        return True, None
    
    async def execute(self, parameters: dict = None, update=None, context=None, chatgpt_client=None) -> Event:
        """
        Execute the command.
        
        Args:
            parameters: Dictionary containing 'time_window_hours' (in hours)
            update: Telegram Update object
            context: Bot context
            chatgpt_client: Not used
            
        Returns:
            Event enum
        """
        
        message_obj = update.message if update.message else update.channel_post
        if not message_obj:
            return Event.COMMAND_EXECUTED
        
        bot = context.bot if context else None
        chat_id = message_obj.chat.id
        
        if not bot or not chat_id:
            await message_obj.reply_text("Прошу прощения, сэр/мадам, но контекст бота недоступен для этой команды.")
            return Event.COMMAND_EXECUTED
        
        params = parameters or {}
        time_window_hours = params.get("time_window_hours")
        
        # Convert to float (should already be validated)
        try:
            time_window_hours = float(time_window_hours)
        except (ValueError, TypeError):
            await message_obj.reply_text("Прошу прощения, сэр/мадам, но формат временного периода неверен.")
            return Event.PARAMETERS_UNCLEAR
        
        try:
            # Get user counts from message storage
            user_counts = message_storage.get_user_counts(chat_id, time_window_hours)
            
            if not user_counts:
                hours_text = "часов" if time_window_hours != 1 else "час"
                if time_window_hours in [2, 3, 4]:
                    hours_text = "часа"
                await message_obj.reply_text(f"Прошу прощения, сэр/мадам, но сообщений не найдено за последние {int(time_window_hours)} {hours_text}.")
                return Event.COMMAND_EXECUTED
            
            # Get top 3 users
            top_users = Counter(user_counts).most_common(3)
            
            # Format response
            hours_text = "часов" if time_window_hours != 1 else "час"
            if time_window_hours in [2, 3, 4]:
                hours_text = "часа"
            response = f"К вашим услугам, сэр/мадам. **Топ-3 самых активных пользователей за последние {int(time_window_hours)} {hours_text}:**\n\n"
            
            for i, (user_id, count) in enumerate(top_users, 1):
                try:
                    # Get user info using bot API
                    chat_member = await bot.get_chat_member(chat_id, user_id)
                    user = chat_member.user
                    user_name = user.first_name or "Неизвестно"
                    if user.last_name:
                        user_name += f" {user.last_name}"
                    if user.username:
                        user_name += f" (@{user.username})"
                    messages_text = "сообщений" if count % 10 in [0, 5, 6, 7, 8, 9] or count % 100 in [11, 12, 13, 14] else "сообщения" if count % 10 in [2, 3, 4] else "сообщение"
                    response += f"{i}. {user_name}: {count} {messages_text}\n"
                except Exception as e:
                    logger.warning(f"Could not get user info for {user_id}: {e}")
                    # If we can't get user info, use user ID
                    messages_text = "сообщений" if count % 10 in [0, 5, 6, 7, 8, 9] or count % 100 in [11, 12, 13, 14] else "сообщения" if count % 10 in [2, 3, 4] else "сообщение"
                    response += f"{i}. Пользователь {user_id}: {count} {messages_text}\n"
            
            await message_obj.reply_text(response, parse_mode="Markdown")
            return Event.COMMAND_EXECUTED
            
        except Exception as e:
            logger.error(f"Error in MostActiveUser command: {e}")
            await message_obj.reply_text(f"Прошу прощения, сэр/мадам, но произошла ошибка при выполнении команды: {str(e)}")
            return Event.COMMAND_EXECUTED

