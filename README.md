# Telegram Bot with ChatGPT Command Execution

A Telegram bot powered by ChatGPT that can understand natural language input and execute predefined commands.

## Project Structure

```
undertable bot/
├── README.md
├── requirements.txt
├── Procfile              # Heroku process file
├── runtime.txt          # Python version for Heroku
├── src/                 # Application source code
│   ├── bot.py           # Main bot entry point
│   ├── config.py        # Configuration settings
│   ├── chatgpt_client.py # ChatGPT/OpenAI API integration
│   ├── command_handler.py # Command execution logic
│   └── commands/        # Command modules
│       ├── __init__.py
│       ├── base.py
│       └── example_commands.py
├── .github/
│   └── workflows/
│       └── bot.yml      # GitHub Actions workflow for Heroku deployment
└── .env.example          # Environment variables template
```

## Features

- Natural language processing via ChatGPT
- Command execution system with confirmation flow
- Extensible command architecture
- Secure configuration management
- **Channel support**: Works in Telegram channels for all participants
- **Private chat support**: Also works in one-on-one conversations
- **Smart interaction**: Users can mention the bot or reply to its messages
- **Confirmation system**: Bot asks for confirmation before executing commands
- **Clarification requests**: Bot asks for clarification when commands are unclear

## Setup

### Local Development

1. Install dependencies: `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and fill in your API keys
3. Configure webhook settings (see Webhook Configuration below)
4. Run the bot: `python src/bot.py`

### Deploying to Heroku

The bot is configured for Heroku deployment with automatic webhook setup.

#### Prerequisites

1. **Heroku Account**: Sign up at [heroku.com](https://www.heroku.com)
2. **Heroku CLI**: Install from [devcenter.heroku.com/articles/heroku-cli](https://devcenter.heroku.com/articles/heroku-cli)

#### Manual Deployment

1. **Create Heroku App**:
   ```bash
   heroku create your-bot-name
   ```

2. **Set Config Vars** (Environment Variables):
   ```bash
   heroku config:set TELEGRAM_BOT_TOKEN=your_token
   heroku config:set OPENAI_API_KEY=your_key
   heroku config:set WEBHOOK_URL=https://your-bot-name.herokuapp.com
   heroku config:set WEBHOOK_PATH=/webhook
   heroku config:set WEBHOOK_SECRET_TOKEN=your_secret_token  # Optional
   heroku config:set OPENAI_MODEL=gpt-4o-mini  # Optional
   ```

3. **Deploy**:
   ```bash
   git push heroku main
   ```

4. **View Logs**:
   ```bash
   heroku logs --tail
   ```

#### Automatic Deployment via GitHub Actions

1. **Set up GitHub Secrets**:
   - Go to your repository on GitHub
   - Navigate to **Settings** > **Secrets and variables** > **Actions**
   - Add the following secrets:
     - `HEROKU_API_KEY`: Get from [dashboard.heroku.com/account](https://dashboard.heroku.com/account)
     - `HEROKU_APP_NAME`: Your Heroku app name
     - `HEROKU_EMAIL`: Your Heroku account email
     - `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
     - `OPENAI_API_KEY`: Your OpenAI API key
     - `WEBHOOK_URL`: Your Heroku app URL (e.g., `https://your-bot-name.herokuapp.com`)
     - `WEBHOOK_SECRET_TOKEN`: (Optional) Secret token for webhook verification
     - `OPENAI_MODEL`: (Optional) Model to use (default: `gpt-4o-mini`)
     - `WEBHOOK_PATH`: (Optional) Webhook path (default: `/webhook`)

2. **Deploy**:
   - Push to `main` or `master` branch
   - The workflow will automatically deploy to Heroku and set config vars

#### Important Notes for Heroku

- **Port**: Heroku automatically sets the `PORT` environment variable - the bot uses this automatically
- **Webhook URL**: Use your Heroku app URL: `https://your-app-name.herokuapp.com`
- **HTTPS**: Heroku provides HTTPS automatically, so your webhook URL will be secure
- **Dyno**: The bot runs as a web dyno (free tier available, but dynos sleep after 30 minutes of inactivity)

## Webhook Configuration

The bot uses webhooks to receive updates from Telegram (instead of long polling). This requires:

1. **A publicly accessible HTTPS URL** where Telegram can send updates
   - **Heroku**: Automatically provides HTTPS (recommended for production)
   - **Other hosting**: Use a domain with SSL certificate
   - **Development**: Use a tunneling service like ngrok or localtunnel

