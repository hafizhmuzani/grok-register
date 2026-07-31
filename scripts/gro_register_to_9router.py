"""
GroRegto9Router — Register Grok + inject to 9Router.

Usage:
    python scripts/gro_register_to_9router.py [--count N]

Workflow:
    1. Run grok-register CLI to create account(s)
    2. Read CPA credential(s) from cpa_auths/
    3. Insert into 9Router's SQLite providerConnections table as grok-cli

Files:
    - grok-register/config.json   — Tempik provider
    - grok-register/cpa_auths/    — CPA credentials (written by grok-register)
    - 9router/db/data.sqlite      — providerConnections table
"""
import glob
import json
import os
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timezone

# ---- Paths (relative to repo root) ----
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GROK_REGISTER_DIR = REPO

# 9Router DB — try multiple locations (AppData\Roaming is the live one)
_NINE_ROUTER_CANDIDATES = [
    os.path.expandvars(r"%APPDATA%\9router\db\data.sqlite"),
    os.path.expandvars(r"%USERPROFILE%\AppData\Roaming\9router\db\data.sqlite"),
    os.path.normpath(os.path.join(REPO, "..", "AppData", "Roaming", "9router", "db", "data.sqlite")),
    os.path.normpath(os.path.join(REPO, "..", "Backup_Windows_Reinstall", "9router", "db", "data.sqlite")),
    os.path.normpath(r"D:\Backup_Windows_Reinstall\9router\db\data.sqlite"),
]

NINE_ROUTER_DB = ""
for candidate in _NINE_ROUTER_CANDIDATES:
    if os.path.isfile(candidate):
        NINE_ROUTER_DB = candidate
        break

if not NINE_ROUTER_DB:
    # Fallback to most common location
    NINE_ROUTER_DB = os.path.expandvars(r"%APPDATA%\9router\db\data.sqlite")

GROK_REGISTER_SCRIPT = os.path.join(GROK_REGISTER_DIR, "grok_register_ttk.py")
CPA_AUTHS_DIR = os.path.join(GROK_REGISTER_DIR, "cpa_auths")
VENV_PYTHON = os.path.join(GROK_REGISTER_DIR, ".venv", "Scripts", "python.exe")


def update_config_count(count: int) -> str:
    """Temporarily update register_count in config.json, return original value."""
    config_path = os.path.join(GROK_REGISTER_DIR, "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    original = cfg.get("register_count", 1)
    cfg["register_count"] = count
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)
    return str(original)


def restore_config_count(original_count: str):
    """Restore register_count in config.json."""
    config_path = os.path.join(GROK_REGISTER_DIR, "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["register_count"] = int(original_count)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)


def run_grok_register(count: int = 1) -> bool:
    """Run grok-register CLI to register `count` accounts."""
    print(f"\n{'='*60}")
    print(f"[1/3] Running grok-register ({count} account(s))...")
    print(f"{'='*60}\n")

    # Set register_count in config.json before running
    original_count = update_config_count(count)

    cmd = [VENV_PYTHON, GROK_REGISTER_SCRIPT, "cli"]
    env = {**os.environ, "PYTHONPATH": ""}
    if "PYTHONPATH" in env:
        del env["PYTHONPATH"]

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=GROK_REGISTER_DIR,
        env=env,
        text=True,
    )

    stdout, _ = proc.communicate(input="start\n", timeout=3600)

    # Restore original config
    restore_config_count(original_count)

    for line in stdout.splitlines():
        print(f"  {line}")

    if proc.returncode != 0:
        print(f"\n[ERROR] grok-register exited with code {proc.returncode}")
        return False

    if "成功 0" in stdout or "成功 0 |" in stdout:
        print("\n[ERROR] No accounts registered successfully.")
        return False

    print(f"\n[OK] Registration completed.")
    return True


def find_latest_cpa_files() -> list[str]:
    """Find new CPA credential files in cpa_auths/."""
    pattern = os.path.join(CPA_AUTHS_DIR, "xai-*.json")
    files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    return files


