"""
Test script to verify that the MCP integration can be imported correctly.
"""

def test_imports():
    """Test that all components can be imported."""
    try:
        from integrations.mcp import (
            AuthedMCPServerAdapter,
            AuthedMCPClientAdapter,
            register_mcp_server,
            grant_mcp_access
        )
        print("✅ All imports successful!")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

if __name__ == "__main__":
    test_imports() 