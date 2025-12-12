"""ChatGPT/OpenAI API client for natural language processing."""
import json
import logging
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL, SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class ChatGPTClient:
    """Client for interacting with ChatGPT API."""
    
    def __init__(self):
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not set in environment variables")
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.model = OPENAI_MODEL
        self.system_prompt = SYSTEM_PROMPT

    def prepare_weather_report(self, raw_report: dict) -> str:
        """
        Analyze response from the API and prepare concise and polite report about air pollution and weather

        Args: 
            raw_report: The report returned from the weather API service
        
        Returns:
            formatted message with weather report and air pollution data
        """

        data = json.dumps(raw_report)
        prompt = f"""Проанализируй следующий ответ от сервиса IQAir в формате json
        и составь отчет о качестве воздуха и прогнозе погоды
        Строку "Тип осадков" включай только в том числе если вероятность средняя или высокая

        Ты можешь менять эмодзи в зависимости от актуальной информации (например, эмодзи яркого солнца если погода солнечная)
        Так же ты можешь отформатировать сообщение так чтобы оно выглядело приятно в качестве сообщения в Телеграме
        Игнорируй данные о погоде, их добавлять в отчет не нужно

        Вот пример, по которому тебе необходимо приготовить отчет:

        🟡 Качество воздуха: Среднее (AQI 91)
        • Безопасно для большинства людей  
        • Чувствительным группам — снизить нагрузки при дискомфорте  

        Рекомендации:
        • Можно гулять без ограничений  
        • Маска не требуется (P2/P3 — при ухудшении воздуха)

        Данные API запроса:
        {data}

        Отвечай в формате JSON:
        {{
            "report": "report"
        }}
        """
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
            result = json.loads(response.choices[0].message.content)
            report = result.get("report", "")
            return report
        except Exception as e:
            print(e)
            return ""
    
    def analyze_message(self, user_message: str, available_commands: list) -> dict:
        """
        Analyze user message and return probabilities for each command.
        
        Args:
            user_message: The user's message
            available_commands: List of available command names and descriptions
            
        Returns:
            dict with 'commands' (list of commands with probabilities) and 'reasoning' (explanation)
        """
        commands_context = "\n".join([
            f"- {cmd['name']}: {cmd['description']}"
            for cmd in available_commands
        ])
        
        prompt = f"""Доступные команды:
{commands_context}

Сообщение пользователя: "{user_message}"

Проанализируйте сообщение пользователя и определите вероятность (от 0 до 100) того, что пользователь хочет выполнить каждую из доступных команд.

Для каждой команды укажите:
- Вероятность (0-100), что пользователь хочет выполнить эту команду
- Параметры, если они нужны
- Краткое обоснование

ВАЖНО: Вероятность должна отражать уверенность в том, что пользователь хочет выполнить именно эту команду.
- 0-30%: Маловероятно, что пользователь хочет эту команду
- 31-60%: Возможно, пользователь хочет эту команду
- 61-94%: Вероятно, пользователь хочет эту команду
- 95-100%: Очень вероятно, что пользователь хочет эту команду

Отвечайте в формате JSON:
{{
    "commands": [
        {{
            "name": "command_name",
            "probability": <число от 0 до 100>,
            "parameters": {{"param1": "value1"}},
            "reasoning": "краткое обоснование"
        }},
        ...
    ],
    "reasoning": "общее объяснение анализа"
}}

Включите все доступные команды в список, даже если вероятность низкая."""
        
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
            
            # Ensure all commands are included with probabilities
            commands_with_probs = result.get("commands", [])
            
            # Add any missing commands with 0 probability
            existing_names = {cmd.get("name") for cmd in commands_with_probs}
            for cmd_info in available_commands:
                if cmd_info["name"] not in existing_names:
                    commands_with_probs.append({
                        "name": cmd_info["name"],
                        "probability": 0,
                        "parameters": {},
                        "reasoning": "Команда не соответствует запросу"
                    })
            
            result["commands"] = commands_with_probs
            return result
            
        except Exception as e:
            # Fallback: return all commands with 0 probability
            return {
                "commands": [
                    {
                        "name": cmd["name"],
                        "probability": 0,
                        "parameters": {},
                        "reasoning": f"Ошибка анализа: {str(e)}"
                    }
                    for cmd in available_commands
                ],
                "reasoning": f"Ошибка при анализе сообщения: {str(e)}"
            }
    
    def analyze_message_intent(self, user_message: str) -> dict:
        """
        Analyze if user message is a command request or just conversational (encouragement, discouragement, greeting, etc.).
        
        Args:
            user_message: The user's message
            
        Returns:
            dict with 'is_command_request' (bool), 'intent_type' (str), and 'should_respond' (bool)
        """
        prompt = f"""Проанализируйте это сообщение пользователя: "{user_message}"

Определите, является ли это сообщение:
1. Запросом на выполнение команды (команда, действие, просьба что-то сделать)
2. Поощрением или благодарностью (спасибо, хорошо, отлично, молодец и т.д.)
3. Неодобрением или критикой (плохо, неправильно, не так и т.д.)
4. Приветствием или прощанием (привет, пока, здравствуйте и т.д.)
5. Просто разговором или комментарием, не требующим выполнения команды

Отвечайте в формате JSON:
{{
    "is_command_request": true/false,
    "intent_type": "command_request" | "encouragement" | "discouragement" | "greeting" | "conversation" | "other",
    "should_respond": true/false,
    "reasoning": "краткое обоснование"
}}

Если это не запрос команды, но это осмысленное сообщение, требующее ответа (поощрение, приветствие, разговор), установите should_respond в true.
Если это просто случайное сообщение или спам, установите should_respond в false."""
        
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
            # Default: assume it's a command request if we can't analyze
            return {
                "is_command_request": True,
                "intent_type": "other",
                "should_respond": False,
                "reasoning": f"Ошибка анализа: {str(e)}"
            }
    
    def generate_conversational_response(self, user_message: str, intent_type: str) -> str:
        """
        Generate a polite conversational response from Alfred's perspective.
        
        Args:
            user_message: The user's message
            intent_type: Type of intent (encouragement, discouragement, greeting, conversation, etc.)
            
        Returns:
            Polite response message in Alfred's style
        """
        prompt = f"""Пользователь отправил это сообщение: "{user_message}"

Тип сообщения: {intent_type}

Сгенерируйте вежливый, краткий ответ от лица Альфреда (дворецкого из серии о Бэтмене). 
Ответ должен быть:
- Формальным и вежливым (обращение "сэр/мадам")
- Кратким (1-2 предложения)
- Соответствующим типу сообщения:
  * Для поощрения/благодарности: поблагодарить и выразить готовность помочь
  * Для неодобрения: извиниться и предложить помощь
  * Для приветствия: поприветствовать и предложить помощь
  * Для разговора: вежливо ответить и предложить помощь

Отвечайте на русском языке в стиле Альфреда."""
        
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
        except Exception:
            # Fallback responses based on intent type
            if intent_type == "encouragement":
                return "Благодарю вас, сэр/мадам. Всегда к вашим услугам."
            elif intent_type == "discouragement":
                return "Прошу прощения, сэр/мадам. Я готов помочь вам исправить ситуацию."
            elif intent_type == "greeting":
                return "Здравствуйте, сэр/мадам. К вашим услугам. Чем могу помочь?"
            else:
                return "Понял вас, сэр/мадам. К вашим услугам. Если вам нужна помощь, просто попросите."
    
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
        except Exception:
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
    
    def extract_summarize_parameters(self, user_message: str) -> dict:
        """
        Extract summarize parameters (time_window_hours or message_count) from user message.
        
        Args:
            user_message: The user's message containing time window or message count information
            
        Returns:
            dict with 'message_count' (int or None), 'time_window_hours' (float or None), and 'success' (bool)
        """
        prompt = f"""Извлеките параметры для команды суммирования из этого сообщения пользователя: "{user_message}"

Пользователь хочет суммировать сообщения. Извлеките либо количество сообщений, либо временной период.

Параметры:
1. Количество сообщений (message_count): целое число от 15 до 1000
   Примеры: "последние 300 сообщений", "300 сообщений", "за 100 сообщений"
   
2. Временной период (time_window_hours): число в часах от 0.5 (30 минут) до 24 часов
   Примеры на русском:
   - "за последний час" = 1 час
   - "за последние 2 часа" = 2 часа
   - "за последние 30 минут" = 0.5 часа
   - "за последние 3 часа" = 3 часа
   - "за день" = 24 часа
   - "за последние 12 часов" = 12 часов
   
ВАЖНО:
- Извлеките ТОЛЬКО ОДИН параметр: либо message_count, либо time_window_hours
- Если указаны оба, приоритет у message_count
- Минимум: 15 сообщений или 0.5 часа (30 минут)
- Максимум: 1000 сообщений или 24 часа
- Верните null для параметра, который не был найден
- Верните success: false, если не удалось извлечь ни один параметр

Отвечайте в формате JSON:
{{
    "message_count": <целое число от 15 до 1000 или null>,
    "time_window_hours": <число в часах от 0.5 до 24 или null>,
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
            message_count = result.get("message_count")
            time_window_hours = result.get("time_window_hours")
            success = False
            
            # Validate message_count if provided
            if message_count is not None:
                try:
                    message_count = int(message_count)
                    if 15 <= message_count <= 1000:
                        result["message_count"] = message_count
                        success = True
                    else:
                        result["message_count"] = None
                        result["reasoning"] = f"Количество сообщений должно быть от 15 до 1000, получено: {message_count}"
                except (ValueError, TypeError):
                    result["message_count"] = None
            
            # Validate time_window_hours if provided
            if time_window_hours is not None:
                try:
                    time_window_hours = float(time_window_hours)
                    if 0.5 <= time_window_hours <= 24:
                        result["time_window_hours"] = time_window_hours
                        success = True
                    else:
                        result["time_window_hours"] = None
                        if not success:
                            result["reasoning"] = f"Временной период должен быть от 0.5 до 24 часов, получено: {time_window_hours}"
                except (ValueError, TypeError):
                    result["time_window_hours"] = None
            
            result["success"] = success
            return result
            
        except Exception as e:
            return {
                "message_count": None,
                "time_window_hours": None,
                "success": False,
                "reasoning": f"Ошибка при извлечении параметров: {str(e)}"
            }
    
    def extract_topic_query(self, user_message: str) -> dict:
        """
        Extract topic query from user message for breakdown_topic command.
        
        Args:
            user_message: The user's message containing topic information
            
        Returns:
            dict with 'topic_query' (str or None) and 'success' (bool)
        """
        prompt = f"""Извлеките название темы обсуждения из этого сообщения пользователя: "{user_message}"

