"""SilenceMe command implementation - ignore specific user's messages."""
from .base import BaseCommand
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.state_machine import Event
from user_ignore_list import user_ignore_list


class SilenceMeCommand(BaseCommand):
    """Command to ignore messages from a specific user."""
    
    def __init__(self):
        super().__init__(
            name="silence_me",
            description="Попросить бота игнорировать ваши сообщения (или отменить игнорирование)"
        )
    
    async def execute(self, parameters: dict = None, update=None, context=None, chatgpt_client=None) -> Event:
        """
        Execute the silence_me command - toggle ignore state for the user.
        
        Args:
            parameters: Not used
            update: Telegram Update object
            context: Bot context
            chatgpt_client: Not used
            
        Returns:
            Event enum
        """
        message_obj = update.message if update.message else update.channel_post
        if not message_obj:
            return Event.COMMAND_EXECUTED
        
        user_id = message_obj.from_user.id if message_obj.from_user else None
        
        if not user_id:
            await message_obj.reply_text("Прошу прощения, сэр/мадам, но не удалось определить пользователя.")
            return Event.COMMAND_EXECUTED
        
        # Check current state
        was_ignored = user_ignore_list.is_ignored(user_id)
        
        # Toggle ignore state
        is_now_ignored = user_ignore_list.toggle_user(user_id)
        
        if is_now_ignored:
            await message_obj.reply_text("Как скажете, сэр/мадам. Я буду игнорировать ваши сообщения. Если вы захотите, чтобы я снова отвечал вам, просто попросите отменить игнорирование.")
            return Event.IGNORE_USER
        else:
            if was_ignored:
                await message_obj.reply_text("К вашим услугам, сэр/мадам. Я снова буду обрабатывать ваши сообщения.")
                return Event.STOP_IGNORING
            else:
                await message_obj.reply_text("К вашим услугам, сэр/мадам. Вы не были в списке игнорируемых пользователей.")
                return Event.COMMAND_EXECUTED

