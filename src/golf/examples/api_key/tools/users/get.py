"""Get GitHub user information."""

from typing import Annotated, Optional, Dict, Any
from pydantic import BaseModel, Field
import httpx

from golf.auth import get_api_key


class Output(BaseModel):
    """User information result."""
    found: bool
    user: Optional[Dict[str, Any]] = None


async def get(
    username: Annotated[Optional[str], Field(description="GitHub username (if not provided, gets authenticated user)")] = None
) -> Output:
    """Get information about a GitHub user.
    
    If no username is provided, returns information about the authenticated user.
    This is useful for testing if authentication is working correctly.
    """
    github_token = get_api_key()
    
    # Determine the API endpoint
    if username:
        url = f"https://api.github.com/users/{username}"
    else:
        # Get authenticated user - requires token
        if not github_token:
            return Output(found=False)
        url = "https://api.github.com/user"
    
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
                timeout=10.0
            )
            
            response.raise_for_status()
            user_data = response.json()
            
            return Output(
                found=True,
                user={
                    "login": user_data["login"],
                    "name": user_data.get("name", ""),
                    "email": user_data.get("email", ""),
                    "bio": user_data.get("bio", ""),
                    "company": user_data.get("company", ""),
                    "location": user_data.get("location", ""),
                    "public_repos": user_data.get("public_repos", 0),
                    "followers": user_data.get("followers", 0),
                    "following": user_data.get("following", 0),
                    "created_at": user_data["created_at"],
                    "url": user_data["html_url"]
                }
            )
            
    except httpx.HTTPStatusError as e:
        if e.response.status_code in [401, 404]:
            return Output(found=False)
        else:
            return Output(found=False)
    except Exception:
        return Output(found=False)


# Export the function to be used as the tool
export = get 