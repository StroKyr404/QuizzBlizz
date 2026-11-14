import hashlib
import hmac
import os
import re
import secrets
import time
import unicodedata
from collections import deque
from typing import Deque, Dict, Mapping, Optional, Tuple
from urllib.parse import urlparse

from fastapi import HTTPException, Request, WebSocket

LOOPBACK_HOSTS = {"127.0.0.1", "::1", "::ffff:127.0.0.1", "localhost"}
LOCAL_TRUSTED_HOSTNAMES = {"localhost", "127.0.0.1", "::1"}
_HOST_HEADER_RE = re.compile(r"^(\[[a-fA-F0-9:]+\]|[a-zA-Z0-9.-]+)(:\d{1,5})?$")

IS_CLOUD_DEPLOY = bool(os.environ.get("RENDER") or os.environ.get("QUIZBLIZZ_REQUIRE_AUTH"))

_env_admin_pwd = os.environ.get("QUIZBLIZZ_ADMIN_PASSWORD", "").strip()
GENERATED_ADMIN_PASSWORD = False
if IS_CLOUD_DEPLOY and not _env_admin_pwd:
    ADMIN_PASSWORD = secrets.token_urlsafe(12)
    GENERATED_ADMIN_PASSWORD = True
else:
    ADMIN_PASSWORD = _env_admin_pwd

AUTH_MODE_PASSWORD = bool(ADMIN_PASSWORD)

_env_secret = os.environ.get("QUIZBLIZZ_SESSION_SECRET", "").strip()
SESSION_SECRET: bytes = _env_secret.encode("utf-8") if _env_secret else secrets.token_bytes(32)
SESSION_COOKIE_NAME = "quizblizz_session"
SESSION_TTL_SECONDS = 12 * 3600  # 12 Stunden

CSRF_HEADER_NAME = "x-requested-with"
CSRF_HEADER_VALUE = "QuizBlizz"


def get_client_ip(conn: object) -> str:
    """Ermittelt die direkte TCP-Client-IP ohne vertrauensunwürdige Header."""
    client = getattr(conn, "client", None)
    if client and getattr(client, "host", None):
        return str(client.host)
    return "unknown"


def get_rate_limit_key(conn: object) -> str:
    """Rate-Limit-Schlüssel (nur im Cloud-Deploy hinter Reverse-Proxy X-Forwarded-For nutzen)."""
    if IS_CLOUD_DEPLOY:
        headers = getattr(conn, "headers", None)
        if headers:
            xff = headers.get("x-forwarded-for", "").strip()
            if xff:
                first_ip = xff.split(",")[0].strip()
                if first_ip:
                    return first_ip[:64]
    return get_client_ip(conn)


def is_loopback_client(conn: object) -> bool:
    return get_client_ip(conn) in LOOPBACK_HOSTS


def _extract_hostname(host_header: str) -> str:
    h = host_header.strip().lower()
    if h.startswith("["):
        end = h.find("]")
        if end != -1:
            return h[1:end]
        return ""
    if ":" in h:
        return h.split(":", 1)[0]
    return h


def is_valid_host_header(host_header: str) -> bool:
    return bool(_HOST_HEADER_RE.match(host_header.strip()))


def is_trusted_local_host_header(headers: Mapping[str, str]) -> bool:
    """Verhindert DNS-Rebinding-Angriffe auf localhost im lokalen Modus."""
    host = headers.get("host", "").strip()
    if not host or not is_valid_host_header(host):
        return False
    return _extract_hostname(host) in LOCAL_TRUSTED_HOSTNAMES


def verify_same_origin(headers: Mapping[str, str]) -> bool:
    """Prüft Origin bzw. Referer auf Übereinstimmung mit dem Host-Header."""
    host = headers.get("host", "").strip().lower()
    if not host or not is_valid_host_header(host):
        return False

    origin = headers.get("origin", "").strip()
    if origin:
        if origin.lower() == "null":
            return False
        parsed = urlparse(origin)
        return parsed.scheme in ("http", "https") and parsed.netloc.lower() == host

    referer = headers.get("referer", "").strip()
    if referer:
        parsed = urlparse(referer)
        return parsed.scheme in ("http", "https") and parsed.netloc.lower() == host

    return True


def require_same_origin_and_csrf_header(request: Request) -> None:
    """Schützt mutierende API-Endpunkte gegen Cross-Site Request Forgery (CSRF)."""
    if not verify_same_origin(request.headers):
        raise HTTPException(status_code=403, detail="Cross-Origin-Anfrage blockiert (Origin ungültig).")
    if request.headers.get(CSRF_HEADER_NAME) != CSRF_HEADER_VALUE:
        raise HTTPException(status_code=403, detail="CSRF-Schutzheader fehlt oder ist ungültig.")


