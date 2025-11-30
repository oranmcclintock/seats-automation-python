import os
import json
import base64
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ENV VARS
API_HOST = os.getenv("API_HOST", "01v2mobileapi.seats.cloud")
USER_AGENT = "SeatsMobile/1728493384 CFNetwork/1568.100.1.2.1 Darwin/24.0.0"

def _extract_raw_token(token: str) -> str:
    t = (token or "").strip()
    return t[7:] if t.startswith("Bearer ") else t

def decode_jwt(token: str):
    """Decodes the JWT to extract TenantId without verifying signature."""
    try:
        payloadPart = _extract_raw_token(token).split(".")[1]
        padding = "=" * ((4 - len(payloadPart) % 4) % 4)
        decodedBytes = base64.urlsafe_b64decode(payloadPart + padding)
        return json.loads(decodedBytes)
    except Exception:
        return {}

def get_headers(token: str):
    """Generates headers dynamically using the TenantId from the token."""
    token_data = decode_jwt(token)
    tenant_id = token_data.get("TenantId", "126") # Fallback to 126

    clean_token = token.strip()
    if not clean_token.startswith("Bearer "):
        clean_token = f"Bearer {clean_token}"

    return {
        "Authorization": clean_token,
        "Abp.TenantId": tenant_id,
        "Host": API_HOST,
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Content-Type": "application/json"
    }

def get_session():
    """Returns a requests Session with automatic retry logic."""
    session = requests.Session()
    retry = Retry(
        total=3,                # Try 3 times
        backoff_factor=1,       # Wait 1s, 2s, 4s
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    return session