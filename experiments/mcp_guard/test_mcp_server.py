"""Minimal local HTTP JSON-RPC server for MCPProxyClient integration tests."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


class MCPTestHandler(BaseHTTPRequestHandler):
    """Handle the JSON-RPC methods used by MCPProxyClient."""

    server_version = "JAMP-MCP-Test/1.0"

    def do_POST(self) -> None:
        if self.path != "/":
            self.send_error(404)
            return

        try:
            request = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        except (json.JSONDecodeError, ValueError):
            self._send_json(400, {"error": "invalid JSON"})
            return

        method = request.get("method")
        request_id = request.get("id")

        if method == "notifications/initialized":
            self.send_response(202)
            self.end_headers()
            return

        if method == "initialize":
            self._send_json(
                200,
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "jamp-local-test-server", "version": "1.0"},
                    },
                },
            )
            return

        if method == "tools/list":
            self._send_json(
                200,
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "tools": [
                            {
                                "name": "dangerous_tool",
                                "description": "Test-only destructive operation.",
                                "annotations": {"destructiveHint": True},
                                "inputSchema": {"type": "object"},
                            },
                            {
                                "name": "safe_tool",
                                "description": "Test-only safe operation.",
                                "annotations": {"destructiveHint": False},
                                "inputSchema": {"type": "object"},
                            },
                        ]
                    },
                },
            )
            return

        if method == "tools/call":
            log_path = Path(os.environ["MCP_SERVER_CALLS_LOG"])
            with log_path.open("a", encoding="utf-8") as log_file:
                log_file.write(json.dumps(request, sort_keys=True) + "\n")
            self._send_json(
                200,
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"content": [{"type": "text", "text": "success"}]},
                },
            )
            return

        self._send_json(
            200,
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            },
        )

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, _format: str, *_args: Any) -> None:
        """Keep test output deterministic; assertions use server_calls.log."""


def main() -> None:
    host = "127.0.0.1"
    port = 8765
    server = ThreadingHTTPServer((host, port), MCPTestHandler)
    print(f"READY: MCP test server listening on http://{host}:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
