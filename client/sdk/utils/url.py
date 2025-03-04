from urllib.parse import urlparse, parse_qs, urlencode

def normalize_url(url: str) -> str:
    """Normalize URL for comparison"""
    parsed = urlparse(url)
    # Sort query parameters
    if parsed.query:
        params = parse_qs(parsed.query)
        sorted_params = {k: sorted(v) for k, v in params.items()}
        query = urlencode(sorted_params, doseq=True)
    else:
        query = ""
    # Normalize port
    port = f":{parsed.port}" if parsed.port and parsed.port not in (80, 443) else ""
    # Always use HTTPS for registry URLs
    scheme = "https" if "getauthed.dev" in parsed.netloc else parsed.scheme
    # Include query string in the normalized URL if it exists
    if query:
        return f"{scheme}://{parsed.netloc}{port}{parsed.path}?{query}"
    return f"{scheme}://{parsed.netloc}{port}{parsed.path}"

def ensure_https(url: str) -> str:
    """Ensure HTTPS for registry URLs
    
    This function ensures that registry URLs use HTTPS. It's a simpler version
    of normalize_url that only handles the scheme without modifying other parts
    of the URL.
    
    Args:
        url: The URL to ensure HTTPS for
        
    Returns:
        str: The URL with HTTPS if it's a registry URL
    """
    parsed = urlparse(url)
    
    # Always use HTTPS for registry URLs
    if "getauthed.dev" in parsed.netloc and parsed.scheme == "http":
        # Reconstruct the URL with https scheme
        return url.replace("http://", "https://", 1)
        
    return url 