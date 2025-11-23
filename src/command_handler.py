"""Command handler for managing and executing bot commands."""
from typing import Dict, List
from commands.base import BaseCommand
from commands.example_commands import (
    TimeCommand,
    RandomNumberCommand,
    EchoCommand
)
from commands.most_active_user import MostActiveUserCommand


class CommandHandler:
    """Manages bot commands and their execution."""
    
    def __init__(self):
        self.commands: Dict[str, BaseCommand] = {}
        self._register_default_commands()
    
    def _register_default_commands(self):
        """Register default commands."""
        default_commands = [
            TimeCommand(),
            RandomNumberCommand(),
            EchoCommand(),
            MostActiveUserCommand()
        ]
        for cmd in default_commands:
            self.register_command(cmd)
    
    def register_command(self, command: BaseCommand):
        """Register a new command."""
        self.commands[command.name] = command
    
    def get_available_commands(self) -> List[dict]:
        """Get list of available commands with descriptions."""
        return [cmd.get_info() for cmd in self.commands.values()]
    
    def execute_command(self, command_name: str, parameters: dict = None, bot=None, chat_id: int = None) -> str:
        """
        Execute a command by name.
        
        Args:
            command_name: Name of the command to execute
            parameters: Parameters for the command
            bot: Optional bot instance (for commands that need it)
            chat_id: Optional chat ID (for commands that need it)
            
        Returns:
            Response message
        """
        if command_name not in self.commands:
            return f"Command '{command_name}' not found."
        
        try:
            command = self.commands[command_name]
            # Check if command needs bot/chat_id (has execute signature with these params)
            import inspect
            sig = inspect.signature(command.execute)
            if 'bot' in sig.parameters or 'chat_id' in sig.parameters:
                return command.execute(parameters, bot=bot, chat_id=chat_id)
            else:
                return command.execute(parameters)
        except Exception as e:
            return f"Error executing command: {str(e)}"