def _sign_payload(payload: str) -> str:
    return hmac.new(SESSION_SECRET, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def create_session_token() -> str:
    expires = int(time.time()) + SESSION_TTL_SECONDS
    nonce = secrets.token_hex(16)
    payload = f"teacher.{expires}.{nonce}"
    sig = _sign_payload(payload)
    return f"{payload}.{sig}"


def verify_session_token(token: Optional[str]) -> bool:
    if not token:
        return False
    parts = token.split(".")
    if len(parts) != 4 or parts[0] != "teacher":
        return False
    payload = ".".join(parts[:3])
    sig = parts[3]
    expected_sig = _sign_payload(payload)
    if not hmac.compare_digest(sig, expected_sig):
        return False
    try:
        expires = int(parts[1])
    except ValueError:
        return False
    return time.time() <= expires


def create_csrf_form_token() -> str:
    ts = str(int(time.time()))
    nonce = secrets.token_hex(12)
    payload = f"csrf.{ts}.{nonce}"
    return f"{payload}.{_sign_payload(payload)}"


def verify_csrf_form_token(token: Optional[str], max_age: int = 3600) -> bool:
    if not token:
        return False
    parts = token.split(".")
    if len(parts) != 4 or parts[0] != "csrf":
        return False
    payload = ".".join(parts[:3])
    if not hmac.compare_digest(parts[3], _sign_payload(payload)):
        return False
    try:
        ts = int(parts[1])
    except ValueError:
        return False
    return 0 <= (time.time() - ts) <= max_age


def is_teacher_authorized_http(request: Request) -> bool:
    if AUTH_MODE_PASSWORD:
        token = request.cookies.get(SESSION_COOKIE_NAME)
        return verify_session_token(token)
    return is_loopback_client(request) and is_trusted_local_host_header(request.headers)


def is_teacher_authorized_ws(websocket: WebSocket) -> bool:
    if AUTH_MODE_PASSWORD:
        token = websocket.cookies.get(SESSION_COOKIE_NAME)
        return verify_session_token(token)
    return is_loopback_client(websocket) and is_trusted_local_host_header(websocket.headers)


def require_teacher_api(request: Request, mutate: bool = False) -> None:
    if not is_teacher_authorized_http(request):
        status = 401 if AUTH_MODE_PASSWORD else 403
        raise HTTPException(
            status_code=status,
            detail="Zugriff nur für die Lehrperson erlaubt."
        )
    if mutate:
        require_same_origin_and_csrf_header(request)


def verify_admin_password(provided: str) -> bool:
    if not ADMIN_PASSWORD:
        return False
    return hmac.compare_digest(provided.strip(), ADMIN_PASSWORD)


def sanitize_player_name(raw_name: object, max_len: int = 20) -> str:
    """Entfernt unsichtbare Steuer-, Format- und Bidi-Zeichen (z. B. Zero-Width/RTL)."""
    text = str(raw_name or "")
    cleaned_chars = []
    for ch in text:
        if ch in ("\n", "\r", "\t"):
            cleaned_chars.append(" ")
            continue
        cat = unicodedata.category(ch)
        # Control (Cc), Format/Zero-Width/Bidi (Cf), Surrogate/Unassigned/Private
        if cat.startswith("C"):
            continue
        cleaned_chars.append(ch)
    normalized = " ".join("".join(cleaned_chars).split())
    return normalized[:max_len].strip()


# --- Quiz-Passwort Hashing (PBKDF2-HMAC-SHA256) ---

PBKDF2_ITERATIONS = 120_000


def hash_quiz_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${salt.hex()}${dk.hex()}"


def verify_quiz_password(
    provided: Optional[str],
    stored_hash: Optional[str],
    legacy_plaintext: Optional[str] = None
) -> bool:
    if not provided:
        return False
    candidate = provided.strip()
    if stored_hash and stored_hash.startswith("pbkdf2_sha256$"):
        parts = stored_hash.split("$")
        if len(parts) != 3:
            return False
        try:
            salt = bytes.fromhex(parts[1])
            expected_dk = bytes.fromhex(parts[2])
        except ValueError:
            return False
        actual_dk = hashlib.pbkdf2_hmac("sha256", candidate.encode("utf-8"), salt, PBKDF2_ITERATIONS)
        return hmac.compare_digest(actual_dk, expected_dk)
    if legacy_plaintext:
        return hmac.compare_digest(candidate, legacy_plaintext.strip())
    return False


# --- Sliding-Window Rate Limiter ---

class RateLimiter:
    def __init__(self, max_buckets: int = 2000):
        self._events: Dict[Tuple[str, str], Deque[float]] = {}
        self._max_buckets = max_buckets

    def _get_active_window(self, bucket: str, key: str, window_seconds: int) -> Tuple[float, Deque[float]]:
        now = time.monotonic()
        cutoff = now - window_seconds
        full_key = (bucket, key)

        if len(self._events) > self._max_buckets:
            self._prune(now)

        dq = self._events.get(full_key)
        if dq is None:
            dq = deque()
            self._events[full_key] = dq

        while dq and dq[0] <= cutoff:
            dq.popleft()
        return now, dq

    def is_limited(self, bucket: str, key: str, limit: int, window_seconds: int) -> bool:
        _, dq = self._get_active_window(bucket, key, window_seconds)
        return len(dq) >= limit

    def check(self, bucket: str, key: str, limit: int, window_seconds: int) -> bool:
        now, dq = self._get_active_window(bucket, key, window_seconds)
        if len(dq) >= limit:
            return False
        dq.append(now)
        return True

    def _prune(self, now: float) -> None:
        stale_keys = [k for k, dq in self._events.items() if not dq or (now - dq[-1]) > 3600]
        for k in stale_keys:
            del self._events[k]


rate_limiter = RateLimiter()
