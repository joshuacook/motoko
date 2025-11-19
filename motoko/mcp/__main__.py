"""MCP server entrypoint for python -m motoko.mcp invocation."""

from .server import serve

if __name__ == "__main__":
    serve()
