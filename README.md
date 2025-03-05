<div align="center">

# Authed

**Identity and authentication for AI Agents**

[![license MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/authed-dev/authed/pulls)
[![support](https://img.shields.io/badge/support-contact%20author-purple.svg)](https://github.com/authed-dev/authed/issues)
[![PyPI Downloads](https://img.shields.io/pypi/dm/authed)](https://pypi.org/project/authed/)

Authed | [Docs](https://docs.getauthed.dev)
</div>

## Overview

Authed is an identity and authentication system built specifically for AI agents. As AI agents become active participants on the internet, they need secure, scalable ways to identify themselves and authenticate with each other across different systems and organizations.

Traditional authentication methods like OAuth and API keys were designed for human users and applications, forcing agents to rely on static credentials that don't scale with the dynamic nature of AI interactions. Authed solves this problem by giving agents their own identity.

Authed is a developer-first, open-source protocol that:

- Provides unique identities for AI agents
- Enables secure agent-to-agent authentication across different ecosystems
- Eliminates the need for static credentials
- Removes human bottlenecks from authentication workflows
- Dynamically enforces access policies between trusted entities

## Quick start

> **Note**: While Authed is open source, we currently only support our hosted registry (https://api.getauthed.dev). Self-hosted registries are possible but not officially supported yet.

### 1. Register as a Provider

Before installing Authed, register as a provider. Save your provider ID and secret - you'll need these for configuration. For detailed instructions, see our registration guide.

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

### 5. Create Your First Agent ID

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

```
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

## Why choose Authed?

#### Designed for agent interactions

Authed is built specifically for the way AI agents interact - dynamic, distributed, and requiring minimal human intervention.

#### Secure by design

Our protocol uses robust cryptographic signatures and verification mechanisms to ensure agents only interact with trusted entities.

#### Scalable identity

As your ecosystem of agents grows, Authed scales with you - no need to manage ever-growing lists of API keys or credentials.


## Roadmap

We are working hard on new features!

- **Self-hosted registries**: Adding support and documentation for self-hosting registries
- **Registry interoperability**: Expanding registry to make them interoperable, allowing agents to authenticate across registries with the same ID
- **Instance-based IDs**: Adding support for instance-based identities
- **Instance binding**: Adding instance binding to agent IDs
- **OpenID integration**: Adding OpenID identity binding for end users
- **Enhanced permissions**: Expanding the permission engine to allow more fine-grained permissions


<div align="center">
Made with ❤️ in Warsaw, Poland and SF
</div>