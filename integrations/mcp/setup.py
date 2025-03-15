from setuptools import setup, find_namespace_packages

setup(
    name="authed-mcp",
    version="0.1.0",
    description="Authed integration with Model Context Protocol (MCP)",
    author="Authed Team",
    author_email="info@authed.ai",
    url="https://github.com/authed/authed",
    packages=find_namespace_packages(include=["integrations.mcp*"]),
    install_requires=[
        "authed>=0.1.0",
        "mcp>=0.1.0",
        "python-dotenv>=1.0.0",
        "fastapi>=0.68.0",
        "uvicorn>=0.15.0",
        "starlette>=0.14.2",
        "httpx>=0.24.0",
    ],
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
) 