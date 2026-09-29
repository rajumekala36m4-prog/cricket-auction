
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
import json
import copy
import random
import uuid
from datetime import datetime
from io import BytesIO

# Fix Windows console UTF-8 output
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from werkzeug.utils import secure_filename
import pandas as pd

# Directory setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
PHOTOS_DIR = os.path.join(STATIC_DIR, 'uploads', 'photos')
PAYMENTS_DIR = os.path.join(STATIC_DIR, 'uploads', 'payments')

os.makedirs(PHOTOS_DIR, exist_ok=True)
os.makedirs(PAYMENTS_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(BASE_DIR, 'tournament_config.json')
REGISTRATIONS_FILE = os.path.join(BASE_DIR, 'registrations.json')
AUCTION_STATE_FILE = os.path.join(BASE_DIR, 'auction_state.json')

app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=STATIC_DIR)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload

# ----------------- CONFIG HELPERS -----------------
def load_config():
    default_config = {
        "tournament_name": "Saidapur Premier League (SPL 2026)",
        "upi_id": "saidapur.cricket@upi",
        "payee_name": "Saidapur Cricket Committee",
        "registration_fee": 200,
        "default_purse": 5000,
        "min_bid": 50,
        "retention_price": 500,
        "max_players": 15,
        "currency_symbol": "₹"
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                default_config.update(cfg)
        except Exception as e:
            print("Error loading config:", e)
    return default_config

def save_config(cfg):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=4)

