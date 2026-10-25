"""Fail-closed MCP tool proxy with destructive-operation confirmation."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class MCPProxyError(RuntimeError):
    """MCP transport, protocol, or tool metadata error."""


class SecurityViolation(MCPProxyError):
    """An MCP tool call violates the proxy's safety policy."""


class MCPProxyClient:
    """Minimal JSON-RPC MCP client that checks tool annotations before calling."""

    def __init__(
        self,
        server_url: str,
        tool_name: str,
        *,
        timeout: float = 15.0,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        parsed = urlparse(server_url)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise ValueError("server_url must be an absolute HTTP(S) URL")
        if parsed.username or parsed.password:
            raise ValueError("server_url must not embed credentials")
        if not isinstance(tool_name, str) or not tool_name.strip():
            raise ValueError("tool_name must be a non-empty string")
        if timeout <= 0:
            raise ValueError("timeout must be positive")

        self._server_url = server_url
        self._tool_name = tool_name
        self._timeout = timeout
        self._opener = opener or urlopen
        self._request_id = 0
        self._session_id: str | None = None

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _post(self, body: dict[str, Any], *, expect_json: bool = True) -> dict[str, Any] | None:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session_id:
            headers["MCP-Session-Id"] = self._session_id

        request = Request(
            self._server_url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with self._opener(request, timeout=self._timeout) as response:
                session_id = response.headers.get("Mcp-Session-Id")
                if session_id:
                    self._session_id = session_id
                raw = response.read()
        except HTTPError as exc:
            raise MCPProxyError(f"MCP server returned HTTP {exc.code}") from None
        except (URLError, TimeoutError, OSError):
            raise MCPProxyError("MCP transport failed") from None

        if not expect_json:
            return None
        if not raw:
            raise MCPProxyError("MCP server returned an empty response")

        try:
            text = raw.decode("utf-8")
            if text.lstrip().startswith("data:"):
                data_lines = [
                    line[5:].strip()
                    for line in text.splitlines()
                    if line.startswith("data:")
                ]
                text = "\n".join(data_lines)
            decoded = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise MCPProxyError("MCP server returned invalid JSON-RPC data") from None

        if not isinstance(decoded, dict):
            raise MCPProxyError("MCP response must be a JSON object")
        if decoded.get("error") is not None:
            error = decoded["error"]
            message = (
                error.get("message", "unknown MCP error")
                if isinstance(error, dict)
                else str(error)
            )
            raise MCPProxyError(f"MCP JSON-RPC error: {message}")
        return decoded

    def _initialize(self) -> None:
        response = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "JAMP-MCPProxyClient", "version": "0.1.0"},
                },
            }
        )
        if response is None or not isinstance(response.get("result"), dict):
            raise MCPProxyError("MCP initialize response is missing result")

        self._post(
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
            expect_json=False,
        )

    def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        response = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": method,
                "params": params,
            }
        )
        if response is None or "result" not in response:
            raise MCPProxyError(f"MCP {method} response is missing result")
        result = response["result"]
        if not isinstance(result, dict):
            raise MCPProxyError(f"MCP {method} result must be an object")
        return result

    def execute_tool(self, payload: dict[str, Any]) -> dict[str, Any]:
        """List metadata before every call and require explicit confirmation if destructive."""
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dict")

        self._session_id = None
        self._initialize()

        listed = self._rpc("tools/list", {})
        tools = listed.get("tools")
        if not isinstance(tools, list):
            raise MCPProxyError("MCP tools/list response has no tools list")

        metadata = next(
            (
                tool
                for tool in tools
                if isinstance(tool, dict) and tool.get("name") == self._tool_name
            ),
            None,
        )
        if metadata is None:
            raise MCPProxyError(f"MCP tool not found: {self._tool_name}")

        annotations = metadata.get("annotations", {})
        destructive = isinstance(annotations, dict) and annotations.get("destructiveHint") is True
        if destructive and payload.get("confirm") is not True:
            raise SecurityViolation("Destructive operation requires confirmation.")

        arguments = {key: value for key, value in payload.items() if key != "confirm"}
        return self._rpc(
            "tools/call",
            {"name": self._tool_name, "arguments": arguments},
        )
