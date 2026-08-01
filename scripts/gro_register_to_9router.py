"""
GroRegto9Router — Register Grok + Auto-Inject to 9Router & grok2api.

Usage:
    python scripts/gro_register_to_9router.py [--count N]

Workflow:
    1. Run grok-register CLI to create account(s)
    2. Parse accounts file → inject SSO tokens to grok2api (via admin API)
    3. Parse CPA credentials → inject to 9Router DB as grok-cli
    4. Summary report

Files:
    - grok-register/config.json    — Tempik provider config
    - grok-register/cpa_auths/     — CPA credentials (written by grok-register)
    - grok-register/token.json     — SSO tokens (written by grok-register)
    - grok2api admin API           — Token pool management
    - 9router/db/data.sqlite       — providerConnections table
"""
import glob
import json
import os
import sqlite3
import subprocess
import sys
import urllib.request
import urllib.error
import uuid
from datetime import datetime, timezone

# ─── Paths ───────────────────────────────────────────────────
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GROK_REGISTER_DIR = REPO

# 9Router DB
_NINE_ROUTER_CANDIDATES = [
    os.path.expandvars(r"%APPDATA%\9router\db\data.sqlite"),
    os.path.expandvars(r"%USERPROFILE%\AppData\Roaming\9router\db\data.sqlite"),
    os.path.normpath(os.path.join(REPO, "..", "Backup_Windows_Reinstall", "9router", "db", "data.sqlite")),
]
NINE_ROUTER_DB = ""
for _c in _NINE_ROUTER_CANDIDATES:
    if os.path.isfile(_c):
        NINE_ROUTER_DB = _c
        break
if not NINE_ROUTER_DB:
    NINE_ROUTER_DB = os.path.expandvars(r"%APPDATA%\9router\db\data.sqlite")

# grok2api
GROK2API_URL = "http://127.0.0.1:8000"
GROK2API_KEY = "grok2api"

GROK_REGISTER_SCRIPT = os.path.join(GROK_REGISTER_DIR, "grok_register_ttk.py")
CPA_AUTHS_DIR = os.path.join(GROK_REGISTER_DIR, "cpa_auths")
TOKEN_JSON = os.path.join(GROK_REGISTER_DIR, "token.json")
VENV_PYTHON = os.path.join(GROK_REGISTER_DIR, ".venv", "Scripts", "python.exe")


# ─── Helpers ─────────────────────────────────────────────────
def log(msg: str):
    print(f"  {msg}")


def update_config_count(count: int) -> str:
    config_path = os.path.join(GROK_REGISTER_DIR, "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    original = cfg.get("register_count", 1)
    cfg["register_count"] = count
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)
    return str(original)


def restore_config_count(original_count: str):
    config_path = os.path.join(GROK_REGISTER_DIR, "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["register_count"] = int(original_count)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)


# ─── Step 1: Run grok-register ──────────────────────────────
def run_grok_register(count: int = 1) -> tuple[bool, str]:
    """Run grok-register CLI. Returns (success, latest_accounts_file)."""
    print(f"\n{'='*60}")
    print(f"[1/4] Running grok-register ({count} account(s))...")
    print(f"{'='*60}\n")

    original_count = update_config_count(count)

    cmd = [VENV_PYTHON, GROK_REGISTER_SCRIPT, "cli"]
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}

    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, cwd=GROK_REGISTER_DIR, env=env, text=True,
    )
    stdout, _ = proc.communicate(input="start\n", timeout=3600)
    restore_config_count(original_count)

    for line in stdout.splitlines():
        log(line)

    # Find latest accounts file
    acc_files = sorted(glob.glob(os.path.join(GROK_REGISTER_DIR, "accounts_*.txt")), key=os.path.getmtime, reverse=True)
    latest_acc = acc_files[0] if acc_files else ""

    if proc.returncode != 0:
        print(f"\n[ERROR] grok-register exited with code {proc.returncode}")
        return False, latest_acc

    print(f"\n[OK] Registration completed.")
    return True, latest_acc


