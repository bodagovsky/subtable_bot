"""Select the public service run by a Heroku web dyno.

Deploy the same repository to two Heroku apps. The Telegram app leaves
HEROKU_SERVICE_ROLE unset; the MCP app sets it to ``mcp``.
"""
import os


def main() -> None:
    role = os.getenv("HEROKU_SERVICE_ROLE", "telegram")
    if role == "telegram":
        from bot import main as run
    elif role == "mcp":
        from mcp_gateway import main as run
    else:
        raise RuntimeError("HEROKU_SERVICE_ROLE must be 'telegram' or 'mcp'")
    run()


if __name__ == "__main__":
    main()
