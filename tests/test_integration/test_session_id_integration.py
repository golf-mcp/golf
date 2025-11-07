import os
import pytest
from unittest.mock import patch
from golf.core.builder import CodeGenerator
from golf.core.config import Settings


class TestSessionIdIntegration:
    def test_builder_generates_session_id_imports_when_redis_configured(self, tmp_path):
        """Test that CodeGenerator generates session imports when Redis is configured."""
        with patch.dict(os.environ, {"PROXY_REDIS_URL": "redis://localhost:6379"}):
            generator = CodeGenerator(tmp_path, Settings(), tmp_path / "output")
            session_imports = generator._generate_session_imports()

            assert len(session_imports) == 7
            assert "from golf.session.store import create_redis_handler, RedisSessionStorage" in session_imports
            assert "import asyncio" in session_imports

    def test_builder_no_session_imports_when_redis_not_configured(self, tmp_path):
        """Test that CodeGenerator doesn't generate session imports when Redis is not configured."""
        with patch.dict(os.environ, {}, clear=True):
            generator = CodeGenerator(tmp_path, Settings(), tmp_path / "output")
            session_imports = generator._generate_session_imports()

            assert session_imports == []

    def test_builder_generates_session_patch_code_when_redis_configured(self, tmp_path):
        """Test that CodeGenerator generates session patching code when Redis is configured."""
        with patch.dict(os.environ, {"PROXY_REDIS_URL": "redis://localhost:6379"}):
            generator = CodeGenerator(tmp_path, Settings(), tmp_path / "output")
            patch_code = generator._generate_session_patch_code()

            assert len(patch_code) > 0
            # Check for key elements of the patch code
            patch_code_str = "\n".join(patch_code)
            assert "redis_session_handler = create_redis_handler()" in patch_code_str
            assert "fastmcp.server.context.Context.session_id = property(redis_session_id)" in patch_code_str
            assert "background_redis_init" in patch_code_str

    def test_builder_no_session_patch_code_when_redis_not_configured(self, tmp_path):
        """Test that CodeGenerator doesn't generate session patching code when Redis is not configured."""
        with patch.dict(os.environ, {}, clear=True):
            generator = CodeGenerator(tmp_path, Settings(), tmp_path / "output")
            patch_code = generator._generate_session_patch_code()

            assert patch_code == []

    def test_session_imports_integration_with_is_redis_configured(self, tmp_path):
        """Test that session imports are properly integrated with Redis configuration detection."""
        generator = CodeGenerator(tmp_path, Settings(), tmp_path / "output")

        # Test when Redis is configured
        with patch("golf.core.builder.is_redis_configured", return_value=True):
            session_imports = generator._generate_session_imports()
            assert len(session_imports) == 7
            assert "create_redis_handler" in "\n".join(session_imports)

        # Test when Redis is not configured
        with patch("golf.core.builder.is_redis_configured", return_value=False):
            session_imports = generator._generate_session_imports()
            assert session_imports == []

    def test_session_patch_integration_with_is_redis_configured(self, tmp_path):
        """Test that session patch code is properly integrated with Redis configuration detection."""
        generator = CodeGenerator(tmp_path, Settings(), tmp_path / "output")

        # Test when Redis is configured
        with patch("golf.core.builder.is_redis_configured", return_value=True):
            patch_code = generator._generate_session_patch_code()
            assert len(patch_code) > 0
            patch_code_str = "\n".join(patch_code)
            assert "Enhanced Redis session storage setup" in patch_code_str

        # Test when Redis is not configured
        with patch("golf.core.builder.is_redis_configured", return_value=False):
            patch_code = generator._generate_session_patch_code()
            assert patch_code == []


class TestEnvironmentVariableIntegration:
    """Test integration with different environment variable configurations."""

    def test_redis_url_only(self, tmp_path):
        """Test configuration with only PROXY_REDIS_URL set."""
        with patch.dict(os.environ, {"PROXY_REDIS_URL": "redis://localhost:6379"}, clear=True):
            from golf.session.store import is_redis_configured, create_redis_handler

            assert is_redis_configured() is True
            handler = create_redis_handler()
            assert handler is not None
            assert handler.redis_url == "redis://localhost:6379"
            assert handler.redis_password is None

    def test_redis_url_and_password(self, tmp_path):
        """Test configuration with both PROXY_REDIS_URL and PROXY_REDIS_PASSWORD set."""
        with patch.dict(
            os.environ, {"PROXY_REDIS_URL": "redis://localhost:6379", "PROXY_REDIS_PASSWORD": "secret123"}, clear=True
        ):
            from golf.session.store import is_redis_configured, create_redis_handler

            assert is_redis_configured() is True
            handler = create_redis_handler()
            assert handler is not None
            assert handler.redis_url == "redis://localhost:6379"
            assert handler.redis_password == "secret123"

    def test_no_redis_configuration(self, tmp_path):
        """Test behavior when no Redis environment variables are set."""
        with patch.dict(os.environ, {}, clear=True):
            from golf.session.store import is_redis_configured, create_redis_handler

            assert is_redis_configured() is False
            handler = create_redis_handler()
            assert handler is None
