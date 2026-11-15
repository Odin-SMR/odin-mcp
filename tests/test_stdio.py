"""Test the installed console command from a directory outside the source tree."""

from datetime import timedelta
import os
from pathlib import Path
import socket
import sys

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import pytest


def test_offline_guard_allows_socketpair_but_rejects_external_connections():
    # Exercise the same fallback used by Windows even when running on Linux.
    socketpair = getattr(socket, "_fallback_socketpair", socket.socketpair)
    left, right = socketpair()
    with left, right:
        left.sendall(b"ok")
        assert right.recv(2) == b"ok"
    with socket.socket() as outbound:
        with pytest.raises(AssertionError):
            outbound.connect(("192.0.2.1", 443))


def test_console_stdio_without_credentials_or_external_network(tmp_path):
    executable = Path(sys.executable).parent / ("odin-mcp.exe" if os.name == "nt" else "odin-mcp")
    assert executable.is_file(), "Install odin-mcp before running its protocol tests"
    # The server is a child process, so it needs its own network block in addition
    # to the parent process fixture. No real credentials are forwarded.
    (tmp_path / "sitecustomize.py").write_text(
        "import socket\n"
        "original_connect = socket.socket.connect\n"
        "def blocked(*args, **kwargs):\n"
        "    raise AssertionError('Offline protocol test attempted a network connection')\n"
        "def connect_local_only(sock, address):\n"
        "    if isinstance(address, tuple) and address[0] in ('127.0.0.1', '::1'):\n"
        "        return original_connect(sock, address)\n"
        "    return blocked()\n"
        "socket.socket.connect = connect_local_only\n"
        "socket.create_connection = blocked\n"
        "socket.getaddrinfo = blocked\n",
        encoding="utf-8",
    )
    parameters = StdioServerParameters(
        command=str(executable),
        args=[],
        cwd=str(tmp_path),
        env={
            "ODIN_AWS_PROFILE": "unconfigured-test-profile",
            "AWS_CONFIG_FILE": str(tmp_path / "absent-aws-config"),
            "AWS_SHARED_CREDENTIALS_FILE": str(tmp_path / "absent-aws-credentials"),
            "AWS_EC2_METADATA_DISABLED": "true",
            "PYTHONPATH": str(tmp_path),
            "PYTHONNOUSERSITE": "1",
        },
    )

    async def exercise():
        with (tmp_path / "server-stderr.log").open("w", encoding="utf-8") as stderr:
            async with stdio_client(parameters, errlog=stderr) as (reader, writer):
                async with ClientSession(reader, writer, read_timeout_seconds=timedelta(seconds=20)) as session:
                    initialized = await session.initialize()
                    assert initialized.serverInfo.name == "odin-level2"
                    tools = await session.list_tools()
                    assert "search_research_guidance_tool" in {tool.name for tool in tools.tools}
                    guide = await session.read_resource("odin://research/guide")
                    assert guide.contents[0].text.startswith("# Researching Odin SMR Level 2")
                    result = await session.call_tool("search_research_guidance_tool", {"query": "N₂O"})
                    assert not result.isError
                    assert result.structuredContent["ok"]
                    assert result.structuredContent["data"]["results"]
                    prompt = await session.get_prompt("plan_odin_analysis", {"question": "Plan a seasonal comparison"})
                    assert prompt.messages

    anyio.run(exercise)