# ----------------- REGISTRATIONS HELPERS -----------------
def load_registrations():
    if os.path.exists(REGISTRATIONS_FILE):
        try:
            with open(REGISTRATIONS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print("Error loading registrations:", e)
    return {}

def save_registrations(regs):
    with open(REGISTRATIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(regs, f, indent=4)

# ----------------- AUCTION STATE HELPERS -----------------
def load_auction_state():
    if os.path.exists(AUCTION_STATE_FILE):
        try:
            with open(AUCTION_STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print("Error loading auction state:", e)
    
    # Default initial state
    cfg = load_config()
    regs = load_registrations()
    
    player_list = list(regs.keys())
    if not player_list:
        player_list = [
            "M. Raju Anna", "Sunil Anna", "M. Gani", "B. Vannu", "E. Prabhu", "K. Raghu (Putta)",
            "S. Ravi", "P. Sai", "M. Srinu", "B. Nani", "K. Kishore", "T. Mahesh",
            "G. Vamsi", "Ch. Vasu", "A. Krishna", "L. Suresh", "K. Prasad", "P. Kumar"
        ]

    state = {
        "teams": {
            "Team A": {"budget": cfg["default_purse"], "spent": 0, "players": [], "retained": None},
            "Team B": {"budget": cfg["default_purse"], "spent": 0, "players": [], "retained": None},
            "Team C": {"budget": cfg["default_purse"], "spent": 0, "players": [], "retained": None},
            "Team D": {"budget": cfg["default_purse"], "spent": 0, "players": [], "retained": None}
        },
        "players": player_list,
        "player_serials": {p: i + 1 for i, p in enumerate(player_list)},
        "auction_players": list(player_list),
        "unsold_players": [],
        "current_player": player_list[0] if player_list else None,
        "history": [],
        "current_round": 1,
        "total_purse": cfg["default_purse"],
        "max_players": cfg["max_players"],
        "min_bid": cfg["min_bid"],
        "retention_price": cfg["retention_price"]
    }
    save_auction_state(state)
    return state

def save_auction_state(state):
    with open(AUCTION_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=4)

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
        reg_fee=cfg["registration_fee"]
    )

@app.route('/register')
def register():
    cfg = load_config()
    return render_template(
        'register.html',
        active_page='register',
        tournament_name=cfg["tournament_name"],
        upi_id=cfg["upi_id"],
        payee_name=cfg["payee_name"],
        reg_fee=cfg["registration_fee"]
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
    is_viewer = request.args.get('viewer', 'false').lower() == 'true'
    return render_template(
        'auction_live.html',
        active_page='auction',
        tournament_name=cfg["tournament_name"],
        viewer_mode=is_viewer
    )

@app.route('/view')
def auction_view():
    cfg = load_config()
    return render_template(
        'auction_live.html',
        active_page='auction',
        tournament_name=cfg["tournament_name"],
        viewer_mode=True
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
    return render_template(
        'admin.html',
        active_page='admin',
        tournament_name=cfg["tournament_name"],
        config=cfg,
        registrations=regs,
        teams=state.get("teams", {})
    )

# ----------------- APIS -----------------

@app.route('/api/register', methods=['POST'])
def api_register():
    try:
        cfg = load_config()
        regs = load_registrations()

        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        role = request.form.get('role', 'All-Rounder')
        batting_style = request.form.get('batting_style', 'Right Hand Bat')
        bowling_style = request.form.get('bowling_style', 'None')
        payment_method = request.form.get('payment_method', 'PhonePe')
        transaction_id = request.form.get('transaction_id', '').strip()
        reg_amount = int(request.form.get('reg_amount', cfg['registration_fee']))

        if not name or not phone:
            return jsonify({'success': False, 'message': 'Name and phone are required'}), 400

        # Handle Photo (Upload or Camera Capture)
        photo_url = ''
        if 'photo' in request.files:
            photo_file = request.files['photo']
            if photo_file and photo_file.filename:
                ext = os.path.splitext(photo_file.filename)[1].lower() or '.jpg'
                filename = f"player_{uuid.uuid4().hex[:8]}{ext}"
                save_path = os.path.join(PHOTOS_DIR, filename)
                photo_file.save(save_path)
                photo_url = f"/static/uploads/photos/{filename}"

        # Handle Payment Screenshot
        screenshot_url = ''
        if 'screenshot' in request.files:
            screen_file = request.files['screenshot']
            if screen_file and screen_file.filename:
                ext = os.path.splitext(screen_file.filename)[1].lower() or '.jpg'
                filename = f"pay_{uuid.uuid4().hex[:8]}{ext}"
                save_path = os.path.join(PAYMENTS_DIR, filename)
                screen_file.save(save_path)
                screenshot_url = f"/static/uploads/payments/{filename}"

        # Create or update registration entry
        serial_no = len(regs) + 1
        player_id = f"SPL{serial_no:03d}"

        existing = regs.get(name, {})
        if existing:
            player_id = existing.get('id', player_id)
            serial_no = existing.get('serial_no', serial_no)
            if not photo_url:
                photo_url = existing.get('photo_url', '')

        regs[name] = {
            'id': player_id,
            'serial_no': serial_no,
            'name': name,
            'phone': phone,
            'role': role,
            'batting_style': batting_style,
            'bowling_style': bowling_style,
            'photo_url': photo_url,
            'reg_amount': reg_amount,
            'payment_status': 'Verified',
            'payment_method': payment_method,
            'transaction_id': transaction_id,
            'payment_screenshot': screenshot_url,
            'created_at': datetime.utcnow().isoformat() + 'Z',
            'approved': True
        }

        save_registrations(regs)
        sync_player_to_auction(name, serial_no)
        
        # Dual-Redundancy: Sync to Google Sheet if configured
        if cfg.get('google_sheet_url'):
            threading.Thread(target=sync_to_google_sheet_async, args=(cfg['google_sheet_url'], regs[name]), daemon=True).start()

        return jsonify({
            'success': True,
            'player_id': player_id,
            'name': name,
            'message': 'Registration successful!'
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
        p_details = regs.get(cur_p, {
            "name": cur_p,
            "role": "All-Rounder",
            "photo_url": "",
            "batting_style": "Right Hand Bat",
            "bowling_style": "Right Arm Medium",
            "reg_amount": state.get("min_bid", 50),
            "payment_status": "Verified"
        })

    response_data = dict(state)
    response_data["player_details"] = p_details
    return jsonify(response_data)

@app.route('/api/auction/sell', methods=['POST'])
def api_auction_sell():
    try:
        data = request.json or {}
        team_name = data.get('team')
        price = int(data.get('price', 0))

        state = load_auction_state()
        cur_p = state.get('current_player')

        if not cur_p:
            return jsonify({'success': False, 'message': 'No player currently on auction'}), 400
        if team_name not in state.get('teams', {}):
            return jsonify({'success': False, 'message': 'Invalid team selected'}), 400

        team = state['teams'][team_name]
        if price > team['budget']:
            return jsonify({'success': False, 'message': f"Insufficient purse! Team has Rs.{team['budget']}"}), 400

        push_history(state)

        # Execute purchase
        team['budget'] -= price
        team['spent'] += price
        team['players'].append({
            'name': cur_p,
            'cost': price,
            'type': 'auction',
            'round': state.get('current_round', 1)
        })

        # Remove from auction_players
        if cur_p in state.get('auction_players', []):
            state['auction_players'].remove(cur_p)

        # Draw next player
        if state.get('auction_players'):
            state['current_player'] = state['auction_players'][0]
        else:
            state['current_player'] = None

        save_auction_state(state)
        return jsonify({'success': True, 'player': cur_p, 'team': team_name, 'price': price})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/auction/unsold', methods=['POST'])
def api_auction_unsold():
    try:
        state = load_auction_state()
        cur_p = state.get('current_player')
        if not cur_p:
            return jsonify({'success': False, 'message': 'No player on auction'}), 400

        push_history(state)

        if 'unsold_players' not in state:
            state['unsold_players'] = []
        if cur_p not in state['unsold_players']:
            state['unsold_players'].append(cur_p)

        if cur_p in state.get('auction_players', []):
            state['auction_players'].remove(cur_p)

        if state.get('auction_players'):
            state['current_player'] = state['auction_players'][0]
        else:
            state['current_player'] = None

        save_auction_state(state)
        return jsonify({'success': True, 'player': cur_p})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/auction/undo', methods=['POST'])
def api_auction_undo():
    try:
        state = load_auction_state()
        if not state.get('history'):
            return jsonify({'success': False, 'message': 'Nothing to undo'}), 400

        prev = state['history'].pop()
        current_history = state['history']
        state.update(prev)
        state['history'] = current_history
        save_auction_state(state)
        return jsonify({'success': True, 'message': 'Undo successful'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/auction/next', methods=['POST'])
def api_auction_next():
    try:
        state = load_auction_state()
        players = state.get('auction_players', [])
        if not players:
            return jsonify({'success': False, 'message': 'No more players in current round'}), 400

        cur_p = state.get('current_player')
        if cur_p in players:
            idx = players.index(cur_p)
            next_idx = (idx + 1) % len(players)
            state['current_player'] = players[next_idx]
        else:
            state['current_player'] = players[0]

        save_auction_state(state)
        return jsonify({'success': True, 'player': state['current_player']})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/auction/select-player', methods=['POST'])
def api_auction_select_player():
    try:
        data = request.json or {}
        player = data.get('player')
        state = load_auction_state()
        state['current_player'] = player
        if player not in state.get('auction_players', []):
            state.setdefault('auction_players', []).insert(0, player)
        save_auction_state(state)
        return jsonify({'success': True, 'player': player})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/auction/round2', methods=['POST'])
def api_auction_round2():
    try:
        state = load_auction_state()
        unsold = state.get('unsold_players', [])
        if not unsold:
            return jsonify({'success': False, 'message': 'No unsold players to re-auction'}), 400

        push_history(state)
        state['auction_players'] = list(unsold)
        state['unsold_players'] = []
        random.shuffle(state['auction_players'])
        state['current_round'] = state.get('current_round', 1) + 1
        state['current_player'] = state['auction_players'][0]

        save_auction_state(state)
        return jsonify({'success': True, 'message': f'Round {state["current_round"]} started!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/config', methods=['POST'])
def api_admin_config():
    try:
        data = request.json or {}
        cfg = load_config()
        cfg.update(data)
        save_config(cfg)
        return jsonify({'success': True, 'config': cfg})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/verify-player', methods=['POST'])
def api_admin_verify_player():
    try:
        data = request.json or {}
        name = data.get('name')
        regs = load_registrations()
        if name in regs:
            regs[name]['payment_status'] = 'Verified'
            regs[name]['approved'] = True
            save_registrations(regs)
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': 'Player not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/reset-auction', methods=['POST'])
def api_admin_reset_auction():
    try:
        cfg = load_config()
        regs = load_registrations()
        player_list = list(regs.keys())
        state = {
            "teams": {
                "Team A": {"budget": cfg["default_purse"], "spent": 0, "players": [], "retained": None},
                "Team B": {"budget": cfg["default_purse"], "spent": 0, "players": [], "retained": None},
                "Team C": {"budget": cfg["default_purse"], "spent": 0, "players": [], "retained": None},
                "Team D": {"budget": cfg["default_purse"], "spent": 0, "players": [], "retained": None}
            },
            "players": player_list,
            "player_serials": {p: i + 1 for i, p in enumerate(player_list)},
            "auction_players": list(player_list),
            "unsold_players": [],
            "current_player": player_list[0] if player_list else None,
            "history": [],
            "current_round": 1,
            "total_purse": cfg["default_purse"],
            "max_players": cfg["max_players"],
            "min_bid": cfg["min_bid"],
            "retention_price": cfg["retention_price"]
        }
        save_auction_state(state)
        return jsonify({'success': True, 'message': 'Auction state reset.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/export-excel')
def api_export_excel():
    try:
        state = load_auction_state()
        regs = load_registrations()

        squad_rows = []
        for t_name, t in state.get('teams', {}).items():
            if t.get('retained'):
                squad_rows.append({
                    'Team': t_name,
                    'Player Name': t['retained'],
                    'Role': regs.get(t['retained'], {}).get('role', 'Retained'),
                    'Price (Rs)': state.get('retention_price', 500),
                    'Type': 'Retention',
                    'Round': '-'
                })
            for p in t.get('players', []):
                squad_rows.append({
                    'Team': t_name,
                    'Player Name': p['name'],
                    'Role': regs.get(p['name'], {}).get('role', 'Player'),
                    'Price (Rs)': p['cost'],
                    'Type': 'Auction',
                    'Round': p.get('round', 1)
                })

        df_squads = pd.DataFrame(squad_rows) if squad_rows else pd.DataFrame(columns=['Team', 'Player Name', 'Role', 'Price (Rs)', 'Type', 'Round'])

        reg_rows = []
        for name, p in regs.items():
            reg_rows.append({
                'ID': p.get('id'),
                'Serial No': p.get('serial_no'),
                'Name': name,
                'Role': p.get('role'),
                'Phone': p.get('phone'),
                'Batting': p.get('batting_style'),
                'Bowling': p.get('bowling_style'),
                'Fee Paid (Rs)': p.get('reg_amount'),
                'Payment Mode': p.get('payment_method'),
                'UPI UTR': p.get('transaction_id'),
                'Payment Status': p.get('payment_status')
            })
        df_regs = pd.DataFrame(reg_rows) if reg_rows else pd.DataFrame(columns=['ID', 'Name', 'Role', 'Phone'])

        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_squads.to_excel(writer, sheet_name='Auction Squads', index=False)
            df_regs.to_excel(writer, sheet_name='All Registrations', index=False)

        output.seek(0)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return send_file(
            output,
            download_name=f"SPL_Cricket_Auction_Summary_{timestamp}.xlsx",
            as_attachment=True,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("=" * 60)
    print("SPL CRICKET AUCTION AND REGISTRATION SUITE RUNNING")
    print("=" * 60)
    print(f"Local Access:    http://127.0.0.1:{port}")
    print(f"Mobile Access:   http://10.28.89.205:{port}/register")
    print(f"Live Auction:    http://10.28.89.205:{port}/auction")
    print(f"Admin Panel:     http://10.28.89.205:{port}/admin")
    print("=" * 60)
    app.run(host='0.0.0.0', port=port, debug=False)
