#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MCP smoke tests against Continuo L6 server.")
    parser.add_argument("--library-path", default=str(Path.home() / "agent-library"))
    parser.add_argument("--entity-name", default="Continuo MCP")
    parser.add_argument("--query-topic", default="Continuo MCP")
    parser.add_argument(
        "--expected-continuo-summary",
        default="",
    )
    parser.add_argument("--assertions", action="store_true")
    parser.add_argument("--json-report", default="")
    parser.add_argument(
        "--server-python",
        default=sys.executable,
        help="Python executable used to launch the Continuo L6 server.",
    )
    return parser.parse_args()


def _first_json_payload(call_result: Any) -> dict[str, Any]:
    for item in call_result.content:
        text = getattr(item, "text", None)
        if not text:
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            continue
    return {}


async def _run(args: argparse.Namespace) -> int:
    report: dict[str, Any] = {
        "status": "pass",
        "tools": [],
        "checks": {},
        "payloads": {},
    }
    server = StdioServerParameters(
        command=str(args.server_python),
        args=[
            "-m",
            "core.l6_server",
            "--library",
            str(args.library_path),
            "--transport",
            "stdio",
        ],
    )

    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = [tool.name for tool in tools.tools]
            report["tools"] = sorted(tool_names)

            find_result = await session.call_tool(
                "find_entity", {"name": args.entity_name, "access_level": "team"}
            )
            summary_result = await session.call_tool(
                "get_cross_agent_summary", {"project": args.entity_name, "access_level": "team"}
            )
            query_result = await session.call_tool(
                "query_agent_memory",
                {"agent": "cursor", "topic": args.query_topic, "access_level": "team"},
            )
            recent_result = await session.call_tool("list_recent_work", {"access_level": "team"})

            print("TOOLS:", ", ".join(sorted(tool_names)))
            for label, result in [
                ("FIND_ENTITY_RAW", find_result),
                ("CROSS_AGENT_SUMMARY_RAW", summary_result),
                ("QUERY_AGENT_MEMORY_RAW", query_result),
                ("LIST_RECENT_WORK_RAW", recent_result),
            ]:
                print(f"{label}:")
                for item in result.content:
                    if hasattr(item, "text"):
                        print(item.text)

            find_payload = _first_json_payload(find_result)
            summary_payload = _first_json_payload(summary_result)
            query_payload = _first_json_payload(query_result)
            recent_payload = _first_json_payload(recent_result)
            report["payloads"] = {
                "find_entity": find_payload,
                "get_cross_agent_summary": summary_payload,
                "query_agent_memory": query_payload,
                "list_recent_work": recent_payload,
            }

            if args.assertions:
                required_tools = {"find_entity", "get_cross_agent_summary", "list_recent_work", "query_agent_memory"}
                missing_tools = sorted(required_tools.difference(set(tool_names)))
                report["checks"]["required_tools"] = len(missing_tools) == 0
                if missing_tools:
                    raise AssertionError(f"Missing MCP tools: {missing_tools}")

                report["checks"]["find_entity_has_matches"] = bool(find_payload.get("matches"))
                if not report["checks"]["find_entity_has_matches"]:
                    raise AssertionError(f"find_entity returned no matches for {args.entity_name}.")

                cursor_summary = find_payload["matches"][0].get("summaries", {}).get("cursor", "")
                if args.expected_continuo_summary:
                    report["checks"]["continuo_summary_matches_expected"] = (
                        cursor_summary == args.expected_continuo_summary
                    )
                    if not report["checks"]["continuo_summary_matches_expected"]:
                        raise AssertionError(
                            f"Unexpected summary. Expected {args.expected_continuo_summary!r}, got {cursor_summary!r}"
                        )
                else:
                    report["checks"]["continuo_summary_matches_expected"] = True

                report["checks"]["cross_agent_summary_has_entities"] = bool(summary_payload.get("entities"))
                if not report["checks"]["cross_agent_summary_has_entities"]:
                    raise AssertionError("get_cross_agent_summary returned no entities.")

                report["checks"]["query_agent_memory_has_matches"] = bool(query_payload.get("matches"))
                if not report["checks"]["query_agent_memory_has_matches"]:
                    raise AssertionError(f"query_agent_memory returned no matches for {args.query_topic}.")

                report["checks"]["list_recent_work_has_sessions_field"] = "sessions" in recent_payload
                if not report["checks"]["list_recent_work_has_sessions_field"]:
                    raise AssertionError("list_recent_work response is missing sessions field.")

    if args.json_report:
        report_path = Path(args.json_report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    parsed_args = _parse_args()
    try:
        raise SystemExit(asyncio.run(_run(parsed_args)))
    except Exception as exc:  # noqa: BLE001
        if parsed_args.json_report:
            report_path = Path(parsed_args.json_report)
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps({"status": "fail", "error": str(exc)}, indent=2), encoding="utf-8")
        raise