# ─── Step 2: Inject SSO tokens → grok2api ───────────────────
def inject_sso_to_grok2api(accounts_file: str) -> int:
    """Parse accounts file, inject new SSO tokens to grok2api. Returns count injected."""
    print(f"\n{'='*60}")
    print(f"[2/4] Injecting SSO tokens → grok2api...")
    print(f"{'='*60}\n")

    if not os.path.isfile(TOKEN_JSON):
        log("[WARN] token.json not found, skipping grok2api injection")
        return 0

    with open(TOKEN_JSON, encoding="utf-8") as f:
        token_data = json.load(f)
    sso_list = token_data.get("ssoBasic", [])
    if not sso_list:
        log("[WARN] No SSO tokens in token.json")
        return 0

    tokens = [entry["token"] for entry in sso_list if entry.get("token")]
    log(f"Total SSO tokens in token.json: {len(tokens)}")

    # Send to grok2api admin API
    try:
        payload = json.dumps({"tokens": tokens, "pool": "basic"}).encode("utf-8")
        req = urllib.request.Request(
            f"{GROK2API_URL}/admin/api/tokens/add?app_key={GROK2API_KEY}",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read().decode())
        added = result.get("count", 0)
        skipped = result.get("skipped", 0)
        log(f"[OK] grok2api: {added} new tokens added, {skipped} already existed")
        return added
    except (urllib.error.URLError, ConnectionRefusedError) as e:
        log(f"[WARN] grok2api unreachable ({e}). Is it running on port 8000?")
        log("  Start it: cd grok2api && uv run granian --interface asgi --host 0.0.0.0 --port 8000 --workers 1 app.main:app")
        return 0
    except Exception as e:
        log(f"[ERROR] grok2api injection failed: {e}")
        return 0