Пользователь хочет разобрать конкретную тему обсуждения. Извлеките название темы из сообщения.

Примеры на русском:
- "разбери тему про загрязнение воздуха" → "загрязнение воздуха"
- "что обсуждали про политику" → "политика"
- "расскажи про загрязнение" → "загрязнение"
- "разбери тему загрязнение воздуха" → "загрязнение воздуха"
- "загрязнение воздуха" → "загрязнение воздуха"
- "про загрязнение" → "загрязнение"
- "тема про политику" → "политика"
- "разобрать тему новости" → "новости"
- "что говорили про здоровье" → "здоровье"
- "разбери загрязнение" → "загрязнение"
- "подробнее про политику" → "политика"
- "тема загрязнение" → "загрязнение"
- "обсуждение про здоровье" → "здоровье"

ВАЖНО:
- Извлеките ТОЛЬКО название темы, без лишних слов
- Уберите слова-маркеры: "разбери", "тема", "про", "что обсуждали", "расскажи", "разобрать", "подробнее", "обсуждение" и т.д.
- Верните чистое название темы (1-5 слов, обычно 2-3 слова)
- Сохраните оригинальную формулировку темы (не меняйте слова)
- Если пользователь указал только номер темы (например, "тема 1" или просто "1"), верните null и success: false
- Если сообщение содержит только общие слова без конкретной темы (например, "разбери тему" без указания какой), верните null и success: false
- Если не удалось извлечь тему, верните null и success: false
- Верните success: true только если уверены, что извлекли конкретное название темы

