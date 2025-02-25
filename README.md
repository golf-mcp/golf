# Authed - OAuth for AI Agents

## Overview

We're building Authed - OAuth for AI agents. As AI agents become real internet participants, they need a way to authenticate across organizations. OAuth and API keys were built for humans and apps, forcing agents to rely on static credentials that don't scale.

Authed is a developer-first, open-source protocol that gives agents their own ID, allowing them to securely authenticate with each other - across different ecosystems - without static keys or manual approvals. Our registry verifies identities and dynamically enforces access policies, ensuring agents only interact with trusted entities.

No static credentials. No human bottlenecks. Just secure, scalable authentication built for how agents actually work.

## Quick start

> **Note**: While Authed is open source, we currently only support our hosted registry (https://api.getauthed.dev). Self-hosting registries is possible but not officially supported yet.

### 1. Register as a provider

Before installing Authed, [register as a provider](https://getauthed.dev/). Save your provider ID and secret - you'll need these for configuration.

### 2. Install Authed

```bash
pip install authed
```

### 3. Generate keys

```bash
authed keys generate --output agent_keys.json
```

### 4. Initialize configuration

```bash
authed init config
```

This will prompt you for:
- Registry URL (https://api.getauthed.dev)
- Provider ID
- Provider secret

### 5. Create your first agent ID

```bash
authed agents create --name my-first-agent
```

## Basic integration

Here's a minimal example using FastAPI:

```python
from fastapi import FastAPI, Request
from authed import Authed, verify_fastapi, protect_httpx
import httpx

app = FastAPI()

# Initialize Authed
auth = Authed.initialize(
    registry_url="https://api.getauthed.dev",
    agent_id="your-agent-id",
    agent_secret="your-agent-secret",
    private_key="your-private-key",
    public_key="your-public-key"
)

# Protected endpoint
@app.post("/secure-endpoint")
@verify_fastapi
async def secure_endpoint(request: Request):
    return {"message": "Authenticated!"}

# Making authenticated requests
@app.get("/call-other-agent")
@protect_httpx()
async def call_other_agent():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://other-agent/secure-endpoint",
            headers={"target-agent-id": "target-agent-uuid"},
            json={"message": "Hello!"}
        )
    return response.json()
```

## Environment setup

Configure Authed using environment variables:

```bash
# Registry and agent configuration
AUTHED_REGISTRY_URL="https://api.getauthed.dev"
AUTHED_AGENT_ID="your-agent-id"
AUTHED_AGENT_SECRET="your-agent-secret"

# Keys for signing and verifying requests
AUTHED_PRIVATE_KEY="your-private-key"
AUTHED_PUBLIC_KEY="your-public-key"
```

## Documentation

For more detailed documentation, visit our [official documentation](https://docs.getauthed.dev).

## License

[MIT License](LICENSE)
