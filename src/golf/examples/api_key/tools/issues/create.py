"""Create a new issue in a GitHub repository."""

from typing import Annotated, List, Optional
from pydantic import BaseModel, Field
import httpx

from golf.auth import get_api_key


class Output(BaseModel):
    """Response from creating an issue."""
    success: bool
    issue_number: Optional[int] = None
    issue_url: Optional[str] = None
    error: Optional[str] = None


async def create(
    repo: Annotated[str, Field(description="Repository name in format 'owner/repo'")],
    title: Annotated[str, Field(description="Issue title")],
    body: Annotated[str, Field(description="Issue description/body (supports Markdown)")] = "",
    labels: Annotated[Optional[List[str]], Field(description="List of label names to apply")] = None
) -> Output:
    """Create a new issue.
    
    Requires authentication with appropriate permissions.
    """
    github_token = get_api_key()
    
    if not github_token:
        return Output(
            success=False,
            error="Authentication required. Please provide a GitHub token."
        )
    
    # Validate repo format
    if '/' not in repo:
        return Output(
            success=False,
            error="Repository must be in format 'owner/repo'"
        )
    
    url = f"https://api.github.com/repos/{repo}/issues"
    
    # Build request payload
    payload = {
        "title": title,
        "body": body
    }
    if labels:
        payload["labels"] = labels
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {github_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "Golf-GitHub-MCP-Server"
                },
                json=payload,
                timeout=10.0
            )
            
            response.raise_for_status()
            issue_data = response.json()
            
            return Output(
                success=True,
                issue_number=issue_data["number"],
                issue_url=issue_data["html_url"]
            )
            
    except httpx.HTTPStatusError as e:
        error_messages = {
            401: "Invalid or missing authentication token",
            403: "Insufficient permissions to create issues in this repository",
            404: "Repository not found",
            422: "Invalid request data"
        }
        return Output(
            success=False,
            error=error_messages.get(e.response.status_code, f"GitHub API error: {e.response.status_code}")
        )
    except Exception as e:
        return Output(
            success=False,
            error=f"Failed to create issue: {str(e)}"
        )


# Export the function to be used as the tool
export = create 