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

Get up and running with Authed in three simple steps:

### 1. Register as a Provider
Head over to [getauthed.dev](https://getauthed.dev) and create an account. You'll receive:
- A Provider ID (unique identifier for your organization)
- A Provider Secret (keep this safe!)

### 2. Install the SDK
```bash
pip install authed
```

### 3. Initialize Your First Agent
```bash
# This command will:
# - Generate a secure key pair for your agent
# - Create a new agent under your provider
# - Set up your .env with all required configuration
authed init setup --provider-id "your-provider-id" --provider-secret "your-provider-secret"
```

That's it! Your agent is ready to authenticate. Check out the Basic Integration section below for usage examples.

## Basic integration

Here's a minimal example using FastAPI:

```python
from fastapi import FastAPI, Request
from authed import Authed, verify_fastapi, protect_httpx
import httpx

app = FastAPI()

# Initialize Authed from environment variables (configured by `authed init setup`)
auth = Authed.from_env()

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

## Integrations

Authed provides integrations with various external systems and protocols:

### Model Context Protocol (MCP)

Authed can be used as an authentication layer for the [Model Context Protocol (MCP)](https://modelcontextprotocol.io), enabling secure access to MCP servers and resources. See the [MCP integration documentation](integrations/mcp/README.md) for details.

## Why choose Authed?

#### Designed for agent interactions

Authed is built specifically for the way AI agents interact - dynamic, distributed, and requiring minimal human intervention.

#### Secure by design

Our protocol uses robust cryptographic signatures and verification mechanisms to ensure agents only interact with trusted entities.

#### Scalable identity

As your ecosystem of agents grows, Authed scales with you - no need to manage ever-growing lists of API keys or credentials.

## Agent-to-Agent communication

Authed provides a Channel component for secure, authenticated communication between agents using WebSockets. This enables agents to establish connections, exchange messages, and maintain persistent communication channels with minimal setup.

### Key keatures

- **Secure WebSocket communication**: Establish authenticated WebSocket connections between agents
- **Message handling**: Register custom handlers for different message types
- **Connection management**: Automatically manage multiple connections
- **Authentication integration**: Leverages Authed's core authentication system

### Quick example

```python
# Initialize Authed
auth = Authed.from_env()

# Create a channel
channel = auth.create_channel()

# Open a channel to another agent
target_channel = await channel.open_channel(
    target_agent_id="target-agent-id",
    websocket_url="wss://target-agent-domain.com/ws"
)

# Send a message
await channel.send_message(
    channel=target_channel,
    content_type=MessageType.REQUEST,
    content_data={"text": "Hello from Agent A!"}
)

# Receive a response
response = await channel.receive_message(target_channel)
```

See the [Channel documentation](https://docs.getauthed.dev/channels) for more details and examples.

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