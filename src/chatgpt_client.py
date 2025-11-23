"""ChatGPT/OpenAI API client for natural language processing."""
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL, SYSTEM_PROMPT


class ChatGPTClient:
    """Client for interacting with ChatGPT API."""
    
    def __init__(self):
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not set in environment variables")
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.model = OPENAI_MODEL
        self.system_prompt = SYSTEM_PROMPT
    
    def analyze_message(self, user_message: str, available_commands: list) -> dict:
        """
        Analyze user message and determine if it matches any commands.
        
        Args:
            user_message: The user's message
            available_commands: List of available command names and descriptions
            
        Returns:
            dict with 'command' (command name or None) and 'reasoning' (explanation)
        """
        commands_context = "\n".join([
            f"- {cmd['name']}: {cmd['description']}"
            for cmd in available_commands
        ])
        
        prompt = f"""Available commands:
{commands_context}

User message: "{user_message}"

Analyze the user's message and determine:
1. Does it match any of the available commands?
2. If yes, which command and what parameters are needed?
3. If no, set command to null.

IMPORTANT: Only return a command if you are CERTAIN it matches one of the available commands. 
If the user's request doesn't clearly match any command, return null for the command field.

Respond in JSON format:
{{
    "command": "command_name or null",
    "parameters": {{"param1": "value1"}},
    "reasoning": "brief explanation"
}}"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            import json
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            return {
                "command": None,
                "parameters": {},
                "reasoning": f"Error analyzing message: {str(e)}"
            }
    
    def generate_clarification(self, user_message: str, available_commands: list) -> str:
        """Generate a clarification message when no command is matched."""
        commands_context = "\n".join([
            f"- {cmd['name']}: {cmd['description']}"
            for cmd in available_commands
        ])
        
        prompt = f"""The user sent this message: "{user_message}"

Available commands:
{commands_context}

I couldn't match the user's request to any of the available commands. 
Generate a helpful clarification message that:
1. Politely explains that you couldn't understand their request
2. Lists the available commands they can use
3. Asks them to rephrase their request or choose a specific command

Keep the message friendly and concise."""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"I couldn't understand your request. Please try rephrasing it or mention one of the available commands."
    
    def generate_response(self, user_message: str) -> str:
        """Generate a conversational response when no command is matched."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Sorry, I encountered an error: {str(e)}"

