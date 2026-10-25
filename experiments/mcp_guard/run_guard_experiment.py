"""Deterministic simulation of JAMP's MCP destructive-operation guard.

No MCP server is contacted and no real database operation is performed.
"""
from unittest.mock import call, patch

from jamp.provider.mcp_proxy import MCPProxyClient, SecurityViolation


def run_guard_test() -> None:
    print("=== JAMP STAGE 4: MCP GUARD TEST ===")

    dangerous_tool_metadata = {
        "name": "delete_database",
        "description": "Deletes the production database permanently.",
        "annotations": {"destructiveHint": True},
    }
    safe_tool_metadata = {
        "name": "read_table",
        "description": "Reads data from a table.",
        "annotations": {"destructiveHint": False},
    }

    proxy = MCPProxyClient(
        server_url="http://mock-mcp-server",
        tool_name="delete_database",
    )

    print("\n--- TEST 1: dangerous tool WITHOUT confirmation ---")
    with (
        patch.object(proxy, "_initialize"),
        patch.object(
            proxy,
            "_rpc",
            return_value={"tools": [dangerous_tool_metadata]},
        ) as mock_rpc,
    ):
        try:
            proxy.execute_tool(payload={"table": "users"})
        except SecurityViolation as exc:
            assert str(exc) == "Destructive operation requires confirmation."
            assert call("tools/call", {"name": "delete_database", "arguments": {"table": "users"}}) not in mock_rpc.call_args_list
            print(f"PASS: blocked before tools/call. Reason: {exc}")
        else:
            raise AssertionError("Guard allowed destructive operation without confirmation")

    print("\n--- TEST 2: dangerous tool WITH explicit confirmation ---")
    with (
        patch.object(proxy, "_initialize"),
        patch.object(
            proxy,
            "_rpc",
            side_effect=[
                {"tools": [dangerous_tool_metadata]},
                {"content": [{"type": "text", "text": "simulated deletion accepted"}]},
            ],
        ) as mock_rpc,
    ):
        result = proxy.execute_tool(payload={"table": "users", "confirm": True})
        mock_rpc.assert_has_calls(
            [
                call("tools/list", {}),
                call("tools/call", {"name": "delete_database", "arguments": {"table": "users"}}),
            ]
        )
        assert "confirm" not in mock_rpc.call_args_list[1].args[1]["arguments"]
        print(f"PASS: explicit confirmation allowed simulated call. Result: {result}")

    print("\n--- TEST 3: safe tool WITHOUT confirmation ---")
    safe_proxy = MCPProxyClient(
        server_url="http://mock-mcp-server",
        tool_name="read_table",
    )
    with (
        patch.object(safe_proxy, "_initialize"),
        patch.object(
            safe_proxy,
            "_rpc",
            side_effect=[
                {"tools": [safe_tool_metadata]},
                {"content": [{"type": "text", "text": "simulated rows: 1, 2, 3"}]},
            ],
        ) as mock_rpc,
    ):
        result = safe_proxy.execute_tool(payload={"table": "users"})
        mock_rpc.assert_has_calls(
            [
                call("tools/list", {}),
                call("tools/call", {"name": "read_table", "arguments": {"table": "users"}}),
            ]
        )
        print(f"PASS: safe simulated call allowed. Result: {result}")

    print("\nRESULT: ALL 3 MCP GUARD SIMULATION CHECKS PASSED")
    print("SCOPE: mocked RPC only; no real MCP server or database was contacted.")


if __name__ == "__main__":
    run_guard_test()
