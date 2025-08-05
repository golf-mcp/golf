# Golf MCP Project Template (Basic)

This is a basic template for creating MCP servers with Golf. It includes development authentication for easy testing. Use `golf init <project-name>` to bootstrap new projects from this template.

## About Golf

Golf is a Python framework for building MCP (Model Context Protocol) servers with minimal boilerplate. Define your server's capabilities as simple Python files, and Golf automatically discovers and compiles them into a runnable FastMCP server.

## Getting Started

After initializing your project:

1. **Navigate to your project directory:**
   ```bash
   cd your-project-name
   ```

2. **Configure authentication (optional):**
   This template includes development authentication in `auth.py` with sample tokens. Edit the file to set up JWT, OAuth, or API key authentication for production use.

3. **Build and run your server:**
   ```bash
   golf build dev    # Development build
   golf run          # Start the server
   ```

## Project Structure

```
your-project/
├── tools/           # Tool implementations (functions LLMs can call)
├── resources/       # Resource implementations (data LLMs can read)  
├── prompts/         # Prompt templates (conversation structures)
├── golf.json        # Server configuration
└── auth.py          # Authentication setup
```

## Adding Components

### Tools
Create `.py` files in `tools/` directory. Each file should export a single async function:

```python
# tools/calculator.py
async def add(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b

export = add
```

### Resources  
Create `.py` files in `resources/` directory with a `resource_uri` and export function:

```python
# resources/status.py
resource_uri = "status://server"

async def status() -> dict:
    """Get server status information."""
    return {"status": "running", "timestamp": "2024-01-01T00:00:00Z"}

export = status
```

### Prompts
Create `.py` files in `prompts/` directory that return message lists:

```python
# prompts/assistant.py
async def assistant() -> list[dict]:
    """System prompt for a helpful assistant."""
    return [
        {
            "role": "system", 
            "content": "You are a helpful assistant for {{project_name}}."
        }
    ]

export = assistant
```

## Authentication Examples

### No Authentication (Default)
Leave `auth.py` empty or remove it entirely.

### API Key Authentication
```python
# auth.py
from golf.auth import configure_api_key

configure_api_key(
    header_name="Authorization",
    header_prefix="Bearer ",
    required=True
)
```

### JWT Authentication  
```python
# auth.py
from golf.auth import configure_jwt_auth

configure_jwt_auth(
    jwks_uri="https://your-domain.auth0.com/.well-known/jwks.json",
    issuer="https://your-domain.auth0.com/",
    audience="https://your-api.example.com"
)
```

### Development Tokens
```python
# auth.py  
from golf.auth import configure_dev_auth

configure_dev_auth(
    tokens={
        "dev-token-123": {
            "client_id": "dev-client",
            "scopes": ["read", "write"]
        }
    }
)
```

## Documentation

For comprehensive documentation, visit: [https://docs.golf.dev](https://docs.golf.dev)

---

Happy building! 🏌️‍♂️