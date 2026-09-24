"""Authenticated public gateway for the local Telegram Streamable HTTP MCP server."""
from __future__ import annotations

import asyncio
import hmac
import os
import sys
from contextlib import suppress

from aiohttp import ClientSession, web

UPSTREAM = "http://127.0.0.1:8000"
HOP_BY_HOP_HEADERS = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers", "transfer-encoding", "upgrade"}


def _authorized(request: web.Request) -> bool:
    expected = os.getenv("TELEGRAM_MCP_AUTH_TOKEN", "")
    provided = request.headers.get("Authorization", "")
    return bool(expected) and hmac.compare_digest(provided, f"Bearer {expected}")


async def proxy(request: web.Request) -> web.StreamResponse:
    if not _authorized(request):
        return web.Response(status=401, text="Unauthorized")
    session: ClientSession = request.app["http_session"]
    url = f"{UPSTREAM}{request.rel_url}"
    headers = {key: value for key, value in request.headers.items() if key.lower() not in HOP_BY_HOP_HEADERS | {"host"}}
    async with session.request(request.method, url, headers=headers, data=request.content.iter_chunked(64 * 1024)) as upstream:
        response_headers = {key: value for key, value in upstream.headers.items() if key.lower() not in HOP_BY_HOP_HEADERS}
        response = web.StreamResponse(status=upstream.status, headers=response_headers)
        await response.prepare(request)
        async for chunk in upstream.content.iter_chunked(64 * 1024):
            await response.write(chunk)
        await response.write_eof()
        return response


async def health(_: web.Request) -> web.Response:
    return web.Response(text="Telegram MCP gateway is running")


async def start_server(app: web.Application) -> None:
    token = os.getenv("TELEGRAM_MCP_AUTH_TOKEN", "")
    if len(token) < 32:
        raise RuntimeError("TELEGRAM_MCP_AUTH_TOKEN must contain at least 32 characters")
    env = {**os.environ, "TELEGRAM_MCP_HOST": "127.0.0.1", "TELEGRAM_MCP_PORT": "8000"}
    app["mcp_process"] = await asyncio.create_subprocess_exec(
        sys.executable, "src/telegram_mcp.py", "--transport", "streamable-http", "--host", "127.0.0.1", "--port", "8000", env=env
    )
    app["http_session"] = ClientSession()


async def stop_server(app: web.Application) -> None:
    await app["http_session"].close()
    process = app["mcp_process"]
    if process.returncode is None:
        process.terminate()
        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(process.wait(), timeout=10)


def main() -> None:
    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_route("*", "/mcp", proxy)
    app.router.add_route("*", "/mcp/{tail:.*}", proxy)
    app.on_startup.append(start_server)
    app.on_cleanup.append(stop_server)
    web.run_app(app, host="0.0.0.0", port=int(os.environ["PORT"]))


if __name__ == "__main__":
    main()