2. **Environment variables** (set in Heroku config vars, `.env` file, or GitHub Secrets):
   - `WEBHOOK_URL`: Full URL (e.g., `https://yourdomain.com` or `https://abc123.ngrok.io`)
   - `WEBHOOK_PORT`: Port for the webhook server (default: 8443)
   - `WEBHOOK_PATH`: Path for webhook endpoint (default: `/webhook`)
   - `WEBHOOK_SECRET_TOKEN`: Optional secret token for webhook verification (recommended)

3. **Example configuration**:
   ```
   WEBHOOK_URL=https://yourdomain.com
   WEBHOOK_PORT=8443
   WEBHOOK_PATH=/webhook
   WEBHOOK_SECRET_TOKEN=your_secret_token_here
   ```

### Development Setup with ngrok

1. Install ngrok: `brew install ngrok` (macOS) or download from [ngrok.com](https://ngrok.com)
2. Start ngrok tunnel: `ngrok http 8443`
3. Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`)
4. Set `WEBHOOK_URL=https://abc123.ngrok.io` in your `.env` file
5. Run the bot: `python src/bot.py`

### Production Setup

**Recommended: Heroku** (see Deploying to Heroku section above)

**Alternative: Self-hosted**:
1. Deploy the bot to a server with a public IP/domain
2. Set up SSL certificate (Let's Encrypt recommended)
3. Configure firewall to allow incoming connections on `WEBHOOK_PORT`
4. Set `WEBHOOK_URL` to your domain (e.g., `https://bot.yourdomain.com`)
5. Optionally set `WEBHOOK_SECRET_TOKEN` for additional security
6. Run the bot (consider using a process manager like systemd or supervisor)

**Note for Heroku Free Tier**: Free dynos sleep after 30 minutes of inactivity. Consider:
- Using a service like [Kaffeine](https://kaffeine.herokuapp.com) to keep dynos awake
- Upgrading to a paid dyno for 24/7 uptime

## Adding Bot to a Channel

1. Go to your channel settings
2. Click on "Administrators" or "Members"
3. Click "Add Administrator" or "Add Members"
4. Search for your bot by username
5. Add it to the channel

**Note**: The bot will only respond when mentioned in channels (unless it's an admin with read permissions).

## Usage

### How to Interact with the Bot

There are two ways to address command requests to the bot:

1. **Mention the bot**: `@your_bot_name what time is it?`
2. **Reply to bot's message**: Reply to any message from the bot with your request

### Command Execution Flow

1. **User makes a request** (by mentioning or replying)
2. **Bot analyzes** the request using ChatGPT
3. **If command is identified**:
   - Bot replies asking for confirmation: "I understood you want to execute: [command]. Is this correct? Reply with 'yes' to confirm."
   - User replies "yes" to confirm
   - Bot executes the command
4. **If command is not found**:
   - Bot replies asking for clarification
   - Lists available commands
   - Asks user to rephrase or choose a specific command

### Examples

**Example 1: Command Request**
```
User: @botname what time is it?
Bot: I understood you want to execute: Get the current date and time
     Is this correct? Reply with 'yes' to confirm.
User: yes
Bot: Current time: 2024-01-15 14:30:45
```

**Example 2: Unclear Request**
```
User: @botname do something cool
Bot: I couldn't understand your request. Available commands:
     - get_time: Get the current date and time
     - random_number: Generate a random number...
     Please rephrase your request or choose a specific command.
```

### In Private Chats:
- Works the same way - mention the bot or reply to its messages
- Use `/start` to see available commands

## Configuration

### Configuration Priority

The bot reads configuration in the following order (later values override earlier ones):
1. `.env` file (for local development)
2. Environment variables (for production/GitHub Actions)
3. **GitHub Secrets** (automatically exposed as environment variables in GitHub Actions)

**Note**: Environment variables always take precedence over `.env` file values.

### Required Variables

- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token (get from [@BotFather](https://t.me/botfather))
- `OPENAI_API_KEY`: Your OpenAI API key
- `WEBHOOK_URL`: Full HTTPS URL where Telegram will send updates

### Optional Variables

- `OPENAI_MODEL`: ChatGPT model to use (default: gpt-4o-mini)
- `WEBHOOK_PORT`: Port for webhook server (default: 8443)
- `WEBHOOK_PATH`: Path for webhook endpoint (default: /webhook)
- `WEBHOOK_SECRET_TOKEN`: Secret token for webhook verification (recommended for production)
- `COMMAND_PREFIX`: Command prefix (default: /)

### Setting Up GitHub Secrets

1. Go to your GitHub repository
2. Navigate to **Settings** > **Secrets and variables** > **Actions**
3. Click **New repository secret**
4. Add each secret with the exact name shown above
5. The `.github/workflows/bot.yml` workflow will automatically use these secrets

**Security Note**: Never commit secrets to your repository. Always use GitHub Secrets or environment variables.

