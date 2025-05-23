"""Search GitHub code."""

from typing import Annotated, List, Optional, Dict, Any
from pydantic import BaseModel, Field
import httpx

from golf.auth import get_api_key


class Output(BaseModel):
    """Code search results."""
    results: List[Dict[str, Any]]
    total_count: int


async def search(
    query: Annotated[str, Field(description="Search query (e.g., 'addClass', 'TODO', etc.)")],
    language: Annotated[Optional[str], Field(description="Filter by programming language (e.g., 'python', 'javascript')")] = None,
    repo: Annotated[Optional[str], Field(description="Search within a specific repository (format: 'owner/repo')")] = None,
    org: Annotated[Optional[str], Field(description="Search within repositories of a specific organization")] = None,
    per_page: Annotated[int, Field(description="Number of results per page (max 100)")] = 10
) -> Output:
    """Search for code on GitHub.
    
    Without authentication, you're limited to 10 requests per minute.
    With authentication, you can make up to 30 requests per minute.
    """
    github_token = get_api_key()
    
    # Build the search query
    search_parts = [query]
    if language:
        search_parts.append(f"language:{language}")
    if repo:
        search_parts.append(f"repo:{repo}")
    if org:
        search_parts.append(f"org:{org}")
    
    search_query = " ".join(search_parts)
    
    url = "https://api.github.com/search/code"
    
    # Prepare headers
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Golf-GitHub-MCP-Server"
    }
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=headers,
                params={
                    "q": search_query,
                    "per_page": min(per_page, 100)
                },
                timeout=10.0
            )
            
            if response.status_code == 403:
                # Rate limit exceeded
                return Output(results=[], total_count=0)
            
            response.raise_for_status()
            data = response.json()
            
            # Format results
            results = []
            for item in data.get("items", []):
                results.append({
                    "name": item["name"],
                    "path": item["path"],
                    "repository": item["repository"]["full_name"],
                    "url": item["html_url"],
                    "score": item.get("score", 0.0)
                })
            
            return Output(
                results=results,
                total_count=data.get("total_count", 0)
            )
            
    except httpx.HTTPStatusError:
        return Output(results=[], total_count=0)
    except Exception:
        return Output(results=[], total_count=0)


# Export the function to be used as the tool
export = search 