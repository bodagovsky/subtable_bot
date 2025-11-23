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
        
        prompt = f"""Пользователь отправил это сообщение: "{user_message}"

Доступные команды:
{commands_context}

Я не смог сопоставить запрос пользователя ни с одной из доступных команд. 
Сгенерируйте полезное сообщение для уточнения, которое:
1. Вежливо объясняет, что вы не смогли понять их запрос
2. Перечисляет доступные команды, которые они могут использовать
3. Просит их переформулировать запрос или выбрать конкретную команду

Сообщение должно быть дружелюбным и кратким. Отвечайте на русском языке."""
        
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
            return "Прошу прощения, сэр/мадам, но я не смог понять ваш запрос. Будьте так любезны, попробуйте переформулировать его или упомяните одну из доступных команд."
    
    def extract_time_window(self, user_message: str) -> dict:
        """
        Extract time window from user message.
        
        Args:
            user_message: The user's message containing time window information
            
        Returns:
            dict with 'time_window_hours' (float or None) and 'success' (bool)
        """
        prompt = f"""Извлеките временной период из этого сообщения пользователя: "{user_message}"

Пользователь спрашивает об активности в определенный период времени. Извлеките временной период и преобразуйте его в часы.

Примеры на русском:
- "за последний день" или "за прошедший день" = 24 часа
- "за последние 2 дня" = 48 часов
- "за последнюю неделю" = 168 часов
- "за последние 3 часа" = 3 часа
- "за прошедшие 12 часов" = 12 часов
- "вчера" = 24 часа
- "за последние 5 дней" = 120 часов
- "за день" = 24 часа
- "за неделю" = 168 часов

Примеры на английском (для совместимости):
- "last day" or "past day" = 24 hours
- "last 2 days" = 48 hours
- "last week" = 168 hours
- "last 3 hours" = 3 hours

ВАЖНО:
- Максимально допустимый период - 1 неделя (168 часов)
- Верните null, если не можете извлечь действительный временной период
- Верните время в часах в виде числа

Отвечайте в формате JSON:
{{
    "time_window_hours": <число в часах или null>,
    "success": <true или false>,
    "reasoning": "краткое объяснение"
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
            
            # Validate the result
            time_window = result.get("time_window_hours")
            if time_window is not None:
                try:
                    time_window = float(time_window)
                    # Validate max 1 week
                    if time_window > 168:
                        return {
                            "time_window_hours": None,
                            "success": False,
                            "reasoning": "Временной период превышает максимум в 1 неделю"
                        }
                    if time_window <= 0:
                        return {
                            "time_window_hours": None,
                            "success": False,
                            "reasoning": "Временной период должен быть положительным"
                        }
                    result["time_window_hours"] = time_window
                    result["success"] = True
                except (ValueError, TypeError):
                    result["success"] = False
                    result["time_window_hours"] = None
            else:
                result["success"] = False
            
            return result
            
        except Exception as e:
            return {
                "time_window_hours": None,
                "success": False,
                "reasoning": f"Ошибка при извлечении временного периода: {str(e)}"
            }
    
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
            return f"Прошу прощения, сэр/мадам, но произошла ошибка: {str(e)}"

