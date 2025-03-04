from urllib.parse import urlparse, parse_qs, urlencode

def is_registry_url(url: str) -> bool:
    """Check if URL is a registry URL"""
    return "getauthed.dev" in urlparse(url).netloc

def normalize_url(url: str, force_https: bool = False) -> str:
    """Normalize URL for consistent comparison
    
    Args:
        url: The URL to normalize
        force_https: Whether to force HTTPS scheme (default False)
    
    Returns:
        Normalized URL with:
        - Sorted query parameters
        - Normalized ports (omitted if 80/443)
        - HTTPS scheme if force_https=True or is registry URL
    """
    parsed = urlparse(url)
    
    # Determine scheme
    scheme = parsed.scheme
    if force_https or is_registry_url(url):
        scheme = "https"
    
    # Normalize port
    port = ""
    if parsed.port and parsed.port not in (80, 443):
        port = f":{parsed.port}"
    
    # Sort query parameters if present
    query = ""
    if parsed.query:
        params = parse_qs(parsed.query)
        sorted_params = {k: sorted(v) for k, v in params.items()}
        query = f"?{urlencode(sorted_params, doseq=True)}"
    
    return f"{scheme}://{parsed.netloc}{port}{parsed.path}{query}"
