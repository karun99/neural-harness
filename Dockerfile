# Neural Harness MCP server — sandboxed stdio build for Glama/registry introspection.
FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir .

# The MCP server speaks stdio; clients (and registry sandboxes) drive it via
# tools/list / tools/call over stdin/stdout.
CMD ["nh-mcp"]