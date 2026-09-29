# neural-harness-mcp — registry listing

Neural Harness's own MCP server. It is **not** the glama-gateway bridge (that is
glama-mcp); it exposes the shared validation engine directly: information
handling, neural synthesis, and fused data-integration checks, plus AiRadio's
Human Voice Index — all read-only, dependency-free, stdlib only.

## Server

| Field | Value |
|---|---|
| name | `neural-harness-mcp` |
| command | `nh-mcp` (pyproject `[project.scripts]`) |
| install | `pip install .` (Python 3.9+, no runtime deps) |
| transport | stdio, JSON-RPC 2.0, protocol `2024-11-05` |
| tools | `nh_list_projects`, `nh_voice`, `nh_validate`, `nh_site` |
| license | MIT (Karun Karun) |
| author | Sai Karun Nandipati — github.com/karun99 |

## Verify by hand

```sh
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"nh_list_projects","arguments":{}}}' \
  | python -m neural_harness.mcp_server
```

Tests: `python -m pytest tests/test_mcp_server.py` (passes with the shared suite).

## How it is seen in Glama

Glama builds every open-source server from the repo's `Dockerfile` in a sandbox,
then introspects it over MCP and scores the tools (TDQS). This repo ships a
`Dockerfile` whose `CMD ["nh-mcp"]` is the stdio server, so the sandbox can run
the handshake above and register the four tools.

1. Sign in at glama.ai with GitHub (OAuth; must have write access to this repo).
2. "Add your server" → https://github.com/karun99/neural-harness.
3. Glama clones, builds the Dockerfile, introspects, and lists it under your
   account when the build succeeds (distribution is withheld otherwise).
4. Optional: also submit an entry to the Official MCP Registry (below) — Glama
   re-publishes the whole official registry.

## Official MCP Registry entry (PR to modelcontextprotocol/servers)

Suggested `mcp_servers.json` record (adapt field names to the registry schema
at the time of the PR):

```json
{
  "name": "neural-harness-mcp",
  "description": "Shared validation engine for neural projects: information handling, neural synthesis, and fused data-integration accuracy, read-only over MCP.",
  "author": "karun99",
  "website": "https://github.com/karun99/neural-harness",
  "repository": "https://github.com/karun99/neural-harness",
  "github": "karun99/neural-harness",
  "package": "pip install neural-harness",
  "tags": ["validation", "neural", "evaluation", "llm", "mcp"],
  "license": "MIT"
}
```

## Awesome-MCP-Servers entry (punkpeye/awesome-mcp-servers)

```md
- [neural-harness-mcp](https://github.com/karun99/neural-harness) - Validation harness: information-handling, neural-synthesis and data-integration checks with a Human Voice Index grade.
```