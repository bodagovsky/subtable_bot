"""Example command implementations."""
from .base import BaseCommand
from datetime import datetime
import random
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.state_machine import Event


class TimeCommand(BaseCommand):
    """Command to get current time."""
    
    def __init__(self):
        super().__init__(
            name="get_time",
            description="Получить текущую дату и время"
        )
    
    async def execute(self, parameters: dict = None, update=None, context=None, chatgpt_client=None) -> Event:
        now = datetime.now()
        message = f"К вашим услугам, сэр/мадам. Текущее время: {now.strftime('%Y-%m-%d %H:%M:%S')}"
        message_obj = update.message if update.message else update.channel_post
        if message_obj:
            await message_obj.reply_text(message)
        return Event.COMMAND_EXECUTED


class RandomNumberCommand(BaseCommand):
    """Command to generate a random number."""
    
    def __init__(self):
        super().__init__(
            name="random_number",
            description="Сгенерировать случайное число между min и max (по умолчанию: 1-100)"
        )
    
    def validate_parameters(self, parameters: dict = None) -> tuple[bool, str | None]:
        """Validate that min and max are valid integers."""
        params = parameters or {}
        
        # If no parameters provided, use defaults (valid)
        if "min" not in params and "max" not in params:
            return True, None
        
        # Validate min if provided
        if "min" in params:
            try:
                int(params["min"])
            except (ValueError, TypeError):
                return False, "Параметр 'min' должен быть целым числом. Пожалуйста, укажите корректное минимальное значение."
        
        # Validate max if provided
        if "max" in params:
            try:
                int(params["max"])
            except (ValueError, TypeError):
                return False, "Параметр 'max' должен быть целым числом. Пожалуйста, укажите корректное максимальное значение."
        
        
        return True, None
    
    async def execute(self, parameters: dict = None, update=None, context=None, chatgpt_client=None) -> Event:
        params = parameters or {}
        min_val = int(params.get("min", 1))
        max_val = int(params.get("max", 100))
        number = random.randint(min_val, max_val)
        message = f"Как вам будет угодно, сэр/мадам. Случайное число: {number}"
        message_obj = update.message if update.message else update.channel_post
        if message_obj:
            await message_obj.reply_text(message)
        return Event.COMMAND_EXECUTED


class EchoCommand(BaseCommand):
    """Command to echo back a message."""
    
    def __init__(self):
        super().__init__(
            name="echo",
            description="Повторить сообщение или текст"
        )
    
    async def execute(self, parameters: dict = None, update=None, context=None, chatgpt_client=None) -> Event:
        params = parameters or {}
        echo_message = params.get("message", "Сообщение не предоставлено")
        message = f"Конечно, сэр/мадам. Эхо: {echo_message}"
        message_obj = update.message if update.message else update.channel_post
        if message_obj:
            await message_obj.reply_text(message)
        return Event.COMMAND_EXECUTED

