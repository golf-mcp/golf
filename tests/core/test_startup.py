"""Tests for startup.py script functionality in Golf MCP builder."""

import json
from pathlib import Path

from golf.core.builder import CodeGenerator, build_project
from golf.core.config import load_settings


class TestStartupScriptGeneration:
    """Test startup script code generation functionality."""

    def test_startup_section_generation_when_startup_exists(self, sample_project: Path, temp_dir: Path) -> None:
        """Test that startup script execution code is generated when startup.py exists."""
        # Create a startup.py file in the project
        startup_file = sample_project / "startup.py"
        startup_file.write_text(
            '''"""Startup script for secrets and initialization."""
import os

# Set environment variables
os.environ["DATABASE_URL"] = "sqlite:///app.db"
os.environ["SECRET_KEY"] = "dev-secret-key"

print("Startup script executed successfully")
'''
        )

        # Create a simple tool
        tool_file = sample_project / "tools" / "simple.py"
        tool_file.write_text(
            '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    return Output(result="done")

export = simple_tool
'''
        )

        # Generate code
        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        generator.generate()

        # Check that server.py was generated
        server_file = temp_dir / "server.py"
        assert server_file.exists()

        server_code = server_file.read_text()

        # Verify startup script execution code is included
        assert "# Execute startup script for loading secrets and initialization" in server_code
        assert "import importlib.util" in server_code
        assert 'startup_path = Path(__file__).parent / "startup.py"' in server_code
        assert "if startup_path.exists():" in server_code
        assert 'spec = importlib.util.spec_from_file_location("startup", startup_path)' in server_code
        assert "spec.loader.exec_module(startup_module)" in server_code

        # Verify error handling is included
        assert "except Exception as e:" in server_code
        assert 'print(f"Warning: Startup script execution failed: {e}", file=sys.stderr)' in server_code

        # Verify environment restoration
        assert "original_dir = os.getcwd()" in server_code
        assert "original_path = sys.path.copy()" in server_code
        assert "os.chdir(original_dir)" in server_code
        assert "sys.path[:] = original_path" in server_code

        # Verify debug output support
        assert 'if os.environ.get("GOLF_DEBUG"):' in server_code
        assert 'print(f"Executing startup script: {startup_path}")' in server_code

    def test_no_startup_section_when_startup_not_exists(self, sample_project: Path, temp_dir: Path) -> None:
        """Test that startup script execution code is not generated when startup.py doesn't exist."""
        # Create a simple tool (no startup.py file)
        tool_file = sample_project / "tools" / "simple.py"
        tool_file.write_text(
            '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    return Output(result="done")

export = simple_tool
'''
        )

        # Generate code
        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        generator.generate()

        # Check that server.py was generated
        server_file = temp_dir / "server.py"
        assert server_file.exists()

        server_code = server_file.read_text()

        # Verify startup script execution code is not included
        assert "# Execute startup script for loading secrets and initialization" not in server_code
        assert 'startup_path = Path(__file__).parent / "startup.py"' not in server_code
        assert 'importlib.util.spec_from_file_location("startup"' not in server_code

    def test_startup_script_copying_during_build(self, sample_project: Path, temp_dir: Path) -> None:
        """Test that startup.py is copied to the build directory during build."""
        # Create startup.py with specific content
        startup_content = '''"""Startup script for secrets and initialization."""
import os

# Set environment variables
os.environ["API_KEY"] = "test-api-key"
os.environ["DATABASE_URL"] = "postgresql://localhost:5432/mydb"

print("Startup configuration loaded")
'''
        startup_file = sample_project / "startup.py"
        startup_file.write_text(startup_content)

        # Create a simple tool
        tool_file = sample_project / "tools" / "simple.py"
        tool_file.write_text(
            '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    return Output(result="done")

export = simple_tool
'''
        )

        # Build the project
        settings = load_settings(sample_project)
        output_dir = temp_dir / "build"
        build_project(sample_project, settings, output_dir, build_env="dev", copy_env=False)

        # Verify startup.py was copied to build directory
        copied_startup = output_dir / "startup.py"
        assert copied_startup.exists()

        # Verify content is identical
        assert copied_startup.read_text() == startup_content

    def test_startup_section_with_working_directory_handling(self, sample_project: Path, temp_dir: Path) -> None:
        """Test that startup script execution handles working directory changes correctly."""
        # Create a startup.py file
        startup_file = sample_project / "startup.py"
        startup_file.write_text(
            '''"""Startup script that depends on working directory."""
import os
from pathlib import Path

# This startup script depends on being in the right directory
config_file = Path("config.txt")
if config_file.exists():
    print(f"Found config file in {os.getcwd()}")
'''
        )

        # Create a simple tool
        tool_file = sample_project / "tools" / "simple.py"
        tool_file.write_text(
            '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    return Output(result="done")

export = simple_tool
'''
        )

        # Generate code
        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        generator.generate()

        server_file = temp_dir / "server.py"
        server_code = server_file.read_text()

        # Verify working directory change and restoration
        assert "script_dir = str(startup_path.parent)" in server_code
        assert "os.chdir(script_dir)" in server_code
        assert "sys.path.insert(0, script_dir)" in server_code

        # Verify restoration in finally block
        assert "finally:" in server_code
        assert "# Always restore original environment" in server_code

    def test_startup_section_with_error_handling_for_deleted_directory(
        self, sample_project: Path, temp_dir: Path
    ) -> None:
        """Test that startup script handles the case where current directory was deleted."""
        # Create a startup.py file
        startup_file = sample_project / "startup.py"
        startup_file.write_text('print("Startup script executed")')

        # Create a simple tool
        tool_file = sample_project / "tools" / "simple.py"
        tool_file.write_text(
            '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    return Output(result="done")

export = simple_tool
'''
        )

        # Generate code
        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        generator.generate()

        server_file = temp_dir / "server.py"
        server_code = server_file.read_text()

        # Verify error handling for deleted current directory
        assert "try:" in server_code
        assert "original_dir = os.getcwd()" in server_code
        assert "except (FileNotFoundError, OSError):" in server_code
        assert "# Use server directory as fallback" in server_code
        assert "original_dir = str(Path(__file__).parent)" in server_code

        # Verify restoration error handling
        assert "except Exception:" in server_code
        assert "# If directory restoration fails, at least fix the path" in server_code

    def test_startup_section_debug_output(self, sample_project: Path, temp_dir: Path) -> None:
        """Test that startup script includes debug output functionality."""
        # Create a startup.py file
        startup_file = sample_project / "startup.py"
        startup_file.write_text('print("Debug startup script")')

        # Create a simple tool
        tool_file = sample_project / "tools" / "simple.py"
        tool_file.write_text(
            '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    return Output(result="done")

export = simple_tool
'''
        )

        # Generate code
        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        generator.generate()

        server_file = temp_dir / "server.py"
        server_code = server_file.read_text()

        # Verify debug output is included
        assert "# Debug output for startup script development" in server_code
        assert 'if os.environ.get("GOLF_DEBUG"):' in server_code
        assert 'print(f"Executing startup script: {startup_path}")' in server_code
        assert 'print(f"Working directory: {os.getcwd()}")' in server_code
        assert 'print(f"Python path: {sys.path[:3]}...")' in server_code

    def test_startup_section_success_message(self, sample_project: Path, temp_dir: Path) -> None:
        """Test that startup script includes success message."""
        # Create a startup.py file
        startup_file = sample_project / "startup.py"
        startup_file.write_text('print("Startup executed")')

        # Create a simple tool
        tool_file = sample_project / "tools" / "simple.py"
        tool_file.write_text(
            '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    return Output(result="done")

export = simple_tool
'''
        )

        # Generate code
        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        generator.generate()

        server_file = temp_dir / "server.py"
        server_code = server_file.read_text()

        # Verify warning messages
        assert 'print("Warning: Could not load startup.py", file=sys.stderr)' in server_code


class TestStartupScriptEdgeCases:
    """Test edge cases for startup script functionality."""

    def test_startup_section_handles_empty_startup_file(self, sample_project: Path, temp_dir: Path) -> None:
        """Test that empty startup.py file is handled correctly."""
        # Create empty startup.py
        startup_file = sample_project / "startup.py"
        startup_file.write_text("")

        # Create a simple tool
        tool_file = sample_project / "tools" / "simple.py"
        tool_file.write_text(
            '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    return Output(result="done")

export = simple_tool
'''
        )

        # Generate code
        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        generator.generate()

        server_file = temp_dir / "server.py"
        assert server_file.exists()

        server_code = server_file.read_text()

        # Even empty startup.py should trigger startup section generation
        assert 'startup_path = Path(__file__).parent / "startup.py"' in server_code
        assert "if startup_path.exists():" in server_code

        # Build the project to verify empty file is copied
        output_dir = temp_dir / "build"
        build_project(sample_project, load_settings(sample_project), output_dir, build_env="dev")

        copied_startup = output_dir / "startup.py"
        assert copied_startup.exists()
        assert copied_startup.read_text() == ""

    def test_startup_section_ordering_in_generated_server(self, sample_project: Path, temp_dir: Path) -> None:
        """Test that startup section appears in the correct order in generated server.py."""
        # Create a startup.py file
        startup_file = sample_project / "startup.py"
        startup_file.write_text('print("Startup script")')

        # Create a simple tool
        tool_file = sample_project / "tools" / "simple.py"
        tool_file.write_text(
            '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    return Output(result="done")

export = simple_tool
'''
        )

        # Generate code
        settings = load_settings(sample_project)
        generator = CodeGenerator(sample_project, settings, temp_dir)
        generator.generate()

        server_file = temp_dir / "server.py"
        server_code = server_file.read_text()

        # Find positions of key sections
        dotenv_load_pos = server_code.find("load_dotenv()")
        startup_section_pos = server_code.find("# Execute startup script for loading secrets and initialization")
        mcp_creation_pos = server_code.find("# Create FastMCP server")
        component_registration_pos = server_code.find("# Register")

        # Verify ordering: imports -> dotenv -> startup -> mcp creation -> component registration
        assert dotenv_load_pos < startup_section_pos, "dotenv load should come before startup section"
        assert startup_section_pos < mcp_creation_pos, "startup section should come before MCP creation"
        assert mcp_creation_pos < component_registration_pos, "MCP creation should come before component registration"

    def test_no_startup_copy_when_file_not_exists(self, sample_project: Path, temp_dir: Path) -> None:
        """Test that no startup.py is copied when it doesn't exist in source."""
        # Create only a tool (no startup.py)
        tool_file = sample_project / "tools" / "simple.py"
        tool_file.write_text(
            '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    return Output(result="done")

export = simple_tool
'''
        )

        # Build the project
        settings = load_settings(sample_project)
        output_dir = temp_dir / "build"
        build_project(sample_project, settings, output_dir, build_env="dev", copy_env=False)

        # Verify startup.py was not copied
        copied_startup = output_dir / "startup.py"
        assert not copied_startup.exists()


