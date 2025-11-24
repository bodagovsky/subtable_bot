"""Silence command implementation."""
from .base import BaseCommand
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from silence_state import silence_state


class SilenceCommand(BaseCommand):
    """Command to stop listening for messages and responding to them unless explicitly asked."""
    
    def __init__(self):
        super().__init__(
            name="silence",
            description="Перестать читать сообщения и отвечать на них (или возобновить работу)"
        )
    
    async def execute(self, parameters: dict = None, bot=None, chat_id: int = None) -> str:
        """
        Execute the silence command - toggle silence state.
        
        Args:
            parameters: Not used
            bot: Telegram bot instance
            chat_id: Chat ID to toggle silence for
            
        Returns:
            Response message
        """
        if not chat_id:
            return "Прошу прощения, сэр/мадам, но не удалось определить чат."
        
        # Toggle silence state
        is_now_silenced = silence_state.toggle_silence(chat_id)
        
        if is_now_silenced:
            return "Как скажете, сэр/мадам. Я больше не буду хранить сообщения и отвечать на них. Если я снова понадоблюсь, просто позовите меня - и я к вашим услугам."
        else:
            return "К вашим услугам, сэр/мадам. Я снова готов слушать и отвечать на ваши запросы."