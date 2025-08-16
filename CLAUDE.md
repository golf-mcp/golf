# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Golf is a Python framework for building MCP (Model Context Protocol) servers with zero boilerplate. It automatically discovers, parses, and compiles Python files containing tools, resources, and prompts into a runnable FastMCP server.

## Breaking Changes in Golf 0.2.x

Golf 0.2.x introduces breaking changes to align with FastMCP 2.11.x:

- **Authentication System**: Complete rewrite using FastMCP's built-in auth providers (JWT, OAuth, Static tokens)
- **Legacy OAuth Removed**: Custom OAuth implementation replaced with standards-compliant FastMCP providers  
- **Configuration Changes**: `auth.py` configuration must be updated to use new auth configs (legacy `pre_build.py` supported)
- **Dependency Updates**: Requires FastMCP >=2.11.0
- **Removed Files**: Legacy `oauth.py` and `provider.py` files removed from auth module
- **Deprecated Functions**: `get_provider_token()` and OAuth-related helpers return None (legacy compatibility)

## Key Architecture

- **Component Discovery**: Golf automatically scans `tools/`, `resources/`, and `prompts/` directories for Python files
- **Code Generation**: The `ManifestBuilder` in `src/golf/core/builder.py` generates FastMCP server code from parsed components
- **CLI Interface**: Entry point is `src/golf/cli/main.py` with commands: `init`, `build`, `run`
- **Configuration**: Project settings managed via `golf.json` files, parsed by `src/golf/core/config.py`
- **Authentication**: Modern JWT/OAuth auth using FastMCP 2.11+ providers in `src/golf/auth/`
- **Telemetry**: Anonymous usage tracking with OpenTelemetry support in `src/golf/telemetry/`

## Common Development Commands

### Testing
```bash
# Run all tests with coverage
make test
# OR directly:
python -m pytest tests/ -v --cov=golf --cov-report=term-missing --cov-report=html

# Run tests without coverage (faster)
make test-fast
# OR directly:
python -m pytest tests/ -v
```

### Code Quality
```bash
# Run linting (ruff)
python -m ruff check src/

# Format code (ruff format only)
python -m ruff format src/ tests/
```

### Installation
```bash
# Install in development mode with telemetry dependencies
make install-dev

# Test CLI installation
golf --version
```

## Project Structure

- `src/golf/cli/` - CLI commands and entry points
- `src/golf/core/` - Core framework logic (builder, parser, config)
- `src/golf/auth/` - Authentication providers (OAuth, API keys)
- `src/golf/telemetry/` - Usage tracking and OpenTelemetry instrumentation
- `src/golf/metrics/` - Prometheus metrics collection
- `src/golf/examples/` - Example projects (basic template)
- `tests/` - Test suite with pytest

## Testing Framework

Uses pytest with these key configurations:
- Test discovery: `test_*.py` files in `tests/` directory
- Async support: `asyncio_mode = "auto"`
- Coverage reporting: HTML reports in `htmlcov/`
- Markers: `slow` and `integration` for test categorization
- Configuration in `pyproject.toml` under `[tool.pytest.ini_options]`

## Code Style

- **Black** formatting (88 char line length)
- **Ruff** linting with strict rules
- **Mypy** type checking with strict settings
- Configuration in `pyproject.toml`

## Git Commit Guidelines

Follow these commit message patterns when making changes:

- `fix[component]: description` - Bug fixes (e.g., `fix[parser]: handle edge case in import resolution`)
- `feat[component]: description` - New features (e.g., `feat[builder]: add shared file support`)
- `refactor[component]: description` - Code refactoring (e.g., `refactor[auth]: simplify provider creation`)
- `test[component]: description` - Test additions/changes (e.g., `test[core]: add integration tests`)
- `docs[component]: description` - Documentation updates (e.g., `docs[api]: update authentication guide`)
- `style[component]: description` - Code formatting (e.g., `style[core]: format with ruff`)

Examples from recent commits:
- `fix[parser]: add shared file discovery for enhanced imports`
- `fix[builder]: enhance import mapping for any shared file`
- `fix[transformer]: improve import transformation patterns`

## Component System

Golf projects have this structure:
```
project/
├── golf.json          # Configuration
├── tools/            # Tool implementations
├── resources/        # Resource implementations
├── prompts/          # Prompt templates
└── auth.py           # Optional authentication configuration
```

Component IDs are derived from file paths: `tools/payments/charge.py` becomes `charge_payments`.

## Authentication in Golf 0.2.x

Golf 0.2.x uses FastMCP's built-in authentication providers:

### JWT Authentication (Production)
```python
# In auth.py
from golf.auth import configure_jwt_auth

configure_jwt_auth(
    jwks_uri_env_var="JWKS_URI",  # JWKS endpoint
    issuer_env_var="JWT_ISSUER",
    audience_env_var="JWT_AUDIENCE", 
    required_scopes=["read:user"],
)
```

### Development Authentication
```python
# In auth.py
from golf.auth import configure_dev_auth

configure_dev_auth(
    tokens={
        "dev-token-123": {
            "client_id": "dev-client",
            "scopes": ["read", "write"],
        }
    },
    required_scopes=["read"],
)
```

### API Key Authentication
```python
# In auth.py  
from golf.auth import configure_api_key

configure_api_key(
    header_name="Authorization",
    header_prefix="Bearer ",
    required=True,
)
```