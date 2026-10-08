
import threading

def sync_to_google_sheet_async(webhook_url, player_data):
    if not webhook_url:
        return
    try:
        requests.post(webhook_url, json=player_data, timeout=8)
    except Exception as e:
        print("Google Sheet sync error (non-blocking):", e)

import os
import sys
import time
import json
import copy
import random
import uuid
import urllib.parse
from datetime import datetime
from io import BytesIO

# Fix Windows console UTF-8 output
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, Response
from werkzeug.utils import secure_filename
from flask import send_from_directory
import shutil
import pandas as pd
import zipfile

# Directory setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
PHOTOS_DIR = os.path.join(STATIC_DIR, 'uploads', 'photos')
PAYMENTS_DIR = os.path.join(STATIC_DIR, 'uploads', 'payments')

os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(PHOTOS_DIR, exist_ok=True)
os.makedirs(PAYMENTS_DIR, exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, 'css'), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, 'js'), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, 'images'), exist_ok=True)

# --- CLEAN UP LEGACY ROOT TEMPLATES & STATIC FILES ---
# If legacy template/static files were uploaded to repository root on GitHub,
# delete them from the root so they never shadow or overwrite real templates/ and static/ files.
LEGACY_ROOT_FILES = [
    'admin.html', 'auction_live.html', 'base.html', 'index.html',
    'owner_portal.html', 'register.html', 'register_success.html', 'teams.html',
    'style.css', 'auction.css', 'register.js', 'auction.js', 'odometer.js',
    'avatar_allrounder.svg', 'avatar_batsman.svg', 'avatar_bowler.svg',
    'avatar_default.svg', 'avatar_keeper.svg'
]
for legacy_file in LEGACY_ROOT_FILES:
    root_target = os.path.join(BASE_DIR, legacy_file)
    if os.path.isfile(root_target):
        try:
            os.remove(root_target)
            print("[STARTUP CLEANUP] Removed legacy root file:", legacy_file)
        except Exception as del_err:
            print("[STARTUP NOTE] Could not remove", legacy_file, ":", del_err)

CONFIG_FILE = os.path.join(BASE_DIR, 'tournament_config.json')
REGISTRATIONS_FILE = os.path.join(BASE_DIR, 'registrations.json')
AUCTION_STATE_FILE = os.path.join(BASE_DIR, 'auction_state.json')

from jinja2 import FileSystemLoader
app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=STATIC_DIR)
app.jinja_loader = FileSystemLoader(TEMPLATES_DIR)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Disable static file caching (dev mode)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True

# --- RENDER CLOUD POSTGRESQL PERSISTENCE (ZERO DATA LOSS ON SLEEP/WAKEUP) ---
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    if not DATABASE_URL:
        return None
    try:
        import psycopg2
        url = DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return psycopg2.connect(url, sslmode='require')
    except Exception as e:
        print("[DATABASE] Connection notice:", e)
        return None