Отвечайте в формате JSON:
{{
    "topic_query": <название темы или null>,
    "success": <true или false>,
    "reasoning": "краткое объяснение того, что было извлечено или почему не удалось"
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
            topic_query = result.get("topic_query")
            success = result.get("success", False)
            
            # Additional validation
            if topic_query:
                topic_query = topic_query.strip()
                # Check if it's not empty and not just a number
                if topic_query and not topic_query.isdigit():
                    # Check length (should be reasonable, not too short or too long)
                    if 2 <= len(topic_query) <= 100:
                        result["topic_query"] = topic_query
                        result["success"] = True
                    else:
                        result["topic_query"] = None
                        result["success"] = False
                        result["reasoning"] = f"Название темы должно быть от 2 до 100 символов, получено: {len(topic_query)}"
                else:
                    result["topic_query"] = None
                    result["success"] = False
                    if not result.get("reasoning"):
                        result["reasoning"] = "Название темы не может быть пустым или числом"
            else:
                result["success"] = False
                if not result.get("reasoning"):
                    result["reasoning"] = "Не удалось извлечь название темы"
            
            return result
            
        except Exception as e:
            logger.error(f"Error extracting topic query: {e}")
            return {
                "topic_query": None,
                "success": False,
                "reasoning": f"Ошибка при извлечении темы: {str(e)}"
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
    
    def summarize_messages(self, messages: list[dict]) -> dict:
        """
        Summarize messages and extract topics using OpenAI.
        
        Args:
            messages: List of message dictionaries with keys:
                - user_id: int
                - message_id: int
                - text: str
                - timestamp: str or float (Unix timestamp)
        
        Returns:
            Dictionary with 'topics' list containing:
                - topic_handle: str (2-3 words, lowercase, underscore-separated)
                - description: str (2-3 words human-readable)
                - start_message: dict with message_id
                - message_count: int
                - summary: str (3-5 main points referring participants)
        """
        # Format messages for OpenAI
        messages_text = "\n".join([
            f"user_id: {msg['user_id']}, message_id: {msg['message_id']}, text: {msg['text']}, timestamp: {msg['timestamp']}"
            for msg in messages
        ])
        
        prompt = f"""Проанализируйте следующие сообщения из чата и определите основные темы обсуждения.

Сообщения:
{messages_text}

Ваша задача:
1. Определить все темы обсуждения (может быть одна или несколько)
2. Для каждой темы создать:
   - topic_handle: короткий идентификатор из 2-3 слов в нижнем регистре, разделенных подчеркиванием (например: air_pollution, politics_news, upcoming_holidays_event)
   - description: краткое описание из 2-3 слов на русском языке (например: "Загрязнение воздуха", "Новости политики")
   - start_message: message_id первого сообщения в теме
   - message_count: количество сообщений, относящихся к теме (одно сообщение может относиться к нескольким темам)
   - summary: 3-5 основных пунктов обсуждения с указанием участников (например: "Dina сказала, что из-за смога трудно дышать")

ВАЖНО:
- Если есть только одна тема, верните массив с одним элементом
- Если тем несколько, верните массив со всеми темами
- Каждый пункт в summary должен ссылаться на конкретного участника (user_id или имя, если возможно)
- topic_handle должен быть уникальным идентификатором темы

Отвечайте в формате JSON:
{{
    "topics": [
        {{
            "topic_handle": "air_pollution",
            "description": "Загрязнение воздуха",
            "start_message": {{"message_id": 12345}},
            "message_count": 168,
            "summary": "1. Dina сказала, что из-за смога трудно дышать\\n2. Mike ответил, что некоторые измерительные устройства считают загрязнение воздуха неправильно\\n3. Thomas сказал, что уже заказал устройство для очистки воздуха"
        }},
        ...
    ]
}}"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.5
            )
            
            import json
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            logger.error(f"Error summarizing messages: {e}")
            return {"topics": []}
    
    def match_topic(self, user_message: str, topics: list[dict]) -> dict:
        """
        Match user message to topics using probability analysis.
        
        Args:
            user_message: User's message query
            topics: List of topic dictionaries with 'topic_handle' and 'description'
            
        Returns:
            Dictionary with 'topics' list containing topics with probabilities
        """
        if not topics:
            return {"topics": []}
        
        # Format topics for analysis
        topics_text = "\n".join([
            f"{i+1}. {topic.get('description', topic.get('topic_handle', ''))} ({topic.get('message_count', 0)} сообщений)"
            for i, topic in enumerate(topics)
        ])
        
        prompt = f"""Пользователь отправил запрос: "{user_message}"

Доступные темы обсуждения:
{topics_text}

Определите вероятность (от 0 до 100) того, что пользователь хочет узнать о каждой из тем.

ВАЖНО: Вероятность должна отражать уверенность в том, что пользователь хочет именно эту тему.
- 0-30%: Маловероятно, что пользователь хочет эту тему
- 31-60%: Возможно, пользователь хочет эту тему
- 61-94%: Вероятно, пользователь хочет эту тему
- 95-100%: Очень вероятно, что пользователь хочет эту тему

Отвечайте в формате JSON:
{{
    "topics": [
        {{
            "topic_index": 0,
            "probability": <число от 0 до 100>,
            "reasoning": "краткое обоснование"
        }},
        ...
    ]
}}

Включите все темы в список, даже если вероятность низкая."""
        
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
            
            # Merge probabilities with topic data
            topic_probs = {tp.get("topic_index"): tp for tp in result.get("topics", [])}
            matched_topics = []
            
            for i, topic in enumerate(topics):
                prob_data = topic_probs.get(i, {"probability": 0, "reasoning": "Не найдено"})
                matched_topics.append({
                    **topic,
                    "probability": prob_data.get("probability", 0),
                    "reasoning": prob_data.get("reasoning", "")
                })
            
            return {"topics": matched_topics}
            
        except Exception as e:
            logger.error(f"Error matching topic: {e}")
            # Return all topics with 0 probability
            return {
                "topics": [
                    {**topic, "probability": 0, "reasoning": f"Ошибка анализа: {str(e)}"}
                    for topic in topics
                ]
            }