class TestStartupScriptManualValidation:
    """Manual validation tests for startup script functionality."""

    def test_build_and_validate_startup_functionality(self, temp_dir: Path) -> None:
        """Create a test project, build it, and validate startup functionality works."""
        # Create a test project directory
        test_project = temp_dir / "startup_test_project"
        test_project.mkdir()

        # Create project structure
        (test_project / "tools").mkdir()
        (test_project / "resources").mkdir()
        (test_project / "prompts").mkdir()

        # Create golf.json
        config = {
            "name": "StartupTestProject",
            "description": "Test project for startup script validation",
            "transport": "stdio",
        }
        (test_project / "golf.json").write_text(json.dumps(config, indent=2))

        # Create a meaningful startup.py that sets environment variables
        startup_content = '''"""Startup script that configures the environment."""
import os

# Set up database connection
os.environ["DATABASE_URL"] = "sqlite:///test.db"

# Configure API keys
os.environ["OPENAI_API_KEY"] = "test-openai-key"
os.environ["ANTHROPIC_API_KEY"] = "test-anthropic-key"

# Set debug mode
os.environ["DEBUG"] = "true"

print("Environment configured successfully")
print(f"Database URL: {os.environ.get('DATABASE_URL')}")
print(f"Debug mode: {os.environ.get('DEBUG')}")
'''
        (test_project / "startup.py").write_text(startup_content)

        # Create a tool that uses environment variables
        tool_content = '''"""Tool that uses environment variables set by startup script."""

from pydantic import BaseModel
import os

class ConfigOutput(BaseModel):
    database_url: str
    debug_mode: str
    openai_configured: bool

def get_config() -> ConfigOutput:
    """Get configuration from environment variables."""
    return ConfigOutput(
        database_url=os.environ.get("DATABASE_URL", "not set"),
        debug_mode=os.environ.get("DEBUG", "false"),
        openai_configured=bool(os.environ.get("OPENAI_API_KEY"))
    )

export = get_config
'''
        (test_project / "tools" / "config.py").write_text(tool_content)

        # Build the project
        settings = load_settings(test_project)
        build_dir = temp_dir / "built_project"
        build_project(test_project, settings, build_dir, build_env="dev", copy_env=False)

        # Validate build artifacts
        assert (build_dir / "server.py").exists()
        assert (build_dir / "startup.py").exists()
        assert (build_dir / "components" / "tools" / "config.py").exists()

        # Validate startup.py content was copied correctly
        copied_startup_content = (build_dir / "startup.py").read_text()
        assert copied_startup_content == startup_content

        # Validate server.py contains startup execution code
        server_content = (build_dir / "server.py").read_text()

        # Check for key startup script execution components
        startup_checks = [
            "# Execute startup script for loading secrets and initialization",
            'startup_path = Path(__file__).parent / "startup.py"',
            "if startup_path.exists():",
            'spec = importlib.util.spec_from_file_location("startup", startup_path)',
            "spec.loader.exec_module(startup_module)",
            "except Exception as e:",
            'print(f"Warning: Startup script execution failed: {e}", file=sys.stderr)',
            "finally:",
            "os.chdir(original_dir)",
            "sys.path[:] = original_path",
        ]

        for check in startup_checks:
            assert check in server_content, f"Missing startup execution code: {check}"

        # Validate the tool was processed correctly
        tool_file = build_dir / "components" / "tools" / "config.py"
        assert tool_file.exists()

        print("✓ Startup script functionality validation passed!")
        return True

    def test_startup_script_with_imports(self, temp_dir: Path) -> None:
        """Test startup script that imports other modules."""
        # Create a test project
        test_project = temp_dir / "import_test_project"
        test_project.mkdir()

        # Create project structure
        (test_project / "tools").mkdir()
        (test_project / "resources").mkdir()
        (test_project / "prompts").mkdir()

        # Create golf.json
        config = {"name": "ImportTestProject", "transport": "stdio"}
        (test_project / "golf.json").write_text(json.dumps(config))

        # Create a helper module
        helper_content = '''"""Helper module for startup script."""

def configure_logging():
    import logging
    logging.basicConfig(level=logging.INFO)
    return "Logging configured"

def load_secrets():
    return {
        "api_key": "secret-key-123",
        "db_password": "db-secret-456"
    }
'''
        (test_project / "helpers.py").write_text(helper_content)

        # Create startup.py that imports the helper
        startup_content = '''"""Startup script with imports."""
import os
from helpers import configure_logging, load_secrets

# Configure logging
log_message = configure_logging()
print(f"Startup: {log_message}")

# Load secrets
secrets = load_secrets()
os.environ["API_KEY"] = secrets["api_key"]
os.environ["DB_PASSWORD"] = secrets["db_password"]

print("Startup script with imports executed successfully")
'''
        (test_project / "startup.py").write_text(startup_content)

        # Create a simple tool
        (test_project / "tools" / "simple.py").write_text(
            '''"""Simple tool."""

from pydantic import BaseModel

class Output(BaseModel):
    result: str

def simple_tool() -> Output:
    return Output(result="done")

export = simple_tool
'''
        )

        # Build the project
        settings = load_settings(test_project)
        build_dir = temp_dir / "built_import_project"
        build_project(test_project, settings, build_dir, build_env="dev", copy_env=False)

        # Validate build
        assert (build_dir / "server.py").exists()
        assert (build_dir / "startup.py").exists()

        # Note: helpers.py won't be automatically copied since it's not in components dirs
        # The startup script will need to handle this or the user needs to manually copy dependencies

        server_content = (build_dir / "server.py").read_text()
        assert 'startup_path = Path(__file__).parent / "startup.py"' in server_content

        print("✓ Startup script with imports test passed!")
