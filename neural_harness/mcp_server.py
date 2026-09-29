"""Model Context Protocol (MCP) stdio server exposing the neural-harness engine.

Implements MCP over stdin/stdout using newline-delimited JSON-RPC 2.0
(dependency-free, Python 3.9+, standard library only). The tool surface mirrors
the `nh` CLI but stays read-only: it runs the shared validation harness
(information handling, neural synthesis, fused data integration) and ranks
prose with AiRadio's Human Voice Index without writing report files.

Tools exposed:

  nh_list_projects   list the known project adapters
  nh_validate        run the full harness for one project
  nh_voice           grade any text's human voice index
  nh_site            evaluate every known project and return a combined report
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import List, Optional

SERVER_NAME = "neural-harness-mcp"
SERVER_VERSION = "1.0.0"
PROTOCOL_VERSION = "2024-11-05"

TOOLS: List[dict] = [
    {
        "name": "nh_list_projects",
        "description": "List known project adapters this harness can validate "
                       "(demo, celebrum, samvit, collabuild).",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "nh_voice",
        "description": "Grade the human voice index of a piece of text using "
                       "AiRadio (0 = robotic, 1 = reads human). Read-only; "
                       "never writes files.",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "nh_validate",
        "description": "Run the full neural-harness validation for one project: "
                       "information handling, neural synthesis, and fused data "
                       "integration, plus a humanized prose report with its "
                       "voice index. Read-only; no files are written.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string",
                            "description": "demo | celebrum | samvit | collabuild"},
                "root": {"type": "string",
                         "description": "parent directory containing a project "
                                        "checkout; defaults to the caller's cwd"},
            },
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "nh_site",
        "description": "Evaluate every known project adapter and return one "
                       "combined summary (best-effort; a failing project is "
                       "skipped, never fatal). Read-only; no files are written.",
        "inputSchema": {
            "type": "object",
            "properties": {"root": {"type": "string",
                                    "description": "directory containing project checkouts"}},
            "required": [],
            "additionalProperties": False,
        },
    },
]


class NeuralHarnessMCPServer:
    # ------------------------------------------------------------ dispatch
    def handle(self, msg: dict) -> Optional[dict]:
        method = msg.get("method")
        msg_id = msg.get("id")
        params = msg.get("params") or {}
        try:
            if method == "initialize":
                return self._reply(msg_id, {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                })
            if method in ("initialized", "notifications/initialized",
                          "notifications/cancelled"):
                return None  # notification: no reply
            if method == "ping":
                return self._reply(msg_id, {})
            if method == "tools/list":
                return self._reply(msg_id, {"tools": TOOLS})
            if method == "tools/call":
                reply = self._call_tool(params)
                if reply is not None and msg_id is not None:
                    reply["id"] = msg_id
                return reply
            return self._error(msg_id, -32601, f"Method not found: {method!r}")
        except Exception as exc:  # never let a bad input kill the server
            return self._error(msg_id, -32602, f"Server error: {exc!r}")

    # ------------------------------------------------------------- tools
    def _call_tool(self, params: dict) -> dict:
        name = params.get("name")
        args = params.get("arguments") or {}

        if name == "nh_list_projects":
            from .projects import ALL
            return self._tool_result({"projects": ALL,
                                      "note": "run nh_validate with one of these names"})

        if name == "nh_voice":
            text = args.get("text")
            if not isinstance(text, str) or not text.strip():
                return self._tool_error("`text` is required and must be non-empty.")
            from .airadio import rate_human_voice
            score = rate_human_voice(text)
            return self._tool_result(score.to_dict())

        if name == "nh_validate":
            project = args.get("project") or "demo"
            root = args.get("root") or os.getcwd()
            return self._tool_result(self._validate(project, root))

        if name == "nh_site":
            root = args.get("root") or os.getcwd()
            return self._tool_result(self._site(root))

        return self._tool_error(f"Unknown tool: {name!r}")

    def _validate(self, project: str, root_dir: str) -> dict:
        from .projects import ALL, run_project
        from .report import build_report
        if project not in ALL:
            return {"project": project, "error": f"unknown project {project!r}",
                    "known": list(ALL)}
        proj_root = root_dir if project == "demo" else os.path.join(root_dir, project)
        harness, results, fused = run_project(project, proj_root)
        report = build_report(harness, results, fused)
        return {
            "project": report["project"],
            "summary": report["summary"],
            "voice": report["voice"],
            "results": report["results"],
        }

    def _site(self, root_dir: str) -> dict:
        from .projects import ALL
        combined = []
        for proj in ALL:
            try:
                combined.append(self._validate(proj, root_dir))
            except Exception as exc:
                combined.append({"project": proj, "error": f"skipped: {exc!r}"})
        return {"evaluated_at_epoch": time.time(), "results": combined}

    # -------------------------------------------------------------- helpers
    @staticmethod
    def _reply(msg_id, result: dict) -> dict:
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    @staticmethod
    def _error(msg_id, code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": msg_id,
                "error": {"code": code, "message": message}}

    @staticmethod
    def _tool_result(data) -> dict:
        text = data if isinstance(data, str) else json.dumps(data, indent=2)
        return {"jsonrpc": "2.0", "id": None,
                "result": {"content": [{"type": "text", "text": text}], "isError": False}}

    @staticmethod
    def _tool_error(message: str) -> dict:
        return {"jsonrpc": "2.0", "id": None,
                "result": {"content": [{"type": "text", "text": message}], "isError": True}}


def serve_stdio(server=None) -> int:
    server = server or NeuralHarnessMCPServer()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        reply = server.handle(msg) if isinstance(msg, dict) else None
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()
    return 0


def serve_stdio_entry() -> None:
    sys.exit(serve_stdio())


if __name__ == "__main__":
    serve_stdio_entry()