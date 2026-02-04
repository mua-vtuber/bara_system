"""Self-signed TLS certificate generation for local HTTPS.

Usage:
    from app.core.ssl import ensure_ssl_certs
    ssl_ctx = ensure_ssl_certs(cert_dir=Path("certs"))
    uvicorn.run(app, ssl_keyfile=..., ssl_certfile=...)
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from app.core.constants import SSL_CERT_DIR, SSL_CERT_VALIDITY_DAYS
from app.core.logging import get_logger

logger = get_logger(__name__)


def _openssl_available() -> bool:
    return shutil.which("openssl") is not None


def _cert_is_valid(cert_path: Path, key_path: Path) -> bool:
    """Return True if both files exist and the cert has not expired."""
    if not cert_path.exists() or not key_path.exists():
        return False

    try:
        result = subprocess.run(
            ["openssl", "x509", "-in", str(cert_path), "-noout", "-enddate"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return False

        # Parse "notAfter=Mon DD HH:MM:SS YYYY GMT"
        line = result.stdout.strip()
        date_str = line.split("=", 1)[1]
        expiry = datetime.strptime(date_str, "%b %d %H:%M:%S %Y %Z").replace(
            tzinfo=timezone.utc
        )
        return datetime.now(timezone.utc) < expiry
    except Exception:
        return False


def ensure_ssl_certs(
    cert_dir: Path = Path(SSL_CERT_DIR),
) -> tuple[Path, Path] | None:
    """Generate a self-signed TLS certificate if one does not already exist.

    Returns ``(cert_path, key_path)`` on success, or ``None`` when openssl
    is not available on the system.
    """
    if not _openssl_available():
        logger.warning(
            "openssl not found on PATH; cannot generate self-signed certificate"
        )
        return None

    cert_dir.mkdir(parents=True, exist_ok=True)
    cert_path = cert_dir / "localhost.crt"
    key_path = cert_dir / "localhost.key"

    if _cert_is_valid(cert_path, key_path):
        logger.info("Using existing SSL certificate: %s", cert_path)
        return cert_path, key_path

    logger.info("Generating new self-signed SSL certificate in %s", cert_dir)

    try:
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-keyout",
                str(key_path),
                "-out",
                str(cert_path),
                "-days",
                str(SSL_CERT_VALIDITY_DAYS),
                "-nodes",
                "-subj",
                "/CN=localhost",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        logger.error("Failed to generate SSL certificate: %s", exc.stderr)
        return None
    except FileNotFoundError:
        logger.warning("openssl binary disappeared during execution")
        return None

    # Restrict private key file permissions (Unix only).
    import os
    import sys
    if sys.platform != "win32":
        try:
            os.chmod(key_path, 0o600)
        except OSError:
            logger.warning("Could not restrict permissions on %s", key_path)

    logger.info("SSL certificate generated: %s", cert_path)
    return cert_path, key_path
