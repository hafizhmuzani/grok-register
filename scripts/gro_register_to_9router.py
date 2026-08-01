"""
GroRegto9Router — Register Grok + Auto-Inject to 9Router & grok2api.

Usage:
    python scripts/gro_register_to_9router.py [--count N] [--workers W]

Workflow:
    1. Run grok-register CLI to create account(s) (with optional multi-worker)
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
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
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


# ─── Worker Setup ────────────────────────────────────────────
def create_worker_dir(worker_id: int, count: int) -> str:
    """Create a temp working directory for a worker with its own config/token/cpa."""
    workdir = os.path.join(tempfile.gettempdir(), f"grok_worker_{worker_id}")
    os.makedirs(workdir, exist_ok=True)

    # Copy config.json with adjusted count
    with open(os.path.join(GROK_REGISTER_DIR, "config.json"), "r", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["register_count"] = count
    with open(os.path.join(workdir, "config.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)

    # Create empty token.json
    with open(os.path.join(workdir, "token.json"), "w", encoding="utf-8") as f:
        json.dump({"ssoBasic": []}, f)

    # Create empty cpa_auths dir
    os.makedirs(os.path.join(workdir, "cpa_auths"), exist_ok=True)

    # Symlink/copy Python files that grok-register imports
    for fname in [
        "grok_register_ttk.py", "account_outputs.py", "registration_flow.py",
        "mail_service.py", "app_config.py", "cpa_export.py", "browser_runtime.py",
        "registration_browser.py", "grok_core.pyd", "human.pyd",
        "cloudflare_turnstile",
    ]:
        src = os.path.join(GROK_REGISTER_DIR, fname)
        dst = os.path.join(workdir, fname)
        if not os.path.exists(src) or os.path.exists(dst):
            continue
        try:
            # Files: try hard link first (fast), fallback to copy
            os.link(src, dst)
        except OSError:
            try:
                shutil.copy2(src, dst)
            except (PermissionError, OSError):
                log(f"[WARN] Could not link {fname}, skipping")

    # Directory symlinks (cpa_xai, etc.) — skip if not accessible
    for dirname in ["cpa_xai"]:
        src = os.path.join(GROK_REGISTER_DIR, dirname)
        dst = os.path.join(workdir, dirname)
        if not os.path.isdir(src) or os.path.exists(dst):
            continue
        try:
            os.symlink(src, dst)
        except OSError:
            pass  # Skip if symlink not supported

    return workdir


def run_single_worker(worker_id: int, count: int, results: dict, lock: threading.Lock):
    """Run one worker: register `count` accounts in a temp dir."""
    prefix = f"[W{worker_id}]"
    workdir = create_worker_dir(worker_id, count)

    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    cmd = [VENV_PYTHON, os.path.join(workdir, "grok_register_ttk.py"), "cli"]

    try:
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, cwd=workdir, env=env, text=True,
        )
        stdout, _ = proc.communicate(input="start\n", timeout=3600)

        for line in stdout.splitlines():
            log(f"{prefix} {line}")

        # Parse results from worker dir
        token_file = os.path.join(workdir, "token.json")
        sso_tokens = []
        if os.path.isfile(token_file):
            try:
                with open(token_file, encoding="utf-8") as f:
                    data = json.load(f)
                sso_tokens = [entry.get("token", "") for entry in data.get("ssoBasic", []) if entry.get("token")]
            except (json.JSONDecodeError, OSError):
                pass

        # Find CPA files
        cpa_dir = os.path.join(workdir, "cpa_auths")
        cpa_files = []
        if os.path.isdir(cpa_dir):
            cpa_files = glob.glob(os.path.join(cpa_dir, "xai-*.json"))

        # Find accounts file
        acc_files = sorted(glob.glob(os.path.join(workdir, "accounts_*.txt")), key=os.path.getmtime, reverse=True)

        with lock:
            results["sso_tokens"].extend(sso_tokens)
            results["cpa_files"].extend(cpa_files)
            results["acc_files"].extend(acc_files)
            if proc.returncode == 0:
                results["success"] += 1
            else:
                results["failed"] += 1

        log(f"{prefix} Done — SSO: {len(sso_tokens)}, CPA: {len(cpa_files)}")

    except subprocess.TimeoutExpired:
        with lock:
            results["failed"] += 1
        log(f"{prefix} TIMEOUT")
    except Exception as e:
        with lock:
            results["failed"] += 1
        log(f"{prefix} ERROR: {e}")


# ─── Step 1: Run grok-register (concurrent) ─────────────────
def run_grok_register(count: int = 1, workers: int = 1) -> dict:
    """Run grok-register with concurrent workers. Returns merged results dict."""
    print(f"\n{'='*60}")
    print(f"[1/4] Running grok-register ({count} account(s), {workers} worker(s))...")
    print(f"{'='*60}\n")

    if workers <= 1:
        # Single worker — use main dir
        original_count = update_config_count(count)
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        cmd = [VENV_PYTHON, GROK_REGISTER_SCRIPT, "cli"]
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, cwd=GROK_REGISTER_DIR, env=env, text=True,
        )
        stdout, _ = proc.communicate(input="start\n", timeout=3600)
        restore_config_count(original_count)

        for line in stdout.splitlines():
            log(line)

        sso_tokens = []
        if os.path.isfile(TOKEN_JSON):
            try:
                with open(TOKEN_JSON, encoding="utf-8") as f:
                    data = json.load(f)
                sso_tokens = [e.get("token", "") for e in data.get("ssoBasic", []) if e.get("token")]
            except (json.JSONDecodeError, OSError):
                pass

        cpa_files = glob.glob(os.path.join(CPA_AUTHS_DIR, "xai-*.json"))
        acc_files = sorted(glob.glob(os.path.join(GROK_REGISTER_DIR, "accounts_*.txt")), key=os.path.getmtime, reverse=True)

        return {
            "sso_tokens": sso_tokens, "cpa_files": cpa_files,
            "acc_files": acc_files,
            "success": 1 if proc.returncode == 0 else 0,
            "failed": 0 if proc.returncode == 0 else 1,
        }

    # Multi-worker — split count across workers
    chunks = []
    base = count // workers
    remainder = count % workers
    for i in range(workers):
        chunk = base + (1 if i < remainder else 0)
        if chunk > 0:
            chunks.append(chunk)

    actual_workers = len(chunks)
    log(f"Splitting {count} accounts across {actual_workers} workers: {chunks}")

    results = {"sso_tokens": [], "cpa_files": [], "acc_files": [], "success": 0, "failed": 0}
    lock = threading.Lock()
    threads = []

    for wid, chunk_size in enumerate(chunks):
        t = threading.Thread(
            target=run_single_worker,
            args=(wid, chunk_size, results, lock),
            daemon=True,
        )
        t.start()
        threads.append(t)
        # Stagger worker starts by 3 seconds
        if wid < actual_workers - 1:
            import time
            time.sleep(3)

    # Wait for all workers
    for t in threads:
        t.join(timeout=3600)

    print(f"\n[OK] Registration completed. Workers: {results['success']} ok, {results['failed']} failed")
    return results


# ─── Step 2: Inject SSO tokens → grok2api ───────────────────
def inject_sso_to_grok2api(sso_tokens: list[str]) -> int:
    """Inject SSO tokens to grok2api via admin API. Returns count injected."""
    print(f"\n{'='*60}")
    print(f"[2/4] Injecting SSO tokens → grok2api...")
    print(f"{'='*60}\n")

    if not sso_tokens:
        log("[WARN] No SSO tokens to inject")
        return 0

    log(f"SSO tokens to inject: {len(sso_tokens)}")

    try:
        payload = json.dumps({"tokens": sso_tokens, "pool": "basic"}).encode("utf-8")
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
def inject_cpa_to_9router(cpa_files: list[str]) -> int:
    """Inject CPA credentials to 9Router. Returns count injected."""
    print(f"\n{'='*60}")
    print(f"[3/4] Injecting CPA credentials → 9Router ({os.path.basename(NINE_ROUTER_DB)})...")
    print(f"{'='*60}\n")

    if not os.path.isfile(NINE_ROUTER_DB):
        log(f"[WARN] 9Router DB not found: {NINE_ROUTER_DB}")
        return 0

    if not cpa_files:
        log("[WARN] No CPA credentials found")
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

    # Also copy CPA files to main cpa_auths dir for retry later
    os.makedirs(CPA_AUTHS_DIR, exist_ok=True)
    for path in cpa_files:
        dst = os.path.join(CPA_AUTHS_DIR, os.path.basename(path))
        if not os.path.isfile(dst):
            shutil.copy2(path, dst)

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

    grok2api_count = 0
    try:
        req = urllib.request.Request(f"{GROK2API_URL}/admin/api/tokens?app_key={GROK2API_KEY}")
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read().decode())
        grok2api_count = len(data.get("tokens", []))
    except Exception:
        grok2api_count = "?"

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


# ─── Cleanup ─────────────────────────────────────────────────
def cleanup_worker_dirs(workers: int):
    """Remove temp worker directories."""
    for i in range(workers):
        workdir = os.path.join(tempfile.gettempdir(), f"grok_worker_{i}")
        if os.path.isdir(workdir):
            try:
                shutil.rmtree(workdir)
            except OSError:
                pass


# ─── Main ───────────────────────────────────────────────────
def main():
    print("GroRegto9Router — Register + inject to 9Router & grok2api")
    print(f"  grok-register dir : {REPO}")
    print(f"  9Router DB        : {NINE_ROUTER_DB}")
    print(f"  grok2api          : {GROK2API_URL}")

    # Parse args
    count = 1
    workers = 1
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--count" and i + 1 < len(args):
            count = max(1, min(int(args[i + 1]), 100))
            i += 2
        elif args[i] == "--workers" and i + 1 < len(args):
            workers = max(1, min(int(args[i + 1]), 5))
            i += 2
        else:
            i += 1

    print(f"  Accounts to make  : {count}")
    print(f"  Workers           : {workers}")

    # Step 1: Register
    results = run_grok_register(count, workers)

    # Step 2: Inject SSO → grok2api
    sso_injected = inject_sso_to_grok2api(results["sso_tokens"])

    # Step 3: Inject CPA → 9Router
    cpa_injected = inject_cpa_to_9router(results["cpa_files"])

    # Step 4: Summary
    print_summary(sso_injected, cpa_injected)

    # Cleanup temp dirs
    if workers > 1:
        cleanup_worker_dirs(workers)


if __name__ == "__main__":
    main()
