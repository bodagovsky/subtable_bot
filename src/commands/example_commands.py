"""Example command implementations."""
from .base import BaseCommand
from datetime import datetime
import random


class TimeCommand(BaseCommand):
    """Command to get current time."""
    
    def __init__(self):
        super().__init__(
            name="get_time",
            description="Get the current date and time"
        )
    
    def execute(self, parameters: dict = None) -> str:
        now = datetime.now()
        return f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}"


class RandomNumberCommand(BaseCommand):
    """Command to generate a random number."""
    
    def __init__(self):
        super().__init__(
            name="random_number",
            description="Generate a random number between min and max (default: 1-100)"
        )
    
    def execute(self, parameters: dict = None) -> str:
        params = parameters or {}
        min_val = int(params.get("min", 1))
        max_val = int(params.get("max", 100))
        number = random.randint(min_val, max_val)
        return f"Random number: {number}"


class EchoCommand(BaseCommand):
    """Command to echo back a message."""
    
    def __init__(self):
        super().__init__(
            name="echo",
            description="Echo back a message or text"
        )
    
    def execute(self, parameters: dict = None) -> str:
        params = parameters or {}
        message = params.get("message", "No message provided")
        return f"Echo: {message}"