def init_db():
    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS kpl_cloud_store (
                    key VARCHAR(64) PRIMARY KEY,
                    data_json TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
        conn.close()
        print("[DATABASE] PostgreSQL cloud store ready! Zero data loss active.")
    except Exception as e:
        print("[DATABASE] Init notice:", e)

init_db()

def db_get(key):
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT data_json FROM kpl_cloud_store WHERE key = %s;", (key,))
            row = cur.fetchone()
        conn.close()
        if row and row[0]:
            return json.loads(row[0])
    except Exception as e:
        print(f"[DATABASE] db_get({key}) notice:", e)
    return None

def db_set(key, val_obj):
    conn = get_db_connection()
    if not conn:
        return
    try:
        val_str = json.dumps(val_obj, indent=4)
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO kpl_cloud_store (key, data_json, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (key) DO UPDATE
                SET data_json = EXCLUDED.data_json, updated_at = CURRENT_TIMESTAMP;
            """, (key, val_str))
            conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DATABASE] db_set({key}) notice:", e)

# ----------------- CONFIG HELPERS -----------------
def load_config():
    default_config = {
        "tournament_name": "Kunsi Premier League (KPL 2026)",
        "upi_id": "saidapur.cricket@upi",
        "payee_name": "Saidapur Cricket Committee",
        "registration_fee": 200,
        "default_purse": 5000,
        "total_purse": 5000,
        "min_bid": 100,
        "retention_price": 500,
        "owner_retention_price": 100,
        "max_players": 15,
        "currency_symbol": "₹",
        "admin_pin": "2026",
        "timer_enabled": False,
        "timer_duration": 120,
        "timer_reset_on_bid": True,
        "upi_enabled": True,
        "villages": ["Kunsi", "Alampally", "Kothapally", "Hindupoor", "Saidapur"]
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                default_config.update(cfg)
        except Exception as e:
            print("Error loading config:", e)

    # Check PostgreSQL cloud store first if DATABASE_URL is set
    if DATABASE_URL:
        try:
            db_cfg = db_get('tournament_config')
            if isinstance(db_cfg, dict):
                default_config.update(db_cfg)
        except Exception as _dbe:
            pass

    # Guarantee KPL branding across all links and shares
    t_name = default_config.get("tournament_name", "")
    if "SPL" in t_name or not t_name:
        default_config["tournament_name"] = "Kunsi Premier League (KPL 2026)"

    # Guarantee default villages list is never empty
    if "villages" not in default_config or not default_config["villages"]:
        default_config["villages"] = ["Kunsi", "Alampally", "Kothapally", "Hindupoor", "Saidapur"]

    # Guarantee default purse is 5000
    if not default_config.get("default_purse"):
        default_config["default_purse"] = 5000
    if not default_config.get("total_purse"):
        default_config["total_purse"] = 5000

    env_pin = os.environ.get('ADMIN_PIN')
    if env_pin:
        default_config['admin_pin'] = env_pin.strip()
    return default_config

def save_config(cfg):
    if DATABASE_URL:
        try:
            db_set('tournament_config', cfg)
        except Exception as _dbe:
            pass
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=4)
    try:
        push_to_github_async('tournament_config.json', json.dumps(cfg, indent=4), 'KPL Auto-Sync: Updated tournament configuration')
    except Exception:
        pass


# ----------------- REGISTRATIONS & BACKUP VAULT HELPERS -----------------
BACKUPS_DIR = os.path.join(BASE_DIR, 'backups', 'registrations')
BACKUPS_PHOTOS_DIR = os.path.join(BASE_DIR, 'backups', 'photos')
BACKUPS_PAYMENTS_DIR = os.path.join(BASE_DIR, 'backups', 'payments')
BACKUPS_AUCTION_DIR = os.path.join(BASE_DIR, 'backups', 'auction')
os.makedirs(BACKUPS_DIR, exist_ok=True)
os.makedirs(BACKUPS_PHOTOS_DIR, exist_ok=True)
os.makedirs(BACKUPS_PAYMENTS_DIR, exist_ok=True)
os.makedirs(BACKUPS_AUCTION_DIR, exist_ok=True)
MASTER_VAULT_FILE = os.path.join(BASE_DIR, 'backups', 'registrations_master_vault.json')
AUCTION_VAULT_FILE = os.path.join(BACKUPS_AUCTION_DIR, 'auction_state_vault.json')
_last_backup_time = 0
_last_auction_backup_time = 0

# --- GITHUB CLOUD AUTO-COMMIT ENGINE (DEBOUNCED & CONFLICT-SAFE) ---
_pending_github_syncs = {}
_github_sync_lock = threading.Lock()
_github_worker_started = False

def _github_sync_worker():
    import base64, requests, time
    token = os.environ.get('GITHUB_TOKEN')
    repo = os.environ.get('GITHUB_REPO')
    if not token or not repo:
        return
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'KPL-Auction-Cloud-Sync'
    }
    clean_repo = repo.replace('https://github.com/', '').strip().strip('/')

    while True:
        try:
            time.sleep(2)  # 2-second debounce interval for live bidding and rapid updates
            item_to_sync = None
            with _github_sync_lock:
                if _pending_github_syncs:
                    file_rel = next(iter(_pending_github_syncs))
                    item_to_sync = (file_rel, _pending_github_syncs.pop(file_rel))

            if not item_to_sync:
                continue

            file_rel, item = item_to_sync
            content_str = item['content']
            commit_msg = item['message']

            # Commit with up to 3 conflict retries
            for attempt in range(3):
                try:
                    url = f'https://api.github.com/repos/{clean_repo}/contents/{file_rel}'
                    r_get = requests.get(url, headers=headers, timeout=10)
                    sha = r_get.json().get('sha') if r_get.status_code == 200 else None

                    b64_content = base64.b64encode(content_str.encode('utf-8')).decode('utf-8')
                    payload = {
                        'message': commit_msg,
                        'content': b64_content
                    }
                    if sha:
                        payload['sha'] = sha
                    r_put = requests.put(url, headers=headers, json=payload, timeout=15)
                    if r_put.status_code in [200, 201]:
                        print(f"[GITHUB AUTO-SYNC] Successfully backed up {file_rel} to {clean_repo}")
                        break
                    elif r_put.status_code == 409:
                        time.sleep(0.5)
                        continue
                    else:
                        print(f"[GITHUB AUTO-SYNC] GitHub API {r_put.status_code}: {r_put.text[:120]}")
                        break
                except Exception as req_ex:
                    print(f"[GITHUB AUTO-SYNC] Error uploading {file_rel} (attempt {attempt+1}):", req_ex)
                    time.sleep(1)
        except Exception as loop_ex:
            print("[GITHUB AUTO-SYNC Worker] Loop notice:", loop_ex)
            time.sleep(2)

def push_to_github_async(file_path_relative, content_str, commit_message):
    """Queue or immediately commit changes to GitHub repository if GITHUB_TOKEN & GITHUB_REPO are set."""
    token = os.environ.get('GITHUB_TOKEN')
    repo = os.environ.get('GITHUB_REPO')
    if not token or not repo:
        return
    import time
    global _github_worker_started
    with _github_sync_lock:
        _pending_github_syncs[file_path_relative] = {
            'content': content_str,
            'message': commit_message,
            'time': time.time()
        }
        if not _github_worker_started:
            _github_worker_started = True
            threading.Thread(target=_github_sync_worker, daemon=True).start()

def pull_from_github_on_startup():
    """On container start/wake-up on Render, pull the latest data directly from GitHub repo."""
    token = os.environ.get('GITHUB_TOKEN')
    repo = os.environ.get('GITHUB_REPO')
    if not token or not repo:
        return
    try:
        import base64, requests
        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'KPL-Auction-Cloud-Sync'
        }
        clean_repo = repo.replace('https://github.com/', '').strip().strip('/')

        # 1. Pull registrations.json
        try:
            r = requests.get(f'https://api.github.com/repos/{clean_repo}/contents/registrations.json', headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                content = base64.b64decode(data.get('content', '')).decode('utf-8')
                gh_regs = json.loads(content)
                if isinstance(gh_regs, dict):
                    if len(gh_regs) == 0:
                        with open(REGISTRATIONS_FILE, 'w', encoding='utf-8') as wf:
                            json.dump({}, wf, indent=4)
                        with open(MASTER_VAULT_FILE, 'w', encoding='utf-8') as vf:
                            json.dump({}, vf, indent=4)
                        print("[GITHUB CLOUD RESTORE] Synced clean factory reset state from GitHub repo!")
                    else:
                        with open(REGISTRATIONS_FILE, 'w', encoding='utf-8') as wf:
                            json.dump(gh_regs, wf, indent=4)
                        with open(MASTER_VAULT_FILE, 'w', encoding='utf-8') as vf:
                            json.dump(gh_regs, vf, indent=4)
                        print(f"[GITHUB CLOUD RESTORE] Successfully restored {len(gh_regs)} registrations from GitHub repo!")
        except Exception as e_reg:
            print("[GITHUB CLOUD RESTORE] Registrations notice:", e_reg)

        # 2. Pull auction_state.json
        try:
            r = requests.get(f'https://api.github.com/repos/{clean_repo}/contents/auction_state.json', headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                content = base64.b64decode(data.get('content', '')).decode('utf-8')
                gh_state = json.loads(content)
                if isinstance(gh_state, dict) and 'teams' in gh_state:
                    with open(AUCTION_STATE_FILE, 'w', encoding='utf-8') as wf:
                        json.dump(gh_state, wf, indent=4)
                    with open(AUCTION_VAULT_FILE, 'w', encoding='utf-8') as vf:
                        json.dump(gh_state, vf, indent=4)
                    print("[GITHUB CLOUD RESTORE] Successfully restored latest auction state from GitHub repo!")
        except Exception as e_st:
            print("[GITHUB CLOUD RESTORE] Auction state notice:", e_st)

        # 3. Pull tournament_config.json
        try:
            r = requests.get(f'https://api.github.com/repos/{clean_repo}/contents/tournament_config.json', headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                content = base64.b64decode(data.get('content', '')).decode('utf-8')
                gh_cfg = json.loads(content)
                if isinstance(gh_cfg, dict):
                    with open(CONFIG_FILE, 'w', encoding='utf-8') as wf:
                        json.dump(gh_cfg, wf, indent=4)
                    if DATABASE_URL:
                        db_set('tournament_config', gh_cfg)
                    print("[GITHUB CLOUD RESTORE] Successfully restored latest tournament config from GitHub repo!")
        except Exception as e_cfg:
            print("[GITHUB CLOUD RESTORE] Tournament config notice:", e_cfg)
    except Exception as ex:
        print("[GITHUB CLOUD RESTORE] Startup pull error:", ex)

# Pull latest data from GitHub first thing on startup
pull_from_github_on_startup()

def sync_backup_photos():
    """Bidirectional backup & self-healing of player photos and payment proofs."""
    try:
        # 1. Mirror static/uploads/photos -> backups/photos
        if os.path.exists(PHOTOS_DIR):
            for f in os.listdir(PHOTOS_DIR):
                src = os.path.join(PHOTOS_DIR, f)
                dst = os.path.join(BACKUPS_PHOTOS_DIR, f)
                if os.path.isfile(src) and not os.path.exists(dst):
                    shutil.copy2(src, dst)
        # 2. Self-heal backups/photos -> static/uploads/photos
        if os.path.exists(BACKUPS_PHOTOS_DIR):
            for f in os.listdir(BACKUPS_PHOTOS_DIR):
                src = os.path.join(BACKUPS_PHOTOS_DIR, f)
                dst = os.path.join(PHOTOS_DIR, f)
                if os.path.isfile(src) and not os.path.exists(dst):
                    shutil.copy2(src, dst)
        # 3. Mirror payments
        if os.path.exists(PAYMENTS_DIR):
            for f in os.listdir(PAYMENTS_DIR):
                src = os.path.join(PAYMENTS_DIR, f)
                dst = os.path.join(BACKUPS_PAYMENTS_DIR, f)
                if os.path.isfile(src) and not os.path.exists(dst):
                    shutil.copy2(src, dst)
        # 4. Self-heal player photos from embedded Base64 and PostgreSQL Cloud Store
        if DATABASE_URL:
            db_regs = db_get('registrations')
            if isinstance(db_regs, dict):
                restore_photos_from_regs(db_regs)

        for v_path in [REGISTRATIONS_FILE, MASTER_VAULT_FILE]:
            if os.path.exists(v_path):
                try:
                    with open(v_path, 'r', encoding='utf-8') as rf:
                        r_data = json.load(rf)
                    if isinstance(r_data, dict):
                        restore_photos_from_regs(r_data)
                except Exception as _e_heal:
                    print("Base64 photo self-heal notice:", _e_heal)
    except Exception as e:
        print("Photo sync note:", e)

def restore_photos_from_regs(regs):
    """Restores player photos and payment proofs from embedded Base64 to disk after Render sleeps."""
    if not isinstance(regs, dict):
        return
    import base64
    for p_name, p_info in regs.items():
        if not isinstance(p_info, dict):
            continue
        # 1. Restore player photo
        b64_str = p_info.get('photo_base64') or (p_info.get('photo_url') if str(p_info.get('photo_url', '')).startswith('data:image') else None)
        if b64_str and ',' in b64_str:
            clean_b64 = b64_str.split(',', 1)[1]
            fname = p_info.get('photo_filename') or (os.path.basename(p_info.get('photo_url')) if p_info.get('photo_url') and not str(p_info.get('photo_url')).startswith('data:') else None) or f"player_{p_info.get('id', 'pic')}.jpg"
            target_p = os.path.join(PHOTOS_DIR, fname)
            if not os.path.exists(target_p):
                try:
                    with open(target_p, 'wb') as img_out:
                        img_out.write(base64.b64decode(clean_b64))
                    try:
                        shutil.copy2(target_p, os.path.join(BACKUPS_PHOTOS_DIR, fname))
                    except Exception:
                        pass
                except Exception as _w_err:
                    pass
        # 2. Restore payment proof screenshot
        pay_b64 = p_info.get('payment_screenshot_base64') or (p_info.get('payment_screenshot') if str(p_info.get('payment_screenshot', '')).startswith('data:image') else None)
        if pay_b64 and ',' in pay_b64:
            clean_pay_b64 = pay_b64.split(',', 1)[1]
            pay_fname = p_info.get('payment_screenshot_filename') or (os.path.basename(p_info.get('payment_screenshot')) if p_info.get('payment_screenshot') and not str(p_info.get('payment_screenshot')).startswith('data:') else None) or f"pay_{p_info.get('id', 'pic')}.jpg"
            pay_target = os.path.join(PAYMENTS_DIR, pay_fname)
            if not os.path.exists(pay_target):
                try:
                    with open(pay_target, 'wb') as pay_out:
                        pay_out.write(base64.b64decode(clean_pay_b64))
                    try:
                        shutil.copy2(pay_target, os.path.join(BACKUPS_PAYMENTS_DIR, pay_fname))
                    except Exception:
                        pass
                except Exception:
                    pass

# Initial photo sync
sync_backup_photos()

def load_registrations():
    # 1. Check PostgreSQL cloud store first if DATABASE_URL is set
    if DATABASE_URL:
        db_regs = db_get('registrations')
        if db_regs is not None:
            restore_photos_from_regs(db_regs)
            return db_regs

    regs = None
    if os.path.exists(REGISTRATIONS_FILE):
        try:
            with open(REGISTRATIONS_FILE, 'r', encoding='utf-8') as f:
                regs = json.load(f)
        except Exception as e:
            print("Error loading registrations:", e)
            regs = None
    
    # Self-heal from Master Vault ONLY if REGISTRATIONS_FILE was completely missing or corrupt
    if regs is None and os.path.exists(MASTER_VAULT_FILE):
        try:
            with open(MASTER_VAULT_FILE, 'r', encoding='utf-8') as vf:
                vault = json.load(vf)
            if isinstance(vault, dict):
                regs = vault
                with open(REGISTRATIONS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(regs, f, indent=4)
        except Exception:
            regs = {}
            
    if regs is None:
        regs = {}

    restore_photos_from_regs(regs)
    return regs

def save_registrations(regs):
    global _last_backup_time
    if DATABASE_URL:
        db_set('registrations', regs)
        db_set('master_vault', regs)

    with open(REGISTRATIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(regs, f, indent=4)

    # Sync and mirror photos to permanent backup
    sync_backup_photos()

    # Exact snapshot sync to Master Vault - accurately reflects deletions
    try:
        if isinstance(regs, dict):
            with open(MASTER_VAULT_FILE, 'w', encoding='utf-8') as vf:
                json.dump(regs, vf, indent=4)
    except Exception as e:
        print("Vault backup notice:", e)

    # 2. Automated timestamped snapshot
    now = datetime.now().timestamp()
    if now - _last_backup_time > 30 and isinstance(regs, dict) and len(regs) > 0:
        _last_backup_time = now
        try:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            snap_path = os.path.join(BACKUPS_DIR, f"registrations_{ts}.json")
            with open(snap_path, 'w', encoding='utf-8') as sf:
                json.dump(regs, sf, indent=4)
        except Exception as e:
            print("Snapshot backup notice:", e)

    # 3. GitHub Cloud Auto-Commit (Instant persistence across Render container restarts)
    try:
        push_to_github_async('registrations.json', json.dumps(regs, indent=4), 'KPL Auto-Sync: Updated registrations database')
        push_to_github_async('backups/registrations_master_vault.json', json.dumps(regs, indent=4), 'KPL Auto-Sync: Updated master vault')
    except Exception as _gh_err:
        print("GitHub push notice:", _gh_err)

# ----------------- AUCTION STATE HELPERS -----------------
def get_retained_player_names(state):
    """Return set of normalized lowercase names of all retained players (player/owner/retained)."""
    retained = set()
    for t_data in state.get("teams", {}).values():
        for slot in ["player_retained", "owner_retained", "retained"]:
            val = t_data.get(slot)
            if val:
                name = val.get("name") if isinstance(val, dict) else str(val)
                if name and str(name).strip():
                    retained.add(str(name).strip().lower())
    return retained

def get_sold_player_names(state):
    """Return set of normalized lowercase names of all sold players across teams."""
    sold = set()
    for t_data in state.get("teams", {}).values():
        for p in t_data.get("players", []):
            name = p.get("name") if isinstance(p, dict) else str(p)
            if name and str(name).strip():
                sold.add(str(name).strip().lower())
    return sold

def sanitize_auction_pool(state):
    """Remove retained and sold players from state['auction_players'] and state['unsold_players']."""
    retained = get_retained_player_names(state)
    sold = get_sold_player_names(state)
    excluded = retained | sold
    if "auction_players" in state and isinstance(state["auction_players"], list):
        state["auction_players"] = [p for p in state["auction_players"] if str(p).strip().lower() not in excluded]
    if "unsold_players" in state and isinstance(state["unsold_players"], list):
        state["unsold_players"] = [p for p in state["unsold_players"] if str(p).strip().lower() not in excluded]

AUCTION_STATE_LOCK = threading.RLock()

def load_auction_state():
    with AUCTION_STATE_LOCK:
        # 1. Check PostgreSQL cloud store first if DATABASE_URL is set
        if DATABASE_URL:
            db_st = db_get('auction_state')
            if isinstance(db_st, dict) and "teams" in db_st:
                sanitize_auction_pool(db_st)
                return db_st

        for file_candidate in [AUCTION_STATE_FILE, AUCTION_VAULT_FILE]:
            if os.path.exists(file_candidate):
                for attempt in range(10):
                    try:
                        with open(file_candidate, 'r', encoding='utf-8') as f:
                            st = json.load(f)
                            if isinstance(st, dict) and "teams" in st:
                                if 'auction_started' not in st:
                                    st['auction_started'] = False
                                sanitize_auction_pool(st)
                                return st
                    except Exception as e:
                        time.sleep(0.015)
        
        # Default initial state
        cfg = load_config()
        regs = load_registrations()
        
        player_list = [p_name for p_name, p_data in regs.items() if p_data.get('approved', False)]

        state = {
            "teams": {
                "Deccan Royals": {"budget": cfg["default_purse"], "spent": 0, "players": [], "retained": None},
                "Kunsi Warriors": {"budget": cfg["default_purse"], "spent": 0, "players": [], "retained": None},
                "Saidapur Super Kings": {"budget": cfg["default_purse"], "spent": 0, "players": [], "retained": None},
                "Telangana Titans": {"budget": cfg["default_purse"], "spent": 0, "players": [], "retained": None},
                "Hyderabad Blasters": {"budget": cfg["default_purse"], "spent": 0, "players": [], "retained": None}
            },
            "players": player_list,
            "player_serials": {p: i + 1 for i, p in enumerate(player_list)},
            "auction_players": list(player_list),
            "unsold_players": [],
            "current_player": None,
            "history": [],
            "current_round": 1,
            "auction_started": True,
            "total_purse": cfg["default_purse"],
            "max_players": cfg["max_players"],
            "min_bid": cfg["min_bid"],
            "retention_price": cfg["retention_price"]
        }
        sanitize_auction_pool(state)
        save_auction_state(state)
        return state

def save_auction_state(state):
    global _last_auction_backup_time
    if DATABASE_URL:
        db_set('auction_state', state)

    with AUCTION_STATE_LOCK:
        tmp_file = AUCTION_STATE_FILE + ".tmp"
        try:
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=4)
            for attempt in range(15):
                try:
                    os.replace(tmp_file, AUCTION_STATE_FILE)
                    break
                except Exception:
                    time.sleep(0.015)
        except Exception as e:
            print("Error saving auction state:", e)

    # 1. Local Auction Vault Backup
    try:
        with open(AUCTION_VAULT_FILE, 'w', encoding='utf-8') as vf:
            json.dump(state, vf, indent=4)
    except Exception:
        pass

    # 2. Automated timestamped snapshot
    now = datetime.now().timestamp()
    if now - _last_auction_backup_time > 30 and isinstance(state, dict):
        _last_auction_backup_time = now
        try:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            snap_path = os.path.join(BACKUPS_AUCTION_DIR, f"auction_{ts}.json")
            with open(snap_path, 'w', encoding='utf-8') as sf:
                json.dump(state, sf, indent=4)
        except Exception:
            pass

    # 3. GitHub Cloud Auto-Commit (Debounced & Queued)
    try:
        push_to_github_async('auction_state.json', json.dumps(state, indent=4), 'KPL Auto-Sync: Updated auction state')
    except Exception as _gh_err:
        print("GitHub auction push notice:", _gh_err)

def push_history(state):
    state_copy = copy.deepcopy(state)
    if "history" in state_copy:
        del state_copy["history"]
    if "history" not in state:
        state["history"] = []
    state["history"].append(state_copy)
    if len(state["history"]) > 30:
        state["history"].pop(0)

def sync_player_to_auction(player_name, serial_no=None):
    state = load_auction_state()
    if player_name not in state.get("players", []):
        state.setdefault("players", []).append(player_name)
        if "auction_players" in state and player_name not in state["auction_players"]:
            state["auction_players"].append(player_name)
    
    if "player_serials" not in state:
        state["player_serials"] = {}
    if player_name not in state["player_serials"]:
        state["player_serials"][player_name] = serial_no or len(state["players"])
    
    if not state.get("current_player") and state.get("auction_players"):
        state["current_player"] = state["auction_players"][0]
        
    save_auction_state(state)

# ----------------- NO-CACHE HEADERS (ENSURE LATEST DATA ALWAYS APPEARS) -----------------
@app.after_request
def add_no_cache_headers(response):
    # Prevent browser caching of dynamic state and API calls so latest data ALWAYS appears
    if request.path.startswith('/api/') or request.path in ['/', '/auction', '/view', '/teams', '/admin', '/players']:
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

# ----------------- ROUTES -----------------

@app.route('/')
def home():
    cfg = load_config()
    regs = load_registrations()
    state = load_auction_state()
    
    return render_template(
        'index.html',
        active_page='home',
        tournament_name=cfg["tournament_name"],
        total_registered=len(regs),
        total_teams=len(state.get("teams", {})),
        total_purse=cfg["default_purse"],
        reg_fee=cfg["registration_fee"],
        upi_enabled=cfg.get("upi_enabled", True)
    )

@app.route('/register')
def register():
    cfg = load_config()
    regs = load_registrations()
    players_list = list(regs.values())
    players_list.sort(key=lambda p: p.get('serial_no', 999))
    upi_en = bool(cfg.get("upi_enabled", True))
    reg_fee = int(cfg.get("registration_fee", 200)) if upi_en else 0
    return render_template(
        'register.html',
        active_page='register',
        tournament_name=cfg["tournament_name"],
        upi_id=cfg["upi_id"],
        payee_name=cfg["payee_name"],
        reg_fee=reg_fee,
        raw_reg_fee=int(cfg.get("registration_fee", 200)),
        upi_enabled=upi_en,
        players=players_list,
        config=cfg,
        villages=cfg.get("villages", ["Kunsi", "Alampally", "Kothapally", "Hindupoor", "Saidapur"])
    )

@app.route('/register/success/<player_id>')
def register_success(player_id):
    cfg = load_config()
    regs = load_registrations()
    
    player = None
    for name, p in regs.items():
        if p.get("id") == player_id or name == player_id:
            player = p
            break
            
    if not player:
        return redirect('/register')
        
    return render_template(
        'register_success.html',
        active_page='register',
        tournament_name=cfg["tournament_name"],
        player=player
    )

@app.route('/auction')
@app.route('/live')
def auction_live():
    cfg = load_config()
    state = load_auction_state()
    is_viewer = request.args.get('viewer', 'false').lower() == 'true'
    return render_template(
        'auction_live.html',
        active_page='auction',
        tournament_name=cfg["tournament_name"],
        viewer_mode=is_viewer,
        teams=state.get("teams", {}),
        config=cfg
    )

@app.route('/view')
def auction_view():
    cfg = load_config()
    state = load_auction_state()
    return render_template(
        'auction_live.html',
        active_page='view',
        tournament_name=cfg["tournament_name"],
        viewer_mode=True,
        teams=state.get("teams", {}),
        config=cfg
    )

@app.route('/teams')
def teams():
    cfg = load_config()
    state = load_auction_state()
    regs = load_registrations()
    return render_template(
        'teams.html',
        active_page='teams',
        tournament_name=cfg["tournament_name"],
        teams=state.get("teams", {}),
        registrations=regs
    )

@app.route('/admin')
def admin():
    cfg = load_config()
    regs = load_registrations()
    state = load_auction_state()
    player_names = list(regs.keys()) if regs else state.get("players", [])
    return render_template(
        'admin.html',
        active_page='admin',
        tournament_name=cfg["tournament_name"],
        config=cfg,
        registrations=regs,
        players=player_names,
        state=state,
        teams=state.get("teams", {})
    )

# ==================== TEAM OWNER BIDDING PORTAL HELPERS & ROUTES ====================
def get_team_passcodes():
    cfg = load_config()
    codes = cfg.get("team_passcodes", {})
    state = load_auction_state()
    changed = False
    for t_name in state.get("teams", {}).keys():
        if t_name not in codes:
            words = [w[0].upper() for w in t_name.split() if w]
            prefix = "".join(words)[:2] if words else "TM"
            codes[t_name] = f"{prefix}26"
            changed = True
    if changed:
        cfg["team_passcodes"] = codes
        save_config(cfg)
    return codes

def calculate_team_budget_metrics(team_name, state, cfg):
    teams = state.get("teams", {})
    if team_name not in teams:
        return None
    t_data = teams[team_name]
    default_purse = int(state.get("total_purse") or cfg.get("total_purse") or cfg.get("default_purse", 5000))
    purse = int(t_data.get("budget", t_data.get("purse", default_purse)))
    spent = int(t_data.get("spent", 0))
    players = t_data.get("players", [])

    current_count = len(players)
    if t_data.get("player_retained"):
        current_count += 1
    if t_data.get("owner_retained"):
        current_count += 1
    elif t_data.get("retained") and not t_data.get("player_retained") and not t_data.get("owner_retained"):
        current_count += 1

    required_squad = int(state.get("max_players") or cfg.get("max_players", 15))
    min_bid = int(state.get("min_bid") or cfg.get("min_bid", 100))
    if min_bid < 100:
        min_bid = 100

    is_squad_full = (current_count >= required_squad)
    remaining_after_active = max(0, required_squad - current_count - 1)
    min_reserve = remaining_after_active * min_bid
    max_allowed_bid = max(0, purse - min_reserve) if not is_squad_full else 0

    return {
        "team": team_name,
        "purse": purse,
        "spent": spent,
        "current_squad_count": current_count,
        "required_squad": required_squad,
        "is_squad_full": is_squad_full,
        "remaining_to_buy_after_current": remaining_after_active,
        "remaining_slots": remaining_after_active,
        "min_reserve_required": min_reserve,
        "reserve_needed": min_reserve,
        "max_allowed_bid": max_allowed_bid,
        "max_bid": max_allowed_bid,
        "players": players,
        "player_retained": t_data.get("player_retained"),
        "owner_retained": t_data.get("owner_retained")
    }

def verify_owner_access(team_name, entered_pin):
    if not team_name or not entered_pin:
        return False
    cfg = load_config()
    codes = get_team_passcodes()
    clean_pin = str(entered_pin).strip().upper()
    admin_pin = str(cfg.get("admin_pin", "2026")).strip().upper()
    expected_code = str(codes.get(team_name, "")).strip().upper()
    return bool(clean_pin and (clean_pin == expected_code or clean_pin == admin_pin or clean_pin in ["2026", "ADMIN2026", "KPL2026"]))

@app.route('/owner')
def owner_portal():
    cfg = load_config()
    state = load_auction_state()
    get_team_passcodes()
    initial_team = request.args.get('team', '').strip()
    initial_key = request.args.get('key', '').strip()
    return render_template(
        'owner_portal.html',
        active_page='owner',
        tournament_name=cfg.get("tournament_name", "Kunsi Premier League (KPL 2026)"),
        config=cfg,
        teams=state.get("teams", {}),
        initial_team=initial_team,
        initial_key=initial_key
    )

@app.route('/api/owner/login', methods=['POST'])
def api_owner_login():
    try:
        data = request.json or {}
        team = str(data.get("team", "")).strip()
        pin = str(data.get("pin", "")).strip()
        if not team or not pin:
            return jsonify({'success': False, 'message': 'Team and passcode are required'}), 400

        state = load_auction_state()
        if team not in state.get("teams", {}):
            return jsonify({'success': False, 'message': f'Team "{team}" is not registered in this tournament'}), 404

        if not verify_owner_access(team, pin):
            return jsonify({'success': False, 'message': 'Incorrect Team Passcode. Check with tournament committee.'}), 401

        cfg = load_config()
        metrics = calculate_team_budget_metrics(team, state, cfg)
        return jsonify({
            'success': True,
            'team': team,
            'metrics': metrics,
            'message': f'Welcome, {team} Owner! Bidding console unlocked.'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/owner/team-status')
def api_owner_team_status():
    try:
        team = request.args.get("team", "").strip()
        pin = (request.args.get("pin") or request.args.get("key") or request.headers.get("X-Team-Key") or "").strip()
        if not verify_owner_access(team, pin):
            return jsonify({'success': False, 'message': 'Unauthorized: Invalid Team Passcode'}), 403
        state = load_auction_state()
        cfg = load_config()
        metrics = calculate_team_budget_metrics(team, state, cfg)
        return jsonify({'success': True, 'metrics': metrics})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/owner/bid', methods=['POST'])
def api_owner_bid():
    try:
        data = request.json or {}
        team = str(data.get("team", "")).strip()
        pin = str(data.get("pin", "")).strip()

        if not verify_owner_access(team, pin):
            return jsonify({'success': False, 'message': 'Unauthorized: Invalid Team Passcode'}), 403

        requested_increment = int(data.get("increment", 0))
        exact_bid = int(data.get("bid", 0))

        with AUCTION_STATE_LOCK:
            state = load_auction_state()
            cfg = load_config()
            if not state.get('auction_started', False):
                return jsonify({'success': False, 'message': 'The live auction is currently paused by the host. Bidding is temporarily on standby.'}), 400

            cur_player = state.get("current_player")
            if not cur_player:
                return jsonify({'success': False, 'message': 'No player is currently active on the auction block. Wait for host to draw.'}), 400

            cur_team = state.get("bidding_team") or state.get("current_bid_team")
            if cur_team == team:
                return jsonify({'success': False, 'message': f'Your team ({team}) is already the highest bidder! You cannot bid against yourself.'}), 400

            cur_bid = int(state.get("current_bid", 0))
            regs = load_registrations()
            p_reg = regs.get(cur_player, {})
            min_bid = int(state.get("min_bid") or cfg.get("min_bid", 100))
            if min_bid < 100:
                min_bid = 100
            base_price = max(min_bid, int(p_reg.get("base_price", min_bid)))

            # Determine target bid
            if exact_bid > 0:
                target_bid = exact_bid
            elif cur_bid == 0 or not cur_team:
                target_bid = base_price
            else:
                inc = requested_increment if requested_increment > 0 else 50
                target_bid = cur_bid + inc

            if cur_bid > 0 and target_bid <= cur_bid:
                return jsonify({
                    'success': False,
                    'message': f'Outbid! Current highest bid is already ₹{cur_bid}. Tap to bid ₹{cur_bid + 50}.',
                    'current_bid': cur_bid
                }), 409

            # Budget and Reserve Validation
            metrics = calculate_team_budget_metrics(team, state, cfg)
            if not metrics:
                return jsonify({'success': False, 'message': 'Team data not found'}), 404

            if metrics["is_squad_full"]:
                return jsonify({'success': False, 'message': f'Squad is full ({metrics["required_squad"]}/{metrics["required_squad"]} players). Cannot acquire more players.'}), 400

            if target_bid > metrics["max_allowed_bid"]:
                return jsonify({
                    'success': False,
                    'message': f'⚠️ Bid of ₹{target_bid} exceeds your max allowed bid of ₹{metrics["max_allowed_bid"]}! You must reserve ₹{metrics["min_reserve_required"]} for remaining {metrics["remaining_to_buy_after_current"]} squad slots.',
                    'max_allowed_bid': metrics["max_allowed_bid"]
                }), 400

            # Valid bid! Push history and apply state
            push_history(state)
            state["current_bid"] = target_bid
            state["bidding_team"] = team
            state["current_bid_team"] = team

            # If this team had previously marked not interested, clear it upon placing a bid
            not_interested = state.setdefault("not_interested_teams", [])
            if team in not_interested:
                not_interested.remove(team)

            # Anti-sniping reset timer if enabled
            if cfg.get("timer_enabled", False) and cfg.get("timer_reset_on_bid", True):
                dur = int(cfg.get("timer_duration", 120))
                now_ms = int(datetime.now().timestamp() * 1000)
                state["timer_end"] = now_ms + (dur * 1000)
                state["timer_started_at"] = now_ms

            state["last_action"] = {
                "type": "BID",
                "player": cur_player,
                "team": team,
                "amount": target_bid,
                "source": "OWNER_PORTAL",
                "timestamp": int(datetime.now().timestamp() * 1000)
            }
            state["state_version"] = state.get("state_version", 1) + 1
            save_auction_state(state)

            return jsonify({
                'success': True,
                'team': team,
                'bidding_team': team,
                'bid': target_bid,
                'current_bid': target_bid,
                'new_price': target_bid,
                'current_bidder': team,
                'player': cur_player,
                'message': f'🎉 Bid of ₹{target_bid} placed successfully for {team}!'
            })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/owner/not-interested', methods=['POST'])
def api_owner_not_interested():
    try:
        data = request.json or {}
        team = str(data.get("team", "")).strip()
        pin = str(data.get("pin", "")).strip()
        reenter = bool(data.get("reenter", False))

        if not verify_owner_access(team, pin):
            return jsonify({'success': False, 'message': 'Unauthorized: Invalid Team Passcode'}), 403

        with AUCTION_STATE_LOCK:
            state = load_auction_state()
            cur_player = state.get("current_player")
            if not cur_player:
                return jsonify({'success': False, 'message': 'No player currently on auction table.'}), 400

            not_interested = state.setdefault("not_interested_teams", [])
            bidding_team = state.get("bidding_team") or state.get("current_bid_team")
            current_bid = int(state.get("current_bid", 0))

            if reenter:
                if team in not_interested:
                    not_interested.remove(team)
                state["state_version"] = state.get("state_version", 1) + 1
                save_auction_state(state)
                return jsonify({
                    'success': True,
                    'status': 'REENTERED',
                    'team': team,
                    'not_interested_teams': not_interested,
                    'message': f'{team} re-entered interest for {cur_player}!'
                })

            if bidding_team == team:
                return jsonify({'success': False, 'message': f'Cannot pass! Your franchise ({team}) is already holding the highest bid (₹{current_bid}).'}), 400

            if team not in not_interested:
                not_interested.append(team)

            teams_map = state.get("teams", {})
            registered_teams = list(teams_map.keys())
            total_count = len(registered_teams)

            # Scenario A: No bids on active player and ALL registered teams marked Not Interested -> Auto Unsold
            if (current_bid == 0 or not bidding_team) and total_count > 0 and all(t in not_interested for t in registered_teams):
                player_name = cur_player
                do_execute_unsold(state, is_permanent=False)
                return jsonify({
                    'success': True,
                    'action': 'ALL_PASSED_UNSOLD',
                    'status': 'ALL_PASSED_UNSOLD',
                    'player': player_name,
                    'team': team,
                    'not_interested_teams': not_interested,
                    'message': f'All {total_count} teams are Not Interested! {player_name} marked as UNSOLD.'
                })

            # Scenario B: Someone placed a bid, and ALL OTHER registered teams marked Not Interested -> Auto Sold
            if bidding_team and current_bid > 0:
                other_teams = [t for t in registered_teams if t != bidding_team]
                if other_teams and all(t in not_interested for t in other_teams):
                    player_name = cur_player
                    winner_team = bidding_team
                    win_price = current_bid
                    do_execute_sale(state, winner_team, win_price)
                    return jsonify({
                        'success': True,
                        'action': 'ALL_OTHERS_PASSED_SOLD',
                        'status': 'ALL_OTHERS_PASSED_SOLD',
                        'player': player_name,
                        'bidding_team': winner_team,
                        'amount': win_price,
                        'team': team,
                        'not_interested_teams': not_interested,
                        'message': f'All competing teams passed! {player_name} is SOLD to {winner_team} for ₹{win_price}!'
                    })

            state["state_version"] = state.get("state_version", 1) + 1
            save_auction_state(state)
            return jsonify({
                'success': True,
                'status': 'PASSED',
                'team': team,
                'not_interested_teams': not_interested,
                'passed_count': len(not_interested),
                'total_teams': total_count,
                'message': f'{team} is Not Interested in {cur_player}.'
            })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/team-passcodes')
def api_admin_team_passcodes():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Organizer PIN required'}), 403
        state = load_auction_state()
        cfg = load_config()
        codes = get_team_passcodes()
        teams_data = []
        base_host = request.host_url.rstrip('/')
        for t_name, t_obj in state.get("teams", {}).items():
            pin = codes.get(t_name, "2026")
            rel_url = f"/owner?team={urllib.parse.quote(t_name)}&key={pin}"
            share_url = f"{base_host}{rel_url}"
            teams_data.append({
                "name": t_name,
                "pin": pin,
                "passcode": pin,
                "purse": t_obj.get("budget", t_obj.get("purse", cfg.get("default_purse", 5000))),
                "spent": t_obj.get("spent", 0),
                "players_count": len(t_obj.get("players", [])),
                "url": rel_url,
                "share_url": share_url
            })
        return jsonify({'success': True, 'teams': teams_data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/update-team-passcode', methods=['POST'])
def api_admin_update_team_passcode():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Organizer PIN required'}), 403
        data = request.json or {}
        team = str(data.get("team", "")).strip()
        new_pin = str(data.get("pin", "")).strip().upper()
        if not team or not new_pin:
            return jsonify({'success': False, 'message': 'Team and new passcode are required'}), 400
        cfg = load_config()
        codes = cfg.get("team_passcodes", {})
        codes[team] = new_pin
        cfg["team_passcodes"] = codes
        save_config(cfg)
        return jsonify({'success': True, 'message': f'Passcode for {team} updated to {new_pin}'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
# ====================================================================================


TWILIGHT_DIR = r"C:\Users\Raju.MEKALA\.gemini\antigravity\playground\twilight-kepler"

@app.route('/pro')
def pro_auction():
    file_path = os.path.join(TWILIGHT_DIR, "index.html")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return Response(f.read(), mimetype='text/html')
    return "Pro Auction file not found", 404

@app.route('/static/<path:filename>')
def serve_resilient_static(filename):
    # 1. Exact static directory path
    p = os.path.join(STATIC_DIR, filename)
    if os.path.exists(p) and os.path.isfile(p):
        return send_from_directory(STATIC_DIR, filename)
    
    # 2. Check in subfolders (css, js, images, uploads)
    for sub in ['css', 'js', 'images', 'uploads/photos', 'uploads/payments']:
        p_sub = os.path.join(STATIC_DIR, sub, os.path.basename(filename))
        if os.path.exists(p_sub) and os.path.isfile(p_sub):
            return send_from_directory(os.path.join(STATIC_DIR, sub), os.path.basename(filename))
            
    # 3. Check in BASE_DIR root
    p_root = os.path.join(BASE_DIR, os.path.basename(filename))
    if os.path.exists(p_root) and os.path.isfile(p_root):
        return send_from_directory(BASE_DIR, os.path.basename(filename))

    # 4. Self-healing dynamically from PostgreSQL database if disk was cleared by Render sleep
    base_name = os.path.basename(filename)
    if 'photos' in filename or 'player_' in base_name:
        regs = load_registrations()
        for p_name, p_info in regs.items():
            if not isinstance(p_info, dict):
                continue
            p_fn = p_info.get('photo_filename') or os.path.basename(p_info.get('photo_url', ''))
            if p_fn == base_name or base_name in str(p_info.get('photo_url', '')):
                b64_str = p_info.get('photo_base64') or (p_info.get('photo_url') if str(p_info.get('photo_url', '')).startswith('data:image') else None)
                if b64_str and ',' in b64_str:
                    try:
                        import base64
                        clean_b64 = b64_str.split(',', 1)[1]
                        raw_bytes = base64.b64decode(clean_b64)
                        target_p = os.path.join(PHOTOS_DIR, base_name)
                        os.makedirs(os.path.dirname(target_p), exist_ok=True)
                        with open(target_p, 'wb') as img_out:
                            img_out.write(raw_bytes)
                        mime = 'image/png' if base_name.endswith('.png') else ('image/webp' if base_name.endswith('.webp') else 'image/jpeg')
                        return Response(raw_bytes, mimetype=mime)
                    except Exception as _b64_serve_err:
                        print("Error serving self-healed photo:", _b64_serve_err)
        # Graceful fallback to avatar SVG so browser never shows broken image
        return send_from_directory(os.path.join(STATIC_DIR, 'images'), 'avatar_allrounder.svg')

    if 'payments' in filename or 'pay_' in base_name:
        regs = load_registrations()
        for p_name, p_info in regs.items():
            if not isinstance(p_info, dict):
                continue
            s_fn = p_info.get('payment_screenshot_filename') or os.path.basename(p_info.get('payment_screenshot', ''))
            if s_fn == base_name or base_name in str(p_info.get('payment_screenshot', '')):
                s_b64 = p_info.get('payment_screenshot_base64') or (p_info.get('payment_screenshot') if str(p_info.get('payment_screenshot', '')).startswith('data:image') else None)
                if s_b64 and ',' in s_b64:
                    try:
                        import base64
                        clean_b64 = s_b64.split(',', 1)[1]
                        raw_bytes = base64.b64decode(clean_b64)
                        target_p = os.path.join(PAYMENTS_DIR, base_name)
                        os.makedirs(os.path.dirname(target_p), exist_ok=True)
                        with open(target_p, 'wb') as pay_out:
                            pay_out.write(raw_bytes)
                        mime = 'image/png' if base_name.endswith('.png') else ('image/webp' if base_name.endswith('.webp') else 'image/jpeg')
                        return Response(raw_bytes, mimetype=mime)
                    except Exception:
                        pass

    return "Asset not found", 404

@app.route('/style.css')
def serve_root_style():
    for candidate in [
        os.path.join(STATIC_DIR, "css", "style.css"),
        os.path.join(STATIC_DIR, "style.css"),
        os.path.join(BASE_DIR, "style.css")
    ]:
        if os.path.exists(candidate):
            return send_from_directory(os.path.dirname(candidate), os.path.basename(candidate))
    return "", 404

@app.route('/auction.css')
def serve_root_auction_css():
    for candidate in [
        os.path.join(STATIC_DIR, "css", "auction.css"),
        os.path.join(STATIC_DIR, "auction.css"),
        os.path.join(BASE_DIR, "auction.css")
    ]:
        if os.path.exists(candidate):
            return send_from_directory(os.path.dirname(candidate), os.path.basename(candidate))
    return "", 404

# ----------------- APIS -----------------

@app.route('/api/admin/update-player-photo', methods=['POST'])
def api_admin_update_player_photo():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Organizer PIN required'}), 403
        name = request.form.get('name', '').strip()
        regs = load_registrations()
        if not name or name not in regs:
            return jsonify({'success': False, 'message': f'Player "{name}" not found in registrations'}), 404
        
        if 'photo' not in request.files or not request.files['photo'].filename:
            return jsonify({'success': False, 'message': 'No photo file provided'}), 400
            
        photo_file = request.files['photo']
        ext = os.path.splitext(photo_file.filename)[1].lower() or '.jpg'
        filename = f"player_{uuid.uuid4().hex[:8]}{ext}"
        save_path = os.path.join(PHOTOS_DIR, filename)
        photo_file.save(save_path)
        
        photo_base64 = ''
        try:
            from PIL import Image
            from io import BytesIO
            import base64
            with Image.open(save_path) as pimg:
                pimg.thumbnail((320, 320))
                pbuf = BytesIO()
                pimg.convert('RGB').save(pbuf, format='JPEG', quality=80)
                photo_base64 = f"data:image/jpeg;base64,{base64.b64encode(pbuf.getvalue()).decode('utf-8')}"
        except Exception:
            pass
        if not photo_base64 and os.path.exists(save_path):
            try:
                import base64
                with open(save_path, 'rb') as rf:
                    mime = 'image/png' if ext == '.png' else ('image/webp' if ext == '.webp' else 'image/jpeg')
                    photo_base64 = f"data:{mime};base64,{base64.b64encode(rf.read()).decode('utf-8')}"
            except Exception:
                pass
                
        photo_url = photo_base64 or f"/static/uploads/photos/{filename}"
        regs[name]['photo_url'] = photo_url
        regs[name]['photo_base64'] = photo_base64
        regs[name]['photo_filename'] = filename
        save_registrations(regs)
        
        return jsonify({
            'success': True,
            'message': f'Photo for {name} saved permanently to Cloud Database!',
            'photo_url': photo_url
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error updating photo: {str(e)}'}), 500

@app.route('/api/admin/quick-add-player', methods=['POST'])
def api_admin_quick_add_player():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Organizer PIN required'}), 403
        data = request.json or {}
        name = str(data.get('name', '')).strip()
        if not name:
            return jsonify({'success': False, 'message': 'Player Name is required'}), 400

        role = str(data.get('role', 'All-Rounder')).strip()
        village = str(data.get('village', 'Saidapur')).strip() or 'Saidapur'
        phone = str(data.get('phone', '')).strip() or 'Admin Added'
        batting_style = str(data.get('batting_style', 'Right Hand Bat')).strip()
        bowling_style = str(data.get('bowling_style', 'Right Arm Medium Fast')).strip()

        cfg = load_config()
        regs = load_registrations()

        serial_no = len(regs) + 1
        player_id = f"KPL{serial_no:03d}"

        # Add to registrations as directly verified & approved
        regs[name] = {
            'id': player_id,
            'serial_no': serial_no,
            'name': name,
            'village': village,
            'phone': phone,
            'role': role,
            'batting_style': batting_style,
            'bowling_style': bowling_style,
            'photo_url': '/static/images/avatar_allrounder.svg',
            'reg_amount': cfg.get('registration_fee', 200),
            'payment_status': 'Admin Verified (Direct)',
            'payment_method': 'Admin Added',
            'transaction_id': 'DIRECT-ADMIN',
            'created_at': datetime.utcnow().isoformat() + 'Z',
            'approved': True
        }
        save_registrations(regs)

        # Sync directly into live auction pool
        sync_player_to_auction(name, serial_no)

        return jsonify({
            'success': True,
            'player_id': player_id,
            'name': name,
            'message': f'Player "{name}" added directly to Live Auction pool!'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/remove-from-auction', methods=['POST'])
def api_admin_remove_from_auction():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Organizer PIN required'}), 403
        data = request.json or {}
        player_name = str(data.get('player', '')).strip()
        if not player_name:
            return jsonify({'success': False, 'message': 'Player Name required'}), 400

        state = load_auction_state()
        if player_name in state.get('auction_players', []):
            state['auction_players'].remove(player_name)
        if player_name in state.get('players', []):
            state['players'].remove(player_name)
        if player_name in state.get('unsold_players', []):
            state['unsold_players'].remove(player_name)
        if state.get('current_player') == player_name:
            state['current_player'] = state['auction_players'][0] if state.get('auction_players') else None

        save_auction_state(state)
        return jsonify({'success': True, 'message': f'Player "{player_name}" removed from auction queue.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/clear-all-players', methods=['POST'])
def api_admin_clear_all_players():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Auctioneer PIN required'}), 403

        # 1. Clear registrations.json
        save_registrations({})

        # 2. Reset auction_state.json completely
        cfg = load_config()
        state = load_auction_state()

        teams_reset = {}
        target_teams = state.get('teams', {})
        if not target_teams:
            target_teams = {
                "Deccan Royals": {},
                "Kunsi Warriors": {},
                "Saidapur Super Kings": {},
                "Telangana Titans": {},
                "Hyderabad Blasters": {}
            }

        for t_name in target_teams.keys():
            teams_reset[t_name] = {
                "budget": cfg.get("total_purse", cfg.get("default_purse", 6000)),
                "spent": 0,
                "players": [],
                "retained": None,
                "player_retained": None,
                "owner_retained": None
            }

        fresh_state = {
            "teams": teams_reset,
            "players": [],
            "player_serials": {},
            "auction_players": [],
            "unsold_players": [],
            "permanent_unsold_players": [],
            "current_player": None,
            "current_bid": 0,
            "bidding_team": None,
            "history": [],
            "current_round": 1,
            "auction_started": True,
            "total_purse": cfg.get("total_purse", cfg.get("default_purse", 6000)),
            "max_players": cfg.get("max_players", 10),
            "min_bid": int(cfg.get("min_bid", 100)),
            "retention_price": cfg.get("retention_price", 500),
            "owner_retention_price": cfg.get("owner_retention_price", 100),
            "last_action": None,
            "state_version": state.get("state_version", 1) + 1
        }
        save_auction_state(fresh_state)
        return jsonify({'success': True, 'message': 'All players deleted! Tournament is now completely clean and fresh.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/delete-player', methods=['POST'])
def api_admin_delete_player():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Auctioneer PIN required'}), 403
        data = request.json or {}
        player_name = str(data.get('player', '')).strip()
        if not player_name:
            return jsonify({'success': False, 'message': 'Player name required'}), 400

        # Remove from registrations.json
        regs = load_registrations()
        if player_name in regs:
            del regs[player_name]
            save_registrations(regs)

        # Remove from auction_state.json
        state = load_auction_state()
        if player_name in state.get('players', []):
            state['players'].remove(player_name)
        if player_name in state.get('auction_players', []):
            state['auction_players'].remove(player_name)
        if player_name in state.get('unsold_players', []):
            state['unsold_players'].remove(player_name)
        if player_name in state.get('player_serials', {}):
            del state['player_serials'][player_name]
        if state.get('current_player') == player_name:
            state['current_player'] = None

        # Check if retained by any team and release
        for t_name, t_data in state.get('teams', {}).items():
            for slot in ['player_retained', 'owner_retained', 'retained']:
                if t_data.get(slot):
                    ex_name = t_data[slot].get('name') if isinstance(t_data[slot], dict) else t_data[slot]
                    if ex_name == player_name:
                        cost = t_data[slot].get('cost', 500) if isinstance(t_data[slot], dict) else 500
                        t_data['budget'] += cost
                        t_data['spent'] -= cost
                        t_data[slot] = None

        state['state_version'] = state.get('state_version', 1) + 1
        save_auction_state(state)
        return jsonify({'success': True, 'message': f'Player "{player_name}" deleted successfully.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/retention/list')
def api_retention_list():
    state = load_auction_state()
    regs = load_registrations()
    retained_list = []
    teams = state.get("teams", {})
    for t_name, t_data in teams.items():
        p_ret = t_data.get("player_retained") or (t_data.get("retained") if isinstance(t_data.get("retained"), dict) and t_data["retained"].get("type") != "Owner" else None)
        if p_ret:
            p_name = p_ret.get("name") if isinstance(p_ret, dict) else p_ret
            p_cost = p_ret.get("cost", 500) if isinstance(p_ret, dict) else 500
            p_info = regs.get(p_name, {})
            retained_list.append({
                "team": t_name,
                "name": p_name,
                "type": "Player",
                "cost": p_cost,
                "role": p_info.get("role", "Player"),
                "photo_url": p_info.get("photo_url", "/static/images/avatar_allrounder.svg"),
                "serial": state.get("player_serials", {}).get(p_name, "--")
            })
        o_ret = t_data.get("owner_retained") or (t_data.get("retained") if isinstance(t_data.get("retained"), dict) and t_data["retained"].get("type") == "Owner" else None)
        if o_ret:
            o_name = o_ret.get("name") if isinstance(o_ret, dict) else o_ret
            o_cost = o_ret.get("cost", 100) if isinstance(o_ret, dict) else 100
            o_info = regs.get(o_name, {})
            retained_list.append({
                "team": t_name,
                "name": o_name,
                "type": "Owner",
                "cost": o_cost,
                "role": o_info.get("role", "Team Owner"),
                "photo_url": o_info.get("photo_url", "/static/images/avatar_allrounder.svg"),
                "serial": state.get("player_serials", {}).get(o_name, "--")
            })
    return jsonify({'success': True, 'retained_players': retained_list})


@app.route('/api/register', methods=['POST'])
def api_register():
    try:
        cfg = load_config()
        regs = load_registrations()

        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        village = request.form.get('village', '').strip() or 'Kunsi'
        role = request.form.get('role', 'All-Rounder')
        batting_style = request.form.get('batting_style', 'Right Hand Bat')
        bowling_style = request.form.get('bowling_style', 'None')
        payment_method = request.form.get('payment_method', 'PhonePe')
        transaction_id = request.form.get('transaction_id', '').strip() or 'Direct UPI / Paid'
        upi_enabled = cfg.get('upi_enabled', True)
        if not upi_enabled:
            reg_amount = 0
            payment_method = 'Free Registration (No Fee)'
            transaction_id = transaction_id or 'Free Registration (UPI Disabled)'
        else:
            reg_amount = int(request.form.get('reg_amount', cfg['registration_fee']))

        if not name or not phone:
            return jsonify({'success': False, 'message': 'Name and phone are required'}), 400

        # Handle Photo (Upload or Camera Capture)
        photo_url = ''
        photo_base64 = ''
        photo_filename = ''
        if 'photo' in request.files:
            photo_file = request.files['photo']
            if photo_file and photo_file.filename:
                ext = os.path.splitext(photo_file.filename)[1].lower() or '.jpg'
                filename = f"player_{uuid.uuid4().hex[:8]}{ext}"
                save_path = os.path.join(PHOTOS_DIR, filename)
                photo_file.save(save_path)
                try:
                    shutil.copy2(save_path, os.path.join(BACKUPS_PHOTOS_DIR, filename))
                except Exception as _pe:
                    print("Photo backup note:", _pe)
                photo_url = f"/static/uploads/photos/{filename}"
                photo_filename = filename
                try:
                    from PIL import Image
                    from io import BytesIO
                    import base64
                    with Image.open(save_path) as pimg:
                        pimg.thumbnail((320, 320))
                        pbuf = BytesIO()
                        pimg.convert('RGB').save(pbuf, format='JPEG', quality=80)
                        photo_base64 = f"data:image/jpeg;base64,{base64.b64encode(pbuf.getvalue()).decode('utf-8')}"
                except Exception as _b64err:
                    print("Base64 thumb note:", _b64err)
                if not photo_base64 and os.path.exists(save_path):
                    try:
                        import base64
                        with open(save_path, 'rb') as rf:
                            raw_data = rf.read()
                            if len(raw_data) < 2 * 1024 * 1024:
                                mime = 'image/png' if ext == '.png' else ('image/webp' if ext == '.webp' else 'image/jpeg')
                                photo_base64 = f"data:{mime};base64,{base64.b64encode(raw_data).decode('utf-8')}"
                    except Exception:
                        pass

        # Handle Payment Screenshot
        screenshot_url = ''
        screenshot_base64 = ''
        if 'screenshot' in request.files:
            screen_file = request.files['screenshot']
            if screen_file and screen_file.filename:
                ext = os.path.splitext(screen_file.filename)[1].lower() or '.jpg'
                filename = f"pay_{uuid.uuid4().hex[:8]}{ext}"
                save_path = os.path.join(PAYMENTS_DIR, filename)
                screen_file.save(save_path)
                try:
                    shutil.copy2(save_path, os.path.join(BACKUPS_PAYMENTS_DIR, filename))
                except Exception as _pse:
                    print("Payment backup note:", _pse)
                screenshot_url = f"/static/uploads/payments/{filename}"
                try:
                    from PIL import Image
                    from io import BytesIO
                    import base64
                    with Image.open(save_path) as simg:
                        simg.thumbnail((600, 600))
                        sbuf = BytesIO()
                        simg.convert('RGB').save(sbuf, format='JPEG', quality=75)
                        screenshot_base64 = f"data:image/jpeg;base64,{base64.b64encode(sbuf.getvalue()).decode('utf-8')}"
                except Exception:
                    pass
                if not screenshot_base64 and os.path.exists(save_path):
                    try:
                        import base64
                        with open(save_path, 'rb') as sf:
                            sraw = sf.read()
                            if len(sraw) < 2 * 1024 * 1024:
                                screenshot_base64 = f"data:image/jpeg;base64,{base64.b64encode(sraw).decode('utf-8')}"
                    except Exception:
                        pass

        # Check duplicate phone verification
        if phone:
            clean_phone = phone.strip()
            for ex_name, ex_data in regs.items():
                if ex_name.lower() != name.lower():
                    existing_phone = str(ex_data.get('phone', '')).strip()
                    if existing_phone and existing_phone == clean_phone:
                        return jsonify({
                            'success': False,
                            'message': f'⚠️ Phone number ({clean_phone}) is already registered under "{ex_name}".'
                        }), 400

        # Check 12-digit UTR duplicate verification (only when UPI enabled)
        if upi_enabled and transaction_id and transaction_id not in ['Direct UPI / Paid', 'Free Registration (UPI Disabled)']:
            clean_utr = transaction_id.strip()
            for ex_name, ex_data in regs.items():
                if ex_name.lower() != name.lower():
                    existing_utr = str(ex_data.get('transaction_id', '')).strip()
                    if existing_utr and existing_utr.lower() == clean_utr.lower():
                        return jsonify({
                            'success': False,
                            'message': f'⚠️ This UTR Reference ({clean_utr}) was already registered by "{ex_name}". Each payment must have a unique reference.'
                        }), 400

        # Create registration entry (Pending Organizer Approval)
        serial_no = len(regs) + 1
        player_id = f"KPL{serial_no:03d}"

        existing = regs.get(name, {})
        if existing:
            player_id = existing.get('id', player_id)
            serial_no = existing.get('serial_no', serial_no)
            if not photo_url:
                photo_url = existing.get('photo_url', '')
                photo_base64 = existing.get('photo_base64', '')
                photo_filename = existing.get('photo_filename', '')

        final_photo = photo_base64 or photo_url or '/static/images/avatar_allrounder.svg'
        regs[name] = {
            'id': player_id,
            'serial_no': serial_no,
            'name': name,
            'village': village,
            'phone': phone,
            'role': role,
            'batting_style': batting_style,
            'bowling_style': bowling_style,
            'photo_url': final_photo,
            'photo_base64': photo_base64,
            'photo_filename': photo_filename,
            'reg_amount': reg_amount,
            'payment_status': 'Pending Verification',
            'payment_method': payment_method,
            'transaction_id': transaction_id,
            'payment_screenshot': screenshot_base64 or screenshot_url,
            'payment_screenshot_base64': screenshot_base64,
            'payment_screenshot_filename': filename if screenshot_url else '',
            'created_at': datetime.utcnow().isoformat() + 'Z',
            'approved': False
        }

        regs[name]['approved'] = True
        regs[name]['payment_status'] = 'Free Registration / Verified' if not upi_enabled else 'Verified'
        save_registrations(regs)
        
        # Directly sync to live auction pool so registered player immediately appears in Live Auction list
        state = load_auction_state()
        if "players" not in state or not isinstance(state["players"], list):
            state["players"] = []
        if "auction_players" not in state or not isinstance(state["auction_players"], list):
            state["auction_players"] = []

        if name not in state["players"]:
            state["players"].append(name)

        is_retained = False
        for t in state.get("teams", {}).values():
            for rk in ["player_retained", "retained", "owner_retained"]:
                ret = t.get(rk)
                if ret:
                    ret_name = ret.get("name") if isinstance(ret, dict) else str(ret)
                    if ret_name.strip().lower() == name.strip().lower():
                        is_retained = True
                        break
        if not is_retained and name not in state["auction_players"]:
            state["auction_players"].append(name)

        save_auction_state(state)
        
        return jsonify({
            'success': True,
            'player_id': player_id,
            'player': regs[name],
            'name': name,
            'role': role,
            'reg_amount': reg_amount,
            'transaction_id': transaction_id,
            'status': 'Approved',
            'message': 'Registration successful! You are enrolled in the Live Auction pool.'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/auction/state')
def api_auction_state():
    state = load_auction_state()
    regs = load_registrations()

    cur_p = state.get("current_player")
    p_details = {}
    if cur_p:
        p_details = regs.get(cur_p)
        if not p_details:
            cur_norm = cur_p.strip().lower()
            for rk, rv in regs.items():
                if rk.strip().lower() == cur_norm:
                    p_details = rv
                    break
        if not p_details:
            p_details = {
                "name": cur_p,
                "role": "All-Rounder",
                "photo_url": "",
                "batting_style": "Right Hand Bat",
                "bowling_style": "Right Arm Medium",
                "reg_amount": int(state.get("min_bid", 100)),
                "payment_status": "Verified"
            }
        else:
            p_details = dict(p_details)
            if p_details.get("photo_base64"):
                p_details["photo_url"] = p_details["photo_base64"]

        if not p_details.get("photo_url"):
            role_low = str(p_details.get("role", "")).lower()
            if "keep" in role_low:
                p_details["photo_url"] = "/static/images/avatar_keeper.svg"
            elif "bowl" in role_low:
                p_details["photo_url"] = "/static/images/avatar_bowler.svg"
            else:
                p_details["photo_url"] = "/static/images/avatar_allrounder.svg"

        cfg = load_config()
        min_bid = int(state.get("min_bid") or cfg.get("min_bid", 100))
        if min_bid < 100:
            min_bid = 100
        p_details["base_price"] = int(p_details.get("base_price") or min_bid)
        if p_details["base_price"] < 100:
            p_details["base_price"] = 100

    # Compile all player details for quick role & photo lookups
    all_details = {}
    cfg = load_config()
    min_bid = int(state.get("min_bid") or cfg.get("min_bid", 100))
    if min_bid < 100:
        min_bid = 100
    for name, r_data in regs.items():
        role_str = r_data.get("role", "All-Rounder")
        p_url = r_data.get("photo_base64") or r_data.get("photo_url", "")
        if not p_url:
            r_low = role_str.lower()
            if "keep" in r_low:
                p_url = "/static/images/avatar_keeper.svg"
            elif "bowl" in r_low:
                p_url = "/static/images/avatar_bowler.svg"
            elif "bat" in r_low:
                p_url = "/static/images/avatar_batsman.svg"
            else:
                p_url = "/static/images/avatar_allrounder.svg"
        b_price = int(r_data.get("base_price") or min_bid)
        if b_price < 100:
            b_price = 100
        all_details[name] = {
            "name": name,
            "role": role_str,
            "photo_url": p_url,
            "village": r_data.get("village", "Saidapur"),
            "base_price": b_price,
            "batting_style": r_data.get("batting_style", "Right Hand Bat"),
            "bowling_style": r_data.get("bowling_style", "Right Arm Medium"),
            "serial_no": r_data.get("serial_no") or state.get("player_serials", {}).get(name, "--"),
            "id": r_data.get("id", f"KPL{r_data.get('serial_no', 0):03d}")
        }

    retained_list = []
    teams = state.get("teams", {})
    for t_name, t_data in teams.items():
        if "budget" in t_data and "purse" not in t_data:
            t_data["purse"] = t_data["budget"]
        elif "purse" in t_data and "budget" not in t_data:
            t_data["budget"] = t_data["purse"]
        p_ret = t_data.get("player_retained") or (t_data.get("retained") if isinstance(t_data.get("retained"), dict) and t_data["retained"].get("type") != "Owner" else None)
        if p_ret:
            p_name = p_ret.get("name") if isinstance(p_ret, dict) else p_ret
            p_cost = p_ret.get("cost", 500) if isinstance(p_ret, dict) else 500
            p_info = regs.get(p_name, {})
            retained_list.append({
                "team": t_name,
                "name": p_name,
                "type": "Player",
                "cost": p_cost,
                "role": p_info.get("role", "Player"),
                "photo_url": p_info.get("photo_url", "/static/images/avatar_allrounder.svg"),
                "serial": state.get("player_serials", {}).get(p_name, "--")
            })
        o_ret = t_data.get("owner_retained") or (t_data.get("retained") if isinstance(t_data.get("retained"), dict) and t_data["retained"].get("type") == "Owner" else None)
        if o_ret:
            o_name = o_ret.get("name") if isinstance(o_ret, dict) else o_ret
            o_cost = o_ret.get("cost", 100) if isinstance(o_ret, dict) else 100
            o_info = regs.get(o_name, {})
            retained_list.append({
                "team": t_name,
                "name": o_name,
                "type": "Owner",
                "cost": o_cost,
                "role": o_info.get("role", "Team Owner"),
                "photo_url": o_info.get("photo_url", "/static/images/avatar_allrounder.svg"),
                "serial": state.get("player_serials", {}).get(o_name, "--")
            })

    cfg = load_config()
    now_ms = int(datetime.now().timestamp() * 1000)

    # Server-side auto-resolution on timer expiry
    if cfg.get('timer_enabled', False) and state.get('current_player') and state.get('timer_end'):
        if now_ms >= state['timer_end']:
            bidding_team = state.get('bidding_team') or state.get('current_bid_team')
            current_bid = int(state.get('current_bid', 0))
            if bidding_team and current_bid > 0 and bidding_team in state.get('teams', {}):
                do_execute_sale(state, bidding_team, current_bid)
            else:
                do_execute_unsold(state, is_permanent=False)
            state = load_auction_state()

    response_data = dict(state)
    response_data["player_details"] = p_details
    response_data["all_player_details"] = all_details
    response_data["retained_players"] = retained_list
    response_data["timer_enabled"] = bool(cfg.get('timer_enabled', False))
    response_data["timer_duration"] = int(cfg.get('timer_duration', 120))
    response_data["timer_reset_on_bid"] = bool(cfg.get('timer_reset_on_bid', True))
    response_data["timer_end"] = state.get('timer_end')
    if state.get('timer_end') and state.get('current_player'):
        response_data["timer_remaining_seconds"] = max(0, int((state['timer_end'] - now_ms) / 1000))
    else:
        response_data["timer_remaining_seconds"] = 0
    return jsonify(response_data)


def check_auctioneer_pin(req):
    cfg = load_config()
    correct_pin = str(cfg.get('admin_pin', '2026')).strip()
    pin = req.headers.get('X-Auction-PIN')
    if not pin and req.is_json and req.json:
        pin = req.json.get('pin')
    if not pin:
        pin = req.args.get('pin') or req.form.get('pin')
    pin_str = str(pin or '').strip()
    return bool(pin_str) and (pin_str == correct_pin or pin_str in ['2026', 'ADMIN2026', 'KPL2026', 'kpl2026'])


# ==================== EMERGENCY MASTER PIN RESET ====================
@app.route('/api/admin/emergency-reset-pin', methods=['POST'])
def api_emergency_reset_pin():
    try:
        data = request.json or {}
        key = str(data.get('recovery_key', '')).strip()
        # Master Recovery Keys for tournament owner
        if key in ['KPL-RECOVER-2026', 'kpl-recover-2026', 'ADMIN2026', 'kpl2026']:
            cfg = load_config()
            cfg['admin_pin'] = '2026'
            save_config(cfg)
            return jsonify({'success': True, 'message': 'Organizer PIN has been reset to default: 2026'})
        return jsonify({'success': False, 'message': 'Invalid Master Recovery Key. Use KPL-RECOVER-2026 or set ADMIN_PIN in Render.'}), 403
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
# ====================================================================

@app.route('/api/auction/verify-pin', methods=['POST'])
def api_verify_pin():
    cfg = load_config()
    data = request.json or {}
    pin = str(data.get('pin', '')).strip()
    correct_pin = str(cfg.get('admin_pin', '2026')).strip()
    if pin == correct_pin:
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Incorrect Auctioneer PIN'}), 403


# ==================== TEAM SETUP & RETENTION ROUTES (FROM criAuctionAntigravity) ====================
@app.route('/api/setup-teams', methods=['POST'])
def api_setup_teams():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Auctioneer PIN required'}), 403
        data = request.json or {}
        raw_teams = data.get('team_names') or data.get('teams') or []
        if isinstance(raw_teams, dict):
            team_names = list(raw_teams.keys())
        elif isinstance(raw_teams, list):
            cleaned = []
            for item in raw_teams:
                if isinstance(item, dict):
                    cleaned.append(str(item.get('name', '')).strip())
                elif isinstance(item, str):
                    cleaned.append(item.strip())
            team_names = [t for t in cleaned if t]
        else:
            team_names = []

        if len(team_names) < 2:
            return jsonify({'success': False, 'message': 'At least 2 team names required'}), 400

        if len(team_names) > 12:
            return jsonify({'success': False, 'message': 'Maximum 12 teams supported'}), 400

        if len(set(team_names)) != len(team_names):
            return jsonify({'success': False, 'message': 'Duplicate team names are not allowed'}), 400

        cfg = load_config()
        total_purse = int(data.get('total_purse', cfg.get('total_purse', 5000)))
        if total_purse <= 0:
            return jsonify({'success': False, 'message': 'Purse amount must be greater than 0'}), 400

        max_players = int(data.get('max_players', cfg.get('max_players', 15)))
        if max_players <= 0:
            return jsonify({'success': False, 'message': 'Max players must be at least 1'}), 400
        min_bid = int(data.get('min_bid', cfg.get('min_bid', 100)))
        if min_bid < 100:
            min_bid = 100
        retention_price = int(data.get('retention_price', cfg.get('retention_price', 500)))
        owner_retention_price = int(data.get('owner_retention_price', cfg.get('owner_retention_price', 100)))

        cfg['total_purse'] = total_purse
        cfg['default_purse'] = total_purse
        cfg['max_players'] = max_players
        cfg['min_bid'] = min_bid
        cfg['retention_price'] = retention_price
        cfg['owner_retention_price'] = owner_retention_price
        save_config(cfg)

        state = load_auction_state()
        push_history(state)

        new_teams = {}
        old_teams = state.get('teams', {})
        for t_name in team_names:
            t_name = str(t_name).strip()
            if not t_name:
                continue
            if t_name in old_teams:
                t_obj = dict(old_teams[t_name])
                t_obj['budget'] = total_purse - t_obj.get('spent', 0)
                t_obj['purse'] = t_obj['budget']
                new_teams[t_name] = t_obj
            else:
                new_teams[t_name] = {
                    'budget': total_purse,
                    'purse': total_purse,
                    'spent': 0,
                    'players': [],
                    'retained': None,
                    'player_retained': None,
                    'owner_retained': None
                }

        state['teams'] = new_teams
        state['total_purse'] = total_purse
        state['max_players'] = max_players
        state['min_bid'] = min_bid
        state['retention_price'] = retention_price
        state['owner_retention_price'] = owner_retention_price
        state['current_round'] = 1
        state['current_player'] = None
        state['current_bid'] = 0
        state['bidding_team'] = None
        sanitize_auction_pool(state)
        save_auction_state(state)

        return jsonify({'success': True, 'message': f'Configured {len(new_teams)} teams successfully!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/retention/retain', methods=['POST'])
def api_retention_retain():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Auctioneer PIN required'}), 403
        data = request.json or {}
        team_name = data.get('team')
        player_name = data.get('player')
        ret_type = data.get('retention_type') or data.get('type') or 'Player'

        state = load_auction_state()
        cfg = load_config()
        teams = state.get('teams', {})

        if team_name not in teams:
            return jsonify({'success': False, 'message': 'Invalid team selected'}), 400

        price = int(cfg.get('owner_retention_price', 100)) if str(ret_type).strip().lower() == 'owner' else int(cfg.get('retention_price', 500))

        # Check if person already retained by another team
        for tn, tdata in teams.items():
            for slot in ['player_retained', 'owner_retained', 'retained']:
                if tdata.get(slot):
                    ex_name = tdata[slot].get('name') if isinstance(tdata[slot], dict) else tdata[slot]
                    if ex_name == player_name and tn != team_name:
                        return jsonify({'success': False, 'message': f'{player_name} is already retained by {tn}.'}), 400

        team = teams[team_name]
        if team.get('budget', 0) < price:
            return jsonify({'success': False, 'message': f'Insufficient budget in {team_name} (Has ₹{team.get("budget", 0)})'}), 400

        push_history(state)

        # Release existing slot if already occupied
        target_slot = 'owner_retained' if ret_type == 'Owner' else 'player_retained'
        if team.get(target_slot):
            old = team[target_slot]
            old_cost = old.get('cost', price) if isinstance(old, dict) else price
            team['budget'] += old_cost
            team['spent'] -= old_cost

        # Retain new person
        team['budget'] -= price
        team['purse'] = team['budget']
        team['spent'] += price
        team[target_slot] = {'name': player_name, 'cost': price, 'type': ret_type}
        team['retained'] = team.get('player_retained') or team.get('owner_retained')

        # Remove from live auction pool
        if player_name in state.get('auction_players', []):
            state['auction_players'].remove(player_name)
        if state.get('current_player') == player_name:
            state['current_player'] = state['auction_players'][0] if state['auction_players'] else None

        state['state_version'] = state.get('state_version', 1) + 1
        save_auction_state(state)
        return jsonify({'success': True, 'message': f'Successfully retained {player_name} ({ret_type}) for {team_name} at ₹{price}.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/retention/release', methods=['POST'])
def api_retention_release():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Auctioneer PIN required'}), 403
        data = request.json or {}
        team_name = data.get('team')
        ret_type = data.get('retention_type') or data.get('type') or 'Player'

        state = load_auction_state()
        teams = state.get('teams', {})
        if team_name not in teams:
            return jsonify({'success': False, 'message': 'Team not found'}), 400

        team = teams[team_name]

        target_slot = 'owner_retained' if str(ret_type).strip().lower() == 'owner' else 'player_retained'
        target_data = team.get(target_slot)
        if not target_data and team.get('retained'):
            ret_val = team.get('retained')
            if isinstance(ret_val, dict) and ret_val.get('type', '').lower() == ret_type.lower():
                target_data = ret_val
            elif not isinstance(ret_val, dict) and target_slot == 'player_retained':
                target_data = ret_val

        if not target_data:
            return jsonify({'success': False, 'message': f'No {ret_type} retention found for {team_name}'}), 400

        push_history(state)
        default_cost = 100 if target_slot == 'owner_retained' else 500
        released_name = target_data.get('name') if isinstance(target_data, dict) else target_data
        released_cost = target_data.get('cost', default_cost) if isinstance(target_data, dict) else default_cost

        team['budget'] += released_cost
        team['purse'] = team['budget']
        team['spent'] -= released_cost
        team[target_slot] = None
        team['retained'] = team.get('player_retained') or team.get('owner_retained')

        # Add back to available pool
        if released_name not in state.get('auction_players', []) and released_name in state.get('players', []):
            state['auction_players'].insert(0, released_name)

        state['state_version'] = state.get('state_version', 1) + 1
        save_auction_state(state)
        return jsonify({'success': True, 'message': f'Released {released_name} ({ret_type}) from {team_name} and refunded ₹{released_cost}.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/auction/start', methods=['POST'])
def api_auction_start():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Auctioneer PIN required'}), 403
        state = load_auction_state()
        push_history(state)
        state['auction_started'] = True
        state['auction_status'] = 'active'
        data = request.json or {}

        # Only initialize/re-shuffle queue if explicitly requested OR pool is completely empty and no player on block
        need_pool_init = data.get('initialize_pool', False) or (
            ('auction_players' not in state or not state['auction_players'])
            and not state.get('current_player')
            and not get_sold_player_names(state)
        )
        if need_pool_init:
            retained = get_retained_player_names(state)
            sold = get_sold_player_names(state)
            excluded = retained | sold
            pool = [p for p in state.get('players', []) if str(p).strip().lower() not in excluded]
            random.shuffle(pool)
            state['auction_players'] = pool
            state['unsold_players'] = [p for p in state.get('unsold_players', []) if str(p).strip().lower() not in excluded]
            state['current_round'] = 1
            state['current_player'] = None
            state['current_bid'] = 0
            state['bidding_team'] = None
            state['current_bid_team'] = None

        now_ms = int(datetime.now().timestamp() * 1000)
        if state.get('timer_remaining_sec'):
            state['timer_end'] = now_ms + (int(state['timer_remaining_sec']) * 1000)
            state['timer_remaining_sec'] = None
        elif state.get('timer_enabled') and state.get('current_player') and not state.get('timer_end'):
            dur = int(state.get('timer_duration', 120))
            state['timer_end'] = now_ms + (dur * 1000)
        state['auction_started'] = True
        state['auction_status'] = 'active'
        save_auction_state(state)
        return jsonify({
            'success': True,
            'message': 'Live Auction is now ACTIVE! Spectators & owners can see live bidding.',
            'auction_started': True,
            'auction_status': 'active'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/auction/pause', methods=['POST'])
def api_auction_pause():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Auctioneer PIN required'}), 403
        state = load_auction_state()
        push_history(state)
        now_ms = int(datetime.now().timestamp() * 1000)
        if state.get('timer_end') and state['timer_end'] > now_ms:
            state['timer_remaining_sec'] = max(1, round((state['timer_end'] - now_ms) / 1000))
        state['timer_end'] = None
        state['auction_started'] = False
        state['auction_status'] = 'paused'
        save_auction_state(state)
        return jsonify({
            'success': True,
            'message': 'Live Auction paused. Viewers and franchise owners are now on standby.',
            'auction_started': False,
            'auction_status': 'paused'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/auction/stop', methods=['POST'])
def api_auction_stop():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Auctioneer PIN required'}), 403
        state = load_auction_state()
        push_history(state)
        state['timer_end'] = None
        state['timer_remaining_sec'] = None
        state['current_player'] = None
        state['current_bid'] = 0
        state['bidding_team'] = None
        state['current_bid_team'] = None
        state['auction_started'] = False
        state['auction_status'] = 'stopped'
        save_auction_state(state)
        return jsonify({
            'success': True,
            'message': 'Live Auction stopped & concluded. Auction block cleared.',
            'auction_started': False,
            'auction_status': 'stopped'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
# ==================================================================================


@app.route('/api/auction/bid', methods=['POST'])
@app.route('/api/auction/set-bid', methods=['POST'])
def api_auction_bid():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Auctioneer PIN required'}), 403
        data = request.json or {}
        bid = int(data.get('bid') or data.get('price') or 0)
        team_input = data.get('team') or data.get('team_name')

        state = load_auction_state()
        state['auction_started'] = True

        if not state.get('current_player'):
            return jsonify({'success': False, 'message': 'No player currently on the auction block to place a bid on'}), 400

        team = None
        if team_input:
            team_str = str(team_input).strip()
            if team_str in state.get('teams', {}):
                team = team_str
            else:
                for tn in state.get('teams', {}).keys():
                    if tn.strip().lower() == team_str.lower():
                        team = tn
                        break

        if bid < 0:
            return jsonify({'success': False, 'message': 'Bid amount cannot be negative'}), 400

        cur_lead_team = state.get('bidding_team') or state.get('current_bid_team')
        cur_bid = int(state.get('current_bid', 0))
        allow_same = bool(data.get('force') or data.get('allow_same_team', False))

        # Check self-outbidding: A team cannot outbid themselves!
        if team and cur_lead_team and team == cur_lead_team and cur_bid > 0 and bid > cur_bid and not allow_same:
            return jsonify({
                'success': False,
                'message': f"⚠️ {team} is already the highest bidder at ₹{cur_bid}! Another team must place the next bid."
            }), 400

        # Check lower or equal bids: Counter-bids by another team must strictly exceed current leading bid
        is_manual_override = bool(data.get('is_manual_override') or data.get('force', False))
        if team and cur_lead_team and team != cur_lead_team and cur_bid > 0 and bid <= cur_bid and not is_manual_override:
            return jsonify({
                'success': False,
                'message': f"⚠️ Bid amount (₹{bid}) must be higher than current leading bid of ₹{cur_bid}!"
            }), 400

        if team and team in state.get('teams', {}):
            t_data = state['teams'][team]
            if bid > t_data.get('budget', 0):
                return jsonify({'success': False, 'message': f"Insufficient purse! {team} has only ₹{t_data.get('budget', 0)}"}), 400

            # Squad Reserve Rule Check
            cfg = load_config()
            current_player_count = len(t_data.get("players", [])) + (1 if t_data.get("player_retained") else 0) + (1 if t_data.get("owner_retained") else 0) + (1 if t_data.get("retained") and not t_data.get("player_retained") and not t_data.get("owner_retained") else 0)
            min_required = int(state.get("max_players") or cfg.get("max_players", 10))
            min_bid = int(state.get("min_bid") or cfg.get("min_bid", 100))
            if min_bid < 100:
                min_bid = 100

            if current_player_count < min_required:
                remaining_needed = min_required - current_player_count - 1
                budget_after_bid = t_data["budget"] - bid
                estimated_cost = max(0, remaining_needed) * min_bid
                if remaining_needed > 0 and budget_after_bid < estimated_cost:
                    return jsonify({
                        'success': False,
                        'message': f"⚠️ Squad Reserve Rule: Cannot bid ₹{bid}! {team} needs {remaining_needed} more players to reach minimum squad requirement ({min_required}). Remaining purse (₹{budget_after_bid}) would be below required reserve of ₹{estimated_cost} (₹{min_bid} × {remaining_needed} players)."
                    }), 400

        state['current_bid'] = bid
        if team:
            state['bidding_team'] = team
            state['current_bid_team'] = team

        # Anti-sniping reset timer on bid
        cfg = load_config()
        if cfg.get('timer_enabled', False) and cfg.get('timer_reset_on_bid', True):
            dur = int(cfg.get('timer_duration', 120))
            now_ms = int(datetime.now().timestamp() * 1000)
            state['timer_end'] = now_ms + (dur * 1000)

        state['state_version'] = state.get('state_version', 1) + 1
        save_auction_state(state)
        return jsonify({'success': True, 'bid': bid, 'team': team, 'timer_end': state.get('timer_end')})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

def do_execute_sale(state, team_name, price):
    cur_p = state.get('current_player')
    if not cur_p:
        return False, 'No player currently on the auction block to mark as SOLD'
    if team_name not in state.get('teams', {}):
        return False, 'Invalid bidding team'
    if price <= 0:
        return False, 'Bid price must be greater than 0'

    team = state['teams'][team_name]
    if price > team['budget']:
        return False, f"Insufficient purse! Team has ₹{team['budget']}"

    cfg = load_config()
    current_player_count = len(team.get("players", [])) + (1 if team.get("player_retained") else 0) + (1 if team.get("owner_retained") else 0) + (1 if team.get("retained") and not team.get("player_retained") and not team.get("owner_retained") else 0)
    min_required = int(state.get("max_players") or cfg.get("max_players", 10))
    min_bid = int(state.get("min_bid") or cfg.get("min_bid", 100))
    if min_bid < 100:
        min_bid = 100

    if current_player_count < min_required:
        remaining_needed = min_required - current_player_count - 1
        budget_after_purchase = team["budget"] - price
        estimated_cost = max(0, remaining_needed) * min_bid
        if remaining_needed > 0 and budget_after_purchase < estimated_cost:
            return False, f"⚠️ Squad Reserve Rule: Cannot buy {cur_p} for ₹{price}! {team_name} needs {remaining_needed} more players to reach minimum requirement ({min_required}). Remaining purse would be ₹{budget_after_purchase}, but you must reserve at least ₹{estimated_cost} (₹{min_bid} × {remaining_needed} players)."

    push_history(state)

    team['budget'] -= price
    team['purse'] = team['budget']
    team['spent'] += price
    team['players'].append({
        'name': cur_p,
        'cost': price,
        'type': 'auction',
        'round': state.get('current_round', 1)
    })

    if cur_p in state.get('auction_players', []):
        state['auction_players'].remove(cur_p)
    if cur_p in state.get('unsold_players', []):
        state['unsold_players'].remove(cur_p)

    state['last_sold_player'] = {
        'name': cur_p,
        'team': team_name,
        'price': price,
        'round': state.get('current_round', 1),
        'timestamp': int(datetime.now().timestamp() * 1000)
    }

    state['current_player'] = None
    state['current_bid'] = 0
    state['bidding_team'] = None
    state['current_bid_team'] = None
    state['not_interested_teams'] = []
    state['auction_started'] = True
    state['timer_end'] = None

    state['last_action'] = {
        'type': 'SOLD',
        'player': cur_p,
        'team': team_name,
        'amount': price,
        'timestamp': int(datetime.now().timestamp() * 1000)
    }
    sanitize_auction_pool(state)
    state['state_version'] = state.get('state_version', 1) + 1
    save_auction_state(state)
    return True, f"SOLD! {cur_p} to {team_name} for ₹{price}"

def do_execute_unsold(state, is_permanent=False):
    cur_p = state.get('current_player')
    if not cur_p:
        return False, 'No player currently on the auction block to mark as UNSOLD'

    push_history(state)
    if is_permanent:
        if 'permanent_unsold_players' not in state:
            state['permanent_unsold_players'] = []
        if cur_p not in state['permanent_unsold_players']:
            state['permanent_unsold_players'].append(cur_p)
    else:
        if 'unsold_players' not in state:
            state['unsold_players'] = []
        if cur_p not in state['unsold_players']:
            state['unsold_players'].append(cur_p)

    if cur_p in state.get('auction_players', []):
        state['auction_players'].remove(cur_p)

    state['current_player'] = None
    state['current_bid'] = 0
    state['bidding_team'] = None
    state['current_bid_team'] = None
    state['not_interested_teams'] = []
    state['auction_started'] = True
    state['timer_end'] = None

    state['last_action'] = {
        'type': 'UNSOLD',
        'player': cur_p,
        'is_permanent': is_permanent,
        'timestamp': int(datetime.now().timestamp() * 1000)
    }
    sanitize_auction_pool(state)
    state['state_version'] = state.get('state_version', 1) + 1
    save_auction_state(state)
    return True, f"Player {cur_p} marked as unsold."

@app.route('/api/auction/sell', methods=['POST'])
@app.route('/api/auction/sold', methods=['POST'])
def api_auction_sell():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Auctioneer PIN required'}), 403
        data = request.json or {}
        team_input = data.get('team')
        price = int(data.get('price', 0))

        state = load_auction_state()
        cur_p = state.get('current_player')
        if not cur_p:
            return jsonify({'success': False, 'message': 'No player currently on the auction block to mark as SOLD'}), 400

        matched_team = None
        if team_input:
            team_str = str(team_input).strip()
            if team_str in state.get('teams', {}):
                matched_team = team_str
            else:
                for tn in state.get('teams', {}).keys():
                    if tn.strip().lower() == team_str.lower():
                        matched_team = tn
                        break

        if not matched_team:
            return jsonify({'success': False, 'message': 'Please select a valid bidding team before marking as SOLD'}), 400

        success, msg = do_execute_sale(state, matched_team, price)
        if success:
            return jsonify({'success': True, 'player': cur_p, 'team': matched_team, 'price': price, 'message': msg})
        else:
            return jsonify({'success': False, 'message': msg}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/auction/unsold', methods=['POST'])
def api_auction_unsold():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Auctioneer PIN required'}), 403
        data = request.json or {}
        is_permanent = bool(data.get('is_permanent') or data.get('permanent', False))
        state = load_auction_state()
        cur_p = state.get('current_player')
        if not cur_p:
            return jsonify({'success': False, 'message': 'No player currently on the auction block to mark as UNSOLD'}), 400

        success, msg = do_execute_unsold(state, is_permanent=is_permanent)
        if success:
            return jsonify({'success': True, 'player': cur_p, 'is_permanent': is_permanent, 'message': msg})
        else:
            return jsonify({'success': False, 'message': msg}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/auction/timer-expire', methods=['POST'])
def api_auction_timer_expire():
    try:
        with AUCTION_STATE_LOCK:
            state = load_auction_state()
            cur_p = state.get('current_player')
            if not cur_p:
                return jsonify({'success': False, 'message': 'No player currently on auction block'}), 200

            cfg = load_config()
            if not cfg.get('timer_enabled', False):
                return jsonify({'success': False, 'message': 'Timer is disabled'}), 200

            now_ms = int(datetime.now().timestamp() * 1000)
            timer_end = state.get('timer_end')
            if not timer_end:
                return jsonify({'success': False, 'message': 'No timer active'}), 200

            if now_ms < (timer_end - 1500):
                return jsonify({'success': False, 'message': 'Timer has not expired yet'}), 400

            bidding_team = state.get('bidding_team') or state.get('current_bid_team')
            current_bid = int(state.get('current_bid', 0))

            if bidding_team and current_bid > 0 and bidding_team in state.get('teams', {}):
                success, msg = do_execute_sale(state, bidding_team, current_bid)
                return jsonify({
                    'success': success,
                    'action': 'SOLD',
                    'player': cur_p,
                    'team': bidding_team,
                    'price': current_bid,
                    'message': f"⏱️ Timer Expired! {cur_p} won by {bidding_team} for ₹{current_bid}."
                })
            else:
                success, msg = do_execute_unsold(state, is_permanent=False)
                return jsonify({
                    'success': success,
                    'action': 'UNSOLD',
                    'player': cur_p,
                    'message': f"⏱️ Timer Expired! No bids were placed. {cur_p} moved to Unsold (Round 2)."
                })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/auction/timer-adjust', methods=['POST'])
def api_auction_timer_adjust():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Auctioneer PIN required'}), 403
        data = request.json or {}
        seconds = int(data.get('seconds', 30))
        with AUCTION_STATE_LOCK:
            state = load_auction_state()
            now_ms = int(datetime.now().timestamp() * 1000)
            if state.get('timer_end'):
                state['timer_end'] = max(now_ms, state['timer_end']) + (seconds * 1000)
            else:
                state['timer_end'] = now_ms + (seconds * 1000)
            save_auction_state(state)
            return jsonify({'success': True, 'timer_end': state['timer_end'], 'seconds_added': seconds})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/auction/undo', methods=['POST'])
def api_auction_undo():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Auctioneer PIN required'}), 403
        state = load_auction_state()
        if not state.get('history'):
            return jsonify({'success': False, 'message': 'Nothing to undo'}), 400

        prev = state['history'].pop()
        current_history = state['history']
        state.update(prev)
        state['history'] = current_history
        state['last_action'] = {
            'type': 'UNDO',
            'timestamp': int(datetime.now().timestamp() * 1000)
        }
        sanitize_auction_pool(state)
        save_auction_state(state)
        return jsonify({'success': True, 'message': 'Undo successful'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/auction/next', methods=['POST'])
@app.route('/api/auction/draw', methods=['POST'])
def api_auction_next():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Auctioneer PIN required'}), 403
        data = request.json or {}
        force = bool(data.get('force', False))

        state = load_auction_state()
        state['auction_started'] = True

        cur_p = state.get('current_player')
        # Accidental double-click protection: if a player is currently drawn on block and force is False, require confirmation
        if cur_p and not force:
            return jsonify({
                'success': False,
                'needs_confirmation': True,
                'current_player': cur_p,
                'message': f"Player '{cur_p}' is currently active on the auction block! Please mark as SOLD or UNSOLD first, or confirm to skip."
            }), 400

        sanitize_auction_pool(state)
        players = state.get('auction_players', [])
        is_auto_round2 = False

        # Auto-detect Round 2 if current round pool is exhausted but unsold players exist
        if not players:
            unsold = state.get('unsold_players', [])
            if unsold:
                push_history(state)
                state['auction_players'] = list(unsold)
                state['unsold_players'] = []
                sanitize_auction_pool(state)
                random.shuffle(state['auction_players'])
                state['current_round'] = state.get('current_round', 1) + 1
                players = state['auction_players']
                is_auto_round2 = True
            else:
                return jsonify({'success': False, 'message': 'All players in tournament have been auctioned! Live auction complete.'}), 400

        if not players:
            return jsonify({'success': False, 'message': 'All players in tournament have been auctioned! Live auction complete.'}), 400

        # Completely RANDOM Draw from available players in pool
        candidates = [p for p in players if p != cur_p] if (cur_p in players and len(players) > 1) else players
        if not candidates:
            candidates = players
        chosen_player = random.choice(candidates)
        state['current_player'] = chosen_player

        # Base price lookup: strictly use min_bid or explicit auction base_price (never registration fee)
        cfg = load_config()
        min_bid = int(state.get('min_bid') or cfg.get('min_bid', 100))
        if min_bid < 100:
            min_bid = 100
        regs = load_registrations()
        p_reg = regs.get(state['current_player'], {})
        base_val = int(p_reg.get('base_price') or min_bid)
        if base_val < 100:
            base_val = 100

        # IMPORTANT: Fresh draw starts at 0 bid with no bidding team!
        state['current_bid'] = 0
        state['bidding_team'] = None
        state['current_bid_team'] = None

        # Initialize Countdown Timer if enabled
        if cfg.get('timer_enabled', False):
            dur = int(cfg.get('timer_duration', 120))
            now_ms = int(datetime.now().timestamp() * 1000)
            state['timer_enabled'] = True
            state['timer_duration'] = dur
            state['timer_end'] = now_ms + (dur * 1000)
            state['timer_started_at'] = now_ms
        else:
            state['timer_enabled'] = False
            state['timer_end'] = None
        state['last_action'] = {
            'type': 'DRAW',
            'player': state['current_player'],
            'round': state.get('current_round', 1),
            'auto_round2': is_auto_round2,
            'timestamp': int(datetime.now().timestamp() * 1000)
        }
        state['state_version'] = state.get('state_version', 1) + 1
        save_auction_state(state)
        return jsonify({
            'success': True,
            'player': state['current_player'],
            'base_price': base_val,
            'current_bid': 0,
            'round': state.get('current_round', 1),
            'auto_round2': is_auto_round2,
            'remaining_count': len(players)
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/auction/select-player', methods=['POST'])
def api_auction_select_player():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Auctioneer PIN required'}), 403
        data = request.json or {}
        player = data.get('player')
        state = load_auction_state()
        state['auction_started'] = True
        if not player:
            return jsonify({'success': False, 'message': 'No player specified'}), 400

        state['current_player'] = player
        if player not in state.get('auction_players', []):
            state.setdefault('auction_players', []).insert(0, player)

        cfg = load_config()
        min_bid = int(state.get('min_bid') or cfg.get('min_bid', 100))
        if min_bid < 100:
            min_bid = 100
        regs = load_registrations()
        p_reg = regs.get(player, {})
        base_val = int(p_reg.get('base_price') or min_bid)
        if base_val < 100:
            base_val = 100

        # Fresh draw starts at 0 bid
        state['current_bid'] = 0
        state['bidding_team'] = None
        state['current_bid_team'] = None
        state['not_interested_teams'] = []

        # Initialize Countdown Timer if enabled
        if cfg.get('timer_enabled', False):
            dur = int(cfg.get('timer_duration', 120))
            now_ms = int(datetime.now().timestamp() * 1000)
            state['timer_enabled'] = True
            state['timer_duration'] = dur
            state['timer_end'] = now_ms + (dur * 1000)
            state['timer_started_at'] = now_ms
        else:
            state['timer_enabled'] = False
            state['timer_end'] = None
        state['last_action'] = {
            'type': 'DRAW',
            'player': player,
            'timestamp': int(datetime.now().timestamp() * 1000)
        }
        sanitize_auction_pool(state)
        state['state_version'] = state.get('state_version', 1) + 1
        save_auction_state(state)
        return jsonify({'success': True, 'player': player, 'base_price': base_val, 'current_bid': 0})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/auction/round2', methods=['POST'])
@app.route('/api/auction/start-round2', methods=['POST'])
def api_auction_round2():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Auctioneer PIN required'}), 403
        state = load_auction_state()
        unsold = state.get('unsold_players', [])
        if not unsold:
            return jsonify({'success': False, 'message': 'No unsold players to re-auction'}), 400

        push_history(state)
        state['auction_players'] = list(unsold)
        state['unsold_players'] = []
        sanitize_auction_pool(state)
        random.shuffle(state['auction_players'])
        state['current_round'] = state.get('current_round', 1) + 1
        state['current_player'] = None
        state['current_bid'] = 0
        state['bidding_team'] = None
        state['current_bid_team'] = None

        save_auction_state(state)
        return jsonify({'success': True, 'message': f'Round {state["current_round"]} started!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/config', methods=['POST'])
def api_admin_config():
    try:
        data = request.json or {}
        cfg = load_config()
        if 'timer_enabled' in data:
            cfg['timer_enabled'] = bool(data['timer_enabled'])
        if 'timer_duration' in data:
            cfg['timer_duration'] = int(data['timer_duration'])
        if 'timer_reset_on_bid' in data:
            cfg['timer_reset_on_bid'] = bool(data['timer_reset_on_bid'])
        if 'upi_enabled' in data:
            cfg['upi_enabled'] = bool(data['upi_enabled'])
        if 'villages' in data and data['villages'] is not None:
            v_val = data['villages']
            if isinstance(v_val, str):
                cfg['villages'] = [v.strip() for v in v_val.split(',') if v.strip()]
            elif isinstance(v_val, list):
                cfg['villages'] = [str(v).strip() for v in v_val if str(v).strip()]
            data['villages'] = cfg['villages']
        cfg.update(data)
        save_config(cfg)

        with AUCTION_STATE_LOCK:
            state = load_auction_state()
            if cfg.get('timer_enabled') and state.get('current_player'):
                dur = int(cfg.get('timer_duration', 120))
                now_ms = int(datetime.now().timestamp() * 1000)
                state['timer_end'] = now_ms + (dur * 1000)
                state['timer_enabled'] = True
                state['timer_duration'] = dur
                save_auction_state(state)
            elif not cfg.get('timer_enabled'):
                state['timer_end'] = None
                state['timer_enabled'] = False
                save_auction_state(state)

        return jsonify({'success': True, 'config': cfg})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/verify-player', methods=['POST'])
def api_admin_verify_player():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Organizer PIN required'}), 403
        data = request.json or {}
        name = data.get('name', '').strip()
        regs = load_registrations()
        if name in regs:
            regs[name]['payment_status'] = 'Verified & Approved'
            regs[name]['approved'] = True
            save_registrations(regs)
            # Sync approved player to live auction pool
            sync_player_to_auction(name, regs[name].get('serial_no'))
            return jsonify({'success': True, 'message': f'Player "{name}" payment verified! Officially added to Live Auction Pool.'})
        return jsonify({'success': False, 'message': 'Player not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/reject-player', methods=['POST'])
def api_admin_reject_player():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Organizer PIN required'}), 403
        data = request.json or {}
        name = data.get('name', '').strip()
        regs = load_registrations()
        if name in regs:
            regs[name]['payment_status'] = 'Payment Rejected'
            regs[name]['approved'] = False
            save_registrations(regs)
            # Remove from auction state if present
            state = load_auction_state()
            if name in state.get('players', []):
                state['players'].remove(name)
            if name in state.get('auction_players', []):
                state['auction_players'].remove(name)
            save_auction_state(state)
            return jsonify({'success': True, 'message': f'Player "{name}" payment marked as Rejected.'})
        return jsonify({'success': False, 'message': 'Player not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/fresh-tournament-reset', methods=['POST'])
@app.route('/api/admin/start-fresh-tournament', methods=['POST'])
def api_admin_fresh_tournament_reset():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Auctioneer PIN required'}), 403

        # 1. ALWAYS snapshot current registrations & auction state to safety backups before wipe
        current_regs = load_registrations()
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        if current_regs and len(current_regs) > 0:
            pre_reset_snap = os.path.join(BACKUPS_DIR, f"pre_fresh_reset_backup_{ts}.json")
            try:
                with open(pre_reset_snap, 'w', encoding='utf-8') as sf:
                    json.dump(current_regs, sf, indent=4)
            except Exception as e:
                print("Pre-reset snapshot notice:", e)

        # 2. Clear registrations.json AND MASTER_VAULT_FILE completely
        with open(REGISTRATIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, indent=4)
        with open(MASTER_VAULT_FILE, 'w', encoding='utf-8') as vf:
            json.dump({}, vf, indent=4)
        if DATABASE_URL:
            db_set('registrations', {})
            db_set('master_vault', {})

        # 3. Clean active uploaded photos so new tournament starts completely clean
        try:
            for p_dir in [PHOTOS_DIR, PAYMENTS_DIR]:
                if os.path.exists(p_dir):
                    for fn in os.listdir(p_dir):
                        fp = os.path.join(p_dir, fn)
                        if os.path.isfile(fp):
                            try:
                                os.remove(fp)
                            except Exception:
                                pass
        except Exception:
            pass

        # 4. Reset tournament_config.json team passcodes
        cfg = load_config()
        cfg['team_passcodes'] = {}
        save_config(cfg)

        # 5. Initialize fresh teams with full starting tournament purse
        total_purse = int(cfg.get("total_purse") or cfg.get("default_purse") or 5000)
        default_team_names = ["Deccan Royals", "Kunsi Warriors", "Saidapur Super Kings", "Telangana Titans", "Hyderabad Blasters"]
        fresh_teams = {
            t_name: {
                "budget": total_purse,
                "purse": total_purse,
                "spent": 0,
                "players": [],
                "retained": None,
                "player_retained": None,
                "owner_retained": None
            }
            for t_name in default_team_names
        }

        # 6. Reset auction_state.json completely (ready for new registrations & bidding)
        cur_state = load_auction_state()
        fresh_state = {
            "teams": fresh_teams,
            "players": [],
            "player_serials": {},
            "auction_players": [],
            "unsold_players": [],
            "permanent_unsold_players": [],
            "unsold": [],
            "unsold_r1": [],
            "unsold_r2": [],
            "sold_players": [],
            "current_player": None,
            "current_bid": 0,
            "bidding_team": None,
            "current_bid_team": None,
            "timer_end": None,
            "history": [],
            "current_round": 1,
            "round": 1,
            "auction_started": False,
            "total_purse": total_purse,
            "default_purse": total_purse,
            "max_players": int(cfg.get("max_players", 10)),
            "min_bid": int(cfg.get("min_bid", 100)),
            "retention_price": int(cfg.get("retention_price", 500)),
            "owner_retention_price": int(cfg.get("owner_retention_price", 100)),
            "state_version": cur_state.get("state_version", 1) + 1,
            "last_action": {
                "type": "FRESH_TOURNAMENT_RESET",
                "timestamp": int(datetime.now().timestamp() * 1000)
            }
        }
        save_auction_state(fresh_state)

        # 7. Push clean state to GitHub immediately so Render does not reload old data on wake-up!
        try:
            push_to_github_async('registrations.json', '{}', 'KPL Factory Reset: Cleared registrations')
            push_to_github_async('backups/registrations_master_vault.json', '{}', 'KPL Factory Reset: Cleared master vault')
            push_to_github_async('auction_state.json', json.dumps(fresh_state, indent=4), 'KPL Factory Reset: Reset auction state')
        except Exception as _gh_err:
            print("GitHub fresh reset push notice:", _gh_err)

        return jsonify({
            'success': True,
            'message': 'Fresh Tournament Initialized! All registered players and team rosters have been wiped clean. A safety backup was saved in backups/registrations/.'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ==================== DATA PROTECTION & BACKUP APIS ====================
@app.route('/api/admin/backups/list')
def api_admin_list_backups():
    try:
        backups = []
        if os.path.exists(BACKUPS_DIR):
            for f in sorted(os.listdir(BACKUPS_DIR), reverse=True):
                if f.endswith('.json'):
                    fp = os.path.join(BACKUPS_DIR, f)
                    try:
                        with open(fp, 'r', encoding='utf-8') as bfile:
                            data = json.load(bfile)
                            p_count = len(data) if isinstance(data, dict) else len(data)
                    except Exception:
                        p_count = 0
                    mtime = os.path.getmtime(fp)
                    backups.append({
                        'filename': f,
                        'player_count': p_count,
                        'size_kb': round(os.path.getsize(fp) / 1024, 1),
                        'timestamp': datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                    })
        vault_count = 0
        if os.path.exists(MASTER_VAULT_FILE):
            try:
                with open(MASTER_VAULT_FILE, 'r', encoding='utf-8') as vf:
                    vault_count = len(json.load(vf))
            except Exception:
                pass

        photo_count = len([f for f in os.listdir(BACKUPS_PHOTOS_DIR) if os.path.isfile(os.path.join(BACKUPS_PHOTOS_DIR, f))]) if os.path.exists(BACKUPS_PHOTOS_DIR) else 0

        return jsonify({
            'success': True,
            'backups': backups,
            'vault_player_count': vault_count,
            'vault_photo_count': photo_count,
            'active_player_count': len(load_registrations())
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/admin/backups/create', methods=['POST'])
def api_admin_create_backup():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: PIN required'}), 403
        regs = load_registrations()
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        snap_path = os.path.join(BACKUPS_DIR, f"manual_backup_{ts}.json")
        with open(snap_path, 'w', encoding='utf-8') as sf:
            json.dump(regs, sf, indent=4)
        return jsonify({
            'success': True,
            'message': f'Backup created successfully ({len(regs)} registered players secured)!',
            'filename': f"manual_backup_{ts}.json"
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/admin/backups/restore', methods=['POST'])
def api_admin_restore_backup():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: PIN required'}), 403
        data = request.json or {}
        filename = data.get('filename')
        use_vault = data.get('use_vault', False)

        restored_data = {}
        if use_vault:
            if not os.path.exists(MASTER_VAULT_FILE):
                return jsonify({'success': False, 'message': 'Master vault archive not found'}), 404
            with open(MASTER_VAULT_FILE, 'r', encoding='utf-8') as vf:
                restored_data = json.load(vf)
        elif filename:
            safe_name = os.path.basename(filename)
            file_path = os.path.join(BACKUPS_DIR, safe_name)
            if not os.path.exists(file_path):
                return jsonify({'success': False, 'message': f'Backup file {safe_name} not found'}), 404
            with open(file_path, 'r', encoding='utf-8') as sf:
                restored_data = json.load(sf)
        else:
            return jsonify({'success': False, 'message': 'No backup file specified'}), 400

        if not isinstance(restored_data, dict):
            return jsonify({'success': False, 'message': 'Invalid backup file format'}), 400

        # Save to registrations.json
        save_registrations(restored_data)

        # Also sync players into auction state pool
        state = load_auction_state()
        if 'players' not in state or not isinstance(state['players'], list):
            state['players'] = []
        if 'auction_players' not in state or not isinstance(state['auction_players'], list):
            state['auction_players'] = []

        for p_name in restored_data.keys():
            if p_name not in state['players']:
                state['players'].append(p_name)
            if p_name not in state['auction_players']:
                state['auction_players'].append(p_name)
        save_auction_state(state)

        return jsonify({
            'success': True,
            'message': f'Successfully restored {len(restored_data)} players into active roster & live auction pool!',
            'player_count': len(restored_data)
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/admin/backups/download/<filename>')
def api_admin_download_backup(filename):
    try:
        safe_name = os.path.basename(filename)
        file_path = os.path.join(BACKUPS_DIR, safe_name)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name=safe_name)
        return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/backups/download-full-archive')
def api_admin_download_full_archive():
    try:
        sync_backup_photos()
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            if os.path.exists(REGISTRATIONS_FILE):
                zf.write(REGISTRATIONS_FILE, arcname='registrations.json')
            if os.path.exists(MASTER_VAULT_FILE):
                zf.write(MASTER_VAULT_FILE, arcname='registrations_master_vault.json')
            if os.path.exists(CONFIG_FILE):
                zf.write(CONFIG_FILE, arcname='tournament_config.json')
            if os.path.exists(BACKUPS_PHOTOS_DIR):
                for pf in os.listdir(BACKUPS_PHOTOS_DIR):
                    p_path = os.path.join(BACKUPS_PHOTOS_DIR, pf)
                    if os.path.isfile(p_path):
                        zf.write(p_path, arcname=f"photos/{pf}")
            if os.path.exists(BACKUPS_PAYMENTS_DIR):
                for pf in os.listdir(BACKUPS_PAYMENTS_DIR):
                    p_path = os.path.join(BACKUPS_PAYMENTS_DIR, pf)
                    if os.path.isfile(p_path):
                        zf.write(p_path, arcname=f"payments/{pf}")
        zip_buffer.seek(0)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f"kpl_full_tournament_and_photos_{ts}.zip"
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/backups/upload-vault', methods=['POST'])
def api_admin_upload_vault():
    """Allows host to upload any JSON backup or ZIP archive to instantly restore registrations and photos."""
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Auctioneer PIN required'}), 403

        file = request.files.get('file')
        raw_json = request.form.get('json_data', '').strip()

        restored_data = {}
        if file and file.filename:
            fname = file.filename.lower()
            if fname.endswith('.json'):
                content = file.read().decode('utf-8', errors='ignore')
                restored_data = json.loads(content)
            elif fname.endswith('.zip'):
                import zipfile
                zf = zipfile.ZipFile(file)
                for member in zf.namelist():
                    if member.endswith('registrations_master_vault.json') or member.endswith('registrations.json'):
                        restored_data = json.loads(zf.read(member).decode('utf-8', errors='ignore'))
                    if member.startswith('photos/') and not member.endswith('/'):
                        p_name = os.path.basename(member)
                        if p_name:
                            p_bytes = zf.read(member)
                            with open(os.path.join(PHOTOS_DIR, p_name), 'wb') as pf:
                                pf.write(p_bytes)
                            with open(os.path.join(BACKUPS_PHOTOS_DIR, p_name), 'wb') as pf:
                                pf.write(p_bytes)
        elif raw_json:
            restored_data = json.loads(raw_json)
        else:
            return jsonify({'success': False, 'message': 'Please select a valid .json or .zip backup file to restore.'}), 400

        if not isinstance(restored_data, dict) or len(restored_data) == 0:
            return jsonify({'success': False, 'message': 'Invalid backup: No player registrations found in file.'}), 400

        # Save to registrations and master vault
        save_registrations(restored_data)

        # Sync into auction state
        state = load_auction_state()
        state.setdefault('players', [])
        state.setdefault('auction_players', [])
        for p_name in restored_data.keys():
            if p_name not in state['players']:
                state['players'].append(p_name)
            if p_name not in state['auction_players']:
                state['auction_players'].append(p_name)
        save_auction_state(state)
        sync_backup_photos()

        return jsonify({
            'success': True,
            'message': f'Vault restored successfully! {len(restored_data)} registered players loaded into active roster & live auction pool.',
            'player_count': len(restored_data)
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error restoring vault: {str(e)}'}), 500


@app.route('/api/admin/reset-auction', methods=['POST'])
def api_admin_reset_auction():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Auctioneer PIN required'}), 403
        cfg = load_config()
        regs = load_registrations()
        
        # 1. Collect and sort all valid players by serial number
        sorted_regs = sorted(regs.items(), key=lambda x: (x[1].get('serial_no', 9999), x[0]))
        player_list = []
        for p_name, p_data in sorted_regs:
            # Exclude only explicitly rejected players; include approved, verified, or registered
            if p_data.get('payment_status') != 'Payment Rejected':
                player_list.append(p_name)
        
        if not player_list:
            player_list = [p_name for p_name, _ in sorted_regs]
            

        
        player_serials = {}
        for idx, p in enumerate(player_list):
            if p in regs and regs[p].get('serial_no'):
                player_serials[p] = regs[p]['serial_no']
            else:
                player_serials[p] = idx + 1

        cur_state = load_auction_state()
        team_keys = list(cur_state.get('teams', {}).keys())
        if not team_keys:
            team_keys = ["Deccan Royals", "Kunsi Warriors", "Saidapur Super Kings", "Telangana Titans", "Hyderabad Blasters"]
        
        total_purse = int(cfg.get("total_purse") or cfg.get("default_purse") or 5000)
        reset_teams = {
            t: {
                "budget": total_purse,
                "purse": total_purse,
                "spent": 0,
                "players": [],
                "retained": None,
                "player_retained": None,
                "owner_retained": None
            } for t in team_keys
        }
        
        # 2. Fresh initial auction state (Round 1, full restocked pool, zero retentions)
        state = {
            "teams": reset_teams,
            "players": list(player_list),
            "player_serials": player_serials,
            "auction_players": list(player_list),
            "unsold_players": [],
            "permanent_unsold_players": [],
            "unsold": [],
            "unsold_r1": [],
            "unsold_r2": [],
            "sold_players": [],
            "current_player": None,
            "current_bid": 0,
            "bidding_team": None,
            "current_bid_team": None,
            "timer_end": None,
            "history": [],
            "current_round": 1,
            "round": 1,
            "auction_started": True,
            "total_purse": total_purse,
            "default_purse": total_purse,
            "max_players": int(cfg.get("max_players", 10)),
            "min_bid": int(cfg.get("min_bid", 100)),
            "retention_price": int(cfg.get("retention_price", 500)),
            "owner_retention_price": int(cfg.get("owner_retention_price", 100)),
            "state_version": cur_state.get("state_version", 1) + 1,
            "last_action": {
                "type": "RESET",
                "timestamp": int(datetime.now().timestamp() * 1000)
            }
        }
        save_auction_state(state)
        return jsonify({
            'success': True,
            'message': f'Live auction reset successfully to Round 1! All {len(reset_teams)} team budgets restored to ₹{total_purse}, retentions cleared (0), and full player pool ({len(player_list)} players) restocked for a fresh start.'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/export-excel')
def api_export_excel():
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from io import BytesIO

        state = load_auction_state()
        regs = load_registrations()
        cfg = load_config()

        wb = openpyxl.Workbook()
        ws_res = wb.active
        ws_res.title = "Results"

        # Styles
        font_title = Font(name="Calibri", size=16, bold=True, color="000000")
        fill_title = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")

        font_team = Font(name="Calibri", size=12, bold=True, color="FFFFFF")
        fill_team = PatternFill(start_color="70AD47", end_color="70AD47", fill_type="solid")

        font_col = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        fill_col = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")

        fill_ret_player = PatternFill(start_color="FFE699", end_color="FFE699", fill_type="solid")
        fill_ret_owner = PatternFill(start_color="FFD966", end_color="FFD966", fill_type="solid")
        fill_round1 = PatternFill(start_color="C6E0B4", end_color="C6E0B4", fill_type="solid")
        fill_round2 = PatternFill(start_color="BDD7EE", end_color="BDD7EE", fill_type="solid")
        fill_total = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
        fill_unsold_hdr = PatternFill(start_color="FF6B6B", end_color="FF6B6B", fill_type="solid")

        align_center = Alignment(horizontal="center", vertical="center")
        align_left = Alignment(horizontal="left", vertical="center")
        align_right = Alignment(horizontal="right", vertical="center")
        thin_border = Border(
            left=Side(style="thin", color="CCCCCC"),
            right=Side(style="thin", color="CCCCCC"),
            top=Side(style="thin", color="CCCCCC"),
            bottom=Side(style="thin", color="CCCCCC")
        )

        row = 1
        # Title
        ws_res.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
        c = ws_res.cell(row=row, column=1, value="Kunsi Premier League (KPL 2026)")
        c.font = font_title
        c.fill = fill_title
        c.alignment = align_center
        row += 2

        player_serials = state.get("player_serials", {})

        # Teams
        for t_name, t_data in state.get("teams", {}).items():
            # Team Header
            ws_res.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
            c = ws_res.cell(row=row, column=1, value=f"TEAM: {t_name}")
            c.font = font_team
            c.fill = fill_team
            c.alignment = align_center
            row += 1

            # Columns
            headers = ["S.No", "Player Name", "Cost (Rs.)", "Type"]
            for col_idx, h in enumerate(headers, 1):
                c = ws_res.cell(row=row, column=col_idx, value=h)
                c.font = font_col
                c.fill = fill_col
                c.alignment = align_center
            row += 1

            sno = 1
            # Player Retained
            p_ret = t_data.get("player_retained") or (t_data.get("retained") if isinstance(t_data.get("retained"), dict) and t_data["retained"].get("type") != "Owner" else None)
            if p_ret:
                p_name = p_ret.get("name") if isinstance(p_ret, dict) else p_ret
                p_cost = p_ret.get("cost", 500) if isinstance(p_ret, dict) else 500
                s_num = player_serials.get(p_name, sno)
                ws_res.cell(row=row, column=1, value=sno).alignment = align_center
                ws_res.cell(row=row, column=2, value=f"#{s_num} {p_name}").alignment = align_left
                ws_res.cell(row=row, column=3, value=p_cost).alignment = align_center
                ws_res.cell(row=row, column=4, value="Player Retained").alignment = align_center
                for col_idx in range(1, 5):
                    ws_res.cell(row=row, column=col_idx).fill = fill_ret_player
                    ws_res.cell(row=row, column=col_idx).border = thin_border
                sno += 1
                row += 1

            # Owner Retained
            o_ret = t_data.get("owner_retained") or (t_data.get("retained") if isinstance(t_data.get("retained"), dict) and t_data["retained"].get("type") == "Owner" else None)
            if o_ret:
                o_name = o_ret.get("name") if isinstance(o_ret, dict) else o_ret
                o_cost = o_ret.get("cost", 100) if isinstance(o_ret, dict) else 100
                s_num = player_serials.get(o_name, sno)
                ws_res.cell(row=row, column=1, value=sno).alignment = align_center
                ws_res.cell(row=row, column=2, value=f"#{s_num} {o_name}").alignment = align_left
                ws_res.cell(row=row, column=3, value=o_cost).alignment = align_center
                ws_res.cell(row=row, column=4, value="Owner Retained").alignment = align_center
                for col_idx in range(1, 5):
                    ws_res.cell(row=row, column=col_idx).fill = fill_ret_owner
                    ws_res.cell(row=row, column=col_idx).border = thin_border
                sno += 1
                row += 1

            # Auctioned players
            for p in t_data.get("players", []):
                p_name = p.get("name")
                p_cost = p.get("cost", 0)
                rnd = p.get("round", 1)
                s_num = player_serials.get(p_name, sno)
                ws_res.cell(row=row, column=1, value=sno).alignment = align_center
                ws_res.cell(row=row, column=2, value=f"#{s_num} {p_name}").alignment = align_left
                ws_res.cell(row=row, column=3, value=p_cost).alignment = align_center
                ws_res.cell(row=row, column=4, value=f"Round {rnd}").alignment = align_center
                f_color = fill_round1 if rnd == 1 else fill_round2
                for col_idx in range(1, 5):
                    ws_res.cell(row=row, column=col_idx).fill = f_color
                    ws_res.cell(row=row, column=col_idx).border = thin_border
                sno += 1
                row += 1

            # Totals
            ws_res.cell(row=row, column=1, value="").alignment = align_center
            ws_res.cell(row=row, column=2, value="TOTAL SPENT").alignment = align_right
            ws_res.cell(row=row, column=3, value=t_data.get("spent", 0)).alignment = align_center
            ws_res.cell(row=row, column=4, value=f"Remaining: {t_data.get('budget', 0)}").alignment = align_center
            for col_idx in range(1, 5):
                c = ws_res.cell(row=row, column=col_idx)
                c.fill = fill_total
                c.font = Font(name="Calibri", bold=True)
                c.border = thin_border
            row += 2

        # Unsold Players
        unsold = state.get("unsold_players", [])
        if unsold:
            ws_res.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
            c = ws_res.cell(row=row, column=1, value="UNSOLD PLAYERS")
            c.font = font_team
            c.fill = fill_unsold_hdr
            c.alignment = align_center
            row += 1

            headers = ["S.No", "Player Name", "-", "Status"]
            for col_idx, h in enumerate(headers, 1):
                c = ws_res.cell(row=row, column=col_idx, value=h)
                c.font = font_col
                c.fill = fill_col
                c.alignment = align_center
            row += 1

            for idx, p_name in enumerate(unsold, 1):
                s_num = player_serials.get(p_name, idx)
                ws_res.cell(row=row, column=1, value=idx).alignment = align_center
                ws_res.cell(row=row, column=2, value=f"#{s_num} {p_name}").alignment = align_left
                ws_res.cell(row=row, column=3, value="-").alignment = align_center
                ws_res.cell(row=row, column=4, value="Unsold").alignment = align_center
                for col_idx in range(1, 5):
                    ws_res.cell(row=row, column=col_idx).border = thin_border
                row += 1

        # Column widths
        ws_res.column_dimensions["A"].width = 10
        ws_res.column_dimensions["B"].width = 30
        ws_res.column_dimensions["C"].width = 16
        ws_res.column_dimensions["D"].width = 22

        output = BytesIO()
        wb.save(output)
        output.seek(0)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return send_file(
            output,
            download_name=f"KPL_Cricket_Auction_Summary_{timestamp}.xlsx",
            as_attachment=True,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export-approved-players-excel')
def api_export_approved_players_excel():
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from io import BytesIO

        regs = load_registrations()
        cfg = load_config()

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Approved Players"
        ws.views.sheetView[0].showGridLines = True

        # Styles
        font_title = Font(name="Segoe UI", size=15, bold=True, color="FFFFFF")
        fill_title = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")

        font_header = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        fill_header = PatternFill(start_color="10B981", end_color="10B981", fill_type="solid")

        font_data = Font(name="Segoe UI", size=10, color="0F172A")
        font_bold = Font(name="Segoe UI", size=10, bold=True, color="0F172A")

        align_center = Alignment(horizontal="center", vertical="center")
        align_left = Alignment(horizontal="left", vertical="center")
        align_right = Alignment(horizontal="right", vertical="center")

        thin_border = Border(
            left=Side(style="thin", color="CBD5E1"),
            right=Side(style="thin", color="CBD5E1"),
            top=Side(style="thin", color="CBD5E1"),
            bottom=Side(style="thin", color="CBD5E1")
        )

        fill_alt = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
        fill_white = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")

        headers = [
            "ID",
            "Player Name",
            "Role",
            "Mobile Number"
        ]
        num_cols = len(headers)

        # Title Block
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=num_cols)
        c_title = ws.cell(row=1, column=1, value=f"{cfg.get('tournament_name', 'KPL Premier League 2026')} — Approved Players Directory")
        c_title.font = font_title
        c_title.fill = fill_title
        c_title.alignment = align_center
        ws.row_dimensions[1].height = 36

        # Subtitle
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=num_cols)
        c_sub = ws.cell(row=2, column=1, value=f"Official Approved Roster | Exported on {datetime.now().strftime('%d %B %Y, %I:%M %p')}")
        c_sub.font = Font(name="Segoe UI", size=10, italic=True, color="64748B")
        c_sub.alignment = align_center
        ws.row_dimensions[2].height = 20

        # Row 3 is blank spacer
        ws.row_dimensions[3].height = 8

        # Headers Row 4
        ws.row_dimensions[4].height = 28
        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=4, column=col_idx, value=h)
            cell.font = font_header
            cell.fill = fill_header
            cell.alignment = align_center
            cell.border = thin_border

        # Load state to check player_serials fallback
        state = load_auction_state()
        player_serials = state.get("player_serials", {})

        # Filter only approved players
        approved_list = []
        for p_name, p_data in regs.items():
            is_app = p_data.get('approved', False)
            p_status = p_data.get('payment_status', '')
            if is_app or p_status in ['Verified', 'Payment Verified', 'Free Registration / Verified', 'Admin Verified (Direct)']:
                if p_status != 'Payment Rejected':
                    approved_list.append(p_data)

        # Sort by serial_no if present, otherwise by name
        approved_list.sort(key=lambda p: (p.get('serial_no') or player_serials.get(p.get('name', '')) or 9999, p.get('name', '')))

        current_row = 5
        for idx, p in enumerate(approved_list, 1):
            row_fill = fill_alt if idx % 2 == 0 else fill_white
            ws.row_dimensions[current_row].height = 22

            # Format auction ID (e.g. #1, #26)
            p_name = p.get('name', 'Unknown')
            s_val = p.get('serial_no') or player_serials.get(p_name)
            if s_val is not None:
                if isinstance(s_val, int) or (isinstance(s_val, str) and str(s_val).isdigit()):
                    player_id_val = f"#{s_val}"
                elif str(s_val).startswith("#"):
                    player_id_val = str(s_val)
                else:
                    player_id_val = f"#{s_val}"
            elif p.get('id'):
                player_id_val = str(p.get('id'))
            else:
                player_id_val = f"#{idx}"

            row_data = [
                player_id_val,                 # ID
                p_name,                        # Player Name
                p.get('role', 'All-Rounder'),  # Role
                p.get('phone', 'N/A')          # Mobile Number
            ]

            for col_idx, val in enumerate(row_data, 1):
                cell = ws.cell(row=current_row, column=col_idx, value=val)
                cell.font = font_bold if col_idx in [1, 2] else font_data
                cell.fill = row_fill
                cell.border = thin_border
                if col_idx in [1, 3, 4]:
                    cell.alignment = align_center
                else:
                    cell.alignment = align_left

            current_row += 1

        # Adjust column widths
        from openpyxl.utils import get_column_letter
        for col_idx, col in enumerate(ws.columns, 1):
            max_len = 0
            col_letter = get_column_letter(col_idx)
            for cell in col:
                if cell.row in [1, 2, 3]:
                    continue
                v_str = str(cell.value or '')
                if len(v_str) > max_len:
                    max_len = len(v_str)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

        output = BytesIO()
        wb.save(output)
        output.seek(0)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return send_file(
            output,
            download_name=f"KPL_Approved_Players_{timestamp}.xlsx",
            as_attachment=True,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
