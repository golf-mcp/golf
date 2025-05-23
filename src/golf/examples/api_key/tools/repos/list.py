"""List GitHub repositories for a user or organization."""

from typing import Annotated, List, Optional, Dict, Any
from pydantic import BaseModel, Field
import httpx

from golf.auth import get_api_key


class Output(BaseModel):
    """List of repositories."""
    repositories: List[Dict[str, Any]]
    total_count: int


async def list(
    username: Annotated[Optional[str], Field(description="GitHub username (lists public repos, or all repos if authenticated as this user)")] = None,
    org: Annotated[Optional[str], Field(description="GitHub organization name (lists public repos, or all repos if authenticated member)")] = None,
    sort: Annotated[str, Field(description="How to sort results - 'created', 'updated', 'pushed', 'full_name'")] = "updated",
    per_page: Annotated[int, Field(description="Number of results per page (max 100)")] = 20
) -> Output:
    """List GitHub repositories.
    
    If neither username nor org is provided, lists repositories for the authenticated user.
    """
    # Get the GitHub token from the request context
    github_token = get_api_key()
    
    # Determine the API endpoint
    if org:
        url = f"https://api.github.com/orgs/{org}/repos"
    elif username:
        url = f"https://api.github.com/users/{username}/repos"
    else:
        # List repos for authenticated user
        if not github_token:
            return Output(repositories=[], total_count=0)
        url = "https://api.github.com/user/repos"
    
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
                    "sort": sort,
                    "per_page": min(per_page, 100),
                    "type": "all" if not username and not org else None
                },
                timeout=10.0
            )
            
            response.raise_for_status()
            repos_data = response.json()
            
            # Format repositories
            repositories = []
            for repo in repos_data:
                repositories.append({
                    "name": repo["name"],
                    "full_name": repo["full_name"],
                    "description": repo.get("description", ""),
                    "private": repo.get("private", False),
                    "stars": repo.get("stargazers_count", 0),
                    "forks": repo.get("forks_count", 0),
                    "language": repo.get("language", ""),
                    "url": repo["html_url"]
                })
            
            return Output(repositories=repositories, total_count=len(repositories))
            
    except httpx.HTTPStatusError as e:
        if e.response.status_code in [401, 404]:
            return Output(repositories=[], total_count=0)
        else:
            return Output(repositories=[], total_count=0)
    except Exception:
        return Output(repositories=[], total_count=0)


# Export the function to be used as the tool
export = list 