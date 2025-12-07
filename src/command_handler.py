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
    
    async def execute_command(
        self, 
        command_name: str, 
        parameters: dict = None, 
        update=None,
        context=None,
        chatgpt_client=None
    ):
        """
        Execute a command by name.
        
        Args:
            command_name: Name of the command to execute
            parameters: Parameters for the command
            update: Telegram Update object
            context: Bot context
            chatgpt_client: ChatGPT client instance
            
        Returns:
            Event enum indicating what happened
        """
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from tools.state_machine import Event
        
        if command_name not in self.commands:
            message_obj = update.message if update.message else update.channel_post
            if message_obj:
                await message_obj.reply_text(f"Прошу прощения, сэр/мадам, но команда '{command_name}' не найдена.")
            return Event.COMMAND_UNCLEAR
        
        # Validate parameters before execution (safety check)
        is_valid, error_message = self.validate_command(command_name, parameters)
        if not is_valid:
            message_obj = update.message if update.message else update.channel_post
            if message_obj:
                await message_obj.reply_text(f"Прошу прощения, сэр/мадам. {error_message}")
            return Event.PARAMETERS_UNCLEAR
        
        try:
            command = self.commands[command_name]
            # All commands now use the same signature: execute(parameters, update, context, chatgpt_client)
            return await command.execute(parameters, update, context, chatgpt_client)
        except Exception as e:
            message_obj = update.message if update.message else update.channel_post
            if message_obj:
                await message_obj.reply_text(f"Прошу прощения, сэр/мадам, но произошла ошибка при выполнении команды: {str(e)}")
            return Event.COMMAND_EXECUTED

