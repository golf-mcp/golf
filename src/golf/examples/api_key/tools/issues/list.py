"""List issues in a GitHub repository."""

from typing import Annotated, List, Optional, Dict, Any
from pydantic import BaseModel, Field
import httpx

from golf.auth import get_api_key


class Output(BaseModel):
    """List of issues from the repository."""
    issues: List[Dict[str, Any]]
    total_count: int


async def list(
    repo: Annotated[str, Field(description="Repository name in format 'owner/repo'")],
    state: Annotated[str, Field(description="Filter by state - 'open', 'closed', or 'all'")] = "open",
    labels: Annotated[Optional[str], Field(description="Comma-separated list of label names to filter by")] = None,
    per_page: Annotated[int, Field(description="Number of results per page (max 100)")] = 20
) -> Output:
    """List issues in a repository.
    
    Returns issues with their number, title, state, and other metadata.
    Pull requests are filtered out from the results.
    """
    github_token = get_api_key()
    
    # Validate repo format
    if '/' not in repo:
        return Output(issues=[], total_count=0)
    
    url = f"https://api.github.com/repos/{repo}/issues"
    
    # Prepare headers
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Golf-GitHub-MCP-Server"
    }
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    
    # Build query parameters
    params = {
        "state": state,
        "per_page": min(per_page, 100)
    }
    if labels:
        params["labels"] = labels
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=headers,
                params=params,
                timeout=10.0
            )
            
            response.raise_for_status()
            issues_data = response.json()
            
            # Filter out pull requests and format issues
            issues = []
            for issue in issues_data:
                # Skip pull requests (they appear in issues endpoint too)
                if "pull_request" in issue:
                    continue
                
                issues.append({
                    "number": issue["number"],
                    "title": issue["title"],
                    "body": issue.get("body", ""),
                    "state": issue["state"],
                    "url": issue["html_url"],
                    "user": issue["user"]["login"],
                    "labels": [label["name"] for label in issue.get("labels", [])]
                })
            
            return Output(issues=issues, total_count=len(issues))
            
    except Exception:
        return Output(issues=[], total_count=0)


# Export the function to be used as the tool
export = list 