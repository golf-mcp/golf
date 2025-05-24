# GitHub MCP Server with API Key Authentication

This example demonstrates how to build a GitHub API MCP server using Golf's API key authentication feature. The server wraps common GitHub operations and passes through authentication tokens from MCP clients to the GitHub API.

## Features

This MCP server provides tools for:

- **Repository Management** 
  - `list-repos` - List repositories for users, organizations, or the authenticated user
  
- **Issue Management** 
  - `create-issues` - Create new issues with labels
  - `list-issues` - List and filter issues by state and labels
  
- **Code Search**
  - `code-search` - Search for code across GitHub with language and repository filters
  
- **User Information**
  - `get-users` - Get user profiles or verify authentication

## Tool Naming Convention

Golf automatically derives tool names from the file structure:
- `tools/issues/create.py` → `create-issues`
- `tools/issues/list.py` → `list-issues`
- `tools/repos/list.py` → `list-repos`
- `tools/search/code.py` → `code-search`
- `tools/users/get.py` → `get-users`

## Configuration

The server is configured in `pre_build.py` to extract GitHub tokens from the `Authorization` header:

```python
configure_api_key(
    header_name="Authorization",
    header_prefix="Bearer ",
    required=True  # Reject requests without a valid API key
)
```

This configuration:
- Handles GitHub's token format: `Authorization: Bearer ghp_xxxxxxxxxxxx`
- **Enforces authentication**: When `required=True` (default), requests without a valid API key will be rejected with a 401 Unauthorized error
- For optional authentication (pass-through mode), set `required=False`

## How It Works

1. **Client sends request** with GitHub token in the Authorization header
2. **Golf middleware** checks if API key is required and present
3. **If required and missing**, the request is rejected with 401 Unauthorized
4. **If present**, the token is extracted based on your configuration
5. **Tools retrieve token** using `get_api_key()` 
6. **Token is forwarded** to GitHub API in the appropriate format
7. **GitHub validates** the token and returns results

## Running the Server

1. Build and run:
   ```bash
   golf build
   golf run
   ```

2. The server will start on `http://127.0.0.1:3000` (configurable in `golf.json`)

3. Test authentication enforcement:
   ```bash
   # This will fail with 401 Unauthorized
   curl http://localhost:3000/mcp
   
   # This will succeed
   curl -H "Authorization: Bearer ghp_your_token_here" http://localhost:3000/mcp
   ```

## GitHub Token Permissions

Depending on which tools you use, you'll need different token permissions:

- **Public repositories**: No token needed for read-only access
- **Private repositories**: Token with `repo` scope
- **Creating issues**: Token with `repo` or `public_repo` scope
- **User information**: Token with `user` scope