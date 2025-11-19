"""Web operation tools."""

import json
from typing import Any

import httpx

from ..types import ToolResult
from .base import BaseTool


class WebFetchTool(BaseTool):
    """Fetch content from a URL."""

    name = "web_fetch"
    description = "Fetch content from a URL (HTML, JSON, text, etc.)"

    def get_schema(self) -> dict[str, Any]:
        """Get tool schema."""
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to fetch",
                },
                "method": {
                    "type": "string",
                    "description": "HTTP method (GET, POST, etc.)",
                    "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                },
                "headers": {
                    "type": "object",
                    "description": "Optional HTTP headers",
                },
                "body": {
                    "type": "string",
                    "description": "Optional request body (for POST/PUT)",
                },
            },
            "required": ["url"],
        }

    def execute(
        self,
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: str | None = None,
    ) -> ToolResult:
        """Execute web fetch.

        Args:
            url: URL to fetch
            method: HTTP method
            headers: Optional headers
            body: Optional request body

        Returns:
            ToolResult with response content
        """
        try:
            # Make request
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                if method == "GET":
                    response = client.get(url, headers=headers)
                elif method == "POST":
                    response = client.post(url, headers=headers, content=body)
                elif method == "PUT":
                    response = client.put(url, headers=headers, content=body)
                elif method == "DELETE":
                    response = client.delete(url, headers=headers)
                elif method == "PATCH":
                    response = client.patch(url, headers=headers, content=body)
                else:
                    return self._create_result(
                        content=f"Error: Unsupported HTTP method: {method}",
                        is_error=True,
                        metadata={"action": "web_fetch", "url": url},
                    )

                response.raise_for_status()

                # Get content
                content_type = response.headers.get("content-type", "")

                if "application/json" in content_type:
                    # Pretty print JSON
                    try:
                        content = json.dumps(response.json(), indent=2)
                    except json.JSONDecodeError:
                        content = response.text
                else:
                    # Plain text or HTML
                    content = response.text

                # Limit size
                max_size = 10000
                if len(content) > max_size:
                    content = content[:max_size] + f"\n... (truncated, {len(content)} total chars)"

                metadata = {
                    "action": "web_fetch",
                    "url": url,
                    "status_code": response.status_code,
                    "content_type": content_type,
                    "size": len(response.text),
                }

                return self._create_result(content=content, metadata=metadata)

        except httpx.HTTPStatusError as e:
            return self._create_result(
                content=f"HTTP Error {e.response.status_code}: {e.response.reason_phrase}",
                is_error=True,
                metadata={"action": "web_fetch", "url": url},
            )
        except httpx.RequestError as e:
            return self._create_result(
                content=f"Request Error: {str(e)}",
                is_error=True,
                metadata={"action": "web_fetch", "url": url},
            )
        except Exception as e:
            return self._create_result(
                content=f"Error fetching URL: {str(e)}",
                is_error=True,
                metadata={"action": "web_fetch", "url": url},
            )


class WebSearchTool(BaseTool):
    """Search the web.

    Note: This is a placeholder implementation. A real implementation would
    require integration with a search API (Google Custom Search, Bing, etc.)
    """

    name = "web_search"
    description = "Search the web for information (requires search API configuration)"

    def __init__(self, api_key: str | None = None, search_engine_id: str | None = None, **kwargs: Any):
        """Initialize web search tool.

        Args:
            api_key: Search API key (e.g., Google Custom Search API key)
            search_engine_id: Search engine ID (e.g., Google Custom Search Engine ID)
            **kwargs: Additional parameters
        """
        super().__init__(**kwargs)
        self.api_key = api_key
        self.search_engine_id = search_engine_id

    def get_schema(self) -> dict[str, Any]:
        """Get tool schema."""
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return (default: 5)",
                },
            },
            "required": ["query"],
        }

    def execute(self, query: str, num_results: int = 5) -> ToolResult:
        """Execute web search.

        Args:
            query: Search query
            num_results: Number of results

        Returns:
            ToolResult with search results

        Note:
            This is a placeholder. Real implementation requires search API setup.
        """
        # Check if API is configured
        if not self.api_key or not self.search_engine_id:
            return self._create_result(
                content=(
                    "Web search not configured. To use web search:\n"
                    "1. Get a Google Custom Search API key from https://developers.google.com/custom-search\n"
                    "2. Create a Custom Search Engine at https://cse.google.com/cse/\n"
                    "3. Pass api_key and search_engine_id to WebSearchTool"
                ),
                is_error=True,
                metadata={"action": "web_search", "query": query},
            )

        try:
            # Google Custom Search API endpoint
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": self.api_key,
                "cx": self.search_engine_id,
                "q": query,
                "num": min(num_results, 10),  # Max 10 per request
            }

            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                # Extract results
                results = []
                for item in data.get("items", []):
                    results.append({
                        "title": item.get("title"),
                        "link": item.get("link"),
                        "snippet": item.get("snippet"),
                    })

                # Format output
                if results:
                    content = "\n\n".join([
                        f"**{r['title']}**\n{r['link']}\n{r['snippet']}"
                        for r in results
                    ])
                else:
                    content = f"No results found for: {query}"

                metadata = {
                    "action": "web_search",
                    "query": query,
                    "results": len(results),
                }

                return self._create_result(content=content, metadata=metadata)

        except httpx.HTTPStatusError as e:
            return self._create_result(
                content=f"Search API Error {e.response.status_code}: {e.response.text}",
                is_error=True,
                metadata={"action": "web_search", "query": query},
            )
        except Exception as e:
            return self._create_result(
                content=f"Error performing search: {str(e)}",
                is_error=True,
                metadata={"action": "web_search", "query": query},
            )
