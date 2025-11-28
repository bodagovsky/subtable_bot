"""Command handler for managing and executing bot commands."""
from typing import Dict, List
from commands.base import BaseCommand
from commands.example_commands import (
    TimeCommand,
    RandomNumberCommand,
    EchoCommand
)
from commands.silence_command import SilenceCommand
from commands.most_active_user import MostActiveUserCommand
from commands.silence_me_command import SilenceMeCommand
from commands.summarize_command import SummarizeCommand
from commands.breakdown_topic_command import BreakdownTopicCommand


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
            MostActiveUserCommand(),
            SilenceCommand(),
            SilenceMeCommand(),
            SummarizeCommand(),
            BreakdownTopicCommand(),
        ]
        for cmd in default_commands:
            self.register_command(cmd)
    
    def register_command(self, command: BaseCommand):
        """Register a new command."""
        self.commands[command.name] = command
    
    def get_available_commands(self) -> List[dict]:
        """Get list of available commands with descriptions."""
        return [cmd.get_info() for cmd in self.commands.values()]
    
    def validate_command(self, command_name: str, parameters: dict = None) -> tuple[bool, str | None]:
        """
        Validate command parameters before execution.
        
        Args:
            command_name: Name of the command to validate
            parameters: Parameters for the command
            
        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if parameters are valid, False otherwise
            - error_message: Error message if invalid, None if valid
        """
        if command_name not in self.commands:
            return False, f"Команда '{command_name}' не найдена."
        
        command = self.commands[command_name]
        return command.validate_parameters(parameters)
    
    async def execute_command(self, command_name: str, parameters: dict = None, bot=None, chat_id: int = None, user_id: int = None) -> str:
        """
        Execute a command by name.
        
        Args:
            command_name: Name of the command to execute
            parameters: Parameters for the command
            bot: Optional bot instance (for commands that need it)
            chat_id: Optional chat ID (for commands that need it)
            user_id: Optional user ID (for commands that need it)
            
        Returns:
            Response message
        """
        if command_name not in self.commands:
            return f"Прошу прощения, сэр/мадам, но команда '{command_name}' не найдена."
        
        # Validate parameters before execution (safety check)
        is_valid, error_message = self.validate_command(command_name, parameters)
        if not is_valid:
            return f"Прошу прощения, сэр/мадам. {error_message}"
        
        try:
            command = self.commands[command_name]
            # Check if command needs bot/chat_id/user_id (has execute signature with these params)
            import inspect
            sig = inspect.signature(command.execute)
            params_to_pass = {}
            if 'bot' in sig.parameters:
                params_to_pass['bot'] = bot
            if 'chat_id' in sig.parameters:
                params_to_pass['chat_id'] = chat_id
            if 'user_id' in sig.parameters:
                params_to_pass['user_id'] = user_id
            
            if params_to_pass:
                return await command.execute(parameters, **params_to_pass)
            else:
                return await command.execute(parameters)
        except Exception as e:
            return f"Прошу прощения, сэр/мадам, но произошла ошибка при выполнении команды: {str(e)}"

