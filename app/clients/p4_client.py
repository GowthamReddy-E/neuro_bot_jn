"""Perforce (P4) client for reading depot files."""

import os
import subprocess
import logging

logger = logging.getLogger(__name__)

# Default P4 server
DEFAULT_P4_PORT = "ssl:sbg-perforce.esl.cisco.com:1666"

# Fixed file locations — use /tmp to avoid HOME permission issues in Docker
P4_TRUST_FILE = "/tmp/.p4trust"
P4_TICKETS_FILE = os.environ.get("P4TICKETS", "/app/.p4tickets")

_trusted = {}


def _p4_env():
    """Build env dict for P4 subprocess calls with explicit P4TRUST, P4TICKETS, and auth."""
    env = os.environ.copy()
    env["P4TRUST"] = P4_TRUST_FILE
    env["P4TICKETS"] = P4_TICKETS_FILE
    if "P4USER" not in env:
        env["P4USER"] = os.environ.get("P4USER", "")
    # P4PASSWD allows direct auth without p4 login
    if "P4PASSWD" not in env:
        p4_passwd = os.environ.get("P4PASSWD", "")
        if p4_passwd:
            env["P4PASSWD"] = p4_passwd
    return env


def _ensure_trust(p4_port=None):
    """Auto-trust the P4 SSL fingerprint on first use."""
    global _trusted
    port = p4_port or DEFAULT_P4_PORT
    if _trusted.get(port):
        return
    try:
        # Force-install trust for this P4 server
        result = subprocess.run(
            ["p4", "-p", port, "trust", "-y", "-f"],
            capture_output=True, text=True, timeout=10,
            env=_p4_env()
        )
        logger.info(f"p4 trust stdout: {result.stdout.strip()}")
        if result.stderr:
            logger.warning(f"p4 trust stderr: {result.stderr.strip()}")
        if result.returncode == 0:
            _trusted[port] = True
            # Verify trust file exists
            if os.path.exists(P4_TRUST_FILE):
                logger.info(f"P4 trust file written to {P4_TRUST_FILE}")
            else:
                logger.warning(f"P4 trust file NOT found at {P4_TRUST_FILE}")
        else:
            logger.warning(f"p4 trust exited with code {result.returncode}")
    except Exception as exc:
        logger.warning(f"p4 trust failed: {exc}")


def p4_print(depot_path, p4_port=None):
    """Read a file from Perforce depot.

    Args:
        depot_path: Full depot path, e.g. //depot/firepower/ims/10_0_0-LINA/product/ASABUILD
        p4_port: P4 server address (default: ssl:sbg-perforce.esl.cisco.com:1666)

    Returns:
        File content as string, or raises Exception on failure.
    """
    _ensure_trust(p4_port)
    port = p4_port or DEFAULT_P4_PORT
    cmd = ["p4", "-p", port, "print", "-q", depot_path]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, env=_p4_env()
        )
        if result.returncode != 0:
            error = result.stderr.strip() or f"p4 print failed with exit code {result.returncode}"
            raise Exception(f"P4 error: {error}")
        return result.stdout
    except subprocess.TimeoutExpired:
        raise Exception(f"P4 timeout reading {depot_path}")
    except FileNotFoundError:
        raise Exception("p4 command not found. Is Perforce client installed?")


def p4_filelog(depot_path, p4_port=None, limit=1):
    """Get recent changelists for a depot file.

    Args:
        depot_path: Full depot path
        p4_port: P4 server address
        limit: Number of changelists to return

    Returns:
        List of dicts: [{"change": "12345", "date": "2026/05/22", "user": "...", "description": "..."}]
    """
    _ensure_trust(p4_port)
    port = p4_port or DEFAULT_P4_PORT
    cmd = ["p4", "-p", port, "filelog", "-m", str(limit), depot_path]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, env=_p4_env()
        )
        if result.returncode != 0:
            return []

        entries = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line.startswith("... #"):
                continue
            # Format: ... #rev change 12345 edit on 2026/05/22 by user@workspace 'description'
            parts = line.split()
            entry = {}
            try:
                change_idx = parts.index("change") + 1
                entry["change"] = parts[change_idx]
                on_idx = parts.index("on") + 1
                entry["date"] = parts[on_idx]
                by_idx = parts.index("by") + 1
                entry["user"] = parts[by_idx].split("@")[0]
                # Description is in quotes at the end
                desc_start = line.find("'")
                desc_end = line.rfind("'")
                if desc_start != desc_end:
                    entry["description"] = line[desc_start + 1:desc_end]
                else:
                    entry["description"] = ""
                entries.append(entry)
            except (ValueError, IndexError):
                continue
        return entries

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def build_depot_path(depot_base, branch, file_path):
    """Build a full depot path from base, branch, and file.

    Args:
        depot_base: e.g. //depot/firepower/ims
        branch: e.g. 10_0_0-LINA or IMS_10_1_MAIN
        file_path: e.g. product/ASABUILD

    Returns:
        Full depot path, e.g. //depot/firepower/ims/10_0_0-LINA/product/ASABUILD
    """
    base = depot_base.rstrip("/")
    return f"{base}/{branch}/{file_path}"
