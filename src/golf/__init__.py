__version__ = "0.2.5"

# Import endpoints with fallback for dev mode
try:
    # In built wheels, this exists (generated from _endpoints.py.in)
    from . import _endpoints
except ImportError:
    # In editable/dev installs, fall back to env-based values
    from . import _endpoints_fallback as _endpoints
