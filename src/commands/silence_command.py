"""Silence command implementation."""
from .base import BaseCommand
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.state_machine import Event
from redis_client import redis_client


class SilenceCommand(BaseCommand):
    """Command to stop listening for messages and responding to them unless explicitly asked."""
    
    def __init__(self):
        super().__init__(
            name="silence",
            description="Перестать читать сообщения и отвечать на них (или возобновить работу)"
        )
    
    async def execute(self, parameters: dict = None, update=None, context=None, chatgpt_client=None) -> Event:
        """
        Execute the silence command - toggle silence state using Redis.
        
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
        
        chat_id = message_obj.chat.id
        user_id = message_obj.from_user.id if message_obj.from_user else None
        
        if not chat_id or not user_id:
            await message_obj.reply_text("Прошу прощения, сэр/мадам, но не удалось определить чат или пользователя.")
            return Event.COMMAND_EXECUTED
        
        # Check if bot is currently silenced
        is_silenced = redis_client.is_bot_silenced(chat_id)
        
        if is_silenced:
            # Check if this user is the one who silenced
            silence_user_id = redis_client.get_silence_user_id(chat_id)
            if silence_user_id == user_id:
                # Unsilence
                redis_client.unsilence_bot(chat_id)
                await message_obj.reply_text("К вашим услугам, сэр/мадам. Я снова готов слушать и отвечать на ваши запросы.")
            else:
                # Different user trying to unsilence - ignore
                await message_obj.reply_text("Прошу прощения, сэр/мадам, но только пользователь, который меня заглушил, может меня разбудить.")
        else:
            # Silence the bot
            redis_client.set_bot_silenced(chat_id, user_id)
            await message_obj.reply_text("Как скажете, сэр/мадам. Я больше не буду хранить сообщения и отвечать на них. Если я снова понадоблюсь, просто позовите меня - и я к вашим услугам.")
        
        return Event.COMMAND_EXECUTED