def insert_into_9router(cpa_path: str) -> bool:
    """Insert CPA credential into 9router providerConnections as grok-cli."""
    print(f"\n{'='*60}")
    print(f"[2/3] Inserting into 9Router DB...")
    print(f"{'='*60}\n")

    if not os.path.isfile(NINE_ROUTER_DB):
        print(f"[ERROR] 9Router database not found: {NINE_ROUTER_DB}")
        return False

    with open(cpa_path, "r", encoding="utf-8") as f:
        cpa = json.load(f)

    access_token = cpa.get("access_token", "")
    refresh_token = cpa.get("refresh_token", "")
    id_token = cpa.get("id_token", "")
    email = cpa.get("email", "unknown@grok.com")
    sub = cpa.get("sub", "")
    expires_in = cpa.get("expires_in", 21600)
    expired_at = cpa.get("expired", "")

    if not access_token:
        print(f"[ERROR] CPA file has no access_token: {cpa_path}")
        return False

    # Compute expiresAt in ISO format
    try:
        expires_dt = datetime.fromisoformat(expired_at.replace("Z", "+00:00"))
        expires_at_iso = expires_dt.isoformat()
    except (ValueError, AttributeError):
        expires_at_iso = datetime.now(timezone.utc).isoformat()

    conn_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    data = {
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "idToken": id_token,
        "expiresAt": expires_at_iso,
        "expiresIn": expires_in,
        "lastRefreshAt": now,
        "backoffLevel": 0,
        "testStatus": "active",
        "providerSpecificData": {
            "email": email,
            "userId": sub,
        },
    }

    print(f"  Email     : {email}")
    print(f"  Token len : {len(access_token)}")
    print(f"  Conn ID   : {conn_id}")
    print(f"  DB        : {NINE_ROUTER_DB}")

    conn = sqlite3.connect(NINE_ROUTER_DB)
    cursor = conn.cursor()

    # Check if this email already exists
    cursor.execute(
        "SELECT id FROM providerConnections WHERE provider = 'grok-cli' AND email = ?",
        (email,),
    )
    existing = cursor.fetchone()
    if existing:
        print(f"\n  [SKIP] Email {email} already in 9Router (id={existing[0]})")
        conn.close()
        return True

    cursor.execute(
        """INSERT INTO providerConnections
           (id, provider, authType, name, email, priority, isActive, data, createdAt, updatedAt)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            conn_id,
            "grok-cli",
            "oauth",
            email,
            email,
            275,  # priority from grok-cli registry
            1,    # isActive
            json.dumps(data),
            now,
            now,
        ),
    )
    conn.commit()
    conn.close()

    print(f"\n  [OK] Inserted into 9Router: {email}")
    return True


def main():
    count = 1
    if len(sys.argv) >= 3 and sys.argv[1] == "--count":
        count = int(sys.argv[2])
    elif len(sys.argv) >= 2 and sys.argv[1].isdigit():
        count = int(sys.argv[1])

    print("GroRegto9Router — Register + inject to 9Router")
    print(f"  grok-register dir : {GROK_REGISTER_DIR}")
    print(f"  9Router DB        : {NINE_ROUTER_DB}")
    print(f"  Accounts to make  : {count}")

    # Step 1: Register
    # Record existing CPA files before registration
    existing_cpa = set(find_latest_cpa_files())

    if not run_grok_register(count):
        sys.exit(1)

    # Step 2: Find NEW CPA files (created during this run)
    all_cpa = set(find_latest_cpa_files())
    new_cpa = sorted(all_cpa - existing_cpa, key=os.path.getmtime, reverse=True)

    if not new_cpa:
        # Fallback: use all CPA files sorted by mtime
        new_cpa = find_latest_cpa_files()
        print(f"\n  [WARN] No new CPA files detected, using latest {len(new_cpa)} file(s)")

    print(f"\n  Found {len(new_cpa)} CPA credential(s) to inject")

    # Step 3: Insert into 9Router
    success = 0
    for cpa_path in new_cpa[:count]:
        print(f"\n  Processing: {os.path.basename(cpa_path)}")
        if insert_into_9router(cpa_path):
            success += 1

    # Step 4: Summary
    print(f"\n{'='*60}")
    print(f"[3/3] Done!")
    print(f"{'='*60}")
    print(f"  Registered : {count}")
    print(f"  Injected   : {success}")
    print(f"\n  9Router models available: gcli/grok-4.3-fast, gcli/grok-4.3-console, gcli/grok-build, etc.")
    print(f"  API endpoint: http://127.0.0.1:20128/v1/chat/completions")
    print(f"  Usage: curl -X POST http://127.0.0.1:20128/v1/chat/completions \\")
    print(f"    -H 'Content-Type: application/json' \\")
    print(f"    -d '{{\"model\":\"gcli/grok-4.3-fast\",\"messages\":[{{\"role\":\"user\",\"content\":\"Hi\"}}]}}'")
    print()

    if success == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
