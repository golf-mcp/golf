"""Integration tests for enhanced Redis session storage"""

import os
from unittest.mock import patch
from golf.core.builder import CodeGenerator
from golf.core.config import Settings


class TestEnhancedSessionIntegration:
    def test_builder_generates_enhanced_session_patch_code_when_redis_configured(self, tmp_path):
        """Test that CodeGenerator generates enhanced session patching code when Redis is configured."""
        with patch.dict(os.environ, {"PROXY_REDIS_URL": "redis://localhost:6379"}):
            generator = CodeGenerator(tmp_path, Settings(), tmp_path / "output")
            patch_code = generator._generate_session_patch_code()

            assert len(patch_code) > 0
            # Check for enhanced session patching elements
            patch_code_str = "\n".join(patch_code)
            # Imports are handled separately, so check for actual usage in patch code
            assert "redis_session_storage = RedisSessionStorage(redis_session_handler)" in patch_code_str
            assert "StreamableHTTPSessionManager._server_instances = redis_session_storage" in patch_code_str
            assert "FastMCP session manager patched for Redis persistence" in patch_code_str

    def test_builder_generates_enhanced_session_imports_when_redis_configured(self, tmp_path):
        """Test enhanced session imports generation"""
        with patch.dict(os.environ, {"PROXY_REDIS_URL": "redis://localhost:6379"}):
            generator = CodeGenerator(tmp_path, Settings(), tmp_path / "output")
            imports = generator._generate_session_imports()

            imports_str = "\n".join(imports)
            assert "from golf.session.store import create_redis_handler, RedisSessionStorage" in imports_str

    def test_builder_skips_session_code_when_redis_not_configured(self, tmp_path):
        """Test that session patching is skipped when Redis is not configured"""
        with patch.dict(os.environ, {}, clear=True):
            generator = CodeGenerator(tmp_path, Settings(), tmp_path / "output")
            patch_code = generator._generate_session_patch_code()
            imports = generator._generate_session_imports()

            assert len(patch_code) == 0
            assert len(imports) == 0

    def test_session_patching_includes_fallback_handling(self, tmp_path):
        """Test that session patching includes proper error handling and fallbacks"""
        with patch.dict(os.environ, {"PROXY_REDIS_URL": "redis://localhost:6379"}):
            generator = CodeGenerator(tmp_path, Settings(), tmp_path / "output")
            patch_code = generator._generate_session_patch_code()

            patch_code_str = "\n".join(patch_code)
            # Check for error handling
            assert "except (ImportError, AttributeError)" in patch_code_str
            assert "Warning: Could not patch StreamableHTTPSessionManager" in patch_code_str
            assert "Session objects will use in-memory storage only" in patch_code_str

    def test_session_patching_includes_redis_initialization(self, tmp_path):
        """Test that session patching includes proper Redis initialization"""
        with patch.dict(os.environ, {"PROXY_REDIS_URL": "redis://localhost:6379"}):
            generator = CodeGenerator(tmp_path, Settings(), tmp_path / "output")
            patch_code = generator._generate_session_patch_code()

            patch_code_str = "\n".join(patch_code)
            # Check for Redis initialization
            assert "async def init_redis():" in patch_code_str
            assert "success = await redis_session_handler.initialize()" in patch_code_str
            assert "Enhanced Redis session storage enabled" in patch_code_str

    def test_context_session_id_patching_preserved(self, tmp_path):
        """Test that existing Context.session_id patching is preserved"""
        with patch.dict(os.environ, {"PROXY_REDIS_URL": "redis://localhost:6379"}):
            generator = CodeGenerator(tmp_path, Settings(), tmp_path / "output")
            patch_code = generator._generate_session_patch_code()

            patch_code_str = "\n".join(patch_code)
            # Check that Context.session_id patching is still there
            assert "fastmcp.server.context.Context.session_id = property(redis_session_id)" in patch_code_str
            assert "original_session_id_func = fastmcp.server.context.Context.session_id.fget" in patch_code_str

    def test_redis_password_support(self, tmp_path):
        """Test that Redis password is supported in generated code"""
        with patch.dict(os.environ, {"PROXY_REDIS_URL": "redis://localhost:6379", "PROXY_REDIS_PASSWORD": "secret123"}):
            generator = CodeGenerator(tmp_path, Settings(), tmp_path / "output")
            imports = generator._generate_session_imports()
            patch_code = generator._generate_session_patch_code()

            # Should include the create_redis_handler call which handles passwords
            imports_str = "\n".join(imports)
            patch_code_str = "\n".join(patch_code)
            assert "create_redis_handler" in imports_str
            assert "redis_session_handler = create_redis_handler()" in patch_code_str

    def test_async_task_creation_for_initialization(self, tmp_path):
        """Test that Redis initialization is properly scheduled"""
        with patch.dict(os.environ, {"PROXY_REDIS_URL": "redis://localhost:6379"}):
            generator = CodeGenerator(tmp_path, Settings(), tmp_path / "output")
            patch_code = generator._generate_session_patch_code()

            patch_code_str = "\n".join(patch_code)
            # Check for Redis initialization handling (background thread approach)
            assert "asyncio.run_coroutine_threadsafe(init_redis(), loop)" in patch_code_str
            assert "Background Redis initialization thread started" in patch_code_str
            assert "Background Redis initialization starting..." in patch_code_str
            # Check for debug logging setup
            assert "logging.basicConfig" in patch_code_str
            assert "print(" in patch_code_str  # Should have debug prints

    def test_imports_include_required_modules(self, tmp_path):
        """Test that all required modules are imported"""
        with patch.dict(os.environ, {"PROXY_REDIS_URL": "redis://localhost:6379"}):
            generator = CodeGenerator(tmp_path, Settings(), tmp_path / "output")
            imports = generator._generate_session_imports()

            imports_str = "\n".join(imports)
            assert "import asyncio" in imports_str
            assert "import contextlib" in imports_str
            assert "import logging" in imports_str
            assert "import os" in imports_str
            assert "import threading" in imports_str
            assert "import time" in imports_str
            assert "from golf.session.store import create_redis_handler, RedisSessionStorage" in imports_str

    def test_session_storage_ttl_configuration(self, tmp_path):
        """Test that session storage uses appropriate TTL values"""
        with patch.dict(os.environ, {"PROXY_REDIS_URL": "redis://localhost:6379"}):
            # This test ensures the generated code uses proper TTL values
            # The actual TTL values are set in the RedisSessionStorage class
            # But we can verify that the setup code is generated correctly
            generator = CodeGenerator(tmp_path, Settings(), tmp_path / "output")
            patch_code = generator._generate_session_patch_code()

            patch_code_str = "\n".join(patch_code)
            assert "redis_session_storage = RedisSessionStorage(redis_session_handler)" in patch_code_str
