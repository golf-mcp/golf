"""Tool for fetching GitHub user information."""

import httpx
from pydantic import BaseModel

from golf.auth import get_provider_token


class GitHubUserResponse(BaseModel):
    """Response model for GitHub user information."""

    login: str
    id: int
    name: str | None = None
    email: str | None = None
    avatar_url: str | None = None
    location: str | None = None
    bio: str | None = None
    public_repos: int = 0
    followers: int = 0
    following: int = 0
    message: str | None = None


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
