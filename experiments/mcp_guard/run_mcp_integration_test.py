"""Exercise MCPProxyClient against a real local HTTP JSON-RPC server."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from jamp.provider.mcp_proxy import MCPProxyClient, SecurityViolation


SERVER_URL = "http://127.0.0.1:8765"


def read_calls(log_path: Path) -> list[dict[str, Any]]:
    """Read JSON-RPC tools/call requests recorded by the HTTP server."""
    raw = log_path.read_text(encoding="utf-8")
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def run_integration_test() -> None:
    server_script = Path(__file__).with_name("test_mcp_server.py")
    with tempfile.TemporaryDirectory(prefix="jamp-mcp-integration-") as temp_dir:
        log_path = Path(temp_dir) / "server_calls.log"
        log_path.touch()
        env = os.environ.copy()
        env["MCP_SERVER_CALLS_LOG"] = str(log_path)
        server = subprocess.Popen(
            [sys.executable, "-u", str(server_script)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        try:
            time.sleep(2)
            if server.poll() is not None:
                output = server.stdout.read() if server.stdout else ""
                raise AssertionError(f"MCP test server exited during startup: {output}")

            print("=== JAMP STAGE 4.5: MCP HTTP INTEGRATION TEST ===")

            print("\n--- TEST 1: dangerous tool WITHOUT confirmation ---")
            try:
                MCPProxyClient(SERVER_URL, "dangerous_tool", timeout=5).execute_tool(
                    {"record_id": "test-1"}
                )
            except SecurityViolation as exc:
                assert str(exc) == "Destructive operation requires confirmation."
            else:
                raise AssertionError("Guard allowed dangerous tool without confirmation")
            assert read_calls(log_path) == [], "Blocked operation reached HTTP tools/call"
            print("PASS: SecurityViolation raised; server_calls.log remains empty.")

            print("\n--- TEST 2: dangerous tool WITH explicit confirmation ---")
            result = MCPProxyClient(
                SERVER_URL, "dangerous_tool", timeout=5
            ).execute_tool({"record_id": "test-2", "confirm": True})
            assert result["content"][0]["text"] == "success"
            calls = read_calls(log_path)
            assert len(calls) == 1, f"Expected one recorded call, got {len(calls)}"
            first_call = calls[0]
            assert first_call.get("method") == "tools/call"
            assert first_call.get("params", {}).get("name") == "dangerous_tool"
            assert "confirm" not in first_call
            assert "confirm" not in first_call.get("params", {}).get("arguments", {})
            print("PASS: real HTTP call succeeded; confirm was not sent to the server.")

            print("\n--- TEST 3: safe tool WITHOUT confirmation ---")
            result = MCPProxyClient(SERVER_URL, "safe_tool", timeout=5).execute_tool(
                {"record_id": "test-3"}
            )
            assert result["content"][0]["text"] == "success"
            calls = read_calls(log_path)
            assert len(calls) == 2, f"Expected two recorded calls, got {len(calls)}"
            second_call = calls[1]
            assert second_call.get("method") == "tools/call"
            assert second_call.get("params", {}).get("name") == "safe_tool"
            assert second_call.get("params", {}).get("arguments") == {"record_id": "test-3"}
            print("PASS: safe tool reached the HTTP server without confirmation.")

            print("\nRESULT: MCP INTEGRATION TEST PASSED")
            print("SCOPE: real local HTTP/JSON-RPC transport; test server only, no production MCP server.")
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
            if server.stdout:
                server.stdout.close()


if __name__ == "__main__":
    run_integration_test()
