import json

import pytest

from jamp.provider.mcp_proxy import MCPProxyClient, MCPProxyError, SecurityViolation


class FakeResponse:
    def __init__(self, body=b"", headers=None):
        self._body = body
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self._body


def make_opener(*, destructive):
    calls = []

    def fake_urlopen(request, timeout):
        body = json.loads(request.data.decode("utf-8"))
        calls.append(body)
        method = body.get("method")

        if method == "notifications/initialized":
            return FakeResponse()
        if method == "initialize":
            result = {
                "protocolVersion": "2025-03-26",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "test-mcp", "version": "1.0"},
            }
        elif method == "tools/list":
            result = {
                "tools": [
                    {
                        "name": "test_tool",
                        "description": "A test tool",
                        "inputSchema": {"type": "object"},
                        "annotations": {"destructiveHint": destructive},
                    }
                ]
            }
        elif method == "tools/call":
            result = {"content": [{"type": "text", "text": "executed"}], "isError": False}
        else:
            raise AssertionError(f"Unexpected MCP method: {method}")

        return FakeResponse(
            json.dumps({"jsonrpc": "2.0", "id": body["id"], "result": result}).encode()
        )

    return fake_urlopen, calls


def test_safe_tool_executes_after_metadata_lookup():
    opener, calls = make_opener(destructive=False)
    client = MCPProxyClient("https://mcp.example.test", "test_tool", opener=opener)

    result = client.execute_tool({"query": "hello"})

    methods = [call.get("method") for call in calls]
    assert methods.index("tools/list") < methods.index("tools/call")
    assert result["content"][0]["text"] == "executed"
    assert calls[-1]["params"] == {
        "name": "test_tool",
        "arguments": {"query": "hello"},
    }


def test_destructive_tool_requires_confirmation():
    opener, calls = make_opener(destructive=True)
    client = MCPProxyClient("https://mcp.example.test", "test_tool", opener=opener)

    with pytest.raises(
        SecurityViolation,
        match="Destructive operation requires confirmation",
    ):
        client.execute_tool({"path": "/tmp/important.txt"})

    assert [call.get("method") for call in calls][-1] == "tools/list"
    assert all(call.get("method") != "tools/call" for call in calls)


def test_destructive_tool_executes_with_explicit_confirmation():
    opener, calls = make_opener(destructive=True)
    client = MCPProxyClient("https://mcp.example.test", "test_tool", opener=opener)

    result = client.execute_tool({"path": "/tmp/important.txt", "confirm": True})

    assert result["isError"] is False
    assert calls[-1]["method"] == "tools/call"
    assert calls[-1]["params"]["arguments"] == {"path": "/tmp/important.txt"}
    assert "confirm" not in calls[-1]["params"]["arguments"]


def test_unknown_tool_fails_closed():
    opener, _ = make_opener(destructive=False)
    client = MCPProxyClient("https://mcp.example.test", "missing_tool", opener=opener)

    with pytest.raises(MCPProxyError, match="MCP tool not found"):
        client.execute_tool({"query": "hello"})


def test_rejects_invalid_server_url():
    with pytest.raises(ValueError, match="absolute HTTP"):
        MCPProxyClient("not-a-url", "test_tool")
