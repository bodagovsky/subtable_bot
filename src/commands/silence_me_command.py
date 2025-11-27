"""SilenceMe command implementation - ignore specific user's messages."""
from .base import BaseCommand
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from user_ignore_list import user_ignore_list


class SilenceMeCommand(BaseCommand):
    """Command to ignore messages from a specific user."""
    
    def __init__(self):
        super().__init__(
            name="silence_me",
            description="Попросить бота игнорировать ваши сообщения (или отменить игнорирование)"
        )
    
    async def execute(self, parameters: dict = None, bot=None, chat_id: int = None, user_id: int = None) -> str:
        """
        Execute the silence_me command - toggle ignore state for the user.
        
        Args:
            parameters: Not used
            bot: Telegram bot instance
            chat_id: Chat ID (not used, but kept for consistency)
            user_id: User ID to toggle ignore for
            
        Returns:
            Response message
        """
        if not user_id:
            return "Прошу прощения, сэр/мадам, но не удалось определить пользователя."
        
        # Check current state
        was_ignored = user_ignore_list.is_ignored(user_id)
        
        # Toggle ignore state
        is_now_ignored = user_ignore_list.toggle_user(user_id)
        
        if is_now_ignored:
            return "Как скажете, сэр/мадам. Я буду игнорировать ваши сообщения. Если вы захотите, чтобы я снова отвечал вам, просто попросите отменить игнорирование."
        else:
            if was_ignored:
                return "К вашим услугам, сэр/мадам. Я снова буду обрабатывать ваши сообщения."
            else:
                return "К вашим услугам, сэр/мадам. Вы не были в списке игнорируемых пользователей."

