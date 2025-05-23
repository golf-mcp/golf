"""Telemetry module for anonymous usage tracking with PostHog."""

import os
import hashlib
import platform
from pathlib import Path
from typing import Optional, Dict, Any
import json

import posthog
from rich.console import Console

from golf import __version__

console = Console()

# PostHog configuration
# This is a client-side API key, safe to be public
# Users can override with GOLF_POSTHOG_API_KEY environment variable
DEFAULT_POSTHOG_API_KEY = "phc_7ccsDDxoC5tK5hodlrs2moGC74cThRzcN63flRYPWGl"
POSTHOG_API_KEY = os.environ.get("GOLF_POSTHOG_API_KEY", DEFAULT_POSTHOG_API_KEY)
POSTHOG_HOST = "https://us.i.posthog.com"

# Telemetry state
_telemetry_enabled: Optional[bool] = None
_anonymous_id: Optional[str] = None


def get_telemetry_config_path() -> Path:
    """Get the path to the telemetry configuration file."""
    return Path.home() / ".golf" / "telemetry.json"


def save_telemetry_preference(enabled: bool) -> None:
    """Save telemetry preference to persistent storage."""
    config_path = get_telemetry_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    config = {
        "enabled": enabled,
        "version": 1
    }
    
    try:
        with open(config_path, "w") as f:
            json.dump(config, f)
    except Exception:
        # Don't fail if we can't save the preference
        pass


def load_telemetry_preference() -> Optional[bool]:
    """Load telemetry preference from persistent storage."""
    config_path = get_telemetry_config_path()
    
    if not config_path.exists():
        return None
    
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
            return config.get("enabled")
    except Exception:
        return None


def is_telemetry_enabled() -> bool:
    """Check if telemetry is enabled.
    
    Checks in order:
    1. Cached value
    2. GOLF_TELEMETRY environment variable
    3. Persistent preference file
    4. Default to True (opt-out model)
    """
    global _telemetry_enabled
    
    if _telemetry_enabled is not None:
        return _telemetry_enabled
    
    # Check environment variables (highest priority)
    env_telemetry = os.environ.get("GOLF_TELEMETRY", "").lower()
    if env_telemetry in ("0", "false", "no", "off"):
        _telemetry_enabled = False
        return False
    elif env_telemetry in ("1", "true", "yes", "on"):
        _telemetry_enabled = True
        return True
    
    # Check persistent preference
    saved_preference = load_telemetry_preference()
    if saved_preference is not None:
        _telemetry_enabled = saved_preference
        return saved_preference
    
    # Default to enabled (opt-out model)
    _telemetry_enabled = True
    return True


def set_telemetry_enabled(enabled: bool, persist: bool = True) -> None:
    """Set telemetry enabled state.
    
    Args:
        enabled: Whether telemetry should be enabled
        persist: Whether to save this preference persistently
    """
    global _telemetry_enabled
    _telemetry_enabled = enabled
    
    if persist:
        save_telemetry_preference(enabled)


def get_anonymous_id() -> str:
    """Get or create a persistent anonymous ID for this machine.
    
    The ID is stored in the user's home directory and is based on
    machine characteristics to be consistent across sessions.
    """
    global _anonymous_id
    
    if _anonymous_id:
        return _anonymous_id
    
    # Try to load existing ID
    id_file = Path.home() / ".golf" / "telemetry_id"
    
    if id_file.exists():
        try:
            _anonymous_id = id_file.read_text().strip()
            if _anonymous_id:
                return _anonymous_id
        except Exception:
            pass
    
    # Generate new ID based on machine characteristics
    # This ensures the same ID across sessions on the same machine
    machine_data = f"{platform.node()}-{platform.machine()}-{platform.system()}"
    machine_hash = hashlib.sha256(machine_data.encode()).hexdigest()[:16]
    _anonymous_id = f"golf-{machine_hash}"
    
    # Try to save for next time
    try:
        id_file.parent.mkdir(parents=True, exist_ok=True)
        id_file.write_text(_anonymous_id)
    except Exception:
        # Not critical if we can't save
        pass
    
    return _anonymous_id


def initialize_telemetry() -> None:
    """Initialize PostHog telemetry if enabled."""
    if not is_telemetry_enabled():
        return
    
    # Skip initialization if no valid API key (empty or placeholder)
    if not POSTHOG_API_KEY or POSTHOG_API_KEY.startswith("phc_YOUR"):
        return
    
    try:
        posthog.project_api_key = POSTHOG_API_KEY
        posthog.host = POSTHOG_HOST
        
        # Disable PostHog's own logging to avoid noise
        posthog.disabled = False
        posthog.debug = False
        
    except Exception:
        # Telemetry should never break the application
        pass


def track_event(event_name: str, properties: Optional[Dict[str, Any]] = None) -> None:
    """Track an anonymous event with minimal data.
    
    Args:
        event_name: Name of the event (e.g., "cli_init", "cli_build")
        properties: Optional properties to include with the event
    """
    if not is_telemetry_enabled():
        return
    
    # Skip if no valid API key (empty or placeholder)
    if not POSTHOG_API_KEY or POSTHOG_API_KEY.startswith("phc_YOUR"):
        return
    
    try:
        # Initialize if needed
        if posthog.project_api_key != POSTHOG_API_KEY:
            initialize_telemetry()
        
        # Get anonymous ID
        anonymous_id = get_anonymous_id()
        
        # Only include minimal, non-identifying properties
        safe_properties = {
            "golf_version": __version__,
            "python_version": f"{platform.python_version_tuple()[0]}.{platform.python_version_tuple()[1]}",
            "os": platform.system(),
        }
        
        # Filter properties to only include safe ones
        if properties:
            # Only include specific safe properties
            safe_keys = {"success", "environment", "template", "command_type"}
            for key in safe_keys:
                if key in properties:
                    safe_properties[key] = properties[key]
        
        # Send event
        posthog.capture(
            distinct_id=anonymous_id,
            event=event_name,
            properties=safe_properties,
        )
        
    except Exception:
        # Telemetry should never break the application
        pass


def track_command(command: str, success: bool = True) -> None:
    """Track a CLI command execution with minimal info.
    
    Args:
        command: The command being executed (e.g., "init", "build", "run")
        success: Whether the command was successful
    """
    # Simplify the event to just command and success
    track_event(f"cli_{command}", {"success": success})


def flush() -> None:
    """Flush any pending telemetry events."""
    if not is_telemetry_enabled():
        return
    
    try:
        posthog.flush()
    except Exception:
        # Ignore flush errors
        pass


def shutdown() -> None:
    """Shutdown telemetry and flush pending events."""
    if not is_telemetry_enabled():
        return
    
    try:
        posthog.shutdown()
    except Exception:
        # Ignore shutdown errors
        pass 