# ─── Step 3: Inject CPA credentials → 9Router ──────────────
def inject_cpa_to_9router() -> int:
    """Read new CPA files from cpa_auths/ and inject to 9Router. Returns count injected."""
    print(f"\n{'='*60}")
    print(f"[3/4] Injecting CPA credentials → 9Router ({os.path.basename(NINE_ROUTER_DB)})...")
    print(f"{'='*60}\n")

    if not os.path.isfile(NINE_ROUTER_DB):
        log(f"[WARN] 9Router DB not found: {NINE_ROUTER_DB}")
        return 0

    cpa_files = sorted(glob.glob(os.path.join(CPA_AUTHS_DIR, "xai-*.json")), key=os.path.getmtime)
    if not cpa_files:
        log("[WARN] No CPA credentials found in cpa_auths/")
        return 0

    conn = sqlite3.connect(NINE_ROUTER_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM providerConnections WHERE provider='grok-cli'")
    existing = {row[0] for row in cursor.fetchall() if row[0]}

    injected = 0
    for path in cpa_files:
        try:
            with open(path, encoding="utf-8") as f:
                cpa = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        email = cpa.get("email", "")
        access_token = cpa.get("access_token", "")
        if not email or not access_token or email in existing:
            continue

        try:
            exp = datetime.fromisoformat(cpa.get("expired", "").replace("Z", "+00:00")).isoformat()
        except (ValueError, TypeError):
            exp = datetime.now(timezone.utc).isoformat()

        now = datetime.now(timezone.utc).isoformat()
        data = {
            "accessToken": access_token,
            "refreshToken": cpa.get("refresh_token", ""),
            "idToken": cpa.get("id_token", ""),
            "expiresAt": exp,
            "expiresIn": cpa.get("expires_in", 21600),
            "lastRefreshAt": now,
            "backoffLevel": 0,
            "testStatus": "active",
            "providerSpecificData": {"email": email, "userId": cpa.get("sub", "")},
        }

        conn_id = str(uuid.uuid4())
        cursor.execute(
            """INSERT INTO providerConnections
               (id, provider, authType, name, email, priority, isActive, data, createdAt, updatedAt)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (conn_id, "grok-cli", "oauth", email, email, 275, 1, json.dumps(data), now, now),
        )
        existing.add(email)
        injected += 1
        log(f"[OK] 9Router grok-cli: {email}")

    conn.commit()
    conn.close()

    # Show totals
    conn2 = sqlite3.connect(NINE_ROUTER_DB)
    c2 = conn2.cursor()
    c2.execute("SELECT COUNT(*) FROM providerConnections WHERE provider='grok-cli'")
    total = c2.fetchone()[0]
    conn2.close()
    log(f"\nTotal grok-cli in 9Router: {total} (new: {injected})")
    return injected


# ─── Step 4: Summary ────────────────────────────────────────
def print_summary(sso_injected: int, cpa_injected: int):
    print(f"\n{'='*60}")
    print(f"[4/4] Summary")
    print(f"{'='*60}\n")

    # Count grok2api tokens
    grok2api_count = 0
    try:
        req = urllib.request.Request(f"{GROK2API_URL}/admin/api/tokens?app_key={GROK2API_KEY}")
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read().decode())
        grok2api_count = len(data.get("tokens", []))
    except Exception:
        grok2api_count = "?"

    # Count 9router grok-cli
    grokcli_count = 0
    if os.path.isfile(NINE_ROUTER_DB):
        try:
            conn = sqlite3.connect(NINE_ROUTER_DB)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM providerConnections WHERE provider='grok-cli'")
            grokcli_count = c.fetchone()[0]
            conn.close()
        except Exception:
            grokcli_count = "?"

    print(f"  ┌────────────────────────────────────────────────┐")
    print(f"  │ Provider      │ Endpoint              │ Akun   │")
    print(f"  ├────────────────────────────────────────────────┤")
    print(f"  │ grok2api      │ localhost:8000/v1     │ {str(grok2api_count):>6} │")
    print(f"  │ 9Router       │ localhost:20128/v1    │        │")
    print(f"  │  ├ grok-cli   │ (CPA/OAuth)          │ {str(grokcli_count):>6} │")
    print(f"  └────────────────────────────────────────────────┘")
    print()
    print(f"  Baru di-inject:")
    print(f"    SSO → grok2api : {sso_injected} akun")
    print(f"    CPA → 9Router  : {cpa_injected} akun")
    print()
    print(f"  Cara pakai:")
    print(f"    grok2api : POST {GROK2API_URL}/v1/chat/completions")
    print(f"               Authorization: Bearer {GROK2API_KEY}")
    print(f"    9Router  : POST http://127.0.0.1:20128/v1/chat/completions")
    print(f"               Authorization: Bearer <your_9router_key>")
    print()


# ─── Main ───────────────────────────────────────────────────
def main():
    print("GroRegto9Router — Register + inject to 9Router & grok2api")
    print(f"  grok-register dir : {REPO}")
    print(f"  9Router DB        : {NINE_ROUTER_DB}")
    print(f"  grok2api          : {GROK2API_URL}")

    # Parse --count
    count = 1
    if "--count" in sys.argv:
        idx = sys.argv.index("--count")
        if idx + 1 < len(sys.argv):
            count = max(1, min(int(sys.argv[idx + 1]), 100))
    print(f"  Accounts to make  : {count}")

    # Step 1: Register
    success, acc_file = run_grok_register(count)
    if not success:
        print("[FATAL] Registration failed.")
        sys.exit(1)

    # Step 2: Inject SSO → grok2api
    sso_injected = inject_sso_to_grok2api(acc_file)

    # Step 3: Inject CPA → 9Router
    cpa_injected = inject_cpa_to_9router()

    # Step 4: Summary
    print_summary(sso_injected, cpa_injected)


if __name__ == "__main__":
    main()
