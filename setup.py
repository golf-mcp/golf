"""
Authed - Agent Authentication SDK
"""
from setuptools import setup, find_packages

setup(
    name="authed",
    version="0.1.2",
    author="Antoni Gmitruk",
    author_email="antoni@getauthed.com",
    description="Agent authentication SDK for secure service-to-service communication",
    url="https://github.com/authed-dev/authed",
    project_urls={
        "Documentation": "https://docs.getauthed.dev",
        "Source code": "https://github.com/authed-dev/authed",
    },
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "click>=8.0.0",
        "httpx>=0.24.0",
        "pydantic>=2.0.0",
        "cryptography>=41.0.0",
        "pyjwt>=2.8.0",
        "websockets>=12.0",
        "uvicorn[standard]>=0.27.0"
    ],
    entry_points={
        "console_scripts": [
            "authed=client.cli.main:cli"
        ]
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Security",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Systems Administration :: Authentication/Directory",
    ],
    python_requires=">=3.8",
    keywords="authentication security agent service-to-service dpop jwt",
) 