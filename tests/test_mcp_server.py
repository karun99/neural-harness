"""Tests for the neural-harness MCP stdio server."""

import json

from neural_harness.mcp_server import NeuralHarnessMCPServer


def _replies(server, *msgs):
    out = []
    for raw in msgs:
        reply = server.handle(json.loads(raw))
        if reply is not None:
            out.append(reply)
    return out


def test_initialize():
    server = NeuralHarnessMCPServer()
    r = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert r["result"]["serverInfo"]["name"] == "neural-harness-mcp"
    assert r["result"]["protocolVersion"] == "2024-11-05"


def test_ping_and_unknown_method():
    server = NeuralHarnessMCPServer()
    assert server.handle({"jsonrpc": "2.0", "id": 2, "method": "ping"})["result"] == {}
    err = server.handle({"jsonrpc": "2.0", "id": 3, "method": "bogus"})
    assert err["error"]["code"] == -32601


def test_notifications_get_no_reply():
    server = NeuralHarnessMCPServer()
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_tools_list():
    server = NeuralHarnessMCPServer()
    r = server.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/list"})
    names = [t["name"] for t in r["result"]["tools"]]
    assert names == ["nh_list_projects", "nh_voice", "nh_validate", "nh_site"]
    for t in r["result"]["tools"]:
        assert "inputSchema" in t


def test_list_projects():
    server = NeuralHarnessMCPServer()
    r = server.handle({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                       "params": {"name": "nh_list_projects", "arguments": {}}})
    text = r["result"]["content"][0]["text"]
    assert "demo" in text and "celebrum" in text and "samvit" in text


def test_voice_is_readonly():
    server = NeuralHarnessMCPServer()
    r = server.handle({"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                       "params": {"name": "nh_voice",
                                  "arguments": {"text": "hello there friend"}}})
    body = json.loads(r["result"]["content"][0]["text"])
    assert "human_voice_index" in body
    assert 0.0 <= body["human_voice_index"] <= 1.0


def test_voice_requires_text():
    server = NeuralHarnessMCPServer()
    r = server.handle({"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                       "params": {"name": "nh_voice", "arguments": {}}})
    assert r["result"]["isError"] is True


def test_validate_demo_project():
    server = NeuralHarnessMCPServer()
    r = server.handle({"jsonrpc": "2.0", "id": 8, "method": "tools/call",
                       "params": {"name": "nh_validate",
                                  "arguments": {"project": "demo"}}})
    body = json.loads(r["result"]["content"][0]["text"])
    assert body["project"] == "demo"
    assert "summary" in body and "voice" in body and "results" in body


def test_validate_unknown_project():
    server = NeuralHarnessMCPServer()
    r = server.handle({"jsonrpc": "2.0", "id": 9, "method": "tools/call",
                       "params": {"name": "nh_validate",
                                  "arguments": {"project": "nope"}}})
    body = json.loads(r["result"]["content"][0]["text"])
    assert "error" in body


def test_site_best_effort():
    server = NeuralHarnessMCPServer()
    r = server.handle({"jsonrpc": "2.0", "id": 10, "method": "tools/call",
                       "params": {"name": "nh_site", "arguments": {}}})
    body = json.loads(r["result"]["content"][0]["text"])
    assert isinstance(body["results"], list)
    assert len(body["results"]) == 4


def test_unknown_tool_is_error():
    server = NeuralHarnessMCPServer()
    r = server.handle({"jsonrpc": "2.0", "id": 11, "method": "tools/call",
                       "params": {"name": "nope", "arguments": {}}})
    assert r["result"]["isError"] is True