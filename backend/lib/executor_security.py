"""
Executor Security — ports nidoai lib/executor_security.ts

SSRF / DNS Rebinding protection for agent tool execution.
When agents gain tool-calling abilities (web_search, api_interaction),
all outbound HTTP requests MUST go through secure_fetch().
"""
import ipaddress
import socket
from urllib.parse import urlparse

import httpx

# IPs that must NEVER be reached by agent tool calls
BLOCKED_RANGES = [
    # Cloud metadata endpoints
    ipaddress.ip_network("169.254.169.254/32"),   # AWS/GCP metadata
    ipaddress.ip_network("100.100.100.200/32"),    # Alibaba metadata
    ipaddress.ip_network("fd00:ec2::254/128"),     # AWS IPv6 metadata

    # Private networks
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),

    # Link-local
    ipaddress.ip_network("169.254.0.0/16"),

    # IPv6 private
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("::1/128"),
]

BLOCKED_PORTS = {22, 23, 25, 445, 3306, 5432, 6379, 27017}


def _is_ip_blocked(ip_str: str) -> bool:
    """Check if an IP falls within any blocked range."""
    try:
        addr = ipaddress.ip_address(ip_str)
        return any(addr in net for net in BLOCKED_RANGES)
    except ValueError:
        return True  # If we can't parse it, block it


def validate_url(url: str) -> dict:
    """
    Validate a URL is safe for agent outbound requests.
    Resolves DNS ONCE to prevent DNS rebinding attacks.

    Returns:
        {"safe": True, "resolved_ip": str} or
        {"safe": False, "reason": str}
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return {"safe": False, "reason": "Invalid URL format."}

    if parsed.scheme not in ("http", "https"):
        return {"safe": False, "reason": f"Blocked scheme: {parsed.scheme}. Only http/https allowed."}

    hostname = parsed.hostname
    if not hostname:
        return {"safe": False, "reason": "No hostname in URL."}

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port in BLOCKED_PORTS:
        return {"safe": False, "reason": f"Blocked port: {port}."}

    # Resolve DNS exactly once (prevents rebinding)
    try:
        resolved_ip = socket.gethostbyname(hostname)
    except socket.gaierror:
        return {"safe": False, "reason": f"DNS resolution failed for {hostname}."}

    if _is_ip_blocked(resolved_ip):
        return {"safe": False, "reason": f"Blocked IP range: {resolved_ip}. SSRF attempt detected."}

    return {"safe": True, "resolved_ip": resolved_ip}


async def secure_fetch(url: str, method: str = "GET", **kwargs) -> dict:
    """
    SSRF-safe HTTP client for agent tool execution.
    Resolves DNS once, validates the target, then makes the request
    using the resolved IP directly (preventing DNS rebinding).

    Returns:
        {"ok": True, "status": int, "body": str} or
        {"ok": False, "error": str}
    """
    validation = validate_url(url)
    if not validation["safe"]:
        return {"ok": False, "error": validation["reason"]}

    resolved_ip = validation["resolved_ip"]
    parsed = urlparse(url)

    # Rebuild URL with resolved IP to prevent DNS rebinding
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    secure_url = f"{parsed.scheme}://{resolved_ip}:{port}{parsed.path}"
    if parsed.query:
        secure_url += f"?{parsed.query}"

    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=False,  # Don't follow redirects (could redirect to internal)
            verify=True,
        ) as client:
            response = await client.request(
                method,
                secure_url,
                headers={"Host": parsed.hostname, **(kwargs.get("headers", {}))},
            )
            body = response.text[:10000]  # Cap response size
            return {"ok": True, "status": response.status_code, "body": body}
    except Exception as e:
        return {"ok": False, "error": f"Request failed: {str(e)[:200]}"}
