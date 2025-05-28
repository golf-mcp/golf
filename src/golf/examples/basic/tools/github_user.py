"""Tool for fetching GitHub user information."""

from typing import Optional
from pydantic import BaseModel
import httpx
from golf.auth import get_provider_token


class GitHubUserResponse(BaseModel):
    """Response model for GitHub user information."""

    login: str
    id: int
    name: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    location: Optional[str] = None
    bio: Optional[str] = None
    public_repos: int = 0
    followers: int = 0
    following: int = 0
    message: Optional[str] = None


async def get_github_user() -> GitHubUserResponse:
    """Fetch authenticated user's GitHub profile information."""
    try:
        # Get GitHub token using our abstraction
        github_token = get_provider_token()

        if not github_token:
            return GitHubUserResponse(
                login="anonymous",
                id=0,
                message="Not authenticated. Please login first.",
            )

        # Call GitHub API to get user info
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {github_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )

            if response.status_code == 200:
                data = response.json()
                return GitHubUserResponse(**data)
            else:
                return GitHubUserResponse(
                    login="error",
                    id=0,
                    message=f"GitHub API error: {response.status_code} - {response.text[:100]}",
                )

    except Exception as e:
        return GitHubUserResponse(
            login="error", id=0, message=f"Error fetching GitHub data: {str(e)}"
        )


# Export the tool
export = get_github_user
