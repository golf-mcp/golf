"""Custom setup.py for golf-mcp with URL injection."""

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py
from setuptools.command.develop import develop as _develop
import os
import pathlib
import sys

TEMPLATE_REL = "src/golf/_endpoints.py.in"
PACKAGE_OUT_REL = "golf/_endpoints.py"


def render_endpoints():
    """Render the endpoints template with environment variables."""
    tpl_path = pathlib.Path(TEMPLATE_REL)
    if not tpl_path.exists():
        raise FileNotFoundError(f"Template not found: {tpl_path}")

    # Require environment variables - no defaults with real URLs
    platform_url = os.environ.get("GOLF_PLATFORM_API_URL")
    otel_url = os.environ.get("GOLF_OTEL_ENDPOINT") 
    
    if not platform_url or not otel_url:
        raise SystemExit(
            "Missing required environment variables for URL injection:\n"
            "  GOLF_PLATFORM_API_URL\n" 
            "  GOLF_OTEL_ENDPOINT\n"
            "Set these before building the package."
        )
    
    values = {
        "PLATFORM_API_URL": platform_url,
        "OTEL_ENDPOINT": otel_url,
    }
    
    try:
        rendered = tpl_path.read_text(encoding="utf-8").format(**values)
    except KeyError as e:
        raise SystemExit(f"Missing template key: {e}") from e
    
    return rendered


class build_py(_build_py):
    """Custom build_py that renders endpoints into the build_lib (wheel contents)."""
    
    def run(self):
        # First run the normal build
        super().run()
        
        # Then render endpoints into the build_lib
        rendered = render_endpoints()
        out_file = pathlib.Path(self.build_lib) / PACKAGE_OUT_REL
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(rendered, encoding="utf-8")
        print(f"Generated {PACKAGE_OUT_REL} with injected URLs", file=sys.stderr)


class develop(_develop):
    """Custom develop for editable installs - generates endpoints file in source tree."""
    
    def run(self):
        # Run normal develop command first
        super().run()
        
        # Generate a working copy file for editable installs
        rendered = render_endpoints()
        # For editable installs, write into the source tree so imports work
        src_file = pathlib.Path("src") / PACKAGE_OUT_REL
        src_file.parent.mkdir(parents=True, exist_ok=True)
        src_file.write_text(rendered, encoding="utf-8")
        print(f"Generated dev-time {PACKAGE_OUT_REL} in source tree", file=sys.stderr)
        print(f"Note: {src_file} is gitignored and should not be committed", file=sys.stderr)


setup(
    cmdclass={
        "build_py": build_py,
        "develop": develop,
    }
)