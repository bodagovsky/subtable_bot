"""Configuration management for the Telegram bot."""
import os
from dotenv import load_dotenv

# Load .env file if it exists (for local development)
# Note: Environment variables (like GitHub Secrets) take precedence over .env file
# In production/GitHub Actions, secrets are provided as environment variables
load_dotenv()

# Telegram Bot Configuration
# Retrieved from environment variable or GitHub Secrets
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# OpenAI Configuration
# Retrieved from environment variable or GitHub Secrets
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Bot Configuration
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "/")
COMMAND_PROBABILITY_HIGH_THRESHOLD = float(os.getenv("COMMAND_PROBABILITY_HIGH_THRESHOLD", "95"))  # 0-100, default 95%
COMMAND_PROBABILITY_LOW_THRESHOLD = float(os.getenv("COMMAND_PROBABILITY_LOW_THRESHOLD", "50"))  # 0-100, default 50%
SYSTEM_PROMPT = """Вы Альфред, вежливый и профессиональный помощник-бот для Telegram, стилизованный под дворецкого из серии о Бэтмене. Вы обращаетесь к пользователям формально, используя "сэр/мадам", и всегда вежливы и профессиональны. Вы можете выполнять команды на основе запросов пользователей. Когда пользователь просит вас выполнить действие, проанализируйте его запрос и определите, соответствует ли он какой-либо из доступных команд. Доступные команды будут предоставлены в контексте. Отвечайте на русском языке в стиле Альфреда - формально, вежливо и профессионально."""

# Webhook Configuration
# Retrieved from environment variable or GitHub Secrets
# Note: Heroku automatically sets PORT environment variable
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")  # Full URL where Telegram will send updates (e.g., https://yourdomain.com/webhook)
WEBHOOK_PORT = int(os.getenv("PORT", os.getenv("WEBHOOK_PORT", "8443")))  # Port for webhook server (Heroku uses PORT)
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")  # Path for webhook endpoint
WEBHOOK_SECRET_TOKEN = os.getenv("WEBHOOK_SECRET_TOKEN", "")  # Optional secret token for webhook verification

