"""Example command implementations."""
from .base import BaseCommand
from datetime import datetime
import random


class TimeCommand(BaseCommand):
    """Command to get current time."""
    
    def __init__(self):
        super().__init__(
            name="get_time",
            description="Получить текущую дату и время"
        )
    
    async def execute(self, parameters: dict = None) -> str:
        now = datetime.now()
        return f"К вашим услугам, сэр/мадам. Текущее время: {now.strftime('%Y-%m-%d %H:%M:%S')}"


class RandomNumberCommand(BaseCommand):
    """Command to generate a random number."""
    
    def __init__(self):
        super().__init__(
            name="random_number",
            description="Сгенерировать случайное число между min и max (по умолчанию: 1-100)"
        )
    
    async def execute(self, parameters: dict = None) -> str:
        params = parameters or {}
        min_val = int(params.get("min", 1))
        max_val = int(params.get("max", 100))
        number = random.randint(min_val, max_val)
        return f"Как вам будет угодно, сэр/мадам. Случайное число: {number}"


class EchoCommand(BaseCommand):
    """Command to echo back a message."""
    
    def __init__(self):
        super().__init__(
            name="echo",
            description="Повторить сообщение или текст"
        )
    
    async def execute(self, parameters: dict = None) -> str:
        params = parameters or {}
        message = params.get("message", "Сообщение не предоставлено")
        return f"Конечно, сэр/мадам. Эхо: {message}"

