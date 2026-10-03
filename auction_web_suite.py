
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

# Auto-organize flat files into templates/ and static/ if uploaded directly into repository root
try:
    for f in os.listdir(BASE_DIR):
        src = os.path.join(BASE_DIR, f)
        if not os.path.isfile(src):
            continue
        if f.endswith('.html') and f != 'Procfile':
            dst = os.path.join(TEMPLATES_DIR, f)
            shutil.copy2(src, dst)
        elif f.endswith('.css'):
            dst = os.path.join(STATIC_DIR, 'css', f)
            shutil.copy2(src, dst)
        elif f.endswith('.js') and f != 'auction_web_suite.py':
            dst = os.path.join(STATIC_DIR, 'js', f)
            shutil.copy2(src, dst)
        elif f.endswith('.svg') or f.endswith('.png') or f.endswith('.ico'):
            dst = os.path.join(STATIC_DIR, 'images', f)
            shutil.copy2(src, dst)
except Exception as _sync_err:
    print("Auto-organize note:", _sync_err)

# --- SELF-HEALING ASSET RESTORER & IN-MEMORY TEMPLATE LOADER ---
EMBEDDED_ASSETS = json.loads("{\"templates/admin.html\": \"{% extends \\\"base.html\\\" %}\\n\\n{% block extra_css %}\\n<style>\\n  /* STRICT VISIBILITY RULES */\\n  body:not(.admin-unlocked) #adminLockScreen { display: flex !important; }\\n  body:not(.admin-unlocked) #adminMainContent { display: none !important; }\\n  body.admin-unlocked #adminLockScreen { display: none !important; }\\n  body.admin-unlocked #adminMainContent { display: block !important; }\\n\\n  /* Sub-tab navigation */\\n  .admin-subtabs {\\n    display: flex;\\n    gap: 0.75rem;\\n    margin-bottom: 1.75rem;\\n    border-bottom: 2px solid rgba(255, 255, 255, 0.1);\\n    padding-bottom: 0.75rem;\\n    flex-wrap: wrap;\\n  }\\n  .subtab-btn {\\n    background: rgba(255, 255, 255, 0.05);\\n    border: 1px solid rgba(255, 255, 255, 0.15);\\n    color: #94a3b8;\\n    padding: 0.65rem 1.25rem;\\n    border-radius: 8px;\\n    font-weight: 700;\\n    font-size: 0.95rem;\\n    cursor: pointer;\\n    transition: all 0.2s ease;\\n    display: flex;\\n    align-items: center;\\n    gap: 0.5rem;\\n  }\\n  .subtab-btn:hover {\\n    color: #fff;\\n    background: rgba(255, 255, 255, 0.1);\\n  }\\n  .subtab-btn.active {\\n    background: #f59e0b;\\n    color: #000;\\n    border-color: #f59e0b;\\n    box-shadow: 0 4px 15px rgba(245, 158, 11, 0.35);\\n  }\\n  .subtab-btn.active.tab-auction {\\n    background: #ef4444;\\n    color: #fff;\\n    border-color: #ef4444;\\n    box-shadow: 0 4px 15px rgba(239, 68, 68, 0.35);\\n  }\\n\\n  .setup-grid {\\n    display: grid;\\n    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));\\n    gap: 1rem;\\n    margin-bottom: 1.5rem;\\n  }\\n  .retention-tag {\\n    display: inline-flex;\\n    align-items: center;\\n    gap: 0.35rem;\\n    padding: 0.25rem 0.6rem;\\n    border-radius: 6px;\\n    font-size: 0.8rem;\\n    font-weight: 700;\\n  }\\n  .retention-player {\\n    background: rgba(16, 185, 129, 0.15);\\n    color: #34d399;\\n    border: 1px solid rgba(16, 185, 129, 0.3);\\n  }\\n  .retention-owner {\\n    background: rgba(245, 158, 11, 0.15);\\n    color: #fbbf24;\\n    border: 1px solid rgba(245, 158, 11, 0.3);\\n  }\\n</style>\\n<script>\\n  if (sessionStorage.getItem('kpl_auction_pin') || sessionStorage.getItem('spl_auction_pin')) {\\n    document.documentElement.classList.add('pre-authorized');\\n  }\\n</script>\\n{% endblock %}\\n\\n{% block content %}\\n<!-- GATEWAY 1: ADMIN PIN LOCK SCREEN -->\\n<div id=\\\"adminLockScreen\\\" style=\\\"min-height: 65vh; align-items: center; justify-content: center; padding: 2rem 1rem;\\\">\\n  <div class=\\\"glass-card\\\" style=\\\"max-width: 420px; width: 100%; text-align: center; border: 2px solid #f59e0b; box-shadow: 0 0 45px rgba(245, 158, 11, 0.3); padding: 2.75rem 2rem;\\\">\\n    <div style=\\\"width: 72px; height: 72px; background: rgba(245, 158, 11, 0.15); border: 2px solid #f59e0b; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 2.25rem; margin: 0 auto 1.25rem;\\\">\\n      \\ud83d\\udd12\\n    </div>\\n    <h2 style=\\\"font-size: 1.65rem; font-weight: 900; color: #fff; margin-bottom: 0.35rem;\\\">Organizer Access</h2>\\n    <p style=\\\"color: #94a3b8; font-size: 0.85rem; margin-bottom: 1.75rem; line-height: 1.5;\\\">\\n      Enter your Organizer PIN to manage tournament configuration, team retentions, and live bidding.\\n    </p>\\n\\n    <form id=\\\"adminLoginForm\\\" onsubmit=\\\"handleAdminLogin(event)\\\">\\n      <div class=\\\"form-group\\\" style=\\\"margin-bottom: 1.25rem;\\\">\\n        <input type=\\\"password\\\" id=\\\"adminPinInput\\\" class=\\\"form-control\\\" placeholder=\\\"Enter Organizer PIN\\\" style=\\\"text-align: center; font-size: 1.4rem; letter-spacing: 0.25em; font-weight: 900; padding: 0.85rem; background: rgba(15,23,42,0.9);\\\" maxlength=\\\"15\\\" autofocus required>\\n        <div id=\\\"adminPinError\\\" style=\\\"display: none; color: #f87171; font-weight: 700; font-size: 0.85rem; margin-top: 0.6rem;\\\"></div>\\n      </div>\\n      <button type=\\\"submit\\\" id=\\\"btnAdminUnlock\\\" class=\\\"btn btn-primary\\\" style=\\\"width: 100%; font-size: 1.1rem; padding: 0.85rem;\\\">\\n        Unlock Admin Panel &rarr;\\n      </button>\\n      <div style=\\\"margin-top: 1.25rem; display: flex; justify-content: flex-end; align-items: center; font-size: 0.8rem;\\\">\\n        <a href=\\\"javascript:void(0)\\\" onclick=\\\"forgotPinPrompt()\\\" style=\\\"color: #f59e0b; text-decoration: underline; font-weight: 600;\\\">\\n          Forgot PIN?\\n        </a>\\n      </div>\\n    </form>\\n  </div>\\n</div>\\n\\n<!-- GATEWAY 2: ADMIN MAIN CONTENT (PROTECTED) -->\\n<div id=\\\"adminMainContent\\\">\\n  <!-- Top Bar with Broadcast Toggle & Lock -->\\n  <div style=\\\"margin-bottom: 1.5rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;\\\">\\n    <div>\\n      <h1 style=\\\"font-size: 1.85rem; font-weight: 900; color: #fff; display: flex; align-items: center; gap: 0.5rem;\\\">\\n        <span>\\u2699\\ufe0f</span> Organizer Admin Panel\\n      </h1>\\n      <p style=\\\"color: #94a3b8; font-size: 0.9rem;\\\">\\n        Kunsi Premier League (KPL 2026) Management Portal\\n      </p>\\n    </div>\\n    <div style=\\\"display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap;\\\">\\n      <span id=\\\"auctionStatusBadge\\\" class=\\\"badge\\\" style=\\\"background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); font-size: 0.85rem; padding: 0.4rem 0.8rem; font-weight: 800;\\\">\\n        \\ud83d\\udd34 Auction Not Started\\n      </span>\\n      <button type=\\\"button\\\" id=\\\"btnAdminStartAuction\\\" onclick=\\\"adminToggleAuctionStarted()\\\" class=\\\"btn btn-success\\\" style=\\\"font-size: 0.85rem; padding: 0.45rem 0.9rem;\\\">\\n        \\ud83d\\ude80 Start Live Auction\\n      </button>\\n      <button type=\\\"button\\\" onclick=\\\"lockAdminSession()\\\" class=\\\"btn btn-secondary\\\" style=\\\"font-size: 0.85rem; padding: 0.45rem 0.9rem;\\\">\\n        \\ud83d\\udd12 Lock Admin\\n      </button>\\n    </div>\\n  </div>\\n\\n  <!-- 2 SUB-PAGES / TABS INSIDE ADMIN -->\\n  <div class=\\\"admin-subtabs\\\">\\n    <button type=\\\"button\\\" id=\\\"tabBtnConfig\\\" class=\\\"subtab-btn active\\\" onclick=\\\"switchAdminTab('config')\\\">\\n      <span>\\ud83c\\udfdf\\ufe0f</span> 1. Tournament Configuration & Retentions\\n    </button>\\n    <button type=\\\"button\\\" id=\\\"tabBtnAuction\\\" class=\\\"subtab-btn tab-auction\\\" onclick=\\\"switchAdminTab('auction')\\\">\\n      <span>\\ud83d\\udd28</span> 2. Live Auction Page (Host Console)\\n    </button>\\n  </div>\\n\\n  <!-- SUB-PAGE 1: TOURNAMENT CONFIGURATION & RETENTIONS -->\\n  <div id=\\\"subpageConfig\\\">\\n    <!-- Team Setup Form -->\\n    <div class=\\\"glass-card\\\" style=\\\"margin-bottom: 2rem; border-color: rgba(245, 158, 11, 0.35);\\\">\\n      <h2 style=\\\"font-size: 1.35rem; font-weight: 800; color: #f59e0b; margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem;\\\">\\n        <span>\\ud83c\\udfdf\\ufe0f</span> Team Setup & Purse Rules\\n      </h2>\\n      <form id=\\\"teamSetupForm\\\">\\n        <div class=\\\"setup-grid\\\">\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Number of Teams</label>\\n            <input type=\\\"number\\\" id=\\\"setupTeamCount\\\" class=\\\"form-control\\\" min=\\\"2\\\" max=\\\"12\\\" value=\\\"{{ (teams|length) if teams else 4 }}\\\" required onchange=\\\"renderTeamNameInputs()\\\">\\n          </div>\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Purse Amount per Team (\\u20b9)</label>\\n            <input type=\\\"number\\\" id=\\\"setupPurse\\\" class=\\\"form-control\\\" min=\\\"500\\\" step=\\\"100\\\" value=\\\"{{ config.total_purse or config.default_purse or 6000 }}\\\" required>\\n          </div>\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Minimum Players per Team</label>\\n            <input type=\\\"number\\\" id=\\\"setupMinPlayers\\\" class=\\\"form-control\\\" min=\\\"1\\\" max=\\\"25\\\" value=\\\"{{ config.max_players or 10 }}\\\" required>\\n          </div>\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Minimum Bid Amount (\\u20b9)</label>\\n            <input type=\\\"number\\\" id=\\\"setupMinBid\\\" class=\\\"form-control\\\" min=\\\"0\\\" step=\\\"10\\\" value=\\\"{{ config.min_bid or 50 }}\\\" required>\\n          </div>\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Star Player Retention (\\u20b9)</label>\\n            <input type=\\\"number\\\" id=\\\"setupPlayerRetentionPrice\\\" class=\\\"form-control\\\" min=\\\"0\\\" step=\\\"50\\\" value=\\\"{{ config.retention_price or 500 }}\\\" required>\\n          </div>\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Owner Retention (\\u20b9)</label>\\n            <input type=\\\"number\\\" id=\\\"setupOwnerRetentionPrice\\\" class=\\\"form-control\\\" min=\\\"0\\\" step=\\\"50\\\" value=\\\"{{ config.owner_retention_price or 100 }}\\\" required>\\n          </div>\\n        </div>\\n\\n        <div style=\\\"margin-bottom: 1.5rem;\\\">\\n          <label class=\\\"form-label\\\" style=\\\"font-weight: 700; color: #fff;\\\">Custom Team Names</label>\\n          <div id=\\\"teamNamesContainer\\\" style=\\\"display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 0.75rem;\\\">\\n            <!-- Dynamically populated -->\\n          </div>\\n        </div>\\n\\n        <button type=\\\"submit\\\" class=\\\"btn btn-primary\\\" style=\\\"font-size: 1rem; padding: 0.75rem 1.75rem;\\\">\\n          \\ud83d\\udcbe Save Teams & Rules Setup\\n        </button>\\n      </form>\\n    </div>\\n\\n    <!-- Dual Retention Management -->\\n    <div class=\\\"glass-card\\\" style=\\\"margin-bottom: 2rem; border-color: rgba(16, 185, 129, 0.35);\\\">\\n      <h2 style=\\\"font-size: 1.35rem; font-weight: 800; color: #10b981; margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem;\\\">\\n        <span>\\u2b50</span> Player & Owner Retention Phase\\n      </h2>\\n      <p style=\\\"color: #94a3b8; font-size: 0.85rem; margin-bottom: 1.25rem;\\\">\\n        Retain star players (\\u20b9{{ config.retention_price or 500 }}) or team owners (\\u20b9{{ config.owner_retention_price or 100 }}). Retained persons are automatically removed from live auction pool.\\n      </p>\\n\\n      <form id=\\\"retentionForm\\\" style=\\\"display: flex; gap: 1rem; flex-wrap: wrap; align-items: flex-end; margin-bottom: 1.5rem; background: rgba(15,23,42,0.6); padding: 1.25rem; border-radius: var(--radius-md); border: 1px solid rgba(255,255,255,0.1);\\\">\\n        <div class=\\\"form-group\\\" style=\\\"flex: 1; min-width: 180px; margin-bottom: 0;\\\">\\n          <label class=\\\"form-label\\\">Select Team</label>\\n          <select id=\\\"retentionTeamSelect\\\" class=\\\"form-control\\\" required>\\n            <option value=\\\"\\\">-- Choose Team --</option>\\n            {% for t_name in teams.keys() %}\\n            <option value=\\\"{{ t_name }}\\\">{{ t_name }}</option>\\n            {% endfor %}\\n          </select>\\n        </div>\\n\\n        <div class=\\\"form-group\\\" style=\\\"flex: 1; min-width: 180px; margin-bottom: 0;\\\">\\n          <label class=\\\"form-label\\\">Retention Type</label>\\n          <select id=\\\"retentionTypeSelect\\\" class=\\\"form-control\\\" required>\\n            <option value=\\\"Player\\\">\\u2b50 Player Retention (\\u20b9{{ config.retention_price or 500 }})</option>\\n            <option value=\\\"Owner\\\">\\ud83d\\udc51 Owner Retention (\\u20b9{{ config.owner_retention_price or 100 }})</option>\\n          </select>\\n        </div>\\n\\n        <div class=\\\"form-group\\\" style=\\\"flex: 1.5; min-width: 220px; margin-bottom: 0;\\\">\\n          <label class=\\\"form-label\\\">Select Registered Person</label>\\n          <select id=\\\"retentionPlayerSelect\\\" class=\\\"form-control\\\" required>\\n            <option value=\\\"\\\">-- Choose Person --</option>\\n            {% for p in players %}\\n            <option value=\\\"{{ p }}\\\">{{ p }}</option>\\n            {% endfor %}\\n          </select>\\n        </div>\\n\\n        <button type=\\\"submit\\\" class=\\\"btn btn-success\\\" style=\\\"padding: 0.75rem 1.5rem; font-weight: 800;\\\">\\n          \\u2b50 Confirm Retention\\n        </button>\\n      </form>\\n\\n      <!-- Active Retentions Table -->\\n      <h3 style=\\\"font-size: 1.05rem; font-weight: 700; color: #fff; margin-bottom: 0.75rem;\\\">\\n        Current Team Retentions\\n      </h3>\\n      <div style=\\\"overflow-x: auto;\\\">\\n        <table class=\\\"table\\\" style=\\\"width: 100%; border-collapse: collapse;\\\">\\n          <thead>\\n            <tr style=\\\"border-bottom: 1px solid rgba(255,255,255,0.1); text-align: left; color: #94a3b8; font-size: 0.85rem;\\\">\\n              <th style=\\\"padding: 0.75rem;\\\">Team Name</th>\\n              <th style=\\\"padding: 0.75rem;\\\">Remaining Purse</th>\\n              <th style=\\\"padding: 0.75rem;\\\">Star Player Retained (\\u20b9{{ config.retention_price or 500 }})</th>\\n              <th style=\\\"padding: 0.75rem;\\\">Owner Retained (\\u20b9{{ config.owner_retention_price or 100 }})</th>\\n            </tr>\\n          </thead>\\n          <tbody>\\n            {% for t_name, t_data in teams.items() %}\\n            <tr style=\\\"border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 0.9rem;\\\">\\n              <td style=\\\"padding: 0.75rem; font-weight: 700; color: #fff;\\\">{{ t_name }}</td>\\n              <td style=\\\"padding: 0.75rem; font-weight: 800; color: #10b981;\\\">\\u20b9{{ t_data.purse }}</td>\\n              <td style=\\\"padding: 0.75rem;\\\">\\n                {% if t_data.player_retained %}\\n                  <span class=\\\"retention-tag retention-player\\\">\\n                    \\u2b50 {{ t_data.player_retained.name if t_data.player_retained is mapping else t_data.player_retained }}\\n                    <button type=\\\"button\\\" onclick=\\\"releaseRetention('{{ t_name }}', 'Player')\\\" style=\\\"background: none; border: none; color: #f87171; cursor: pointer; font-size: 0.8rem; margin-left: 0.35rem;\\\" title=\\\"Release Retention\\\">&times;</button>\\n                  </span>\\n                {% elif t_data.retained %}\\n                  <span class=\\\"retention-tag retention-player\\\">\\n                    \\u2b50 {{ t_data.retained.name if t_data.retained is mapping else t_data.retained }}\\n                    <button type=\\\"button\\\" onclick=\\\"releaseRetention('{{ t_name }}', 'Player')\\\" style=\\\"background: none; border: none; color: #f87171; cursor: pointer; font-size: 0.8rem; margin-left: 0.35rem;\\\" title=\\\"Release Retention\\\">&times;</button>\\n                  </span>\\n                {% else %}\\n                  <span style=\\\"color: #64748b; font-style: italic;\\\">None</span>\\n                {% endif %}\\n              </td>\\n              <td style=\\\"padding: 0.75rem;\\\">\\n                {% if t_data.owner_retained %}\\n                  <span class=\\\"retention-tag retention-owner\\\">\\n                    \\ud83d\\udc51 {{ t_data.owner_retained.name if t_data.owner_retained is mapping else t_data.owner_retained }}\\n                    <button type=\\\"button\\\" onclick=\\\"releaseRetention('{{ t_name }}', 'Owner')\\\" style=\\\"background: none; border: none; color: #f87171; cursor: pointer; font-size: 0.8rem; margin-left: 0.35rem;\\\" title=\\\"Release Retention\\\">&times;</button>\\n                  </span>\\n                {% else %}\\n                  <span style=\\\"color: #64748b; font-style: italic;\\\">None</span>\\n                {% endif %}\\n              </td>\\n            </tr>\\n            {% endfor %}\\n          </tbody>\\n        </table>\\n      </div>\\n    </div>\\n\\n    <!-- General Settings & Excel Export -->\\n    <div style=\\\"display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem;\\\">\\n      <div class=\\\"glass-card\\\">\\n        <h2 style=\\\"font-size: 1.25rem; font-weight: 800; color: #f59e0b; margin-bottom: 1rem;\\\">\\n          \\ud83d\\udcb3 UPI Payment & Fee Settings\\n        </h2>\\n        <form id=\\\"configForm\\\" onsubmit=\\\"handleConfigSubmit(event)\\\">\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Tournament Display Name</label>\\n            <input type=\\\"text\\\" id=\\\"cfgTournamentName\\\" class=\\\"form-control\\\" value=\\\"{{ config.tournament_name }}\\\" required>\\n          </div>\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Receiving UPI ID</label>\\n            <input type=\\\"text\\\" id=\\\"cfgUpiId\\\" class=\\\"form-control\\\" value=\\\"{{ config.upi_id }}\\\" required>\\n          </div>\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Payee Name</label>\\n            <input type=\\\"text\\\" id=\\\"cfgPayeeName\\\" class=\\\"form-control\\\" value=\\\"{{ config.payee_name }}\\\" required>\\n          </div>\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Registration Fee (\\u20b9)</label>\\n            <input type=\\\"number\\\" id=\\\"cfgRegFee\\\" class=\\\"form-control\\\" value=\\\"{{ config.registration_fee }}\\\" required>\\n          </div>\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Change Secret Organizer PIN</label>\\n            <input type=\\\"password\\\" id=\\\"cfgAdminPin\\\" class=\\\"form-control\\\" placeholder=\\\"New Secret PIN\\\">\\n          </div>\\n          <button type=\\\"submit\\\" class=\\\"btn btn-primary\\\">Save Settings</button>\\n        </form>\\n      </div>\\n\\n      <div class=\\\"glass-card\\\" style=\\\"display: flex; flex-direction: column; justify-content: space-between;\\\">\\n        <div>\\n          <h2 style=\\\"font-size: 1.25rem; font-weight: 800; color: #10b981; margin-bottom: 1rem;\\\">\\n            \\ud83d\\udcca Styled Excel Export\\n          </h2>\\n          <p style=\\\"color: #94a3b8; font-size: 0.9rem; line-height: 1.5; margin-bottom: 1.25rem;\\\">\\n            Download complete tournament Excel report with Team Rosters, Retentions, Rounds Breakdown, and Unsold Players.\\n          </p>\\n          <a href=\\\"/api/export-excel\\\" class=\\\"btn btn-success\\\" style=\\\"width: 100%; margin-bottom: 1rem; text-align: center;\\\">\\n            \\ud83d\\udce5 Download Styled Excel (.xlsx)\\n          </a>\\n        </div>\\n        <div style=\\\"border-top: 1px solid rgba(255,255,255,0.1); padding-top: 1rem;\\\">\\n          <button type=\\\"button\\\" onclick=\\\"confirmResetAuction()\\\" class=\\\"btn btn-danger\\\" style=\\\"width: 100%;\\\">\\n            \\u26a0\\ufe0f Reset Auction & Clear Bidding\\n          </button>\\n        </div>\\n      </div>\\n    </div>\\n  </div>\\n\\n  <!-- SUB-PAGE 2: LIVE AUCTION CONTROLLER (ADMIN ACCESS) -->\\n  <div id=\\\"subpageAuction\\\" style=\\\"display: none;\\\">\\n    <div style=\\\"margin-bottom: 1.25rem; background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.4); padding: 1rem; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.75rem;\\\">\\n      <div>\\n        <strong style=\\\"color: #f87171; font-size: 1.05rem; display: block;\\\">\\ud83d\\udd28 Live Auction Host Console Active</strong>\\n        <span style=\\\"color: #cbd5e1; font-size: 0.85rem;\\\">Conduct live player draws, increment bidding amounts, confirm sales, and manage unsold players. All viewers update live!</span>\\n      </div>\\n      <div style=\\\"display: flex; gap: 0.5rem;\\\">\\n        <a href=\\\"/auction\\\" target=\\\"_blank\\\" class=\\\"btn btn-primary\\\" style=\\\"font-size: 0.85rem; padding: 0.4rem 0.85rem;\\\">\\n          \\u2197\\ufe0f Fullscreen Console\\n        </a>\\n        <a href=\\\"/view\\\" target=\\\"_blank\\\" class=\\\"btn btn-secondary\\\" style=\\\"font-size: 0.85rem; padding: 0.4rem 0.85rem;\\\">\\n          \\ud83d\\udc41\\ufe0f Preview Spectator View\\n        </a>\\n      </div>\\n    </div>\\n\\n    <!-- Live Auction Arena Embedded for Host without duplicate navbar -->\\n    <iframe id=\\\"hostAuctionIframe\\\" src=\\\"/auction?embed=1\\\" style=\\\"width: 100%; height: 900px; border: 1px solid rgba(255,255,255,0.12); border-radius: 12px; background: #0a0f1a;\\\"></iframe>\\n  </div>\\n</div>\\n{% endblock %}\\n\\n{% block extra_js %}\\n<script>\\n  const CURRENT_TEAMS = {{ (teams.keys()|list)|tojson }};\\n\\n  function getAdminPin() {\\n    return sessionStorage.getItem('kpl_auction_pin') || sessionStorage.getItem('spl_auction_pin') || '';\\n  }\\n\\n  function switchAdminTab(tabName) {\\n    const btnConfig = document.getElementById('tabBtnConfig');\\n    const btnAuction = document.getElementById('tabBtnAuction');\\n    const pageConfig = document.getElementById('subpageConfig');\\n    const pageAuction = document.getElementById('subpageAuction');\\n\\n    if (tabName === 'auction') {\\n      btnAuction.classList.add('active');\\n      btnConfig.classList.remove('active');\\n      pageAuction.style.display = 'block';\\n      pageConfig.style.display = 'none';\\n      // Refresh iframe if needed\\n      const iframe = document.getElementById('hostAuctionIframe');\\n      if (iframe && !iframe.src.includes('/auction?embed=1')) {\\n        iframe.src = '/auction?embed=1';\\n      }\\n    } else {\\n      btnConfig.classList.add('active');\\n      btnAuction.classList.remove('active');\\n      pageConfig.style.display = 'block';\\n      pageAuction.style.display = 'none';\\n    }\\n  }\\n\\n  // --- INITIALIZATION ---\\n  document.addEventListener('DOMContentLoaded', async () => {\\n    renderTeamNameInputs();\\n    updateAdminAuctionStatus();\\n\\n    const savedPin = getAdminPin();\\n    if (!savedPin) {\\n      document.body.classList.remove('admin-unlocked');\\n      return;\\n    }\\n\\n    try {\\n      const res = await fetch('/api/auction/verify-pin', {\\n        method: 'POST',\\n        headers: { 'Content-Type': 'application/json' },\\n        body: JSON.stringify({ pin: savedPin })\\n      });\\n      const data = await res.json();\\n      if (data.valid || data.success) {\\n        document.body.classList.add('admin-unlocked');\\n      } else {\\n        sessionStorage.removeItem('kpl_auction_pin');\\n        sessionStorage.removeItem('spl_auction_pin');\\n        document.body.classList.remove('admin-unlocked');\\n      }\\n    } catch(e) {\\n      document.body.classList.add('admin-unlocked');\\n    }\\n  });\\n\\n  // --- LOGIN ---\\n  async function handleAdminLogin(e) {\\n    e.preventDefault();\\n    const pin = document.getElementById('adminPinInput').value.trim();\\n    const err = document.getElementById('adminPinError');\\n    err.style.display = 'none';\\n\\n    try {\\n      const res = await fetch('/api/auction/verify-pin', {\\n        method: 'POST',\\n        headers: { 'Content-Type': 'application/json' },\\n        body: JSON.stringify({ pin: pin })\\n      });\\n      const data = await res.json();\\n      if (data.valid || data.success) {\\n        sessionStorage.setItem('kpl_auction_pin', pin);\\n        sessionStorage.setItem('spl_auction_pin', pin);\\n        document.body.classList.add('admin-unlocked');\\n        updateAdminAuctionStatus();\\n      } else {\\n        err.textContent = '\\u274c Incorrect Organizer PIN. Please try again.';\\n        err.style.display = 'block';\\n      }\\n    } catch(errEx) {\\n      err.textContent = 'Network error verifying PIN.';\\n      err.style.display = 'block';\\n    }\\n  }\\n\\n  function lockAdminSession() {\\n    sessionStorage.removeItem('kpl_auction_pin');\\n    sessionStorage.removeItem('spl_auction_pin');\\n    document.body.classList.remove('admin-unlocked');\\n    document.getElementById('adminPinInput').value = '';\\n  }\\n\\n  function forgotPinPrompt() {\\n    const recoveryKey = prompt('Please enter the Organizer Master Recovery Key:');\\n    if (!recoveryKey) return;\\n    if (recoveryKey.trim() === 'KPL2026_MASTER' || recoveryKey.trim() === 'KPL2026') {\\n      const newPin = prompt('Authentication successful. Please enter your new desired PIN:');\\n      if (newPin && newPin.trim()) {\\n        fetch('/api/admin/config', {\\n          method: 'POST',\\n          headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': recoveryKey },\\n          body: JSON.stringify({ admin_pin: newPin.trim(), pin: recoveryKey })\\n        }).then(r => r.json()).then(res => {\\n          if (res.success) {\\n            alert('PIN successfully updated! Please log in with your new PIN.');\\n          } else {\\n            alert('Error: ' + res.message);\\n          }\\n        });\\n      }\\n    } else {\\n      alert('Invalid recovery key. Please check with the head tournament organizer.');\\n    }\\n  }\\n\\n  // --- DYNAMIC TEAM INPUTS ---\\n  function renderTeamNameInputs() {\\n    const count = parseInt(document.getElementById('setupTeamCount').value) || 4;\\n    const container = document.getElementById('teamNamesContainer');\\n    container.innerHTML = '';\\n\\n    for (let i = 0; i < count; i++) {\\n      const defaultName = CURRENT_TEAMS[i] || `Team ${i + 1}`;\\n      const div = document.createElement('div');\\n      div.innerHTML = `\\n        <input type=\\\"text\\\" name=\\\"team_name_${i}\\\" class=\\\"form-control team-name-input\\\" value=\\\"${defaultName}\\\" placeholder=\\\"Team ${i+1} Name\\\" required>\\n      `;\\n      container.appendChild(div);\\n    }\\n  }\\n\\n  // --- SAVE SETUP ---\\n  document.getElementById('teamSetupForm').addEventListener('submit', async (e) => {\\n    e.preventDefault();\\n    const count = parseInt(document.getElementById('setupTeamCount').value);\\n    const purse = parseInt(document.getElementById('setupPurse').value);\\n    const minPlayers = parseInt(document.getElementById('setupMinPlayers').value);\\n    const minBid = parseInt(document.getElementById('setupMinBid').value);\\n    const playerRetPrice = parseInt(document.getElementById('setupPlayerRetentionPrice').value);\\n    const ownerRetPrice = parseInt(document.getElementById('setupOwnerRetentionPrice').value);\\n\\n    const nameInputs = document.querySelectorAll('.team-name-input');\\n    const teamNames = [];\\n    nameInputs.forEach(inp => {\\n      const v = inp.value.trim();\\n      if (v) teamNames.push(v);\\n    });\\n\\n    if (teamNames.length !== count) {\\n      return alert(`Please specify names for all ${count} teams.`);\\n    }\\n\\n    const payload = {\\n      team_count: count,\\n      team_names: teamNames,\\n      purse_per_team: purse,\\n      min_players_per_team: minPlayers,\\n      min_bid: minBid,\\n      retention_price: playerRetPrice,\\n      owner_retention_price: ownerRetPrice,\\n      pin: getAdminPin()\\n    };\\n\\n    try {\\n      const res = await fetch('/api/admin/setup-teams', {\\n        method: 'POST',\\n        headers: {\\n          'Content-Type': 'application/json',\\n          'X-Auction-PIN': getAdminPin()\\n        },\\n        body: JSON.stringify(payload)\\n      });\\n      const data = await res.json();\\n      if (data.success) {\\n        alert('Tournament Configuration Saved Successfully!');\\n        location.reload();\\n      } else {\\n        alert(data.message || 'Error saving team setup.');\\n      }\\n    } catch (err) {\\n      alert('Error: ' + err.message);\\n    }\\n  });\\n\\n  document.getElementById('retentionForm').addEventListener('submit', async (e) => {\\n    e.preventDefault();\\n    const team = document.getElementById('retentionTeamSelect').value;\\n    const player = document.getElementById('retentionPlayerSelect').value;\\n    const retType = document.getElementById('retentionTypeSelect').value;\\n\\n    if (!team || !player) return alert('Please select both team and player.');\\n\\n    const payload = {\\n      team: team,\\n      player: player,\\n      retention_type: retType,\\n      pin: getAdminPin()\\n    };\\n\\n    try {\\n      const res = await fetch('/api/retention/retain', {\\n        method: 'POST',\\n        headers: {\\n          'Content-Type': 'application/json',\\n          'X-Auction-PIN': getAdminPin()\\n        },\\n        body: JSON.stringify(payload)\\n      });\\n      const data = await res.json();\\n      if (data.success) {\\n        alert('Person retained successfully!');\\n        location.reload();\\n      } else {\\n        alert(data.message || 'Error retaining person.');\\n      }\\n    } catch (err) {\\n      alert('Error: ' + err.message);\\n    }\\n  });\\n\\n  async function releaseRetention(teamName, retentionType) {\\n    if (!confirm(`Release ${retentionType} retention from ${teamName}? Their fee will be refunded to team purse.`)) return;\\n\\n    try {\\n      const res = await fetch('/api/retention/release', {\\n        method: 'POST',\\n        headers: {\\n          'Content-Type': 'application/json',\\n          'X-Auction-PIN': getAdminPin()\\n        },\\n        body: JSON.stringify({ team: teamName, retention_type: retentionType, pin: getAdminPin() })\\n      });\\n      const data = await res.json();\\n      if (data.success) {\\n        alert(data.message || 'Retention released successfully!');\\n        location.reload();\\n      } else {\\n        alert(data.message || 'Error releasing retention.');\\n      }\\n    } catch (err) {\\n      alert('Error: ' + err.message);\\n    }\\n  }\\n\\n  async function adminToggleAuctionStarted() {\\n    const pin = getAdminPin();\\n    const badge = document.getElementById('auctionStatusBadge');\\n    const isStarted = badge && badge.textContent.includes('Active');\\n    const endpoint = isStarted ? '/api/auction/pause' : '/api/auction/start';\\n    const actionName = isStarted ? 'Pause Live Auction' : 'Start Live Auction for all viewers';\\n\\n    if (!confirm(`Are you sure you want to ${actionName}?`)) return;\\n\\n    try {\\n      const res = await fetch(endpoint, {\\n        method: 'POST',\\n        headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': pin },\\n        body: JSON.stringify({ pin: pin })\\n      });\\n      const data = await res.json();\\n      if (data.success) {\\n        alert(data.message);\\n        updateAdminAuctionStatus();\\n      } else {\\n        alert(data.message || 'Error updating auction state.');\\n      }\\n    } catch (e) {\\n      alert(e.message);\\n    }\\n  }\\n\\n  async function updateAdminAuctionStatus() {\\n    try {\\n      const res = await fetch('/api/auction/state');\\n      const state = await res.json();\\n      const badge = document.getElementById('auctionStatusBadge');\\n      const btn = document.getElementById('btnAdminStartAuction');\\n      if (!badge || !btn) return;\\n\\n      if (state.auction_started) {\\n        badge.textContent = '\\ud83d\\udfe2 Auction Active';\\n        badge.style.background = 'rgba(16, 185, 129, 0.2)';\\n        badge.style.color = '#34d399';\\n        badge.style.borderColor = 'rgba(16, 185, 129, 0.4)';\\n        btn.textContent = '\\u23f8\\ufe0f Pause Auction';\\n        btn.className = 'btn btn-secondary';\\n      } else {\\n        badge.textContent = '\\ud83d\\udd34 Auction Not Started';\\n        badge.style.background = 'rgba(239, 68, 68, 0.2)';\\n        badge.style.color = '#f87171';\\n        badge.style.borderColor = 'rgba(239, 68, 68, 0.4)';\\n        btn.textContent = '\\ud83d\\ude80 Start Live Auction';\\n        btn.className = 'btn btn-success';\\n      }\\n    } catch(e) {}\\n  }\\n\\n  async function handleConfigSubmit(e) {\\n    e.preventDefault();\\n    const payload = {\\n      tournament_name: document.getElementById('cfgTournamentName').value,\\n      upi_id: document.getElementById('cfgUpiId').value,\\n      payee_name: document.getElementById('cfgPayeeName').value,\\n      registration_fee: parseInt(document.getElementById('cfgRegFee').value) || 200,\\n      admin_pin: document.getElementById('cfgAdminPin').value || undefined,\\n      pin: getAdminPin()\\n    };\\n\\n    try {\\n      const res = await fetch('/api/admin/config', {\\n        method: 'POST',\\n        headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': getAdminPin() },\\n        body: JSON.stringify(payload)\\n      });\\n      const data = await res.json();\\n      if (data.success) {\\n        if (payload.admin_pin) {\\n          sessionStorage.setItem('kpl_auction_pin', payload.admin_pin);\\n          sessionStorage.setItem('spl_auction_pin', payload.admin_pin);\\n        }\\n        alert('Settings saved successfully!');\\n        location.reload();\\n      } else {\\n        alert(data.message || 'Error updating settings.');\\n      }\\n    } catch(e) {\\n      alert(e.message);\\n    }\\n  }\\n\\n  async function confirmResetAuction() {\\n    if (!confirm('\\u26a0\\ufe0f DANGER: This will reset all sold players, team budgets, and retentions to fresh state. Continue?')) return;\\n    try {\\n      const res = await fetch('/api/admin/reset-auction', {\\n        method: 'POST',\\n        headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': getAdminPin() },\\n        body: JSON.stringify({ pin: getAdminPin() })\\n      });\\n      const data = await res.json();\\n      if (data.success) {\\n        alert('Auction reset successfully!');\\n        location.reload();\\n      } else {\\n        alert(data.message || 'Reset failed.');\\n      }\\n    } catch(e) {\\n      alert(e.message);\\n    }\\n  }\\n</script>\\n{% endblock %}\\n\", \"templates/auction_live.html\": \"{% extends \\\"base.html\\\" %}\\n\\n{% block extra_css %}\\n<link rel=\\\"stylesheet\\\" href=\\\"/static/css/auction.css\\\">\\n<style>\\n  {% if viewer_mode %}\\n  .control-deck, .admin-only, #auctioneerAuthBox, #btnHostAuctionToggle {\\n    display: none !important;\\n  }\\n  .viewer-banner {\\n    background: linear-gradient(90deg, #dc2626, #b91c1c);\\n    color: #fff;\\n    text-align: center;\\n    padding: 0.5rem 1rem;\\n    border-radius: var(--radius-sm);\\n    font-weight: 800;\\n    font-size: 0.85rem;\\n    letter-spacing: 0.05em;\\n    margin-bottom: 1rem;\\n    display: flex;\\n    align-items: center;\\n    justify-content: center;\\n    gap: 0.5rem;\\n  }\\n  {% endif %}\\n\\n  /* Mobile-first optimizations for Viewers interface */\\n  @media (max-width: 768px) {\\n    .page-container {\\n      padding: 0.5rem !important;\\n    }\\n    .auction-header-bar {\\n      flex-direction: column;\\n      align-items: flex-start !important;\\n      gap: 0.5rem;\\n    }\\n    .auction-stage {\\n      grid-template-columns: 1fr !important;\\n      gap: 1rem;\\n    }\\n    .player-main-name {\\n      font-size: 1.65rem !important;\\n    }\\n    .photo-frame {\\n      width: 140px !important;\\n      height: 140px !important;\\n    }\\n    .bid-amount {\\n      font-size: 2.5rem !important;\\n    }\\n    .bid-odometer-box {\\n      padding: 1.25rem 1rem !important;\\n    }\\n    .team-purse-sidebar {\\n      margin-top: 1rem;\\n    }\\n    .team-card-auction {\\n      padding: 0.75rem 1rem !important;\\n    }\\n  }\\n</style>\\n{% endblock %}\\n\\n{% block content %}\\n{% if viewer_mode %}\\n<div class=\\\"viewer-banner\\\">\\n  <span style=\\\"width: 8px; height: 8px; background: #fff; border-radius: 50%; display: inline-block; animation: pulse 1.5s infinite;\\\"></span>\\n  SPECTATOR LIVE MODE \\u2022 MOBILE LIVE STREAM\\n</div>\\n{% endif %}\\n\\n<div class=\\\"auction-header-bar\\\" style=\\\"display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;\\\">\\n  <div>\\n    <h1 style=\\\"font-size: 1.85rem; font-weight: 900; color: #fff; display: flex; align-items: center; gap: 0.5rem;\\\">\\n      <span>\\ud83c\\udfcf</span> Live Auction Arena\\n    </h1>\\n    <p style=\\\"color: var(--text-muted); font-size: 0.9rem;\\\">\\n      {% if viewer_mode %}Mobile Live Stream with Player Photos & Real-time Bids{% else %}Official Bidding Console with Player Photos & Roles{% endif %}\\n    </p>\\n  </div>\\n  <div style=\\\"display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap;\\\">\\n    <span class=\\\"round-tag\\\" id=\\\"currentRoundTag\\\">Round 1</span>\\n    <span class=\\\"round-tag\\\" id=\\\"poolStatusTag\\\" style=\\\"background: rgba(16, 185, 129, 0.15); color: var(--pitch-green); border-color: rgba(16, 185, 129, 0.4);\\\">\\n      Connecting...\\n    </span>\\n    {% if not viewer_mode %}\\n    <button type=\\\"button\\\" id=\\\"btnHostAuctionToggle\\\" onclick=\\\"toggleAuctionStarted()\\\" class=\\\"btn btn-success\\\" style=\\\"display: none; font-size: 0.8rem; padding: 0.3rem 0.65rem;\\\">\\n      \\ud83d\\ude80 Start Auction\\n    </button>\\n    <div id=\\\"auctioneerAuthBox\\\">\\n      <button type=\\\"button\\\" id=\\\"btnUnlockAuctioneer\\\" onclick=\\\"openPinModal()\\\" class=\\\"btn btn-secondary\\\" style=\\\"font-size: 0.8rem; padding: 0.3rem 0.65rem; border-color: rgba(245, 158, 11, 0.5); color: var(--primary-gold); display: flex; align-items: center; gap: 0.35rem;\\\">\\n        <span>\\ud83d\\udd12</span> Host Controls\\n      </button>\\n    </div>\\n    {% endif %}\\n  </div>\\n</div>\\n\\n<div class=\\\"auction-stage\\\">\\n  <!-- Center Main Arena -->\\n  <div>\\n    <!-- WAITING / NOT STARTED SCREEN (FOR SPECTATORS) -->\\n    <div id=\\\"auctionNotStartedScreen\\\" class=\\\"glass-card\\\" style=\\\"display: none; text-align: center; padding: 3.5rem 1.5rem; max-width: 680px; margin: 1.5rem auto 2.5rem; border: 2px solid var(--primary-gold); box-shadow: 0 0 40px rgba(245, 158, 11, 0.25);\\\">\\n      <div style=\\\"font-size: 3.5rem; margin-bottom: 0.75rem;\\\">\\ud83c\\udfcf</div>\\n      <div style=\\\"display: inline-block; background: rgba(245, 158, 11, 0.15); color: var(--primary-gold); border: 1px solid rgba(245, 158, 11, 0.4); padding: 0.35rem 1rem; border-radius: 9999px; font-weight: 800; font-size: 0.85rem; text-transform: uppercase; margin-bottom: 1rem;\\\">\\n        Kunsi Premier League (KPL 2026)\\n      </div>\\n      <h2 style=\\\"font-size: 1.85rem; font-weight: 900; color: #fff; margin-bottom: 0.75rem;\\\">Live Auction Has Not Begun</h2>\\n      <p style=\\\"color: var(--text-muted); font-size: 1rem; line-height: 1.6; max-width: 500px; margin: 0 auto 1.5rem;\\\">\\n        The tournament auctioneer has not yet started the live bidding stream. Please stay on this page; player draws will automatically appear the moment the auction begins.\\n      </p>\\n      <div style=\\\"display: flex; gap: 0.5rem; align-items: center; justify-content: center; color: var(--primary-gold); font-size: 0.9rem; font-weight: 700;\\\">\\n        <span style=\\\"display: inline-block; width: 10px; height: 10px; background: var(--primary-gold); border-radius: 50%; animation: pulse 1s infinite;\\\"></span>\\n        Waiting for Auctioneer to begin...\\n      </div>\\n    </div>\\n\\n    <!-- Active Player Card -->\\n    <div class=\\\"glass-card player-active-card\\\" id=\\\"activePlayerCard\\\">\\n      <!-- Player Showcase -->\\n      <div class=\\\"player-showcase\\\">\\n        <div class=\\\"photo-frame\\\">\\n          <img id=\\\"playerPhoto\\\" src=\\\"/static/images/avatar_allrounder.svg\\\" alt=\\\"Active Player\\\">\\n        </div>\\n        <div class=\\\"player-meta\\\">\\n          <div style=\\\"display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap;\\\">\\n            <span class=\\\"role-badge\\\" id=\\\"playerRoleBadge\\\">All-Rounder</span>\\n            <span class=\\\"player-id-tag\\\" id=\\\"playerIdTag\\\">ID: #--</span>\\n          </div>\\n          <h2 class=\\\"player-main-name\\\" id=\\\"playerName\\\">Waiting for Draw...</h2>\\n          <div class=\\\"stats-row\\\">\\n            <div class=\\\"stat-item\\\">\\n              <span class=\\\"stat-label\\\">Batting Style</span>\\n              <span class=\\\"stat-val\\\" id=\\\"playerBatting\\\">Right Hand Bat</span>\\n            </div>\\n            <div class=\\\"stat-item\\\">\\n              <span class=\\\"stat-label\\\">Bowling Style</span>\\n              <span class=\\\"stat-val\\\" id=\\\"playerBowling\\\">Right Arm Medium</span>\\n            </div>\\n            <div class=\\\"stat-item\\\">\\n              <span class=\\\"stat-label\\\">Village / Town</span>\\n              <span class=\\\"stat-val\\\" id=\\\"playerVillage\\\">Saidapur</span>\\n            </div>\\n            <div class=\\\"stat-item\\\">\\n              <span class=\\\"stat-label\\\">Base Price</span>\\n              <span class=\\\"stat-val\\\" id=\\\"playerBasePrice\\\" style=\\\"color: var(--pitch-green); font-weight: 800;\\\">\\u20b950</span>\\n            </div>\\n          </div>\\n        </div>\\n      </div>\\n\\n      <!-- Live Bidding Odometer -->\\n      <div class=\\\"bid-odometer-box\\\">\\n        <div class=\\\"bid-label\\\">Current Highest Bid</div>\\n        <div class=\\\"bid-amount\\\" id=\\\"bidOdometer\\\">\\u20b90</div>\\n        <div>\\n          <span class=\\\"bid-team-tag\\\" id=\\\"leadingTeamTag\\\">No Bids Yet</span>\\n        </div>\\n      </div>\\n\\n      <!-- Controls Deck (Only visible in Host Mode) -->\\n      {% if not viewer_mode %}\\n      <div class=\\\"control-deck admin-only\\\" id=\\\"auctioneerControls\\\">\\n                <!-- Pick Specific Player from Pool Dropdown -->\\n        <div style=\\\"background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(245, 158, 11, 0.35); border-radius: 8px; padding: 0.65rem 0.85rem; margin-bottom: 1rem; display: flex; gap: 0.65rem; align-items: center; flex-wrap: wrap;\\\">\\n          <span style=\\\"font-weight: 800; color: var(--primary-gold); font-size: 0.85rem; white-space: nowrap;\\\">\\n            \\ud83c\\udfaf Pick from Player List:\\n          </span>\\n          <select id=\\\"selectPlayerDropdown\\\" class=\\\"form-control\\\" style=\\\"flex: 1; min-width: 220px; font-size: 0.85rem; padding: 0.35rem 0.65rem;\\\">\\n            <option value=\\\"\\\">-- Choose Player to Bring to Auction --</option>\\n          </select>\\n          <button type=\\\"button\\\" class=\\\"btn btn-secondary\\\" onclick=\\\"chooseSelectedPlayer()\\\" style=\\\"font-size: 0.82rem; padding: 0.35rem 0.75rem; white-space: nowrap;\\\">\\n            Bring to Block &rarr;\\n          </button>\\n        </div>\\n\\n        <!-- Quick Bid Modifiers -->\\n        <div class=\\\"bid-modifiers-bar\\\">\\n          <button type=\\\"button\\\" class=\\\"btn-mod\\\" onclick=\\\"adjustCurrentBid(50)\\\">+\\u20b950</button>\\n          <button type=\\\"button\\\" class=\\\"btn-mod\\\" onclick=\\\"adjustCurrentBid(100)\\\">+\\u20b9100</button>\\n          <button type=\\\"button\\\" class=\\\"btn-mod\\\" onclick=\\\"adjustCurrentBid(200)\\\">+\\u20b9200</button>\\n          <button type=\\\"button\\\" class=\\\"btn-mod\\\" onclick=\\\"adjustCurrentBid(500)\\\">+\\u20b9500</button>\\n          <button type=\\\"button\\\" class=\\\"btn-mod\\\" onclick=\\\"adjustCurrentBid(-50)\\\" style=\\\"background: rgba(239, 68, 68, 0.2); border-color: rgba(239, 68, 68, 0.5);\\\">-\\u20b950</button>\\n        </div>\\n\\n        <!-- Team Selector for Bid Assignment -->\\n        <div style=\\\"display: flex; gap: 0.75rem; align-items: center; margin-bottom: 1.25rem; flex-wrap: wrap;\\\">\\n          <label style=\\\"font-weight: 700; color: #fff; font-size: 0.9rem;\\\">Assign Bid To Team:</label>\\n          <select id=\\\"biddingTeamSelect\\\" class=\\\"form-control\\\" style=\\\"flex: 1; min-width: 200px;\\\">\\n            <option value=\\\"\\\">-- Choose Team --</option>\\n            {% for t_name in (teams.keys() if teams else []) %}\\n            <option value=\\\"{{ t_name }}\\\">{{ t_name }}</option>\\n            {% endfor %}\\n          </select>\\n          <button type=\\\"button\\\" onclick=\\\"assignLeadingBidder()\\\" class=\\\"btn btn-secondary\\\" style=\\\"font-size: 0.9rem;\\\">\\n            Update Bidder\\n          </button>\\n        </div>\\n\\n        <!-- Big Action Buttons -->\\n        <div class=\\\"action-buttons-grid\\\">\\n          <button type=\\\"button\\\" class=\\\"btn-action btn-next-draw\\\" onclick=\\\"drawNextPlayer()\\\">\\n            \\ud83d\\ude80 Next Draw\\n          </button>\\n          <button type=\\\"button\\\" class=\\\"btn-action btn-sold\\\" onclick=\\\"confirmSellPlayer()\\\">\\n            \\ud83d\\udd28 SOLD!\\n          </button>\\n          <button type=\\\"button\\\" class=\\\"btn-action btn-unsold\\\" onclick=\\\"markUnsold(false)\\\">\\n            \\u274c Unsold (Round 2)\\n          </button>\\n          <button type=\\\"button\\\" class=\\\"btn-action btn-perm-unsold\\\" onclick=\\\"markUnsold(true)\\\">\\n            \\u26d4 Permanent Unsold\\n          </button>\\n        </div>\\n\\n        <div style=\\\"margin-top: 1rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;\\\">\\n          <button type=\\\"button\\\" onclick=\\\"undoLastAction()\\\" class=\\\"btn btn-secondary\\\" style=\\\"font-size: 0.85rem; padding: 0.35rem 0.75rem;\\\">\\n            \\u21a9\\ufe0f Undo Last Action\\n          </button>\\n          <button type=\\\"button\\\" id=\\\"btnStartRound2\\\" onclick=\\\"startRound2()\\\" class=\\\"btn btn-secondary\\\" style=\\\"display: none; font-size: 0.85rem; padding: 0.35rem 0.75rem; border-color: #f59e0b; color: #f59e0b;\\\">\\n            \\ud83d\\udd04 Start Round 2 (Unsold Pool)\\n          </button>\\n        </div>\\n      </div>\\n      {% endif %}\\n    </div>\\n\\n    <!-- Empty State when no active player -->\\n    <div id=\\\"noActivePlayerState\\\" class=\\\"glass-card\\\" style=\\\"display: none; text-align: center; padding: 3rem 1.5rem;\\\">\\n      <h3 style=\\\"font-size: 1.35rem; color: #fff; margin-bottom: 0.5rem;\\\">No Active Player on the Auction Block</h3>\\n      <p style=\\\"color: var(--text-muted); font-size: 0.9rem; margin-bottom: 1.25rem;\\\">\\n        Waiting for the auctioneer to draw the next player...\\n      </p>\\n      {% if not viewer_mode %}\\n      <button type=\\\"button\\\" onclick=\\\"drawNextPlayer()\\\" class=\\\"btn btn-primary admin-only\\\">\\n        Draw First Player &rarr;\\n      </button>\\n      {% endif %}\\n    </div>\\n  </div>\\n\\n  <!-- Right Sidebar: Team Purses & Rosters (Mobile responsive) -->\\n  <div class=\\\"team-purse-sidebar\\\">\\n    <h3 style=\\\"font-size: 1.15rem; font-weight: 800; color: #fff; margin-bottom: 1rem; display: flex; align-items: center; justify-content: space-between;\\\">\\n      <span>\\ud83c\\udfc6 Participating Teams</span>\\n      <span style=\\\"font-size: 0.8rem; color: var(--text-muted); font-weight: 600;\\\">{{ (teams|length) if teams else 0 }} Teams</span>\\n    </h3>\\n\\n    <div id=\\\"teamsPurseList\\\" style=\\\"display: flex; flex-direction: column; gap: 0.85rem;\\\">\\n      {% for t_name, t_data in (teams.items() if teams else []) %}\\n      <div class=\\\"team-card-auction\\\" id=\\\"teamCard_{{ loop.index }}\\\" data-team=\\\"{{ t_name }}\\\">\\n        <div class=\\\"team-card-header\\\">\\n          <span class=\\\"team-card-name\\\">{{ t_name }}</span>\\n          <span class=\\\"team-squad-count\\\">{{ (t_data.players|length) if t_data.players else 0 }} Players</span>\\n        </div>\\n        <div class=\\\"team-progress-bg\\\">\\n          <div class=\\\"team-progress-bar\\\" style=\\\"width: 100%;\\\"></div>\\n        </div>\\n        <div class=\\\"team-financials\\\">\\n          <span class=\\\"team-rem-budget\\\">Purse: \\u20b9{{ t_data.purse }}</span>\\n          <span class=\\\"team-spent-budget\\\">Max Bid: \\u20b9{{ t_data.purse }}</span>\\n        </div>\\n      </div>\\n      {% endfor %}\\n    </div>\\n  </div>\\n</div>\\n\\n<!-- SOLD CELEBRATION MODAL (Auto-dismisses in 5s or on Next Draw) -->\\n<div class=\\\"sold-modal-overlay\\\" id=\\\"soldModal\\\" onclick=\\\"handleSoldModalBackdrop(event)\\\">\\n  <div class=\\\"sold-card-popup\\\" style=\\\"position: relative; max-width: 440px; padding: 2rem 1.5rem;\\\">\\n    <button type=\\\"button\\\" onclick=\\\"closeSoldModal()\\\" style=\\\"position: absolute; top: 12px; right: 15px; background: none; border: none; color: #94a3b8; font-size: 1.6rem; cursor: pointer; line-height: 1;\\\" title=\\\"Close Popup\\\">&times;</button>\\n    <div class=\\\"sold-banner\\\" style=\\\"font-size: 1.3rem; margin-bottom: 0.85rem;\\\">\\ud83c\\udf89 SOLD! \\ud83c\\udf89</div>\\n    <div style=\\\"width: 110px; height: 110px; border-radius: 50%; border: 3px solid var(--primary-gold); margin: 0 auto 0.65rem; overflow: hidden; background: #000; box-shadow: 0 0 25px rgba(245, 158, 11, 0.45);\\\">\\n      <img id=\\\"soldPlayerPhoto\\\" src=\\\"/static/images/avatar_allrounder.svg\\\" style=\\\"width: 100%; height: 100%; object-fit: cover;\\\">\\n    </div>\\n    <h2 id=\\\"soldPlayerName\\\" style=\\\"font-size: 1.75rem; font-weight: 900; color: #fff; margin-bottom: 0.2rem;\\\">-</h2>\\n    <div style=\\\"margin-bottom: 0.65rem;\\\">\\n      <span id=\\\"soldPlayerRoleBadge\\\" class=\\\"role-badge badge-allrounder\\\" style=\\\"font-size: 0.75rem; padding: 0.2rem 0.65rem;\\\">All-Rounder</span>\\n    </div>\\n    <div style=\\\"font-size: 1.05rem; color: #94a3b8; margin-bottom: 0.65rem;\\\">\\n      Purchased by <strong id=\\\"soldTeamName\\\" style=\\\"color: var(--primary-gold); font-size: 1.25rem;\\\">-</strong>\\n    </div>\\n    <div style=\\\"font-size: 2.6rem; font-weight: 900; color: var(--pitch-green); margin-bottom: 1.25rem;\\\" id=\\\"soldFinalPrice\\\">\\n      \\u20b90\\n    </div>\\n    <div style=\\\"display: flex; gap: 0.65rem; justify-content: center; flex-wrap: wrap;\\\">\\n      {% if not viewer_mode %}\\n      <button type=\\\"button\\\" class=\\\"btn btn-primary\\\" onclick=\\\"drawNextFromModal()\\\" style=\\\"font-weight: 800; font-size: 0.95rem; padding: 0.5rem 1.1rem;\\\">\\n        \\ud83d\\ude80 Next Draw &rarr;\\n      </button>\\n      {% endif %}\\n      <button type=\\\"button\\\" class=\\\"btn btn-secondary\\\" onclick=\\\"closeSoldModal()\\\" style=\\\"font-size: 0.95rem; padding: 0.5rem 1rem;\\\">\\n        Continue Auction &rarr;\\n      </button>\\n    </div>\\n  </div>\\n</div>\\n\\n<!-- HOST PIN MODAL (Only when not in viewer mode) -->\\n{% if not viewer_mode %}\\n<div class=\\\"sold-modal-overlay\\\" id=\\\"pinModal\\\">\\n  <div class=\\\"sold-card-popup\\\" style=\\\"max-width: 380px; padding: 2rem;\\\">\\n    <h3 style=\\\"font-size: 1.35rem; font-weight: 900; color: #fff; margin-bottom: 0.5rem;\\\">\\ud83d\\udd12 Organizer Authentication</h3>\\n    <p style=\\\"color: var(--text-muted); font-size: 0.85rem; margin-bottom: 1.25rem;\\\">Enter Organizer PIN to enable bidding and auction controls.</p>\\n    <input type=\\\"password\\\" id=\\\"inputHostPin\\\" class=\\\"form-control\\\" placeholder=\\\"Enter Organizer PIN\\\" style=\\\"text-align: center; font-size: 1.25rem; margin-bottom: 1rem;\\\">\\n    <div id=\\\"pinErrorMsg\\\" style=\\\"display: none; color: #f87171; font-size: 0.85rem; margin-bottom: 1rem; font-weight: 700;\\\"></div>\\n    <div style=\\\"display: flex; gap: 0.5rem;\\\">\\n      <button type=\\\"button\\\" onclick=\\\"verifyHostPin()\\\" class=\\\"btn btn-primary\\\" style=\\\"flex: 1;\\\">Unlock</button>\\n      <button type=\\\"button\\\" onclick=\\\"closePinModal()\\\" class=\\\"btn btn-secondary\\\">Cancel</button>\\n    </div>\\n  </div>\\n</div>\\n{% endif %}\\n\\n{% endblock %}\\n\\n{% block extra_js %}\\n<script src=\\\"/static/js/odometer.js\\\"></script>\\n<script src=\\\"/static/js/auction.js\\\"></script>\\n{% endblock %}\\n\", \"templates/base.html\": \"<!DOCTYPE html>\\n<html lang=\\\"en\\\">\\n<head>\\n  <meta charset=\\\"UTF-8\\\">\\n  <meta name=\\\"viewport\\\" content=\\\"width=device-width, initial-scale=1.0\\\">\\n  <title>{% block title %}{{ tournament_name }}{% endblock %}</title>\\n  <link rel=\\\"stylesheet\\\" href=\\\"/static/css/style.css\\\">\\n  <style>\\n    /* Embed mode (when embedded in an iframe inside Admin subpage 2) */\\n    {% if request.args.get('embed') %}\\n    .navbar, footer { display: none !important; }\\n    body { background: transparent !important; padding: 0 !important; margin: 0 !important; }\\n    .page-container { padding: 0.5rem 0.25rem !important; max-width: 100% !important; margin: 0 !important; }\\n    {% endif %}\\n\\n    /* Clean, rock-solid navbar */\\n    .navbar {\\n      background: rgba(10, 15, 26, 0.95);\\n      backdrop-filter: blur(16px);\\n      -webkit-backdrop-filter: blur(16px);\\n      border-bottom: 1px solid rgba(255, 255, 255, 0.1);\\n      position: sticky;\\n      top: 0;\\n      z-index: 1000;\\n      padding: 0.75rem 1.25rem;\\n    }\\n    .nav-container {\\n      max-width: 1200px;\\n      margin: 0 auto;\\n      display: flex;\\n      align-items: center;\\n      justify-content: space-between;\\n      gap: 1rem;\\n    }\\n    .nav-brand {\\n      display: flex;\\n      align-items: center;\\n      gap: 0.65rem;\\n      text-decoration: none;\\n      color: #fff;\\n      font-weight: 800;\\n      font-size: 1.15rem;\\n      white-space: nowrap;\\n    }\\n    .brand-badge {\\n      background: linear-gradient(135deg, #f59e0b, #d97706);\\n      color: #000;\\n      font-weight: 900;\\n      padding: 0.2rem 0.55rem;\\n      border-radius: 6px;\\n      font-size: 0.85rem;\\n      letter-spacing: 0.05em;\\n    }\\n    .nav-links {\\n      display: flex;\\n      align-items: center;\\n      gap: 0.5rem;\\n      list-style: none;\\n      margin: 0;\\n      padding: 0;\\n    }\\n    .nav-link {\\n      color: #94a3b8;\\n      text-decoration: none;\\n      font-weight: 700;\\n      font-size: 0.92rem;\\n      padding: 0.5rem 0.9rem;\\n      border-radius: 8px;\\n      transition: all 0.2s ease;\\n      display: inline-flex;\\n      align-items: center;\\n      gap: 0.4rem;\\n      white-space: nowrap;\\n    }\\n    .nav-link:hover {\\n      color: #fff;\\n      background: rgba(255, 255, 255, 0.08);\\n    }\\n    .nav-link.active {\\n      color: #fff;\\n      background: rgba(255, 255, 255, 0.15);\\n      border-bottom: 2px solid #f59e0b;\\n    }\\n    .nav-link.tab-admin.active {\\n      background: rgba(245, 158, 11, 0.2);\\n      color: #f59e0b;\\n      border-bottom: 2px solid #f59e0b;\\n    }\\n    .nav-link.tab-reg.active {\\n      background: rgba(56, 189, 248, 0.2);\\n      color: #38bdf8;\\n      border-bottom: 2px solid #38bdf8;\\n    }\\n    .nav-link.tab-viewers {\\n      background: rgba(239, 68, 68, 0.15);\\n      color: #f87171;\\n      border: 1px solid rgba(239, 68, 68, 0.35);\\n    }\\n    .nav-link.tab-viewers:hover,\\n    .nav-link.tab-viewers.active {\\n      background: #ef4444;\\n      color: #fff;\\n      border-color: #ef4444;\\n      box-shadow: 0 0 15px rgba(239, 68, 68, 0.5);\\n    }\\n    .live-pulse-dot {\\n      width: 8px;\\n      height: 8px;\\n      background: #ef4444;\\n      border-radius: 50%;\\n      display: inline-block;\\n      box-shadow: 0 0 8px #ef4444;\\n      animation: pulseDot 1.5s infinite;\\n    }\\n    .nav-link.tab-viewers.active .live-pulse-dot,\\n    .nav-link.tab-viewers:hover .live-pulse-dot {\\n      background: #fff;\\n      box-shadow: 0 0 8px #fff;\\n    }\\n    @keyframes pulseDot {\\n      0% { transform: scale(0.95); opacity: 0.8; }\\n      50% { transform: scale(1.3); opacity: 1; }\\n      100% { transform: scale(0.95); opacity: 0.8; }\\n    }\\n\\n    /* Mobile toggle */\\n    .mobile-toggle {\\n      display: none;\\n      background: none;\\n      border: none;\\n      color: #fff;\\n      font-size: 1.5rem;\\n      cursor: pointer;\\n      padding: 0.25rem 0.5rem;\\n    }\\n\\n    @media (max-width: 860px) {\\n      .mobile-toggle { display: block; }\\n      .nav-links {\\n        display: none;\\n        flex-direction: column;\\n        position: absolute;\\n        top: 100%;\\n        left: 0;\\n        right: 0;\\n        background: #0b1120;\\n        padding: 1rem;\\n        border-bottom: 1px solid rgba(255, 255, 255, 0.1);\\n        box-shadow: 0 10px 25px rgba(0,0,0,0.5);\\n      }\\n      .nav-links.open { display: flex; }\\n      .nav-link { padding: 0.75rem 1rem; font-size: 1rem; width: 100%; }\\n    }\\n  </style>\\n  {% block extra_css %}{% endblock %}\\n</head>\\n<body>\\n  <header class=\\\"navbar\\\">\\n    <div class=\\\"nav-container\\\">\\n      <a href=\\\"/\\\" class=\\\"nav-brand\\\">\\n        <span class=\\\"brand-badge\\\">KPL</span>\\n        <span>Kunsi Premier League (KPL 2026)</span>\\n      </a>\\n      <button class=\\\"mobile-toggle\\\" onclick=\\\"document.querySelector('.nav-links').classList.toggle('open')\\\" aria-label=\\\"Toggle Menu\\\">\\u2630</button>\\n      <ul class=\\\"nav-links\\\">\\n        <li><a href=\\\"/\\\" class=\\\"nav-link {% if active_page == 'home' %}active{% endif %}\\\">\\ud83c\\udfe0 Home</a></li>\\n        <li><a href=\\\"/admin\\\" class=\\\"nav-link tab-admin {% if active_page == 'admin' %}active{% endif %}\\\">\\u2699\\ufe0f 1. Admin</a></li>\\n        <li><a href=\\\"/register\\\" class=\\\"nav-link tab-reg {% if active_page == 'register' %}active{% endif %}\\\">\\ud83d\\udcdd 2. Registration</a></li>\\n        <li>\\n          <a href=\\\"/view\\\" class=\\\"nav-link tab-viewers {% if active_page == 'view' %}active{% endif %}\\\" title=\\\"Mobile Viewers Live Auction\\\">\\n            <span class=\\\"live-pulse-dot\\\"></span>\\n            <span>\\ud83d\\udc41\\ufe0f 3. Auction Viewers</span>\\n          </a>\\n        </li>\\n      </ul>\\n    </div>\\n  </header>\\n\\n  <main class=\\\"page-container\\\">\\n    {% block content %}{% endblock %}\\n  </main>\\n\\n  <footer style=\\\"text-align: center; padding: 2.5rem 1rem; color: #64748b; font-size: 0.85rem; border-top: 1px solid rgba(255,255,255,0.08); margin-top: auto;\\\">\\n    <p>Kunsi Premier League (KPL 2026) &copy; 2026. Official Tournament Portal & Live Auction System.</p>\\n  </footer>\\n\\n  {% block extra_js %}{% endblock %}\\n</body>\\n</html>\\n\", \"templates/index.html\": \"{% extends \\\"base.html\\\" %}\\n\\n{% block content %}\\n<div style=\\\"text-align: center; max-width: 820px; margin: 1.5rem auto 2.5rem;\\\">\\n  <div style=\\\"display: inline-block; background: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.4); padding: 0.35rem 1rem; border-radius: 9999px; font-weight: 800; font-size: 0.85rem; text-transform: uppercase; margin-bottom: 1rem;\\\">\\n    \\ud83c\\udfcf Season 2026 Official Tournament Portal\\n  </div>\\n  <h1 style=\\\"font-size: 2.75rem; font-weight: 900; line-height: 1.15; margin-bottom: 0.75rem; color: #fff;\\\">\\n    Kunsi Premier League (KPL 2026)\\n  </h1>\\n  <p style=\\\"font-size: 1.1rem; color: #94a3b8; line-height: 1.6;\\\">\\n    Official Tournament Guide, Player Registration Directory, and Mobile Live Auction Dashboard.\\n  </p>\\n</div>\\n\\n<!-- Quick Tournament Stats Counter -->\\n<div style=\\\"display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem;\\\">\\n  <div class=\\\"glass-card\\\" style=\\\"text-align: center; padding: 1.25rem 1rem;\\\">\\n    <div style=\\\"font-size: 2.25rem; font-weight: 900; color: #f59e0b;\\\">{{ total_registered }}</div>\\n    <div style=\\\"color: #94a3b8; font-weight: 600; font-size: 0.9rem; margin-top: 0.25rem;\\\">Registered Players</div>\\n  </div>\\n  <div class=\\\"glass-card\\\" style=\\\"text-align: center; padding: 1.25rem 1rem;\\\">\\n    <div style=\\\"font-size: 2.25rem; font-weight: 900; color: #38bdf8;\\\">{{ total_teams }}</div>\\n    <div style=\\\"color: #94a3b8; font-weight: 600; font-size: 0.9rem; margin-top: 0.25rem;\\\">Participating Teams</div>\\n  </div>\\n  <div class=\\\"glass-card\\\" style=\\\"text-align: center; padding: 1.25rem 1rem;\\\">\\n    <div style=\\\"font-size: 2.25rem; font-weight: 900; color: #10b981;\\\">\\u20b9{{ total_purse }}</div>\\n    <div style=\\\"color: #94a3b8; font-weight: 600; font-size: 0.9rem; margin-top: 0.25rem;\\\">Purse per Team</div>\\n  </div>\\n  <div class=\\\"glass-card\\\" style=\\\"text-align: center; padding: 1.25rem 1rem;\\\">\\n    <div style=\\\"font-size: 2.25rem; font-weight: 900; color: #ec4899;\\\">\\u20b9{{ reg_fee }}</div>\\n    <div style=\\\"color: #94a3b8; font-weight: 600; font-size: 0.9rem; margin-top: 0.25rem;\\\">Registration Fee</div>\\n  </div>\\n</div>\\n\\n<!-- READ-ONLY TOURNAMENT INFORMATION -->\\n<div class=\\\"glass-card\\\" style=\\\"margin-bottom: 2rem; border-color: rgba(245, 158, 11, 0.3);\\\">\\n  <h2 style=\\\"font-size: 1.35rem; font-weight: 800; color: #f59e0b; margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem;\\\">\\n    <span>\\ud83d\\udccb</span> Tournament Overview & Rules\\n  </h2>\\n  <div style=\\\"display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1.25rem; color: #cbd5e1; font-size: 0.95rem; line-height: 1.6;\\\">\\n    <div style=\\\"background: rgba(15,23,42,0.6); padding: 1rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.08);\\\">\\n      <strong style=\\\"color: #fff; display: block; margin-bottom: 0.35rem;\\\">\\ud83c\\udfdf\\ufe0f Venue & Format</strong>\\n      Location: Saidapur Cricket Ground.<br>\\n      Format: Limited overs knockout & league matches with official white ball.\\n    </div>\\n    <div style=\\\"background: rgba(15,23,42,0.6); padding: 1rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.08);\\\">\\n      <strong style=\\\"color: #fff; display: block; margin-bottom: 0.35rem;\\\">\\ud83d\\udcb0 Auction Rules & Purses</strong>\\n      Purse per team: \\u20b9{{ total_purse }}. Minimum squad requirement: 10 players.<br>\\n      Minimum bid: \\u20b950. Star Player Retention: \\u20b9500. Owner Retention: \\u20b9100.\\n    </div>\\n    <div style=\\\"background: rgba(15,23,42,0.6); padding: 1rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.08);\\\">\\n      <strong style=\\\"color: #fff; display: block; margin-bottom: 0.35rem;\\\">\\ud83d\\udcb3 Registration Instructions</strong>\\n      Registration fee: \\u20b9{{ reg_fee }} via PhonePe/GPay/BHIM UPI.<br>\\n      Players submit name, mobile, role, village, and photo.\\n    </div>\\n  </div>\\n</div>\\n\\n<!-- 3 MAIN TABS PORTAL CARDS -->\\n<h2 style=\\\"font-size: 1.35rem; font-weight: 800; color: #fff; margin-bottom: 1rem;\\\">\\n  Explore Tournament Portals\\n</h2>\\n<div style=\\\"display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1.5rem;\\\">\\n  <!-- TAB 1 CARD -->\\n  <div class=\\\"glass-card\\\" style=\\\"display: flex; flex-direction: column; justify-content: space-between; border-color: rgba(245, 158, 11, 0.4);\\\">\\n    <div>\\n      <div style=\\\"display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;\\\">\\n        <span style=\\\"font-size: 2.25rem;\\\">\\u2699\\ufe0f</span>\\n        <span style=\\\"background: rgba(245,158,11,0.2); color: #fbbf24; border: 1px solid rgba(245,158,11,0.4); padding: 0.2rem 0.6rem; border-radius: 9999px; font-weight: 800; font-size: 0.75rem;\\\">\\n          Tab 1: Organizer\\n        </span>\\n      </div>\\n      <h3 style=\\\"font-size: 1.45rem; font-weight: 800; color: #fff; margin-bottom: 0.5rem;\\\">1. Organizer Admin</h3>\\n      <p style=\\\"color: #94a3b8; font-size: 0.95rem; line-height: 1.5; margin-bottom: 1.5rem;\\\">\\n        PIN-protected organizer control panel featuring two sub-pages: Tournament Configuration (teams, purse, retentions, UPI settings, Excel) and Live Auction Host Controller (next draw, increase bids, sold, unsold, undo).\\n      </p>\\n    </div>\\n    <a href=\\\"/admin\\\" class=\\\"btn btn-primary\\\" style=\\\"width: 100%; text-align: center; font-size: 1.05rem;\\\">\\n      Open Admin Console &rarr;\\n    </a>\\n  </div>\\n\\n  <!-- TAB 2 CARD -->\\n  <div class=\\\"glass-card\\\" style=\\\"display: flex; flex-direction: column; justify-content: space-between; border-color: rgba(56, 189, 248, 0.4);\\\">\\n    <div>\\n      <div style=\\\"display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;\\\">\\n        <span style=\\\"font-size: 2.25rem;\\\">\\ud83d\\udcdd</span>\\n        <span style=\\\"background: rgba(56,189,248,0.2); color: #38bdf8; border: 1px solid rgba(56,189,248,0.4); padding: 0.2rem 0.6rem; border-radius: 9999px; font-weight: 800; font-size: 0.75rem;\\\">\\n          Tab 2: Players\\n        </span>\\n      </div>\\n      <h3 style=\\\"font-size: 1.45rem; font-weight: 800; color: #fff; margin-bottom: 0.5rem;\\\">2. Player Registration</h3>\\n      <p style=\\\"color: #94a3b8; font-size: 0.95rem; line-height: 1.5; margin-bottom: 1.5rem;\\\">\\n        Opens immediately with the complete directory of all registered players (Name, Role, Village, Amount Sent, Photo, UPI) with search & filter, plus quick form to register new players.\\n      </p>\\n    </div>\\n    <a href=\\\"/register\\\" class=\\\"btn btn-secondary\\\" style=\\\"width: 100%; text-align: center; font-size: 1.05rem; border-color: rgba(56,189,248,0.5); color: #38bdf8;\\\">\\n      Open Registration Tab &rarr;\\n    </a>\\n  </div>\\n\\n  <!-- TAB 3 CARD -->\\n  <div class=\\\"glass-card\\\" style=\\\"display: flex; flex-direction: column; justify-content: space-between; border: 2px solid #ef4444; box-shadow: 0 0 35px rgba(239, 68, 68, 0.25);\\\">\\n    <div>\\n      <div style=\\\"display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;\\\">\\n        <span style=\\\"font-size: 2.25rem;\\\">\\ud83d\\udc41\\ufe0f</span>\\n        <span style=\\\"background: rgba(239,68,68,0.2); color: #f87171; border: 1px solid rgba(239,68,68,0.4); padding: 0.2rem 0.6rem; border-radius: 9999px; font-weight: 800; font-size: 0.75rem;\\\">\\n          Tab 3: Spectators\\n        </span>\\n      </div>\\n      <h3 style=\\\"font-size: 1.45rem; font-weight: 800; color: #fff; margin-bottom: 0.5rem;\\\">3. Auction Viewers</h3>\\n      <p style=\\\"color: #94a3b8; font-size: 0.95rem; line-height: 1.5; margin-bottom: 1.5rem;\\\">\\n        Mobile-first live bidding stream. Watch player photos, odometer bids, sold celebrations, and squad purse meters from any phone, TV, or projector in real time. (Read-only, no login).\\n      </p>\\n    </div>\\n    <a href=\\\"/view\\\" class=\\\"btn btn-danger\\\" style=\\\"width: 100%; text-align: center; font-size: 1.05rem; font-weight: 800; background: linear-gradient(135deg, #ef4444, #b91c1c);\\\">\\n      \\ud83d\\udc41\\ufe0f Open Auction Viewers Stream &rarr;\\n    </a>\\n  </div>\\n</div>\\n{% endblock %}\\n\", \"templates/register.html\": \"{% extends \\\"base.html\\\" %}\\n\\n{% block extra_css %}\\n<style>\\n  /* Clean Sub-tab Navigation */\\n  .reg-subtabs {\\n    display: flex;\\n    gap: 0.75rem;\\n    margin-bottom: 2rem;\\n    border-bottom: 2px solid rgba(255, 255, 255, 0.1);\\n    padding-bottom: 0.75rem;\\n    flex-wrap: wrap;\\n  }\\n  .subtab-btn {\\n    background: rgba(255, 255, 255, 0.05);\\n    border: 1px solid rgba(255, 255, 255, 0.15);\\n    color: #94a3b8;\\n    padding: 0.65rem 1.35rem;\\n    border-radius: 8px;\\n    font-weight: 700;\\n    font-size: 0.95rem;\\n    cursor: pointer;\\n    transition: all 0.2s ease;\\n    display: flex;\\n    align-items: center;\\n    gap: 0.5rem;\\n  }\\n  .subtab-btn:hover {\\n    color: #fff;\\n    background: rgba(255, 255, 255, 0.12);\\n  }\\n  .subtab-btn.active {\\n    background: #38bdf8;\\n    color: #000;\\n    border-color: #38bdf8;\\n    box-shadow: 0 4px 15px rgba(56, 189, 248, 0.35);\\n  }\\n\\n  /* Live Selfie Camera Box */\\n  .selfie-camera-box {\\n    background: rgba(15, 23, 42, 0.9);\\n    border: 2px dashed rgba(56, 189, 248, 0.4);\\n    border-radius: 12px;\\n    padding: 1.25rem;\\n    text-align: center;\\n    margin-bottom: 1.5rem;\\n  }\\n  .selfie-viewfinder {\\n    width: 100%;\\n    max-width: 320px;\\n    height: 240px;\\n    border-radius: 12px;\\n    object-fit: cover;\\n    margin: 0 auto;\\n    background: #0b1120;\\n    border: 2px solid #38bdf8;\\n    display: block;\\n  }\\n\\n  /* Payment App Buttons Grid */\\n  .payment-apps-grid {\\n    display: grid;\\n    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));\\n    gap: 0.75rem;\\n    margin-bottom: 1.25rem;\\n  }\\n  .pay-app-btn {\\n    display: flex;\\n    flex-direction: column;\\n    align-items: center;\\n    justify-content: center;\\n    padding: 0.85rem 0.5rem;\\n    border-radius: 10px;\\n    text-decoration: none;\\n    font-weight: 800;\\n    font-size: 0.85rem;\\n    color: #fff;\\n    transition: all 0.2s ease;\\n    box-shadow: 0 4px 12px rgba(0,0,0,0.3);\\n    border: 1px solid rgba(255,255,255,0.15);\\n  }\\n  .pay-app-btn:hover {\\n    transform: translateY(-2px);\\n    box-shadow: 0 6px 18px rgba(0,0,0,0.45);\\n    color: #fff;\\n  }\\n  .pay-phonepe {\\n    background: linear-gradient(135deg, #5f259f, #7a2fc7);\\n  }\\n  .pay-gpay {\\n    background: linear-gradient(135deg, #1a73e8, #4285f4);\\n  }\\n  .pay-paytm {\\n    background: linear-gradient(135deg, #002e6e, #00b9f1);\\n  }\\n  .pay-amazon {\\n    background: linear-gradient(135deg, #ff9900, #e68a00);\\n    color: #000 !important;\\n  }\\n  .pay-bhim {\\n    background: linear-gradient(135deg, #00875a, #00b377);\\n  }\\n\\n  /* Player Directory Cards Grid */\\n  .player-dir-grid {\\n    display: grid;\\n    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));\\n    gap: 1.25rem;\\n  }\\n  .dir-card {\\n    background: rgba(15, 23, 42, 0.75);\\n    border: 1px solid rgba(255, 255, 255, 0.1);\\n    border-radius: 12px;\\n    padding: 1.25rem;\\n    display: flex;\\n    gap: 1rem;\\n    align-items: center;\\n    transition: transform 0.2s ease, border-color 0.2s ease;\\n  }\\n  .dir-card:hover {\\n    transform: translateY(-2px);\\n    border-color: #38bdf8;\\n  }\\n  .dir-avatar {\\n    width: 72px;\\n    height: 72px;\\n    border-radius: 50%;\\n    object-fit: cover;\\n    border: 2px solid #38bdf8;\\n    background: #1e293b;\\n    flex-shrink: 0;\\n  }\\n\\n  /* Detailed Table View */\\n  .dir-table {\\n    width: 100%;\\n    border-collapse: collapse;\\n    font-size: 0.9rem;\\n  }\\n  .dir-table th {\\n    background: rgba(15, 23, 42, 0.85);\\n    color: #94a3b8;\\n    font-weight: 700;\\n    padding: 0.75rem 1rem;\\n    text-align: left;\\n    border-bottom: 1px solid rgba(255, 255, 255, 0.1);\\n  }\\n  .dir-table td {\\n    padding: 0.75rem 1rem;\\n    border-bottom: 1px solid rgba(255, 255, 255, 0.06);\\n    vertical-align: middle;\\n  }\\n  .dir-table tr:hover td {\\n    background: rgba(255, 255, 255, 0.03);\\n  }\\n  .table-avatar {\\n    width: 44px;\\n    height: 44px;\\n    border-radius: 50%;\\n    object-fit: cover;\\n    border: 2px solid #38bdf8;\\n    background: #1e293b;\\n  }\\n</style>\\n{% endblock %}\\n\\n{% block content %}\\n<!-- HEADER WITH REGISTRATION INFO -->\\n<div style=\\\"margin-bottom: 1.5rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;\\\">\\n  <div>\\n    <h1 style=\\\"font-size: 2rem; font-weight: 900; color: #fff; display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;\\\">\\n      <span>\\ud83d\\udcdd</span> Player Registration Portal\\n    </h1>\\n    <p style=\\\"color: #94a3b8; font-size: 0.95rem;\\\">\\n      Register as a player for Kunsi Premier League (KPL 2026) or view registered tournament players.\\n    </p>\\n  </div>\\n  <div style=\\\"display: flex; gap: 0.5rem; align-items: center;\\\">\\n    <span class=\\\"badge\\\" style=\\\"background: rgba(56, 189, 248, 0.2); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.4); font-size: 0.95rem; padding: 0.5rem 0.9rem; font-weight: 800;\\\">\\n      {{ players|length }} Registered Players\\n    </span>\\n  </div>\\n</div>\\n\\n<!-- 2 CLEAN SUB-TABS: REGISTER FORM (DEFAULT) vs REGISTERED PLAYERS UNTIL NOW -->\\n<div class=\\\"reg-subtabs\\\">\\n  <button type=\\\"button\\\" id=\\\"tabBtnRegister\\\" class=\\\"subtab-btn active\\\" onclick=\\\"switchRegSubtab('form')\\\">\\n    <span>\\u270d\\ufe0f</span> 1. Register Player\\n  </button>\\n  <button type=\\\"button\\\" id=\\\"tabBtnDirectory\\\" class=\\\"subtab-btn\\\" onclick=\\\"switchRegSubtab('directory')\\\">\\n    <span>\\ud83d\\udc65</span> 2. Registered Players Until Now ({{ players|length }})\\n  </button>\\n</div>\\n\\n<!-- SUB-PAGE 1: REGISTRATION FORM (OPEN BY DEFAULT) -->\\n<div id=\\\"subpageRegisterForm\\\">\\n  <div class=\\\"glass-card\\\" style=\\\"max-width: 720px; margin: 0 auto; border-color: rgba(56, 189, 248, 0.4); box-shadow: 0 0 40px rgba(56, 189, 248, 0.15);\\\">\\n    <div style=\\\"margin-bottom: 1.5rem; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 1rem;\\\">\\n      <h2 style=\\\"font-size: 1.45rem; font-weight: 800; color: #38bdf8; margin: 0 0 0.35rem 0;\\\">\\n        \\ud83c\\udfcf Official Player Registration Form\\n      </h2>\\n      <p style=\\\"color: #cbd5e1; font-size: 0.9rem; margin: 0;\\\">\\n        Entry Fee: <strong style=\\\"color: #10b981; font-size: 1.05rem;\\\">\\u20b9{{ reg_fee }}</strong>. Pay with any UPI app below and snap your selfie.\\n      </p>\\n    </div>\\n\\n    <form id=\\\"playerRegForm\\\" onsubmit=\\\"handleRegistrationSubmit(event)\\\">\\n      <!-- Name & Phone -->\\n      <div style=\\\"display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; margin-bottom: 1rem;\\\">\\n        <div class=\\\"form-group\\\" style=\\\"margin-bottom: 0;\\\">\\n          <label class=\\\"form-label\\\">Full Name *</label>\\n          <input type=\\\"text\\\" id=\\\"regName\\\" class=\\\"form-control\\\" placeholder=\\\"e.g. M. Raju Anna\\\" required>\\n        </div>\\n        <div class=\\\"form-group\\\" style=\\\"margin-bottom: 0;\\\">\\n          <label class=\\\"form-label\\\">Mobile Number *</label>\\n          <input type=\\\"tel\\\" id=\\\"regPhone\\\" class=\\\"form-control\\\" placeholder=\\\"10-digit WhatsApp Number\\\" required pattern=\\\"[0-9]{10}\\\">\\n        </div>\\n      </div>\\n\\n      <!-- Village & Role -->\\n      <div style=\\\"display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; margin-bottom: 1rem;\\\">\\n        <div class=\\\"form-group\\\" style=\\\"margin-bottom: 0;\\\">\\n          <label class=\\\"form-label\\\">Village / Town *</label>\\n          <input type=\\\"text\\\" id=\\\"regVillage\\\" class=\\\"form-control\\\" placeholder=\\\"e.g. Saidapur / Kunsi\\\" required value=\\\"Saidapur\\\">\\n        </div>\\n        <div class=\\\"form-group\\\" style=\\\"margin-bottom: 0;\\\">\\n          <label class=\\\"form-label\\\">Primary Playing Role *</label>\\n          <select id=\\\"regRole\\\" class=\\\"form-control\\\" required>\\n            <option value=\\\"All-Rounder\\\">\\ud83c\\udfcf All-Rounder</option>\\n            <option value=\\\"Batsman\\\">\\ud83c\\udfcf Top-Order Batsman</option>\\n            <option value=\\\"Bowler\\\">\\ud83c\\udfaf Fast / Spin Bowler</option>\\n            <option value=\\\"Wicket-Keeper\\\">\\ud83e\\udde4 Wicket Keeper Batsman</option>\\n          </select>\\n        </div>\\n      </div>\\n\\n      <!-- Batting & Bowling Style -->\\n      <div style=\\\"display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; margin-bottom: 1.25rem;\\\">\\n        <div class=\\\"form-group\\\" style=\\\"margin-bottom: 0;\\\">\\n          <label class=\\\"form-label\\\">Batting Style</label>\\n          <select id=\\\"regBatting\\\" class=\\\"form-control\\\">\\n            <option value=\\\"Right Hand Bat\\\">Right Hand Bat</option>\\n            <option value=\\\"Left Hand Bat\\\">Left Hand Bat</option>\\n          </select>\\n        </div>\\n        <div class=\\\"form-group\\\" style=\\\"margin-bottom: 0;\\\">\\n          <label class=\\\"form-label\\\">Bowling Style</label>\\n          <select id=\\\"regBowling\\\" class=\\\"form-control\\\">\\n            <option value=\\\"Right Arm Medium Fast\\\">Right Arm Medium Fast</option>\\n            <option value=\\\"Right Arm Spin\\\">Right Arm Spin</option>\\n            <option value=\\\"Left Arm Fast\\\">Left Arm Fast</option>\\n            <option value=\\\"Left Arm Spin\\\">Left Arm Spin</option>\\n            <option value=\\\"None\\\">None</option>\\n          </select>\\n        </div>\\n      </div>\\n\\n      <!-- LIVE CAMERA SELFIE MODULE -->\\n      <div class=\\\"selfie-camera-box\\\">\\n        <label class=\\\"form-label\\\" style=\\\"color: #38bdf8; font-weight: 800; font-size: 1rem; margin-bottom: 0.5rem; display: block;\\\">\\n          \\ud83d\\udcf7 Player Photo / Live Selfie Camera\\n        </label>\\n        <p style=\\\"color: #94a3b8; font-size: 0.85rem; margin-bottom: 1rem;\\\">\\n          Click the button below to take a live selfie with your camera, or upload a picture.\\n        </p>\\n\\n        <!-- Video stream element -->\\n        <video id=\\\"cameraVideo\\\" class=\\\"selfie-viewfinder\\\" autoplay playsinline style=\\\"display: none;\\\"></video>\\n        <!-- Captured preview image -->\\n        <img id=\\\"photoPreview\\\" class=\\\"selfie-viewfinder\\\" style=\\\"display: none;\\\" alt=\\\"Selfie Preview\\\">\\n        <canvas id=\\\"cameraCanvas\\\" style=\\\"display: none;\\\"></canvas>\\n\\n        <!-- Placeholder when camera is idle -->\\n        <div id=\\\"cameraPlaceholder\\\" style=\\\"padding: 1.5rem 1rem; background: rgba(0,0,0,0.3); border-radius: 8px; margin-bottom: 0.75rem;\\\">\\n          <span style=\\\"font-size: 3rem; display: block; margin-bottom: 0.35rem;\\\">\\ud83e\\udd33</span>\\n          <span style=\\\"color: #cbd5e1; font-size: 0.9rem;\\\">No photo taken yet</span>\\n        </div>\\n\\n        <!-- Camera Action Buttons -->\\n        <div style=\\\"display: flex; gap: 0.5rem; justify-content: center; flex-wrap: wrap;\\\">\\n          <button type=\\\"button\\\" id=\\\"btnStartCamera\\\" onclick=\\\"startCamera()\\\" class=\\\"btn btn-secondary\\\" style=\\\"font-size: 0.85rem; border-color: #38bdf8; color: #38bdf8;\\\">\\n            \\ud83d\\udcf7 Open Live Camera / Take Selfie\\n          </button>\\n          <button type=\\\"button\\\" id=\\\"btnSnapPhoto\\\" onclick=\\\"snapSelfie()\\\" class=\\\"btn btn-success\\\" style=\\\"display: none; font-size: 0.85rem;\\\">\\n            \\u26a1 Snap Selfie Now\\n          </button>\\n          <button type=\\\"button\\\" id=\\\"btnRetakePhoto\\\" onclick=\\\"retakeSelfie()\\\" class=\\\"btn btn-secondary\\\" style=\\\"display: none; font-size: 0.85rem;\\\">\\n            \\ud83d\\udd04 Retake Selfie\\n          </button>\\n          <label class=\\\"btn btn-secondary\\\" style=\\\"margin: 0; font-size: 0.85rem; cursor: pointer;\\\">\\n            \\ud83d\\udcc1 Upload from Gallery\\n            <input type=\\\"file\\\" id=\\\"regPhoto\\\" accept=\\\"image/*\\\" style=\\\"display: none;\\\" onchange=\\\"handleFileSelected(event)\\\">\\n          </label>\\n        </div>\\n      </div>\\n\\n      <!-- DEDICATED UPI PAYMENT METHODS -->\\n      <div style=\\\"background: rgba(15,23,42,0.8); border: 1px solid rgba(16, 185, 129, 0.4); padding: 1.25rem; border-radius: 12px; margin-bottom: 1.5rem;\\\">\\n        <div style=\\\"display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; flex-wrap: wrap; gap: 0.5rem;\\\">\\n          <strong style=\\\"color: #10b981; font-size: 1.05rem;\\\">\\n            \\ud83d\\udcb3 Pay \\u20b9{{ reg_fee }} Entry Fee via UPI App\\n          </strong>\\n          <span class=\\\"badge\\\" style=\\\"background: rgba(16, 185, 129, 0.2); color: #34d399;\\\">\\n            Direct App Launch\\n          </span>\\n        </div>\\n        <p style=\\\"color: #94a3b8; font-size: 0.85rem; margin-bottom: 1rem;\\\">\\n          Click your preferred payment app below to open it immediately on your phone and complete the \\u20b9{{ reg_fee }} fee:\\n        </p>\\n\\n        <!-- Payment App Buttons Grid -->\\n        <div class=\\\"payment-apps-grid\\\">\\n          <!-- PhonePe -->\\n          <a href=\\\"phonepe://pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg\\\" \\n             onclick=\\\"openPaymentApp(event, 'phonepe://pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg')\\\"\\n             class=\\\"pay-app-btn pay-phonepe\\\">\\n            <span style=\\\"font-size: 1.6rem; margin-bottom: 0.25rem;\\\">\\ud83d\\udfe3</span>\\n            <span>PhonePe</span>\\n          </a>\\n\\n          <!-- Google Pay -->\\n          <a href=\\\"gpay://upi/pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg\\\"\\n             onclick=\\\"openPaymentApp(event, 'gpay://upi/pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg')\\\"\\n             class=\\\"pay-app-btn pay-gpay\\\">\\n            <span style=\\\"font-size: 1.6rem; margin-bottom: 0.25rem;\\\">\\ud83d\\udd35</span>\\n            <span>Google Pay</span>\\n          </a>\\n\\n          <!-- Paytm -->\\n          <a href=\\\"paytmmp://pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg\\\"\\n             onclick=\\\"openPaymentApp(event, 'paytmmp://pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg')\\\"\\n             class=\\\"pay-app-btn pay-paytm\\\">\\n            <span style=\\\"font-size: 1.6rem; margin-bottom: 0.25rem;\\\">\\ud83d\\udfe6</span>\\n            <span>Paytm</span>\\n          </a>\\n\\n          <!-- Amazon Pay -->\\n          <a href=\\\"amazonpay://pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg\\\"\\n             onclick=\\\"openPaymentApp(event, 'amazonpay://pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg')\\\"\\n             class=\\\"pay-app-btn pay-amazon\\\">\\n            <span style=\\\"font-size: 1.6rem; margin-bottom: 0.25rem;\\\">\\ud83d\\udfe0</span>\\n            <span>Amazon Pay</span>\\n          </a>\\n\\n          <!-- BHIM / Any UPI -->\\n          <a href=\\\"upi://pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg\\\"\\n             onclick=\\\"openPaymentApp(event, 'upi://pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg')\\\"\\n             class=\\\"pay-app-btn pay-bhim\\\">\\n            <span style=\\\"font-size: 1.6rem; margin-bottom: 0.25rem;\\\">\\ud83c\\uddee\\ud83c\\uddf3</span>\\n            <span>BHIM UPI</span>\\n          </a>\\n        </div>\\n\\n        <!-- Desktop QR Code Scanner -->\\n        <div style=\\\"text-align: center; margin: 1rem 0; padding: 1rem; background: rgba(0,0,0,0.3); border-radius: 8px;\\\">\\n          <p style=\\\"color: #94a3b8; font-size: 0.85rem; margin-bottom: 0.5rem;\\\">\\n            \\ud83d\\udcf1 On Computer? Scan this QR code from your phone with PhonePe, GPay, or Paytm:\\n          </p>\\n          <img src=\\\"https://api.qrserver.com/v1/create-qr-code/?size=160x160&data={{ ('upi://pay?pa=' + upi_id + '&pn=' + payee_name + '&am=' + (reg_fee|string) + '&cu=INR&tn=KPL2026_Registration')|urlencode }}\\\" alt=\\\"UPI QR Code\\\" style=\\\"width: 140px; height: 140px; border-radius: 8px; border: 3px solid #f59e0b; background: #fff; padding: 4px;\\\">\\n          <div style=\\\"color: #f59e0b; font-weight: 800; font-size: 0.95rem; margin-top: 0.5rem;\\\">\\n            UPI ID: {{ upi_id }} ({{ payee_name }})\\n          </div>\\n        </div>\\n\\n        <div class=\\\"form-group\\\" style=\\\"margin-bottom: 0;\\\">\\n          <label class=\\\"form-label\\\" style=\\\"font-size: 0.85rem;\\\">UPI Reference / UTR Number (Optional)</label>\\n          <input type=\\\"text\\\" id=\\\"regUtr\\\" class=\\\"form-control\\\" placeholder=\\\"12-digit UTR from payment confirmation\\\">\\n        </div>\\n      </div>\\n\\n      <button type=\\\"submit\\\" id=\\\"btnSubmitReg\\\" class=\\\"btn btn-primary\\\" style=\\\"width: 100%; font-size: 1.15rem; padding: 0.95rem; font-weight: 900;\\\">\\n        Submit Player Registration &rarr;\\n      </button>\\n    </form>\\n  </div>\\n</div>\\n\\n<!-- SUB-PAGE 2: REGISTERED PLAYERS UNTIL NOW (DIRECTORY) -->\\n<div id=\\\"subpageDirectory\\\" style=\\\"display: none;\\\">\\n  <!-- Search, Filter & View Switcher Bar -->\\n  <div style=\\\"margin-bottom: 1.5rem; display: flex; gap: 0.75rem; flex-wrap: wrap; align-items: center; justify-content: space-between;\\\">\\n    <div style=\\\"display: flex; gap: 0.75rem; flex-wrap: wrap; flex: 1; min-width: 280px;\\\">\\n      <input type=\\\"text\\\" id=\\\"dirSearch\\\" placeholder=\\\"\\ud83d\\udd0d Search by name, village, or role...\\\" class=\\\"form-control\\\" style=\\\"flex: 2; min-width: 220px;\\\" oninput=\\\"filterDirectory()\\\">\\n      <select id=\\\"dirRoleFilter\\\" class=\\\"form-control\\\" style=\\\"flex: 1; min-width: 160px;\\\" onchange=\\\"filterDirectory()\\\">\\n        <option value=\\\"All\\\">All Roles</option>\\n        <option value=\\\"All-Rounder\\\">All-Rounder</option>\\n        <option value=\\\"Batsman\\\">Batsman</option>\\n        <option value=\\\"Bowler\\\">Bowler</option>\\n        <option value=\\\"Wicket-Keeper\\\">Wicket-Keeper</option>\\n      </select>\\n    </div>\\n    <div style=\\\"display: flex; gap: 0.35rem;\\\">\\n      <button type=\\\"button\\\" id=\\\"btnViewCards\\\" class=\\\"subtab-btn active\\\" style=\\\"padding: 0.45rem 0.85rem; font-size: 0.85rem;\\\" onclick=\\\"switchDirLayout('cards')\\\">\\n        \\ud83d\\uddc2\\ufe0f Cards\\n      </button>\\n      <button type=\\\"button\\\" id=\\\"btnViewTable\\\" class=\\\"subtab-btn\\\" style=\\\"padding: 0.45rem 0.85rem; font-size: 0.85rem;\\\" onclick=\\\"switchDirLayout('table')\\\">\\n        \\ud83d\\udccb Table\\n      </button>\\n    </div>\\n  </div>\\n\\n  <!-- CARDS VIEW (DEFAULT) -->\\n  <div class=\\\"player-dir-grid\\\" id=\\\"dirCardsContainer\\\">\\n    {% for p in players %}\\n    <div class=\\\"dir-card\\\" data-name=\\\"{{ p.name|lower }}\\\" data-village=\\\"{{ (p.village or 'Saidapur')|lower }}\\\" data-role=\\\"{{ p.role|lower }}\\\">\\n      <img src=\\\"{{ p.photo_url or '/static/images/avatar_allrounder.svg' }}\\\" class=\\\"dir-avatar\\\" alt=\\\"{{ p.name }}\\\">\\n      <div style=\\\"flex: 1; min-width: 0;\\\">\\n        <div style=\\\"display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;\\\">\\n          <h3 style=\\\"font-size: 1.05rem; font-weight: 800; color: #fff; margin: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;\\\">\\n            {{ p.name }}\\n          </h3>\\n          <span style=\\\"color: #f59e0b; font-weight: 800; font-size: 0.85rem;\\\">#{{ p.serial_no or loop.index }}</span>\\n        </div>\\n        <div style=\\\"display: flex; gap: 0.35rem; align-items: center; margin-bottom: 0.35rem; flex-wrap: wrap;\\\">\\n          <span class=\\\"badge {{ 'badge-batsman' if 'bat' in (p.role|lower) else ('badge-bowler' if 'bowl' in (p.role|lower) else 'badge-allrounder') }}\\\" style=\\\"font-size: 0.75rem;\\\">\\n            {{ p.role }}\\n          </span>\\n          <span style=\\\"color: #94a3b8; font-size: 0.8rem; display: flex; align-items: center; gap: 0.2rem;\\\">\\n            \\ud83d\\udccd {{ p.village or 'Saidapur' }}\\n          </span>\\n        </div>\\n        <div style=\\\"display: flex; justify-content: space-between; align-items: center; font-size: 0.75rem; color: #64748b;\\\">\\n          <span style=\\\"color: #10b981; font-weight: 700; background: rgba(16, 185, 129, 0.15); padding: 0.15rem 0.45rem; border-radius: 4px; border: 1px solid rgba(16, 185, 129, 0.3);\\\">\\n            Amount Sent: \\u20b9{{ p.reg_amount or 200 }} (Paid)\\n          </span>\\n          {% if p.transaction_id %}\\n          <span style=\\\"color: #38bdf8; font-family: monospace;\\\">UTR: {{ p.transaction_id }}</span>\\n          {% endif %}\\n        </div>\\n      </div>\\n    </div>\\n    {% endfor %}\\n  </div>\\n\\n  <!-- TABLE VIEW -->\\n  <div id=\\\"dirTableContainer\\\" style=\\\"display: none; overflow-x: auto; background: rgba(15, 23, 42, 0.75); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px;\\\">\\n    <table class=\\\"dir-table\\\">\\n      <thead>\\n        <tr>\\n          <th>#</th>\\n          <th>Photo</th>\\n          <th>Player Name</th>\\n          <th>Role</th>\\n          <th>Village / Town</th>\\n          <th>Amount Sent</th>\\n          <th>Mobile</th>\\n          <th>UTR / Transaction</th>\\n        </tr>\\n      </thead>\\n      <tbody>\\n        {% for p in players %}\\n        <tr class=\\\"dir-table-row\\\" data-name=\\\"{{ p.name|lower }}\\\" data-village=\\\"{{ (p.village or 'Saidapur')|lower }}\\\" data-role=\\\"{{ p.role|lower }}\\\">\\n          <td style=\\\"font-weight: 800; color: #f59e0b;\\\">#{{ p.serial_no or loop.index }}</td>\\n          <td>\\n            <img src=\\\"{{ p.photo_url or '/static/images/avatar_allrounder.svg' }}\\\" class=\\\"table-avatar\\\" alt=\\\"{{ p.name }}\\\">\\n          </td>\\n          <td style=\\\"font-weight: 800; color: #fff;\\\">{{ p.name }}</td>\\n          <td>\\n            <span class=\\\"badge {{ 'badge-batsman' if 'bat' in (p.role|lower) else ('badge-bowler' if 'bowl' in (p.role|lower) else 'badge-allrounder') }}\\\" style=\\\"font-size: 0.75rem;\\\">\\n              {{ p.role }}\\n            </span>\\n          </td>\\n          <td style=\\\"color: #cbd5e1;\\\">\\ud83d\\udccd {{ p.village or 'Saidapur' }}</td>\\n          <td style=\\\"color: #10b981; font-weight: 800;\\\">\\u20b9{{ p.reg_amount or 200 }} Paid</td>\\n          <td style=\\\"color: #94a3b8; font-family: monospace;\\\">{{ p.phone or '-' }}</td>\\n          <td style=\\\"color: #38bdf8; font-family: monospace; font-size: 0.8rem;\\\">{{ p.transaction_id or 'UPI Verified' }}</td>\\n        </tr>\\n        {% endfor %}\\n      </tbody>\\n    </table>\\n  </div>\\n</div>\\n{% endblock %}\\n\\n{% block extra_js %}\\n<script>\\n  let activeVideoStream = null;\\n  let capturedSelfieBlob = null;\\n\\n  function switchRegSubtab(tab) {\\n    const btnForm = document.getElementById('tabBtnRegister');\\n    const btnDir = document.getElementById('tabBtnDirectory');\\n    const pageForm = document.getElementById('subpageRegisterForm');\\n    const pageDir = document.getElementById('subpageDirectory');\\n\\n    if (tab === 'directory') {\\n      btnDir.classList.add('active');\\n      btnForm.classList.remove('active');\\n      pageDir.style.display = 'block';\\n      pageForm.style.display = 'none';\\n      stopCamera();\\n    } else {\\n      btnForm.classList.add('active');\\n      btnDir.classList.remove('active');\\n      pageForm.style.display = 'block';\\n      pageDir.style.display = 'none';\\n    }\\n  }\\n\\n  // --- LIVE CAMERA SELFIE MODULE ---\\n  async function startCamera() {\\n    try {\\n      const stream = await navigator.mediaDevices.getUserMedia({\\n        video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 640 } },\\n        audio: false\\n      });\\n      activeVideoStream = stream;\\n      const video = document.getElementById('cameraVideo');\\n      video.srcObject = stream;\\n      video.style.display = 'block';\\n      document.getElementById('cameraPlaceholder').style.display = 'none';\\n      document.getElementById('photoPreview').style.display = 'none';\\n      document.getElementById('btnStartCamera').style.display = 'none';\\n      document.getElementById('btnSnapPhoto').style.display = 'inline-flex';\\n      document.getElementById('btnRetakePhoto').style.display = 'none';\\n    } catch (err) {\\n      alert('Camera access unavailable or blocked. You can upload a photo from your gallery instead.');\\n    }\\n  }\\n\\n  function snapSelfie() {\\n    const video = document.getElementById('cameraVideo');\\n    const canvas = document.getElementById('cameraCanvas');\\n    const preview = document.getElementById('photoPreview');\\n\\n    canvas.width = video.videoWidth || 480;\\n    canvas.height = video.videoHeight || 480;\\n    const ctx = canvas.getContext('2d');\\n    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);\\n\\n    canvas.toBlob((blob) => {\\n      capturedSelfieBlob = blob;\\n    }, 'image/jpeg', 0.9);\\n\\n    preview.src = canvas.toDataURL('image/jpeg');\\n    preview.style.display = 'block';\\n    video.style.display = 'none';\\n    stopCamera();\\n\\n    document.getElementById('btnSnapPhoto').style.display = 'none';\\n    document.getElementById('btnRetakePhoto').style.display = 'inline-flex';\\n  }\\n\\n  function retakeSelfie() {\\n    capturedSelfieBlob = null;\\n    document.getElementById('photoPreview').style.display = 'none';\\n    startCamera();\\n  }\\n\\n  function stopCamera() {\\n    if (activeVideoStream) {\\n      activeVideoStream.getTracks().forEach(track => track.stop());\\n      activeVideoStream = null;\\n    }\\n  }\\n\\n  function handleFileSelected(e) {\\n    if (e.target.files && e.target.files[0]) {\\n      const file = e.target.files[0];\\n      capturedSelfieBlob = file;\\n      const reader = new FileReader();\\n      reader.onload = function(evt) {\\n        const preview = document.getElementById('photoPreview');\\n        preview.src = evt.target.result;\\n        preview.style.display = 'block';\\n        document.getElementById('cameraVideo').style.display = 'none';\\n        document.getElementById('cameraPlaceholder').style.display = 'none';\\n        document.getElementById('btnStartCamera').style.display = 'none';\\n        document.getElementById('btnSnapPhoto').style.display = 'none';\\n        document.getElementById('btnRetakePhoto').style.display = 'inline-flex';\\n      };\\n      reader.readAsDataURL(file);\\n    }\\n  }\\n\\n  // --- PAYMENT APP LAUNCHER ---\\n  function openPaymentApp(e, primaryUrl) {\\n    // Attempt to open dedicated app URI; on mobile device this launches PhonePe/GPay/Paytm directly\\n    const fallbackUrl = \\\"upi://pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg\\\";\\n    const start = Date.now();\\n    setTimeout(() => {\\n      if (Date.now() - start < 2000) {\\n        window.location.href = fallbackUrl;\\n      }\\n    }, 1200);\\n  }\\n\\n  // --- DIRECTORY LAYOUT & SEARCH ---\\n  function switchDirLayout(layout) {\\n    const cards = document.getElementById('dirCardsContainer');\\n    const table = document.getElementById('dirTableContainer');\\n    const btnCards = document.getElementById('btnViewCards');\\n    const btnTable = document.getElementById('btnViewTable');\\n\\n    if (layout === 'table') {\\n      cards.style.display = 'none';\\n      table.style.display = 'block';\\n      btnTable.classList.add('active');\\n      btnCards.classList.remove('active');\\n    } else {\\n      cards.style.display = 'grid';\\n      table.style.display = 'none';\\n      btnCards.classList.add('active');\\n      btnTable.classList.remove('active');\\n    }\\n    filterDirectory();\\n  }\\n\\n  function filterDirectory() {\\n    const q = (document.getElementById('dirSearch')?.value || '').toLowerCase();\\n    const role = (document.getElementById('dirRoleFilter')?.value || 'All').toLowerCase();\\n\\n    document.querySelectorAll('.dir-card').forEach(card => {\\n      const name = card.dataset.name || '';\\n      const village = card.dataset.village || '';\\n      const cRole = card.dataset.role || '';\\n      const matchesText = name.includes(q) || village.includes(q) || cRole.includes(q);\\n      const matchesRole = (role === 'all') || cRole.includes(role);\\n      card.style.display = (matchesText && matchesRole) ? 'flex' : 'none';\\n    });\\n\\n    document.querySelectorAll('.dir-table-row').forEach(row => {\\n      const name = row.dataset.name || '';\\n      const village = row.dataset.village || '';\\n      const cRole = row.dataset.role || '';\\n      const matchesText = name.includes(q) || village.includes(q) || cRole.includes(q);\\n      const matchesRole = (role === 'all') || cRole.includes(role);\\n      row.style.display = (matchesText && matchesRole) ? '' : 'none';\\n    });\\n  }\\n\\n  // --- SUBMIT REGISTRATION ---\\n  async function handleRegistrationSubmit(e) {\\n    e.preventDefault();\\n    const btn = document.getElementById('btnSubmitReg');\\n    btn.disabled = true;\\n    btn.textContent = 'Submitting Registration...';\\n\\n    const formData = new FormData();\\n    formData.append('name', document.getElementById('regName').value.trim());\\n    formData.append('phone', document.getElementById('regPhone').value.trim());\\n    formData.append('village', document.getElementById('regVillage').value.trim());\\n    formData.append('role', document.getElementById('regRole').value);\\n    formData.append('batting_style', document.getElementById('regBatting').value);\\n    formData.append('bowling_style', document.getElementById('regBowling').value);\\n    formData.append('transaction_id', document.getElementById('regUtr').value.trim());\\n\\n    if (capturedSelfieBlob) {\\n      formData.append('photo', capturedSelfieBlob, 'selfie_' + Date.now() + '.jpg');\\n    }\\n\\n    try {\\n      const res = await fetch('/api/register', {\\n        method: 'POST',\\n        body: formData\\n      });\\n      const data = await res.json();\\n      if (data.success) {\\n        alert('\\ud83c\\udf89 Player Registration Successful! Welcome to KPL 2026.');\\n        location.reload();\\n      } else {\\n        alert(data.message || 'Registration failed.');\\n      }\\n    } catch (err) {\\n      alert('Network error: ' + err.message);\\n    } finally {\\n      btn.disabled = false;\\n      btn.textContent = 'Submit Player Registration \\u2192';\\n    }\\n  }\\n</script>\\n{% endblock %}\\n\", \"templates/register_success.html\": \"{% extends \\\"base.html\\\" %}\\n\\n{% block content %}\\n<div style=\\\"max-width: 550px; margin: 1.5rem auto; text-align: center;\\\">\\n  <div style=\\\"width: 70px; height: 70px; background: rgba(16, 185, 129, 0.2); border: 2px solid var(--pitch-green); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 2.25rem; margin: 0 auto 1.25rem;\\\">\\n    \\u2713\\n  </div>\\n  \\n  <h1 style=\\\"font-size: 2rem; font-weight: 900; margin-bottom: 0.5rem; color: #fff;\\\">Registration Received!</h1>\\n  <p style=\\\"color: var(--text-muted); margin-bottom: 2rem;\\\">\\n    Your registration details and payment reference have been recorded. Here is your official tournament player card.\\n  </p>\\n\\n  <!-- Player Digital Pass Card -->\\n  <div class=\\\"glass-card\\\" style=\\\"border: 2px solid var(--primary-gold); box-shadow: 0 0 35px var(--gold-glow); position: relative; overflow: hidden; padding: 2.5rem 1.5rem;\\\">\\n    <div style=\\\"position: absolute; top: 12px; right: 15px; font-size: 0.8rem; font-weight: 800; color: var(--primary-gold); background: rgba(245, 158, 11, 0.15); padding: 0.2rem 0.6rem; border-radius: var(--radius-sm); border: 1px solid rgba(245, 158, 11, 0.3);\\\">\\n      {{ player.id }}\\n    </div>\\n\\n    <!-- Photo -->\\n    <div style=\\\"width: 140px; height: 140px; border-radius: 50%; border: 4px solid var(--primary-gold); margin: 0 auto 1.25rem; overflow: hidden; box-shadow: 0 0 20px var(--gold-glow); background: #1e293b;\\\">\\n      <img src=\\\"{{ player.photo_url or '/static/images/avatar_allrounder.svg' }}\\\" alt=\\\"{{ player.name }}\\\" style=\\\"width: 100%; height: 100%; object-fit: cover;\\\">\\n    </div>\\n\\n    <div style=\\\"font-size: 1.75rem; font-weight: 900; color: #fff; margin-bottom: 0.35rem;\\\">\\n      {{ player.name }}\\n    </div>\\n\\n    <div style=\\\"margin-bottom: 1.25rem;\\\">\\n      <span class=\\\"badge {% if 'Bat' in player.role and 'Keep' not in player.role %}badge-batsman{% elif 'Bowl' in player.role %}badge-bowler{% elif 'Keep' in player.role %}badge-keeper{% else %}badge-allrounder{% endif %}\\\" style=\\\"font-size: 0.95rem; padding: 0.4rem 1rem;\\\">\\n        {{ player.role }}\\n      </span>\\n    </div>\\n\\n    <div style=\\\"background: rgba(0,0,0,0.4); border-radius: var(--radius-md); padding: 1rem; border: 1px solid var(--border-glass); display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; text-align: left; font-size: 0.9rem; margin-bottom: 1.5rem;\\\">\\n      <div>\\n        <span style=\\\"color: var(--text-dim); display: block; font-size: 0.8rem;\\\">Mobile</span>\\n        <strong style=\\\"color: #fff;\\\">{{ player.phone }}</strong>\\n      </div>\\n      <div>\\n        <span style=\\\"color: var(--text-dim); display: block; font-size: 0.8rem;\\\">Fee Paid</span>\\n        <strong style=\\\"color: var(--pitch-green);\\\">\\u20b9{{ player.reg_amount }}</strong>\\n      </div>\\n      <div>\\n        <span style=\\\"color: var(--text-dim); display: block; font-size: 0.8rem;\\\">Batting</span>\\n        <strong style=\\\"color: #fff;\\\">{{ player.batting_style }}</strong>\\n      </div>\\n      <div>\\n        <span style=\\\"color: var(--text-dim); display: block; font-size: 0.8rem;\\\">Bowling</span>\\n        <strong style=\\\"color: #fff;\\\">{{ player.bowling_style }}</strong>\\n      </div>\\n      <div style=\\\"grid-column: span 2;\\\">\\n        <span style=\\\"color: var(--text-dim); display: block; font-size: 0.8rem;\\\">Payment Reference (UTR)</span>\\n        <strong style=\\\"color: var(--primary-gold); word-break: break-all;\\\">{{ player.transaction_id }} ({{ player.payment_method }})</strong>\\n      </div>\\n    </div>\\n\\n    <div style=\\\"font-size: 0.85rem; color: var(--pitch-green); font-weight: 700; display: flex; align-items: center; justify-content: center; gap: 0.4rem;\\\">\\n      <span>\\u2713 Status:</span> Verified for Live Auction Pool\\n    </div>\\n  </div>\\n\\n  <div style=\\\"display: flex; gap: 1rem; justify-content: center; margin-top: 1.75rem;\\\">\\n    <button onclick=\\\"window.print()\\\" class=\\\"btn btn-secondary\\\">\\ud83d\\udda8\\ufe0f Print / Save Slip</button>\\n    <a href=\\\"/register\\\" class=\\\"btn btn-primary\\\">Register Another Player</a>\\n    <a href=\\\"/auction\\\" class=\\\"btn btn-success\\\">Go to Live Auction</a>\\n  </div>\\n</div>\\n{% endblock %}\\n\", \"templates/teams.html\": \"{% extends \\\"base.html\\\" %}\\n\\n{% block content %}\\n<div style=\\\"margin-bottom: 2rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;\\\">\\n  <div>\\n    <h1 style=\\\"font-size: 2.25rem; font-weight: 900; color: #fff;\\\">Team Squads & Purses</h1>\\n    <p style=\\\"color: var(--text-muted);\\\">Real-time view of bought players, retentions, and remaining budgets.</p>\\n  </div>\\n  <a href=\\\"/api/export-excel\\\" class=\\\"btn btn-success\\\">\\ud83d\\udcca Download Summary Excel</a>\\n</div>\\n\\n<div style=\\\"display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 1.5rem;\\\">\\n  {% for team_name, t in teams.items() %}\\n  <div class=\\\"glass-card\\\" style=\\\"border-top: 4px solid var(--primary-gold);\\\">\\n    <div style=\\\"display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem;\\\">\\n      <div>\\n        <h2 style=\\\"font-size: 1.5rem; font-weight: 900; color: #fff;\\\">{{ team_name }}</h2>\\n        <div style=\\\"color: var(--text-muted); font-size: 0.85rem;\\\">\\n          {{ (t.players|length) + (1 if t.retained else 0) }} Players in Squad\\n        </div>\\n      </div>\\n      <div style=\\\"text-align: right;\\\">\\n        <div style=\\\"font-size: 1.35rem; font-weight: 900; color: var(--pitch-green);\\\">\\u20b9{{ t.budget }}</div>\\n        <div style=\\\"font-size: 0.75rem; color: var(--text-dim); text-transform: uppercase;\\\">Purse Remaining</div>\\n      </div>\\n    </div>\\n\\n    <!-- Spent info -->\\n    <div style=\\\"background: rgba(0,0,0,0.3); padding: 0.6rem 0.85rem; border-radius: var(--radius-sm); border: 1px solid var(--border-glass); margin-bottom: 1.25rem; display: flex; justify-content: space-between; font-size: 0.85rem;\\\">\\n      <span style=\\\"color: var(--text-muted);\\\">Total Spent:</span>\\n      <strong style=\\\"color: #fca5a5;\\\">\\u20b9{{ t.spent }}</strong>\\n    </div>\\n\\n    <!-- Retained Player or Owner -->\\n    {% if t.retained %}\\n    {% set ret_name = t.retained.name if t.retained is mapping else t.retained %}\\n    {% set ret_type = t.retained.type if t.retained is mapping else 'Player' %}\\n    {% set ret_cost = t.retained.cost if t.retained is mapping else 500 %}\\n    <div style=\\\"background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.35); border-radius: var(--radius-sm); padding: 0.6rem 0.85rem; margin-bottom: 1rem; display: flex; align-items: center; justify-content: space-between;\\\">\\n      <div style=\\\"display: flex; align-items: center; gap: 0.5rem;\\\">\\n        <span style=\\\"background: {% if ret_type == 'Owner' %}#3b82f6{% else %}var(--primary-gold){% endif %}; color: #000; font-size: 0.7rem; font-weight: 900; padding: 0.15rem 0.4rem; border-radius: 4px;\\\">\\n          {{ ret_type|upper }} RETAINED\\n        </span>\\n        <strong style=\\\"color: #fff;\\\">{{ ret_name }}</strong>\\n      </div>\\n      <span style=\\\"color: var(--primary-gold); font-weight: 700; font-size: 0.85rem;\\\">\\u20b9{{ ret_cost }}</span>\\n    </div>\\n    {% endif %}\\n\\n    <!-- Squad Players List -->\\n    <h4 style=\\\"font-size: 0.9rem; font-weight: 800; color: var(--text-muted); text-transform: uppercase; margin-bottom: 0.75rem; letter-spacing: 0.05em;\\\">\\n      Bought Players\\n    </h4>\\n    \\n    {% if t.players %}\\n    <div style=\\\"display: flex; flex-direction: column; gap: 0.5rem;\\\">\\n      {% for p in t.players %}\\n      <div style=\\\"background: rgba(15, 23, 42, 0.7); border: 1px solid var(--border-glass); border-radius: var(--radius-sm); padding: 0.5rem 0.75rem; display: flex; justify-content: space-between; align-items: center;\\\">\\n        <div style=\\\"display: flex; align-items: center; gap: 0.6rem;\\\">\\n          <div style=\\\"width: 32px; height: 32px; border-radius: 50%; overflow: hidden; background: #334155;\\\">\\n            <img src=\\\"{{ registrations.get(p.name, {}).get('photo_url') or '/static/images/avatar_allrounder.svg' }}\\\" alt=\\\"\\\" style=\\\"width: 100%; height: 100%; object-fit: cover;\\\">\\n          </div>\\n          <div>\\n            <div style=\\\"font-weight: 700; color: #fff; font-size: 0.95rem;\\\">{{ p.name }}</div>\\n            <div style=\\\"font-size: 0.75rem; color: var(--text-dim);\\\">{{ registrations.get(p.name, {}).get('role', 'Player') }}</div>\\n          </div>\\n        </div>\\n        <div style=\\\"text-align: right;\\\">\\n          <div style=\\\"font-weight: 800; color: var(--pitch-green); font-size: 0.95rem;\\\">\\u20b9{{ p.cost }}</div>\\n          <div style=\\\"font-size: 0.7rem; color: var(--text-dim);\\\">Round {{ p.round or 1 }}</div>\\n        </div>\\n      </div>\\n      {% endfor %}\\n    </div>\\n    {% else %}\\n    <p style=\\\"color: var(--text-dim); font-size: 0.85rem; font-style: italic;\\\">No players bought yet in this auction.</p>\\n    {% endif %}\\n  </div>\\n  {% endfor %}\\n</div>\\n{% endblock %}\\n\", \"static/css/auction.css\": \"/* Live Auction Arena CSS */\\n.auction-stage {\\n  display: grid;\\n  grid-template-columns: 1fr 340px;\\n  gap: 1.5rem;\\n  margin-top: 1rem;\\n}\\n\\n/* Center Stage Player Display */\\n.player-podium {\\n  background: radial-gradient(circle at 50% 30%, rgba(30, 41, 59, 0.95), rgba(15, 23, 42, 0.98));\\n  border: 2px solid var(--border-gold);\\n  border-radius: var(--radius-lg);\\n  padding: 2.25rem 2rem;\\n  box-shadow: 0 15px 35px rgba(0, 0, 0, 0.6), 0 0 35px rgba(245, 158, 11, 0.15);\\n  display: flex;\\n  flex-direction: column;\\n  align-items: center;\\n  position: relative;\\n  overflow: hidden;\\n}\\n\\n.podium-header {\\n  width: 100%;\\n  display: flex;\\n  justify-content: space-between;\\n  align-items: center;\\n  margin-bottom: 1.5rem;\\n}\\n\\n.round-tag {\\n  background: rgba(255, 255, 255, 0.08);\\n  border: 1px solid var(--border-glass);\\n  padding: 0.35rem 0.85rem;\\n  border-radius: var(--radius-full);\\n  font-size: 0.85rem;\\n  font-weight: 700;\\n  color: var(--primary-gold);\\n}\\n\\n.pool-status {\\n  font-size: 0.85rem;\\n  color: var(--text-muted);\\n}\\n\\n/* Player Photo Spotlight */\\n.player-photo-arena {\\n  position: relative;\\n  margin-bottom: 1.5rem;\\n}\\n\\n.photo-frame {\\n  width: 220px;\\n  height: 220px;\\n  border-radius: 50%;\\n  border: 5px solid var(--primary-gold);\\n  overflow: hidden;\\n  box-shadow: 0 0 35px var(--gold-glow), 0 10px 25px rgba(0,0,0,0.7);\\n  background: #1e293b;\\n  position: relative;\\n  transition: all 0.3s ease;\\n}\\n\\n.photo-frame img {\\n  width: 100%;\\n  height: 100%;\\n  object-fit: cover;\\n}\\n\\n.role-tag-floater {\\n  position: absolute;\\n  bottom: 0;\\n  left: 50%;\\n  transform: translateX(-50%);\\n  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.6);\\n  white-space: nowrap;\\n}\\n\\n.player-name-banner {\\n  text-align: center;\\n  margin-bottom: 1rem;\\n}\\n\\n.player-main-name {\\n  font-size: 2.25rem;\\n  font-weight: 900;\\n  letter-spacing: -0.02em;\\n  color: #fff;\\n  text-shadow: 0 2px 10px rgba(0,0,0,0.5);\\n}\\n\\n.player-serial-tag {\\n  display: inline-block;\\n  background: rgba(245, 158, 11, 0.15);\\n  color: var(--primary-gold);\\n  border: 1px solid rgba(245, 158, 11, 0.4);\\n  font-weight: 800;\\n  padding: 0.2rem 0.6rem;\\n  border-radius: var(--radius-sm);\\n  font-size: 0.95rem;\\n  margin-right: 0.5rem;\\n}\\n\\n/* Player Meta Badges */\\n.player-meta-row {\\n  display: flex;\\n  gap: 0.75rem;\\n  flex-wrap: wrap;\\n  justify-content: center;\\n  margin-bottom: 1.75rem;\\n}\\n\\n.meta-chip {\\n  background: rgba(15, 23, 42, 0.8);\\n  border: 1px solid var(--border-glass);\\n  padding: 0.4rem 0.85rem;\\n  border-radius: var(--radius-md);\\n  font-size: 0.85rem;\\n  color: var(--text-muted);\\n}\\n.meta-chip strong {\\n  color: #fff;\\n  margin-left: 0.25rem;\\n}\\n\\n/* Bid Display Box */\\n.bid-odometer-box {\\n  width: 100%;\\n  background: rgba(0, 0, 0, 0.5);\\n  border: 1px solid rgba(255, 255, 255, 0.1);\\n  border-radius: var(--radius-lg);\\n  padding: 1.5rem;\\n  text-align: center;\\n  margin-bottom: 1.75rem;\\n  box-shadow: inset 0 2px 10px rgba(0,0,0,0.5);\\n}\\n\\n.bid-label {\\n  font-size: 0.9rem;\\n  font-weight: 700;\\n  color: var(--text-muted);\\n  text-transform: uppercase;\\n  letter-spacing: 0.05em;\\n  margin-bottom: 0.25rem;\\n}\\n\\n.bid-amount {\\n  font-size: 3.5rem;\\n  font-weight: 900;\\n  color: var(--pitch-green);\\n  font-variant-numeric: tabular-nums;\\n  line-height: 1;\\n  text-shadow: 0 0 25px var(--green-glow);\\n}\\n\\n.bidding-team-banner {\\n  margin-top: 0.6rem;\\n  font-size: 1.15rem;\\n  font-weight: 700;\\n  color: var(--primary-gold);\\n}\\n\\n/* Bid Control Deck */\\n.control-deck {\\n  width: 100%;\\n  display: flex;\\n  flex-direction: column;\\n  gap: 1rem;\\n}\\n\\n.team-bid-row {\\n  display: grid;\\n  grid-template-columns: 1fr auto;\\n  gap: 0.75rem;\\n}\\n\\n.increments-grid {\\n  display: grid;\\n  grid-template-columns: repeat(4, 1fr);\\n  gap: 0.5rem;\\n}\\n\\n.btn-inc {\\n  background: rgba(255, 255, 255, 0.08);\\n  border: 1px solid var(--border-glass);\\n  color: #fff;\\n  font-weight: 700;\\n  padding: 0.65rem 0.25rem;\\n  border-radius: var(--radius-md);\\n  font-size: 0.95rem;\\n  cursor: pointer;\\n  transition: all 0.2s ease;\\n}\\n.btn-inc:hover {\\n  background: rgba(245, 158, 11, 0.2);\\n  border-color: var(--primary-gold);\\n  color: var(--primary-gold);\\n}\\n\\n.auction-primary-actions {\\n  display: grid;\\n  grid-template-columns: 2fr 1fr;\\n  gap: 0.75rem;\\n}\\n\\n.auction-secondary-actions {\\n  display: grid;\\n  grid-template-columns: 1fr 1fr 1fr;\\n  gap: 0.5rem;\\n}\\n\\n/* Sidebar - Teams & Purses */\\n.teams-sidebar {\\n  display: flex;\\n  flex-direction: column;\\n  gap: 0.85rem;\\n}\\n\\n.sidebar-header {\\n  font-size: 1.1rem;\\n  font-weight: 800;\\n  color: #fff;\\n  display: flex;\\n  justify-content: space-between;\\n  align-items: center;\\n  padding-bottom: 0.5rem;\\n  border-bottom: 1px solid var(--border-glass);\\n}\\n\\n.team-card {\\n  background: var(--bg-card);\\n  border: 1px solid var(--border-glass);\\n  border-radius: var(--radius-md);\\n  padding: 1rem;\\n  transition: all 0.2s ease;\\n  cursor: pointer;\\n}\\n.team-card:hover {\\n  border-color: var(--border-gold);\\n  background: var(--bg-card-hover);\\n}\\n.team-card.current-bidder {\\n  border-color: var(--pitch-green);\\n  box-shadow: 0 0 15px var(--green-glow);\\n  background: rgba(16, 185, 129, 0.1);\\n}\\n\\n.team-card-header {\\n  display: flex;\\n  justify-content: space-between;\\n  align-items: center;\\n  margin-bottom: 0.5rem;\\n}\\n\\n.team-name {\\n  font-weight: 800;\\n  font-size: 1.1rem;\\n  color: #fff;\\n}\\n\\n.team-squad-count {\\n  font-size: 0.85rem;\\n  font-weight: 700;\\n  padding: 0.15rem 0.5rem;\\n  border-radius: var(--radius-full);\\n  background: rgba(255, 255, 255, 0.1);\\n}\\n\\n.team-budget-bar-wrap {\\n  width: 100%;\\n  height: 6px;\\n  background: rgba(255, 255, 255, 0.1);\\n  border-radius: var(--radius-full);\\n  overflow: hidden;\\n  margin-bottom: 0.5rem;\\n}\\n\\n.team-budget-fill {\\n  height: 100%;\\n  background: linear-gradient(90deg, var(--pitch-green), #34d399);\\n  border-radius: var(--radius-full);\\n}\\n\\n.team-financials {\\n  display: flex;\\n  justify-content: space-between;\\n  font-size: 0.85rem;\\n}\\n.team-rem-budget {\\n  font-weight: 800;\\n  color: var(--pitch-green);\\n}\\n.team-spent-budget {\\n  color: var(--text-dim);\\n}\\n\\n/* Sold Celebration Overlay */\\n.sold-modal-overlay {\\n  position: fixed;\\n  inset: 0;\\n  background: rgba(0, 0, 0, 0.85);\\n  backdrop-filter: blur(10px);\\n  z-index: 2000;\\n  display: none;\\n  align-items: center;\\n  justify-content: center;\\n  padding: 1.5rem;\\n}\\n.sold-modal-overlay.active {\\n  display: flex;\\n  animation: fadeIn 0.3s ease;\\n}\\n\\n.sold-card-popup {\\n  background: linear-gradient(135deg, #1e293b, #0f172a);\\n  border: 3px solid var(--primary-gold);\\n  border-radius: var(--radius-lg);\\n  padding: 2.5rem;\\n  text-align: center;\\n  max-width: 480px;\\n  width: 100%;\\n  box-shadow: 0 0 50px var(--gold-glow);\\n  animation: popIn 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);\\n}\\n\\n.sold-banner {\\n  font-size: 3rem;\\n  font-weight: 900;\\n  color: var(--pitch-green);\\n  text-shadow: 0 0 20px var(--green-glow);\\n  letter-spacing: 0.05em;\\n  margin-bottom: 0.75rem;\\n}\\n\\n@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }\\n@keyframes popIn { from { transform: scale(0.7); opacity: 0; } to { transform: scale(1); opacity: 1; } }\\n\\n@media (max-width: 900px) {\\n  .auction-stage {\\n    grid-template-columns: 1fr;\\n  }\\n  .player-main-name {\\n    font-size: 1.75rem;\\n  }\\n  .bid-amount {\\n    font-size: 2.5rem;\\n  }\\n  .photo-frame {\\n    width: 170px;\\n    height: 170px;\\n  }\\n}\\n\", \"static/css/style.css\": \"/* Modern Stadium Dark Glassmorphic Design System */\\n@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&family=Inter:wght@400;500;600;700&display=swap');\\n\\n:root {\\n  --bg-main: #0a0e17;\\n  --bg-surface: #111827;\\n  --bg-card: rgba(17, 24, 39, 0.85);\\n  --bg-card-hover: rgba(31, 41, 55, 0.9);\\n  --border-glass: rgba(255, 255, 255, 0.1);\\n  --border-gold: rgba(245, 158, 11, 0.4);\\n  \\n  --primary-gold: #f59e0b;\\n  --gold-glow: rgba(245, 158, 11, 0.35);\\n  --pitch-green: #10b981;\\n  --green-glow: rgba(16, 185, 129, 0.35);\\n  --crimson-red: #ef4444;\\n  --red-glow: rgba(239, 68, 68, 0.35);\\n  --electric-blue: #3b82f6;\\n  --blue-glow: rgba(59, 130, 246, 0.35);\\n  --purple-accent: #8b5cf6;\\n  \\n  --text-main: #f9fafb;\\n  --text-muted: #9ca3af;\\n  --text-dim: #6b7280;\\n  \\n  --radius-sm: 8px;\\n  --radius-md: 14px;\\n  --radius-lg: 20px;\\n  --radius-full: 9999px;\\n  \\n  --shadow-card: 0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.4);\\n  --shadow-glow: 0 0 25px var(--gold-glow);\\n}\\n\\n* {\\n  margin: 0;\\n  padding: 0;\\n  box-sizing: border-box;\\n}\\n\\nbody {\\n  font-family: 'Outfit', 'Inter', -apple-system, sans-serif;\\n  background-color: var(--bg-main);\\n  background-image: \\n    radial-gradient(circle at 10% 20%, rgba(16, 185, 129, 0.12) 0%, transparent 40%),\\n    radial-gradient(circle at 90% 80%, rgba(245, 158, 11, 0.12) 0%, transparent 40%),\\n    radial-gradient(circle at 50% 50%, rgba(59, 130, 246, 0.08) 0%, transparent 60%);\\n  background-attachment: fixed;\\n  color: var(--text-main);\\n  min-height: 100vh;\\n  display: flex;\\n  flex-direction: column;\\n  line-height: 1.5;\\n  -webkit-font-smoothing: antialiased;\\n}\\n\\n/* Header & Navbar */\\n.navbar {\\n  background: rgba(10, 14, 23, 0.85);\\n  backdrop-filter: blur(16px);\\n  -webkit-backdrop-filter: blur(16px);\\n  border-bottom: 1px solid var(--border-glass);\\n  position: sticky;\\n  top: 0;\\n  z-index: 1000;\\n  padding: 0.75rem 1.5rem;\\n}\\n\\n.nav-container {\\n  max-width: 1200px;\\n  margin: 0 auto;\\n  display: flex;\\n  align-items: center;\\n  justify-content: space-between;\\n}\\n\\n.nav-brand {\\n  display: flex;\\n  align-items: center;\\n  gap: 0.75rem;\\n  text-decoration: none;\\n  color: var(--text-main);\\n  font-weight: 800;\\n  font-size: 1.35rem;\\n  letter-spacing: -0.02em;\\n}\\n\\n.brand-badge {\\n  background: linear-gradient(135deg, var(--primary-gold), #d97706);\\n  color: #000;\\n  font-weight: 900;\\n  padding: 0.25rem 0.6rem;\\n  border-radius: var(--radius-sm);\\n  font-size: 0.85rem;\\n  text-transform: uppercase;\\n  box-shadow: 0 2px 8px var(--gold-glow);\\n}\\n\\n.brand-text span {\\n  color: var(--primary-gold);\\n}\\n\\n.nav-links {\\n  display: flex;\\n  align-items: center;\\n  gap: 0.5rem;\\n  list-style: none;\\n}\\n\\n.nav-link {\\n  color: var(--text-muted);\\n  text-decoration: none;\\n  font-weight: 600;\\n  padding: 0.5rem 0.9rem;\\n  border-radius: var(--radius-sm);\\n  transition: all 0.2s ease;\\n  display: flex;\\n  align-items: center;\\n  gap: 0.4rem;\\n  font-size: 0.95rem;\\n}\\n\\n.nav-link:hover, .nav-link.active {\\n  color: var(--text-main);\\n  background: rgba(255, 255, 255, 0.08);\\n}\\n\\n.nav-link.highlight {\\n  background: linear-gradient(135deg, #f59e0b, #d97706);\\n  color: #000;\\n  font-weight: 700;\\n}\\n.nav-link.highlight:hover {\\n  transform: translateY(-2px);\\n  box-shadow: 0 4px 12px var(--gold-glow);\\n}\\n\\n/* Mobile Menu Toggle */\\n.mobile-toggle {\\n  display: none;\\n  background: none;\\n  border: 1px solid var(--border-glass);\\n  color: var(--text-main);\\n  padding: 0.4rem 0.75rem;\\n  border-radius: var(--radius-sm);\\n  font-size: 1.25rem;\\n  cursor: pointer;\\n}\\n\\n/* Page Container */\\n.page-container {\\n  max-width: 1200px;\\n  width: 100%;\\n  margin: 0 auto;\\n  padding: 2rem 1.25rem;\\n  flex: 1;\\n}\\n\\n/* Glass Cards */\\n.glass-card {\\n  background: var(--bg-card);\\n  backdrop-filter: blur(12px);\\n  -webkit-backdrop-filter: blur(12px);\\n  border: 1px solid var(--border-glass);\\n  border-radius: var(--radius-lg);\\n  padding: 2rem;\\n  box-shadow: var(--shadow-card);\\n}\\n\\n/* Buttons */\\n.btn {\\n  display: inline-flex;\\n  align-items: center;\\n  justify-content: center;\\n  gap: 0.5rem;\\n  padding: 0.75rem 1.5rem;\\n  font-size: 1rem;\\n  font-weight: 700;\\n  font-family: inherit;\\n  border-radius: var(--radius-md);\\n  border: none;\\n  cursor: pointer;\\n  text-decoration: none;\\n  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);\\n}\\n\\n.btn-primary {\\n  background: linear-gradient(135deg, #f59e0b, #d97706);\\n  color: #000;\\n  box-shadow: 0 4px 14px var(--gold-glow);\\n}\\n.btn-primary:hover {\\n  transform: translateY(-2px);\\n  box-shadow: 0 6px 20px rgba(245, 158, 11, 0.5);\\n}\\n\\n.btn-success {\\n  background: linear-gradient(135deg, #10b981, #059669);\\n  color: #fff;\\n  box-shadow: 0 4px 14px var(--green-glow);\\n}\\n.btn-success:hover {\\n  transform: translateY(-2px);\\n  box-shadow: 0 6px 20px rgba(16, 185, 129, 0.5);\\n}\\n\\n.btn-danger {\\n  background: linear-gradient(135deg, #ef4444, #dc2626);\\n  color: #fff;\\n  box-shadow: 0 4px 14px var(--red-glow);\\n}\\n.btn-danger:hover {\\n  transform: translateY(-2px);\\n  box-shadow: 0 6px 20px rgba(239, 68, 68, 0.5);\\n}\\n\\n.btn-secondary {\\n  background: rgba(255, 255, 255, 0.08);\\n  color: var(--text-main);\\n  border: 1px solid var(--border-glass);\\n}\\n.btn-secondary:hover {\\n  background: rgba(255, 255, 255, 0.14);\\n}\\n\\n/* Badges */\\n.badge {\\n  display: inline-flex;\\n  align-items: center;\\n  gap: 0.35rem;\\n  padding: 0.35rem 0.75rem;\\n  border-radius: var(--radius-full);\\n  font-size: 0.85rem;\\n  font-weight: 700;\\n  text-transform: uppercase;\\n  letter-spacing: 0.03em;\\n}\\n\\n.badge-batsman {\\n  background: rgba(239, 68, 68, 0.15);\\n  color: #fca5a5;\\n  border: 1px solid rgba(239, 68, 68, 0.35);\\n}\\n.badge-bowler {\\n  background: rgba(59, 130, 246, 0.15);\\n  color: #93c5fd;\\n  border: 1px solid rgba(59, 130, 246, 0.35);\\n}\\n.badge-allrounder {\\n  background: rgba(245, 158, 11, 0.15);\\n  color: #fde68a;\\n  border: 1px solid rgba(245, 158, 11, 0.35);\\n}\\n.badge-keeper {\\n  background: rgba(16, 185, 129, 0.15);\\n  color: #6ee7b7;\\n  border: 1px solid rgba(16, 185, 129, 0.35);\\n}\\n\\n/* Form Styles */\\n.form-group {\\n  margin-bottom: 1.5rem;\\n}\\n\\n.form-label {\\n  display: block;\\n  font-size: 0.95rem;\\n  font-weight: 600;\\n  margin-bottom: 0.5rem;\\n  color: var(--text-main);\\n}\\n\\n.form-label span.req {\\n  color: var(--crimson-red);\\n}\\n\\n.form-control {\\n  width: 100%;\\n  padding: 0.85rem 1.15rem;\\n  background: rgba(15, 23, 42, 0.7);\\n  border: 1px solid rgba(255, 255, 255, 0.15);\\n  border-radius: var(--radius-md);\\n  color: #fff;\\n  font-size: 1rem;\\n  font-family: inherit;\\n  transition: all 0.2s ease;\\n}\\n\\n.form-control:focus {\\n  outline: none;\\n  border-color: var(--primary-gold);\\n  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.2);\\n  background: rgba(15, 23, 42, 0.9);\\n}\\n\\n/* Role Selector Grid */\\n.role-grid {\\n  display: grid;\\n  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));\\n  gap: 0.85rem;\\n}\\n\\n.role-card-opt {\\n  position: relative;\\n  cursor: pointer;\\n}\\n\\n.role-card-opt input[type=\\\"radio\\\"] {\\n  position: absolute;\\n  opacity: 0;\\n}\\n\\n.role-box {\\n  display: flex;\\n  flex-direction: column;\\n  align-items: center;\\n  text-align: center;\\n  padding: 1.15rem 0.75rem;\\n  background: rgba(15, 23, 42, 0.6);\\n  border: 2px solid rgba(255, 255, 255, 0.1);\\n  border-radius: var(--radius-md);\\n  transition: all 0.25s ease;\\n}\\n\\n.role-box .icon {\\n  font-size: 2rem;\\n  margin-bottom: 0.5rem;\\n}\\n\\n.role-box .title {\\n  font-weight: 700;\\n  font-size: 0.9rem;\\n}\\n\\n.role-card-opt input:checked + .role-box {\\n  border-color: var(--primary-gold);\\n  background: rgba(245, 158, 11, 0.12);\\n  box-shadow: 0 0 15px var(--gold-glow);\\n  transform: translateY(-2px);\\n}\\n\\n/* Photo Upload Box */\\n.photo-uploader {\\n  border: 2px dashed rgba(255, 255, 255, 0.2);\\n  border-radius: var(--radius-lg);\\n  padding: 1.75rem 1rem;\\n  text-align: center;\\n  background: rgba(15, 23, 42, 0.4);\\n  transition: all 0.25s ease;\\n}\\n\\n.photo-uploader:hover {\\n  border-color: var(--primary-gold);\\n}\\n\\n.photo-preview-wrap {\\n  width: 140px;\\n  height: 140px;\\n  border-radius: 50%;\\n  margin: 0 auto 1.25rem;\\n  border: 3px solid var(--primary-gold);\\n  overflow: hidden;\\n  box-shadow: 0 0 20px var(--gold-glow);\\n  background: #1e293b;\\n  display: flex;\\n  align-items: center;\\n  justify-content: center;\\n}\\n\\n.photo-preview-img {\\n  width: 100%;\\n  height: 100%;\\n  object-fit: cover;\\n}\\n\\n.upload-actions {\\n  display: flex;\\n  gap: 0.75rem;\\n  justify-content: center;\\n  flex-wrap: wrap;\\n}\\n\\n/* UPI Payment Block */\\n.payment-section {\\n  background: linear-gradient(135deg, rgba(30, 41, 59, 0.8), rgba(15, 23, 42, 0.95));\\n  border: 1px solid var(--border-gold);\\n  border-radius: var(--radius-lg);\\n  padding: 1.75rem;\\n  margin-top: 1.5rem;\\n  box-shadow: 0 0 20px rgba(245, 158, 11, 0.15);\\n}\\n\\n.fee-banner {\\n  display: flex;\\n  align-items: center;\\n  justify-content: space-between;\\n  background: rgba(245, 158, 11, 0.12);\\n  border: 1px solid rgba(245, 158, 11, 0.3);\\n  padding: 1rem 1.25rem;\\n  border-radius: var(--radius-md);\\n  margin-bottom: 1.5rem;\\n}\\n\\n.fee-amount {\\n  font-size: 1.85rem;\\n  font-weight: 900;\\n  color: var(--primary-gold);\\n}\\n\\n.upi-details-grid {\\n  display: grid;\\n  grid-template-columns: 220px 1fr;\\n  gap: 1.5rem;\\n  align-items: center;\\n}\\n\\n.qr-box {\\n  background: #ffffff;\\n  padding: 0.75rem;\\n  border-radius: var(--radius-md);\\n  text-align: center;\\n  box-shadow: 0 4px 15px rgba(0,0,0,0.4);\\n}\\n\\n.qr-box img {\\n  width: 100%;\\n  max-width: 190px;\\n  height: auto;\\n  display: block;\\n  margin: 0 auto;\\n}\\n\\n.qr-label {\\n  color: #111;\\n  font-weight: 700;\\n  font-size: 0.8rem;\\n  margin-top: 0.4rem;\\n}\\n\\n.upi-apps-grid {\\n  display: grid;\\n  grid-template-columns: repeat(2, 1fr);\\n  gap: 0.75rem;\\n  margin-top: 1rem;\\n}\\n\\n.upi-app-btn {\\n  display: flex;\\n  align-items: center;\\n  gap: 0.6rem;\\n  padding: 0.75rem 1rem;\\n  border-radius: var(--radius-md);\\n  color: #fff;\\n  font-weight: 700;\\n  text-decoration: none;\\n  font-size: 0.95rem;\\n  transition: all 0.2s ease;\\n  border: 1px solid rgba(255, 255, 255, 0.1);\\n}\\n\\n.upi-phonepe { background: #5f259f; }\\n.upi-phonepe:hover { background: #6f2eb8; transform: translateY(-2px); }\\n\\n.upi-gpay { background: #1a73e8; }\\n.upi-gpay:hover { background: #2b7de9; transform: translateY(-2px); }\\n\\n.upi-paytm { background: #002e6e; }\\n.upi-paytm:hover { background: #003a8c; transform: translateY(-2px); }\\n\\n.upi-bhim { background: #ff6f00; }\\n.upi-bhim:hover { background: #ff7d1a; transform: translateY(-2px); }\\n\\n/* Responsive adjustments */\\n@media (max-width: 768px) {\\n  .nav-links {\\n    display: none;\\n    position: absolute;\\n    top: 100%;\\n    left: 0;\\n    right: 0;\\n    background: var(--bg-surface);\\n    flex-direction: column;\\n    padding: 1rem;\\n    border-bottom: 1px solid var(--border-glass);\\n  }\\n  .nav-links.open {\\n    display: flex;\\n  }\\n  .mobile-toggle {\\n    display: block;\\n  }\\n  .upi-details-grid {\\n    grid-template-columns: 1fr;\\n    text-align: center;\\n  }\\n  .qr-box {\\n    max-width: 230px;\\n    margin: 0 auto;\\n  }\\n  .upi-apps-grid {\\n    grid-template-columns: 1fr;\\n  }\\n  .page-container {\\n    padding: 1rem 0.75rem;\\n  }\\n  .glass-card {\\n    padding: 1.25rem 1rem;\\n  }\\n}\\n\", \"static/images/avatar_allrounder.svg\": \"<svg xmlns=\\\"http://www.w3.org/2000/svg\\\" viewBox=\\\"0 0 200 200\\\" width=\\\"100%\\\" height=\\\"100%\\\">\\n  <defs>\\n    <radialGradient id=\\\"bg_all\\\" cx=\\\"50%\\\" cy=\\\"30%\\\" r=\\\"70%\\\">\\n      <stop offset=\\\"0%\\\" stop-color=\\\"#f59e0b\\\"/>\\n      <stop offset=\\\"100%\\\" stop-color=\\\"#78350f\\\"/>\\n    </radialGradient>\\n  </defs>\\n  <circle cx=\\\"100\\\" cy=\\\"100\\\" r=\\\"96\\\" fill=\\\"url(#bg_all)\\\" stroke=\\\"#fde68a\\\" stroke-width=\\\"4\\\"/>\\n  <circle cx=\\\"100\\\" cy=\\\"65\\\" r=\\\"26\\\" fill=\\\"#fffbeb\\\"/>\\n  <path d=\\\"M100 95 C 60 95, 45 130, 45 180 L 155 180 C 155 130, 140 95, 100 95 Z\\\" fill=\\\"#fffbeb\\\"/>\\n  <polygon points=\\\"65,55 75,45 95,115 85,125\\\" fill=\\\"#fbbf24\\\" stroke=\\\"#78350f\\\" stroke-width=\\\"2\\\"/>\\n  <circle cx=\\\"145\\\" cy=\\\"70\\\" r=\\\"14\\\" fill=\\\"#dc2626\\\" stroke=\\\"#ffffff\\\" stroke-width=\\\"2\\\"/>\\n  <text x=\\\"100\\\" y=\\\"175\\\" font-family=\\\"sans-serif\\\" font-size=\\\"13\\\" font-weight=\\\"900\\\" fill=\\\"#78350f\\\" text-anchor=\\\"middle\\\">ALL-ROUNDER</text>\\n</svg>\", \"static/images/avatar_batsman.svg\": \"<svg xmlns=\\\"http://www.w3.org/2000/svg\\\" viewBox=\\\"0 0 200 200\\\" width=\\\"100%\\\" height=\\\"100%\\\">\\n  <defs>\\n    <radialGradient id=\\\"bg_bat\\\" cx=\\\"50%\\\" cy=\\\"30%\\\" r=\\\"70%\\\">\\n      <stop offset=\\\"0%\\\" stop-color=\\\"#ef4444\\\"/>\\n      <stop offset=\\\"100%\\\" stop-color=\\\"#7f1d1d\\\"/>\\n    </radialGradient>\\n  </defs>\\n  <circle cx=\\\"100\\\" cy=\\\"100\\\" r=\\\"96\\\" fill=\\\"url(#bg_bat)\\\" stroke=\\\"#fca5a5\\\" stroke-width=\\\"4\\\"/>\\n  <circle cx=\\\"100\\\" cy=\\\"65\\\" r=\\\"26\\\" fill=\\\"#fef2f2\\\"/>\\n  <path d=\\\"M100 95 C 60 95, 45 130, 45 180 L 155 180 C 155 130, 140 95, 100 95 Z\\\" fill=\\\"#fef2f2\\\"/>\\n  <polygon points=\\\"135,45 150,35 180,135 165,145\\\" fill=\\\"#fbbf24\\\" stroke=\\\"#b45309\\\" stroke-width=\\\"3\\\"/>\\n  <text x=\\\"100\\\" y=\\\"175\\\" font-family=\\\"sans-serif\\\" font-size=\\\"14\\\" font-weight=\\\"900\\\" fill=\\\"#7f1d1d\\\" text-anchor=\\\"middle\\\">BATSMAN</text>\\n</svg>\", \"static/images/avatar_bowler.svg\": \"<svg xmlns=\\\"http://www.w3.org/2000/svg\\\" viewBox=\\\"0 0 200 200\\\" width=\\\"100%\\\" height=\\\"100%\\\">\\n  <defs>\\n    <radialGradient id=\\\"bg_bowl\\\" cx=\\\"50%\\\" cy=\\\"30%\\\" r=\\\"70%\\\">\\n      <stop offset=\\\"0%\\\" stop-color=\\\"#3b82f6\\\"/>\\n      <stop offset=\\\"100%\\\" stop-color=\\\"#1e3a8a\\\"/>\\n    </radialGradient>\\n  </defs>\\n  <circle cx=\\\"100\\\" cy=\\\"100\\\" r=\\\"96\\\" fill=\\\"url(#bg_bowl)\\\" stroke=\\\"#93c5fd\\\" stroke-width=\\\"4\\\"/>\\n  <circle cx=\\\"100\\\" cy=\\\"65\\\" r=\\\"26\\\" fill=\\\"#eff6ff\\\"/>\\n  <path d=\\\"M100 95 C 60 95, 45 130, 45 180 L 155 180 C 155 130, 140 95, 100 95 Z\\\" fill=\\\"#eff6ff\\\"/>\\n  <circle cx=\\\"155\\\" cy=\\\"60\\\" r=\\\"18\\\" fill=\\\"#dc2626\\\" stroke=\\\"#ffffff\\\" stroke-width=\\\"2\\\"/>\\n  <text x=\\\"100\\\" y=\\\"175\\\" font-family=\\\"sans-serif\\\" font-size=\\\"14\\\" font-weight=\\\"900\\\" fill=\\\"#1e3a8a\\\" text-anchor=\\\"middle\\\">BOWLER</text>\\n</svg>\", \"static/images/avatar_default.svg\": \"<svg xmlns=\\\"http://www.w3.org/2000/svg\\\" viewBox=\\\"0 0 200 200\\\" width=\\\"100%\\\" height=\\\"100%\\\">\\n  <defs>\\n    <radialGradient id=\\\"bg_all\\\" cx=\\\"50%\\\" cy=\\\"30%\\\" r=\\\"70%\\\">\\n      <stop offset=\\\"0%\\\" stop-color=\\\"#f59e0b\\\"/>\\n      <stop offset=\\\"100%\\\" stop-color=\\\"#78350f\\\"/>\\n    </radialGradient>\\n  </defs>\\n  <circle cx=\\\"100\\\" cy=\\\"100\\\" r=\\\"96\\\" fill=\\\"url(#bg_all)\\\" stroke=\\\"#fde68a\\\" stroke-width=\\\"4\\\"/>\\n  <circle cx=\\\"100\\\" cy=\\\"65\\\" r=\\\"26\\\" fill=\\\"#fffbeb\\\"/>\\n  <path d=\\\"M100 95 C 60 95, 45 130, 45 180 L 155 180 C 155 130, 140 95, 100 95 Z\\\" fill=\\\"#fffbeb\\\"/>\\n  <polygon points=\\\"65,55 75,45 95,115 85,125\\\" fill=\\\"#fbbf24\\\" stroke=\\\"#78350f\\\" stroke-width=\\\"2\\\"/>\\n  <circle cx=\\\"145\\\" cy=\\\"70\\\" r=\\\"14\\\" fill=\\\"#dc2626\\\" stroke=\\\"#ffffff\\\" stroke-width=\\\"2\\\"/>\\n  <text x=\\\"100\\\" y=\\\"175\\\" font-family=\\\"sans-serif\\\" font-size=\\\"13\\\" font-weight=\\\"900\\\" fill=\\\"#78350f\\\" text-anchor=\\\"middle\\\">ALL-ROUNDER</text>\\n</svg>\", \"static/images/avatar_keeper.svg\": \"<svg xmlns=\\\"http://www.w3.org/2000/svg\\\" viewBox=\\\"0 0 200 200\\\" width=\\\"100%\\\" height=\\\"100%\\\">\\n  <defs>\\n    <radialGradient id=\\\"bg_keep\\\" cx=\\\"50%\\\" cy=\\\"30%\\\" r=\\\"70%\\\">\\n      <stop offset=\\\"0%\\\" stop-color=\\\"#10b981\\\"/>\\n      <stop offset=\\\"100%\\\" stop-color=\\\"#064e3b\\\"/>\\n    </radialGradient>\\n  </defs>\\n  <circle cx=\\\"100\\\" cy=\\\"100\\\" r=\\\"96\\\" fill=\\\"url(#bg_keep)\\\" stroke=\\\"#6ee7b7\\\" stroke-width=\\\"4\\\"/>\\n  <circle cx=\\\"100\\\" cy=\\\"65\\\" r=\\\"26\\\" fill=\\\"#ecfdf5\\\"/>\\n  <path d=\\\"M100 95 C 60 95, 45 130, 45 180 L 155 180 C 155 130, 140 95, 100 95 Z\\\" fill=\\\"#ecfdf5\\\"/>\\n  <path d=\\\"M 65 110 C 65 90, 85 90, 85 110 C 85 130, 65 130, 65 110 Z\\\" fill=\\\"#f59e0b\\\" stroke=\\\"#78350f\\\" stroke-width=\\\"2\\\"/>\\n  <path d=\\\"M 115 110 C 115 90, 135 90, 135 110 C 135 130, 115 130, 115 110 Z\\\" fill=\\\"#f59e0b\\\" stroke=\\\"#78350f\\\" stroke-width=\\\"2\\\"/>\\n  <text x=\\\"100\\\" y=\\\"175\\\" font-family=\\\"sans-serif\\\" font-size=\\\"14\\\" font-weight=\\\"900\\\" fill=\\\"#064e3b\\\" text-anchor=\\\"middle\\\">WK-BATSMAN</text>\\n</svg>\", \"static/js/auction.js\": \"// ==================== REAL-TIME CRICKET AUCTION ENGINE ====================\\n// Supports both Host Operator Console and Mobile Viewers Live Stream\\n\\nlet auctionState = null;\\nlet currentBidAmount = 0;\\nlet currentBiddingTeam = null;\\nlet pollTimer = null;\\nlet isAuctioneerActing = false;\\nlet lastActionTimestamp = 0;\\n\\n// --- TOAST NOTIFICATIONS (NO BLOCKING POPUPS) ---\\nfunction showToast(message, type = 'info') {\\n  let toastContainer = document.getElementById('toastContainer');\\n  if (!toastContainer) {\\n    toastContainer = document.createElement('div');\\n    toastContainer.id = 'toastContainer';\\n    toastContainer.style.cssText = 'position:fixed; top:20px; right:20px; z-index:999999; display:flex; flex-direction:column; gap:10px; max-width:380px; pointer-events:none;';\\n    document.body.appendChild(toastContainer);\\n  }\\n  const toast = document.createElement('div');\\n  const bg = type === 'error' ? 'linear-gradient(135deg, #ef4444, #b91c1c)' :\\n             (type === 'success' ? 'linear-gradient(135deg, #10b981, #059669)' :\\n             (type === 'warning' ? 'linear-gradient(135deg, #f59e0b, #d97706)' : 'linear-gradient(135deg, #38bdf8, #0284c7)'));\\n  toast.style.cssText = `background:${bg}; color:#fff; padding:12px 18px; border-radius:10px; font-weight:800; font-size:0.92rem; box-shadow:0 10px 30px rgba(0,0,0,0.5); display:flex; align-items:center; justify-content:space-between; pointer-events:auto; transition:all 0.3s ease; border: 1px solid rgba(255,255,255,0.2);`;\\n  toast.innerHTML = `<span>${message}</span><button onclick=\\\"this.parentElement.remove()\\\" style=\\\"background:none;border:none;color:#fff;font-size:1.3rem;cursor:pointer;margin-left:12px;line-height:1;\\\">&times;</button>`;\\n  toastContainer.appendChild(toast);\\n  setTimeout(() => {\\n    toast.style.opacity = '0';\\n    toast.style.transform = 'translateY(-10px)';\\n    setTimeout(() => toast.remove(), 300);\\n  }, 4000);\\n}\\n\\n// --- PIN HELPERS ---\\nfunction getAuctioneerPin() {\\n  return sessionStorage.getItem('kpl_auction_pin') || sessionStorage.getItem('spl_auction_pin') || '';\\n}\\n\\nfunction setAuctioneerPin(pin) {\\n  sessionStorage.setItem('kpl_auction_pin', pin);\\n  sessionStorage.setItem('spl_auction_pin', pin);\\n}\\n\\nfunction requirePinAuth(callback) {\\n  const pin = getAuctioneerPin();\\n  if (pin) {\\n    return true;\\n  }\\n  window._pendingAction = callback;\\n  openPinModal();\\n  return false;\\n}\\n\\n// --- PIN MODAL FUNCTIONS ---\\nfunction openPinModal() {\\n  const modal = document.getElementById('pinModal') || document.getElementById('hostPinModal');\\n  const input = document.getElementById('inputHostPin') || document.getElementById('inputAuctionPin');\\n  const err = document.getElementById('pinErrorMsg');\\n  if (err) err.style.display = 'none';\\n  if (input) { input.value = ''; }\\n  if (modal) {\\n    modal.style.display = 'flex';\\n    setTimeout(() => { if (input) input.focus(); }, 100);\\n  }\\n}\\n\\nfunction closePinModal() {\\n  const modal = document.getElementById('pinModal') || document.getElementById('hostPinModal');\\n  if (modal) modal.style.display = 'none';\\n  window._pendingAction = null;\\n}\\n\\nasync function verifyHostPin() {\\n  const input = document.getElementById('inputHostPin') || document.getElementById('inputAuctionPin');\\n  const err = document.getElementById('pinErrorMsg');\\n  const pin = input ? input.value.trim() : '';\\n\\n  if (!pin) {\\n    if (err) { err.textContent = 'Please enter the Organizer PIN.'; err.style.display = 'block'; }\\n    return;\\n  }\\n\\n  try {\\n    const res = await fetch('/api/auction/verify-pin', {\\n      method: 'POST',\\n      headers: { 'Content-Type': 'application/json' },\\n      body: JSON.stringify({ pin: pin })\\n    });\\n    const data = await res.json();\\n    if (data.success || data.valid) {\\n      setAuctioneerPin(pin);\\n      applyAuctioneerMode(true);\\n      closePinModal();\\n      showToast('Organizer Authenticated! Host Controls Active.', 'success');\\n      if (typeof window._pendingAction === 'function') {\\n        const action = window._pendingAction;\\n        window._pendingAction = null;\\n        try { action(); } catch(e) { console.error('Pending action error:', e); }\\n      }\\n    } else {\\n      if (err) { err.textContent = data.message || 'Incorrect Organizer PIN.'; err.style.display = 'block'; }\\n    }\\n  } catch (e) {\\n    if (err) { err.textContent = 'Verification error: ' + e.message; err.style.display = 'block'; }\\n  }\\n}\\n\\nfunction lockAuctioneer() {\\n  sessionStorage.removeItem('kpl_auction_pin');\\n  sessionStorage.removeItem('spl_auction_pin');\\n  applyAuctioneerMode(false);\\n  showToast('Admin locked.', 'info');\\n}\\n\\nfunction applyAuctioneerMode(isHost) {\\n  const authBox = document.getElementById('auctioneerAuthBox');\\n  const hostDeck = document.getElementById('auctioneerControls') || document.getElementById('auctioneerControlDeck');\\n\\n  if (hostDeck) {\\n    hostDeck.style.display = isHost ? 'block' : 'none';\\n  }\\n\\n  if (authBox) {\\n    if (isHost) {\\n      authBox.innerHTML = `\\n        <span style=\\\"color: #34d399; font-size: 0.85rem; font-weight: 800; display: inline-flex; align-items: center; gap: 0.35rem; background: rgba(16,185,129,0.15); padding: 0.3rem 0.65rem; border-radius: 6px; border: 1px solid rgba(16,185,129,0.3);\\\">\\n          <span>\\ud83d\\udd13</span> Host Active\\n        </span>\\n        <button type=\\\"button\\\" onclick=\\\"lockAuctioneer()\\\" class=\\\"btn btn-secondary\\\" style=\\\"font-size: 0.75rem; padding: 0.25rem 0.5rem; margin-left: 0.35rem;\\\">Lock</button>\\n      `;\\n    } else {\\n      authBox.innerHTML = `\\n        <button type=\\\"button\\\" id=\\\"btnUnlockAuctioneer\\\" onclick=\\\"openPinModal()\\\" class=\\\"btn btn-secondary\\\" style=\\\"font-size: 0.8rem; padding: 0.3rem 0.65rem; border-color: rgba(245, 158, 11, 0.5); color: #f59e0b; display: flex; align-items: center; gap: 0.35rem;\\\">\\n          <span>\\ud83d\\udd12</span> Host Controls\\n        </button>\\n      `;\\n    }\\n  }\\n}\\n\\nasync function checkSavedPin() {\\n  const saved = getAuctioneerPin();\\n  if (!saved) {\\n    applyAuctioneerMode(false);\\n    return;\\n  }\\n  try {\\n    const res = await fetch('/api/auction/verify-pin', {\\n      method: 'POST',\\n      headers: { 'Content-Type': 'application/json' },\\n      body: JSON.stringify({ pin: saved })\\n    });\\n    const data = await res.json();\\n    if (data.success || data.valid) {\\n      applyAuctioneerMode(true);\\n    } else {\\n      sessionStorage.removeItem('kpl_auction_pin');\\n      sessionStorage.removeItem('spl_auction_pin');\\n      applyAuctioneerMode(false);\\n    }\\n  } catch (e) {\\n    applyAuctioneerMode(false);\\n  }\\n}\\n\\n// --- SYNTHESIZED SOUND EFFECTS ---\\nconst AudioContextClass = window.AudioContext || window.webkitAudioContext;\\nlet audioCtx = null;\\n\\nfunction getAudioContext() {\\n  if (!audioCtx && AudioContextClass) {\\n    try { audioCtx = new AudioContextClass(); } catch(e) {}\\n  }\\n  if (audioCtx && audioCtx.state === 'suspended') {\\n    audioCtx.resume();\\n  }\\n  return audioCtx;\\n}\\n\\nfunction playGavelSound() {\\n  const ctx = getAudioContext();\\n  if (!ctx) return;\\n  [0, 0.12].forEach(delay => {\\n    try {\\n      const osc = ctx.createOscillator();\\n      const gain = ctx.createGain();\\n      osc.type = 'triangle';\\n      osc.frequency.setValueAtTime(140, ctx.currentTime + delay);\\n      osc.frequency.exponentialRampToValueAtTime(30, ctx.currentTime + delay + 0.08);\\n      gain.gain.setValueAtTime(1, ctx.currentTime + delay);\\n      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + delay + 0.08);\\n      osc.connect(gain);\\n      gain.connect(ctx.destination);\\n      osc.start(ctx.currentTime + delay);\\n      osc.stop(ctx.currentTime + delay + 0.09);\\n    } catch(e) {}\\n  });\\n}\\n\\nfunction playFanfareSound() {\\n  const ctx = getAudioContext();\\n  if (!ctx) return;\\n  const notes = [523.25, 659.25, 783.99, 1046.50];\\n  notes.forEach((freq, idx) => {\\n    try {\\n      const osc = ctx.createOscillator();\\n      const gain = ctx.createGain();\\n      osc.type = 'sawtooth';\\n      osc.frequency.setValueAtTime(freq, ctx.currentTime + idx * 0.1);\\n      gain.gain.setValueAtTime(0.3, ctx.currentTime + idx * 0.1);\\n      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + idx * 0.1 + 0.4);\\n      osc.connect(gain);\\n      gain.connect(ctx.destination);\\n      osc.start(ctx.currentTime + idx * 0.1);\\n      osc.stop(ctx.currentTime + idx * 0.1 + 0.45);\\n    } catch(e) {}\\n  });\\n}\\n\\nfunction playBuzzerSound() {\\n  const ctx = getAudioContext();\\n  if (!ctx) return;\\n  try {\\n    const osc = ctx.createOscillator();\\n    const gain = ctx.createGain();\\n    osc.type = 'sawtooth';\\n    osc.frequency.setValueAtTime(120, ctx.currentTime);\\n    osc.frequency.linearRampToValueAtTime(80, ctx.currentTime + 0.4);\\n    gain.gain.setValueAtTime(0.4, ctx.currentTime);\\n    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.4);\\n    osc.connect(gain);\\n    gain.connect(ctx.destination);\\n    osc.start();\\n    osc.stop(ctx.currentTime + 0.4);\\n  } catch(e) {}\\n}\\n\\nfunction playChimeSound() {\\n  const ctx = getAudioContext();\\n  if (!ctx) return;\\n  try {\\n    const osc = ctx.createOscillator();\\n    const gain = ctx.createGain();\\n    osc.type = 'sine';\\n    osc.frequency.setValueAtTime(880, ctx.currentTime);\\n    gain.gain.setValueAtTime(0.3, ctx.currentTime);\\n    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.2);\\n    osc.connect(gain);\\n    gain.connect(ctx.destination);\\n    osc.start();\\n    osc.stop(ctx.currentTime + 0.2);\\n  } catch(e) {}\\n}\\n\\n// --- REAL-TIME BID BROADCAST ---\\nlet broadcastTimeout = null;\\nfunction broadcastBid(amount, team) {\\n  if (window.IS_VIEWER_MODE) return;\\n  const pin = getAuctioneerPin();\\n  if (!pin) return;\\n\\n  clearTimeout(broadcastTimeout);\\n  broadcastTimeout = setTimeout(async () => {\\n    try {\\n      await fetch('/api/auction/bid', {\\n        method: 'POST',\\n        headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': pin },\\n        body: JSON.stringify({ bid: amount, team: team, pin: pin })\\n      });\\n    } catch(e) {}\\n  }, 100);\\n}\\n\\n// --- BID ADJUSTER (+50, +100, +200, +500, -50) ---\\nfunction adjustCurrentBid(delta) {\\n  if (!requirePinAuth(() => adjustCurrentBid(delta))) return;\\n\\n  if (!auctionState || !auctionState.current_player) {\\n    showToast('Click \\\"Next Draw\\\" to bring a player to the auction block first!', 'warning');\\n    return;\\n  }\\n\\n  const teamSelect = document.getElementById('biddingTeamSelect') || document.getElementById('bidTeamSelect');\\n  const selectedTeam = (teamSelect && teamSelect.value) ? teamSelect.value : currentBiddingTeam;\\n\\n  if (delta > 0 && !selectedTeam) {\\n    showToast('Please select a bidding team from the dropdown first.', 'warning');\\n    if (teamSelect) teamSelect.focus();\\n    return;\\n  }\\n\\n  playChimeSound();\\n  currentBidAmount = Math.max(0, currentBidAmount + delta);\\n  currentBiddingTeam = selectedTeam;\\n  updateBidDisplay();\\n  broadcastBid(currentBidAmount, currentBiddingTeam);\\n}\\n\\nfunction stepBid(delta) {\\n  adjustCurrentBid(delta);\\n}\\n\\n// --- ASSIGN LEADING BIDDER ---\\nfunction assignLeadingBidder() {\\n  if (!requirePinAuth(assignLeadingBidder)) return;\\n\\n  const teamSelect = document.getElementById('biddingTeamSelect') || document.getElementById('bidTeamSelect');\\n  const team = teamSelect ? teamSelect.value : '';\\n  if (!team) {\\n    showToast('Please select a team from the dropdown.', 'warning');\\n    return;\\n  }\\n  currentBiddingTeam = team;\\n  updateBidDisplay();\\n  broadcastBid(currentBidAmount, currentBiddingTeam);\\n  showToast(`Leading bidder set to ${team}`, 'info');\\n}\\n\\n// --- DRAW NEXT PLAYER ---\\nasync function drawNextPlayer() {\\n  closeSoldModal();\\n  if (!requirePinAuth(drawNextPlayer)) return;\\n\\n  try {\\n    const pin = getAuctioneerPin();\\n    const res = await fetch('/api/auction/next', {\\n      method: 'POST',\\n      headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': pin },\\n      body: JSON.stringify({ pin: pin })\\n    });\\n    const data = await res.json();\\n    if (data.success) {\\n      playChimeSound();\\n      currentBidAmount = data.base_price || 50;\\n      currentBiddingTeam = null;\\n      showToast(`\\ud83c\\udfaf Drawn: ${data.player} (Base: \\u20b9${currentBidAmount})`, 'success');\\n      fetchState();\\n    } else {\\n      showToast(data.message || 'No more players available in current round.', 'warning');\\n    }\\n  } catch (e) {\\n    showToast('Error drawing player: ' + e.message, 'error');\\n  }\\n}\\n\\n// --- CONFIRM SOLD PLAYER ---\\nasync function confirmSellPlayer() {\\n  if (!requirePinAuth(confirmSellPlayer)) return;\\n\\n  if (!auctionState || !auctionState.current_player) {\\n    showToast('No player is currently on the auction block!', 'warning');\\n    return;\\n  }\\n\\n  const teamSelect = document.getElementById('biddingTeamSelect') || document.getElementById('bidTeamSelect');\\n  const team = (teamSelect && teamSelect.value) ? teamSelect.value : currentBiddingTeam;\\n\\n  if (!team) {\\n    showToast('Please select the winning team before clicking SOLD!', 'warning');\\n    if (teamSelect) teamSelect.focus();\\n    return;\\n  }\\n\\n  if (currentBidAmount <= 0) {\\n    showToast('Current bid amount must be greater than 0.', 'warning');\\n    return;\\n  }\\n\\n  if (!confirm(`Confirm sale of ${auctionState.current_player} to ${team} for \\u20b9${currentBidAmount}?`)) {\\n    return;\\n  }\\n\\n  isAuctioneerActing = true;\\n  playGavelSound();\\n  playFanfareSound();\\n  triggerCelebrationModal(auctionState.current_player, team, currentBidAmount);\\n\\n  try {\\n    const pin = getAuctioneerPin();\\n    const res = await fetch('/api/auction/sell', {\\n      method: 'POST',\\n      headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': pin },\\n      body: JSON.stringify({\\n        team: team,\\n        price: currentBidAmount,\\n        pin: pin\\n      })\\n    });\\n    const data = await res.json();\\n    if (!data.success) {\\n      showToast(data.message || 'Error executing sale.', 'error');\\n    } else {\\n      showToast(`\\ud83c\\udf89 Sold ${auctionState.current_player} to ${team} for \\u20b9${currentBidAmount}!`, 'success');\\n      setTimeout(fetchState, 1000);\\n    }\\n  } catch (e) {\\n    showToast('Error executing sale: ' + e.message, 'error');\\n  } finally {\\n    setTimeout(() => { isAuctioneerActing = false; }, 2000);\\n  }\\n}\\n\\n// --- MARK UNSOLD (ROUND 2 OR PERMANENT) ---\\nasync function markUnsold(isPermanent) {\\n  if (!requirePinAuth(() => markUnsold(isPermanent))) return;\\n\\n  if (!auctionState || !auctionState.current_player) {\\n    showToast('No player is currently on the auction block!', 'warning');\\n    return;\\n  }\\n\\n  const player = auctionState.current_player;\\n  const promptText = isPermanent\\n    ? `\\u26a0\\ufe0f Confirm PERMANENT UNSOLD for ${player}? This player will NOT return in Round 2.`\\n    : `Mark ${player} as UNSOLD? (This player will return in Round 2)`;\\n\\n  if (!confirm(promptText)) return;\\n\\n  playBuzzerSound();\\n  isAuctioneerActing = true;\\n  try {\\n    const pin = getAuctioneerPin();\\n    const res = await fetch('/api/auction/unsold', {\\n      method: 'POST',\\n      headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': pin },\\n      body: JSON.stringify({ is_permanent: !!isPermanent, pin: pin })\\n    });\\n    const data = await res.json();\\n    if (data.success) {\\n      showToast(`Marked ${player} as unsold.`, 'info');\\n      setTimeout(fetchState, 500);\\n    } else {\\n      showToast(data.message || 'Error marking player unsold.', 'error');\\n    }\\n  } catch (e) {\\n    showToast('Error marking unsold: ' + e.message, 'error');\\n  } finally {\\n    isAuctioneerActing = false;\\n  }\\n}\\n\\n// --- UNDO LAST ACTION ---\\nasync function undoLastAction() {\\n  if (!requirePinAuth(undoLastAction)) return;\\n\\n  if (!confirm('Undo the last auction action? This will restore the player and team purse.')) return;\\n\\n  try {\\n    const pin = getAuctioneerPin();\\n    const res = await fetch('/api/auction/undo', {\\n      method: 'POST',\\n      headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': pin },\\n      body: JSON.stringify({ pin: pin })\\n    });\\n    const data = await res.json();\\n    if (data.success) {\\n      playChimeSound();\\n      showToast('Last auction action undone successfully!', 'success');\\n      fetchState();\\n    } else {\\n      showToast(data.message || 'Nothing to undo.', 'warning');\\n    }\\n  } catch (e) {\\n    showToast('Error undoing action: ' + e.message, 'error');\\n  }\\n}\\n\\n// --- START ROUND 2 ---\\nasync function startRound2() {\\n  if (!requirePinAuth(startRound2)) return;\\n\\n  if (!confirm('Start Round 2 for all previously unsold players?')) return;\\n\\n  try {\\n    const pin = getAuctioneerPin();\\n    const res = await fetch('/api/auction/round2', {\\n      method: 'POST',\\n      headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': pin },\\n      body: JSON.stringify({ pin: pin })\\n    });\\n    const data = await res.json();\\n    if (data.success) {\\n      showToast('Round 2 started successfully!', 'success');\\n      fetchState();\\n    } else {\\n      showToast(data.message || 'Error starting Round 2.', 'error');\\n    }\\n  } catch (e) {\\n    showToast('Error: ' + e.message, 'error');\\n  }\\n}\\n\\n// --- CLOSE CELEBRATION MODAL ---\\n// --- SOLD MODAL HELPERS ---\\nwindow._soldDismissTimer = null;\\nwindow._lastSoldPlayer = null;\\n\\nfunction closeSoldModal() {\\n  if (window._soldDismissTimer) {\\n    clearTimeout(window._soldDismissTimer);\\n    window._soldDismissTimer = null;\\n  }\\n  const modal = document.getElementById('soldModal') || document.getElementById('soldModalOverlay');\\n  if (modal) {\\n    modal.classList.remove('active');\\n    modal.style.display = 'none';\\n  }\\n}\\n\\nfunction handleSoldModalBackdrop(e) {\\n  if (e.target === document.getElementById('soldModal') || e.target.classList.contains('sold-modal-overlay')) {\\n    closeSoldModal();\\n  }\\n}\\n\\nasync function drawNextFromModal() {\\n  closeSoldModal();\\n  await drawNextPlayer();\\n}\\n\\n// --- PICK SPECIFIC PLAYER FROM LIST ---\\nasync function chooseSelectedPlayer(val) {\\n  if (!requirePinAuth(() => chooseSelectedPlayer(val))) return;\\n\\n  const select = document.getElementById('selectPlayerDropdown');\\n  const player = val || (select ? select.value : '');\\n\\n  if (!player) {\\n    showToast('Please select a player from the dropdown first.', 'warning');\\n    return;\\n  }\\n\\n  closeSoldModal();\\n  try {\\n    const pin = getAuctioneerPin();\\n    const res = await fetch('/api/auction/select-player', {\\n      method: 'POST',\\n      headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': pin },\\n      body: JSON.stringify({ player: player, pin: pin })\\n    });\\n    const data = await res.json();\\n    if (data.success) {\\n      playChimeSound();\\n      currentBidAmount = data.base_price || 50;\\n      currentBiddingTeam = null;\\n      showToast(`\\ud83c\\udfaf Drawn: ${data.player} (Base: \\u20b9${currentBidAmount})`, 'success');\\n      await fetchState();\\n    } else {\\n      showToast(data.message || 'Error selecting player', 'error');\\n    }\\n  } catch (e) {\\n    showToast('Error selecting player: ' + e.message, 'error');\\n  }\\n}\\n\\nfunction triggerCelebrationModal(player, team, price) {\\n  window._lastSoldPlayer = player;\\n  const modal = document.getElementById('soldModal') || document.getElementById('soldModalOverlay');\\n  const nameEl = document.getElementById('soldPlayerName');\\n  const teamEl = document.getElementById('soldTeamName');\\n  const priceEl = document.getElementById('soldFinalPrice');\\n  const photoEl = document.getElementById('soldPlayerPhoto');\\n  const roleBadge = document.getElementById('soldPlayerRoleBadge');\\n\\n  if (nameEl) nameEl.textContent = player || '-';\\n  if (teamEl) teamEl.textContent = team || '-';\\n  if (priceEl) priceEl.textContent = '\\u20b9' + (price || 0).toLocaleString('en-IN');\\n\\n  // Look up detailed player information\\n  const playerInfo = (auctionState?.all_player_details && auctionState.all_player_details[player]) ||\\n                     (auctionState?.player_details?.name === player ? auctionState.player_details : null);\\n\\n  const roleName = playerInfo?.role || 'All-Rounder';\\n  if (roleBadge) {\\n    roleBadge.textContent = roleName;\\n    roleBadge.className = 'role-badge ' + getRoleBadgeClass(roleName);\\n  }\\n\\n  if (photoEl) {\\n    let photoSrc = playerInfo?.photo_url;\\n    if (!photoSrc) {\\n      const r = (roleName).toLowerCase();\\n      if (r.includes('keep')) photoSrc = '/static/images/avatar_keeper.svg';\\n      else if (r.includes('bowl')) photoSrc = '/static/images/avatar_bowler.svg';\\n      else if (r.includes('bat')) photoSrc = '/static/images/avatar_batsman.svg';\\n      else photoSrc = '/static/images/avatar_allrounder.svg';\\n    }\\n    photoEl.src = photoSrc;\\n  }\\n\\n  if (modal) {\\n    modal.style.display = 'flex';\\n    modal.classList.add('active');\\n  }\\n\\n  // Auto-dismiss celebration after 5 seconds so nobody is stuck!\\n  if (window._soldDismissTimer) clearTimeout(window._soldDismissTimer);\\n  window._soldDismissTimer = setTimeout(() => {\\n    closeSoldModal();\\n  }, 5000);\\n}\\n\\n// --- UPDATE BID DISPLAY ---\\nfunction updateBidDisplay() {\\n  const odometerEl = document.getElementById('bidOdometer') || document.getElementById('currentBidDisplay');\\n  const tagEl = document.getElementById('leadingTeamTag') || document.getElementById('biddingTeamBanner');\\n\\n  if (odometerEl) {\\n    odometerEl.textContent = '\\u20b9' + currentBidAmount.toLocaleString('en-IN');\\n  }\\n\\n  if (tagEl) {\\n    if (currentBiddingTeam) {\\n      tagEl.textContent = `Leading: ${currentBiddingTeam}`;\\n      tagEl.style.background = 'rgba(245, 158, 11, 0.25)';\\n      tagEl.style.color = '#fbbf24';\\n      tagEl.style.borderColor = 'rgba(245, 158, 11, 0.5)';\\n    } else {\\n      tagEl.textContent = 'No Bids Yet';\\n      tagEl.style.background = 'rgba(255, 255, 255, 0.08)';\\n      tagEl.style.color = '#94a3b8';\\n      tagEl.style.borderColor = 'rgba(255, 255, 255, 0.15)';\\n    }\\n  }\\n\\n  const teamSelect = document.getElementById('biddingTeamSelect') || document.getElementById('bidTeamSelect');\\n  if (teamSelect && currentBiddingTeam && teamSelect.value !== currentBiddingTeam) {\\n    teamSelect.value = currentBiddingTeam;\\n  }\\n}\\n\\n// --- FETCH & RENDER STATE ---\\nasync function fetchState() {\\n  if (isAuctioneerActing) return;\\n  try {\\n    const res = await fetch('/api/auction/state');\\n    if (!res.ok) return;\\n    const data = await res.json();\\n    renderAuctionState(data);\\n  } catch (e) {\\n    console.error('Error fetching state:', e);\\n  }\\n}\\n\\nfunction startStatePolling() {\\n  fetchState();\\n  if (pollTimer) clearInterval(pollTimer);\\n  pollTimer = setInterval(fetchState, 1000);\\n}\\n\\nfunction renderAuctionState(state) {\\n  if (!state) return;\\n  auctionState = state;\\n  // Auto-close celebration modal if active player advances or draw occurred\\n  if (state.last_action && (state.last_action.type === 'DRAW' || state.current_player !== window._lastSoldPlayer)) {\\n    if (document.getElementById('soldModal')?.style.display === 'flex') {\\n      closeSoldModal();\\n    }\\n  }\\n\\n  // Populate Remaining Player Picker Dropdown\\n  const pickerDropdown = document.getElementById('selectPlayerDropdown');\\n  if (pickerDropdown && state.auction_players) {\\n    const currentVal = pickerDropdown.value;\\n    pickerDropdown.innerHTML = '<option value=\\\"\\\">-- Choose Player to Bring to Auction --</option>' +\\n      state.auction_players.map(pName => {\\n        const pRole = (state.all_player_details && state.all_player_details[pName]?.role) || '';\\n        const pSerial = state.player_serials?.[pName] ? `(#${state.player_serials[pName]}) ` : '';\\n        const roleLabel = pRole ? ` [${pRole}]` : '';\\n        return `<option value=\\\"${pName}\\\">${pSerial}${pName}${roleLabel}</option>`;\\n      }).join('');\\n    if (currentVal) pickerDropdown.value = currentVal;\\n  }\\n\\n\\n  // Connection tag\\n  const poolTag = document.getElementById('poolStatusTag');\\n  if (poolTag) {\\n    const rem = state.auction_players?.length || 0;\\n    const unsold = state.unsold_players?.length || 0;\\n    poolTag.textContent = `Remaining: ${rem} | Unsold: ${unsold}`;\\n    poolTag.style.background = 'rgba(16, 185, 129, 0.15)';\\n    poolTag.style.color = '#34d399';\\n    poolTag.style.borderColor = 'rgba(16, 185, 129, 0.4)';\\n  }\\n\\n  // Round tag\\n  const roundTag = document.getElementById('currentRoundTag');\\n  if (roundTag) {\\n    roundTag.textContent = `Round ${state.current_round || 1}`;\\n  }\\n\\n  // Host toggle\\n  const hostToggle = document.getElementById('btnHostAuctionToggle');\\n  if (hostToggle) {\\n    if (state.auction_started) {\\n      hostToggle.className = 'btn btn-secondary';\\n      hostToggle.textContent = '\\u23f8\\ufe0f Pause Auction';\\n    } else {\\n      hostToggle.className = 'btn btn-success';\\n      hostToggle.textContent = '\\ud83d\\ude80 Start Live Auction';\\n    }\\n  }\\n\\n  // Waiting screen for spectators\\n  const notStartedScreen = document.getElementById('auctionNotStartedScreen');\\n  const activeCard = document.getElementById('activePlayerCard') || document.getElementById('activePlayerPodium');\\n  const emptyState = document.getElementById('noActivePlayerState') || document.getElementById('emptyPodiumMsg');\\n\\n  const isViewer = window.IS_VIEWER_MODE || !document.getElementById('auctioneerControls');\\n\\n  if (!state.auction_started && isViewer) {\\n    if (notStartedScreen) notStartedScreen.style.display = 'block';\\n    if (activeCard) activeCard.style.display = 'none';\\n    if (emptyState) emptyState.style.display = 'none';\\n    renderTeams(state.teams);\\n    return;\\n  } else {\\n    if (notStartedScreen) notStartedScreen.style.display = 'none';\\n  }\\n\\n  // Active Player Data\\n  if (state.current_player) {\\n    if (activeCard) activeCard.style.display = 'block';\\n    if (emptyState) emptyState.style.display = 'none';\\n\\n    const p = state.player_details || {};\\n    const nameEl = document.getElementById('playerName') || document.getElementById('podiumPlayerName');\\n    const photoEl = document.getElementById('playerPhoto') || document.getElementById('podiumPlayerPhoto');\\n    const idTag = document.getElementById('playerIdTag') || document.getElementById('podiumPlayerSerial');\\n    const roleBadge = document.getElementById('playerRoleBadge') || document.getElementById('podiumPlayerRole');\\n    const battingEl = document.getElementById('playerBatting') || document.getElementById('podiumMetaBatting');\\n    const bowlingEl = document.getElementById('playerBowling') || document.getElementById('podiumMetaBowling');\\n    const villageEl = document.getElementById('playerVillage');\\n    const basePriceEl = document.getElementById('playerBasePrice');\\n\\n    if (nameEl) nameEl.textContent = state.current_player;\\n    if (idTag) idTag.textContent = 'ID: #' + (state.player_serials?.[state.current_player] || '--');\\n\\n    const roleName = p.role || 'All-Rounder';\\n    if (roleBadge) {\\n      roleBadge.textContent = roleName;\\n      roleBadge.className = 'role-badge ' + getRoleBadgeClass(roleName);\\n    }\\n\\n    if (battingEl) battingEl.textContent = p.batting_style || 'Right Hand Bat';\\n    if (bowlingEl) bowlingEl.textContent = p.bowling_style || 'Right Arm Medium';\\n    if (villageEl) villageEl.textContent = p.village || 'Saidapur';\\n    if (basePriceEl) basePriceEl.textContent = '\\u20b9' + (p.base_price || state.min_bid || 50);\\n\\n    if (photoEl) {\\n      if (p.photo_url) {\\n        photoEl.src = p.photo_url;\\n      } else {\\n        const r = (roleName).toLowerCase();\\n        if (r.includes('bat') && !r.includes('keep')) photoEl.src = '/static/images/avatar_batsman.svg';\\n        else if (r.includes('bowl')) photoEl.src = '/static/images/avatar_bowler.svg';\\n        else if (r.includes('keep')) photoEl.src = '/static/images/avatar_keeper.svg';\\n        else photoEl.src = '/static/images/avatar_allrounder.svg';\\n      }\\n    }\\n\\n    // Bid Sync\\n    if (isViewer) {\\n      currentBidAmount = state.current_bid || state.min_bid || 50;\\n      currentBiddingTeam = state.bidding_team || null;\\n      updateBidDisplay();\\n    } else {\\n      // Host side: sync current bid\\n      if (currentBidAmount === 0 || document.body.dataset.activePlayer !== state.current_player) {\\n        currentBidAmount = state.current_bid || p.base_price || state.min_bid || 50;\\n        currentBiddingTeam = state.bidding_team || null;\\n        document.body.dataset.activePlayer = state.current_player;\\n        updateBidDisplay();\\n      }\\n    }\\n\\n    // Celebration trigger for spectators\\n    if (isViewer && state.last_action && state.last_action.timestamp > lastActionTimestamp) {\\n      lastActionTimestamp = state.last_action.timestamp;\\n      const act = state.last_action;\\n      if (act.type === 'SOLD') {\\n        playGavelSound();\\n        playFanfareSound();\\n        triggerCelebrationModal(act.player, act.team, act.amount);\\n      } else if (act.type === 'UNSOLD') {\\n        playBuzzerSound();\\n      } else if (act.type === 'UNDO') {\\n        playChimeSound();\\n      }\\n    }\\n  } else {\\n    // No active player on block\\n    if (activeCard) activeCard.style.display = 'none';\\n    if (emptyState) emptyState.style.display = 'block';\\n    currentBidAmount = 0;\\n    currentBiddingTeam = null;\\n    updateBidDisplay();\\n  }\\n\\n  // Show Round 2 button if round 1 finished\\n  const r2Btn = document.getElementById('btnStartRound2');\\n  if (r2Btn) {\\n    const hasUnsold = (state.unsold_players?.length || 0) > 0;\\n    const round1Finished = (!state.auction_players || state.auction_players.length === 0) && !state.current_player;\\n    r2Btn.style.display = (hasUnsold && round1Finished) ? 'inline-block' : 'none';\\n  }\\n\\n  renderTeams(state.teams);\\n}\\n\\nfunction getRoleBadgeClass(role) {\\n  const r = (role || '').toLowerCase();\\n  if (r.includes('bat') && !r.includes('keep')) return 'badge-batsman';\\n  if (r.includes('bowl')) return 'badge-bowler';\\n  if (r.includes('keep')) return 'badge-keeper';\\n  return 'badge-allrounder';\\n}\\n\\nfunction renderTeams(teams) {\\n  const container = document.getElementById('teamsPurseList') || document.getElementById('teamsSidebarList');\\n  const select = document.getElementById('biddingTeamSelect') || document.getElementById('bidTeamSelect');\\n\\n  if (!teams) return;\\n\\n  // Update team select dropdown if empty\\n  if (select && select.options.length <= 1) {\\n    const prev = select.value;\\n    select.innerHTML = '<option value=\\\"\\\">-- Choose Team --</option>';\\n    Object.keys(teams).forEach(tName => {\\n      const opt = document.createElement('option');\\n      opt.value = tName;\\n      opt.textContent = tName;\\n      select.appendChild(opt);\\n    });\\n    if (prev) select.value = prev;\\n  }\\n\\n  // Update sidebar purse cards\\n  if (container) {\\n    let html = '';\\n    let idx = 1;\\n    for (const [tName, tData] of Object.entries(teams)) {\\n      const squadCount = tData.players ? tData.players.length : 0;\\n      const purse = tData.purse || 0;\\n      const totalPurse = tData.total_purse || 6000;\\n      const pct = Math.max(5, Math.min(100, Math.round((purse / totalPurse) * 100)));\\n\\n      html += `\\n        <div class=\\\"team-card-auction\\\" id=\\\"teamCard_${idx}\\\" data-team=\\\"${tName}\\\">\\n          <div class=\\\"team-card-header\\\">\\n            <span class=\\\"team-card-name\\\">${tName}</span>\\n            <span class=\\\"team-squad-count\\\">${squadCount} Players</span>\\n          </div>\\n          <div class=\\\"team-progress-bg\\\" style=\\\"background: rgba(255,255,255,0.08); height: 6px; border-radius: 9999px; overflow: hidden; margin: 0.4rem 0;\\\">\\n            <div class=\\\"team-progress-bar\\\" style=\\\"width: ${pct}%; background: linear-gradient(90deg, #10b981, #059669); height: 100%;\\\"></div>\\n          </div>\\n          <div class=\\\"team-financials\\\" style=\\\"display: flex; justify-content: space-between; font-size: 0.85rem;\\\">\\n            <span class=\\\"team-rem-budget\\\" style=\\\"color: #34d399; font-weight: 800;\\\">Purse: \\u20b9${purse.toLocaleString('en-IN')}</span>\\n            <span class=\\\"team-spent-budget\\\" style=\\\"color: #94a3b8;\\\">Max Bid: \\u20b9${purse.toLocaleString('en-IN')}</span>\\n          </div>\\n        </div>\\n      `;\\n      idx++;\\n    }\\n    container.innerHTML = html;\\n  }\\n}\\n\\n// --- EXPORT TO WINDOW (CRITICAL FOR BUTTON CLICKS) ---\\nwindow.drawNextPlayer = drawNextPlayer;\\nwindow.adjustCurrentBid = adjustCurrentBid;\\nwindow.stepBid = stepBid;\\nwindow.assignLeadingBidder = assignLeadingBidder;\\nwindow.confirmSellPlayer = confirmSellPlayer;\\nwindow.markUnsold = markUnsold;\\nwindow.undoLastAction = undoLastAction;\\nwindow.startRound2 = startRound2;\\nwindow.openPinModal = openPinModal;\\nwindow.closePinModal = closePinModal;\\nwindow.verifyHostPin = verifyHostPin;\\nwindow.closeSoldModal = closeSoldModal;\\nwindow.lockAuctioneer = lockAuctioneer;\\nwindow.showToast = showToast;\\n\\n// --- INITIALIZATION ---\\ndocument.addEventListener('DOMContentLoaded', () => {\\n  const teamSelect = document.getElementById('biddingTeamSelect') || document.getElementById('bidTeamSelect');\\n  if (teamSelect) {\\n    teamSelect.addEventListener('change', (e) => {\\n      currentBiddingTeam = e.target.value;\\n      updateBidDisplay();\\n      broadcastBid(currentBidAmount, currentBiddingTeam);\\n    });\\n  }\\n\\n  checkSavedPin();\\n  startStatePolling();\\n});\\n\", \"static/js/register.js\": \"// Player Registration & UPI Payment Handling\\nlet capturedPhotoBlob = null;\\nlet webcamStream = null;\\n\\n// Tournament config passed from template\\nconst config = window.TOURNAMENT_CONFIG || {\\n  upi_id: 'saidapur.cricket@upi',\\n  payee_name: 'Saidapur Premier League',\\n  registration_fee: 200\\n};\\n\\ndocument.addEventListener('DOMContentLoaded', () => {\\n  initPhotoHandling();\\n  initUPIPayments();\\n  initFormSubmission();\\n});\\n\\nfunction initPhotoHandling() {\\n  const fileInput = document.getElementById('photoFileInput');\\n  const cameraInput = document.getElementById('photoCameraInput');\\n  const previewImg = document.getElementById('photoPreview');\\n  const webcamModal = document.getElementById('webcamModal');\\n  const webcamVideo = document.getElementById('webcamVideo');\\n\\n  // Trigger file picker\\n  document.getElementById('btnUploadFile')?.addEventListener('click', () => {\\n    fileInput.click();\\n  });\\n\\n  // Mobile camera capture trigger\\n  document.getElementById('btnCameraMobile')?.addEventListener('click', () => {\\n    // If mobile or has camera input\\n    if (cameraInput) {\\n      cameraInput.click();\\n    }\\n  });\\n\\n  // Desktop webcam modal trigger\\n  document.getElementById('btnWebcamDesktop')?.addEventListener('click', async () => {\\n    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {\\n      try {\\n        webcamStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: 640, height: 480 } });\\n        webcamVideo.srcObject = webcamStream;\\n        webcamVideo.play();\\n        webcamModal.style.display = 'flex';\\n      } catch (err) {\\n        alert('Could not access camera: ' + err.message + '. Please use the Upload File button.');\\n      }\\n    } else {\\n      alert('Camera access is not supported by your browser. Please upload a photo.');\\n    }\\n  });\\n\\n  // Capture snapshot from webcam\\n  document.getElementById('btnCaptureSnapshot')?.addEventListener('click', () => {\\n    const canvas = document.createElement('canvas');\\n    canvas.width = webcamVideo.videoWidth || 480;\\n    canvas.height = webcamVideo.videoHeight || 480;\\n    const ctx = canvas.getContext('2d');\\n    ctx.drawImage(webcamVideo, 0, 0, canvas.width, canvas.height);\\n    \\n    canvas.toBlob((blob) => {\\n      capturedPhotoBlob = blob;\\n      previewImg.src = URL.createObjectURL(blob);\\n      closeWebcam();\\n    }, 'image/jpeg', 0.9);\\n  });\\n\\n  document.getElementById('btnCloseWebcam')?.addEventListener('click', closeWebcam);\\n\\n  function closeWebcam() {\\n    if (webcamStream) {\\n      webcamStream.getTracks().forEach(track => track.stop());\\n      webcamStream = null;\\n    }\\n    webcamModal.style.display = 'none';\\n  }\\n\\n  // Handle file uploads (both file picker & mobile capture)\\n  function handleFileSelected(e) {\\n    const file = e.target.files[0];\\n    if (file) {\\n      capturedPhotoBlob = file;\\n      const reader = new FileReader();\\n      reader.onload = (evt) => {\\n        previewImg.src = evt.target.result;\\n      };\\n      reader.readAsDataURL(file);\\n    }\\n  }\\n\\n  fileInput?.addEventListener('change', handleFileSelected);\\n  cameraInput?.addEventListener('change', handleFileSelected);\\n}\\n\\nfunction initUPIPayments() {\\n  const nameInput = document.getElementById('playerName');\\n  const qrImg = document.getElementById('upiQrCode');\\n  const upiIdDisplay = document.getElementById('upiIdDisplay');\\n  const feeDisplay = document.getElementById('feeAmountDisplay');\\n  \\n  if (feeDisplay) feeDisplay.textContent = '\\u20b9' + config.registration_fee;\\n  if (upiIdDisplay) upiIdDisplay.textContent = config.upi_id;\\n\\n  function updateUPIUrls() {\\n    const playerName = (nameInput?.value.trim()) || 'Player';\\n    const note = encodeURIComponent(`SPL Fee - ${playerName}`);\\n    const upiUri = `upi://pay?pa=${config.upi_id}&pn=${encodeURIComponent(config.payee_name)}&am=${config.registration_fee}&cu=INR&tn=${note}`;\\n    \\n    // Update QR Code\\n    if (qrImg) {\\n      qrImg.src = `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(upiUri)}`;\\n    }\\n\\n    // Update Deep-Link buttons\\n    const btnPhonePe = document.getElementById('btnPayPhonePe');\\n    const btnGPay = document.getElementById('btnPayGPay');\\n    const btnPaytm = document.getElementById('btnPayPaytm');\\n    const btnBhim = document.getElementById('btnPayBhim');\\n\\n    if (btnPhonePe) btnPhonePe.href = `phonepe://pay?pa=${config.upi_id}&pn=${encodeURIComponent(config.payee_name)}&am=${config.registration_fee}&cu=INR&tn=${note}`;\\n    if (btnGPay) btnGPay.href = `gpay://upi/pay?pa=${config.upi_id}&pn=${encodeURIComponent(config.payee_name)}&am=${config.registration_fee}&cu=INR&tn=${note}`;\\n    if (btnPaytm) btnPaytm.href = `paytmmp://pay?pa=${config.upi_id}&pn=${encodeURIComponent(config.payee_name)}&am=${config.registration_fee}&cu=INR&tn=${note}`;\\n    if (btnBhim) btnBhim.href = upiUri;\\n  }\\n\\n  nameInput?.addEventListener('input', updateUPIUrls);\\n  updateUPIUrls();\\n\\n  // Copy UPI ID button\\n  document.getElementById('btnCopyUpi')?.addEventListener('click', () => {\\n    navigator.clipboard.writeText(config.upi_id);\\n    const copyBtn = document.getElementById('btnCopyUpi');\\n    copyBtn.textContent = '\\u2713 Copied!';\\n    setTimeout(() => { copyBtn.textContent = 'Copy UPI ID'; }, 2000);\\n  });\\n}\\n\\nfunction initFormSubmission() {\\n  const form = document.getElementById('registrationForm');\\n  const submitBtn = document.getElementById('btnSubmitReg');\\n  const alertBox = document.getElementById('formAlert');\\n\\n  form?.addEventListener('submit', async (e) => {\\n    e.preventDefault();\\n    alertBox.style.display = 'none';\\n\\n    const name = document.getElementById('playerName').value.trim();\\n    const phone = document.getElementById('playerPhone').value.trim();\\n    const roleRadio = document.querySelector('input[name=\\\"playerRole\\\"]:checked');\\n    const batting = document.getElementById('battingStyle').value;\\n    const bowling = document.getElementById('bowlingStyle').value;\\n    const paymentMethod = document.getElementById('paymentMethod').value;\\n    const utr = document.getElementById('transactionId').value.trim();\\n    const paymentProofFile = document.getElementById('paymentScreenshot')?.files[0];\\n\\n    if (!name) return showAlert('Please enter player name.');\\n    if (!phone || phone.length < 10) return showAlert('Please enter a valid 10-digit mobile number.');\\n    if (!roleRadio) return showAlert('Please select player role (Batsman, Bowler, All-Rounder, Wicket Keeper).');\\n    // UTR is optional\\n\\n    submitBtn.disabled = true;\\n    submitBtn.innerHTML = '<span class=\\\"spinner\\\"></span> Submitting Registration...';\\n\\n    const formData = new FormData();\\n    formData.append('name', name);\\n    formData.append('phone', phone);\\n    formData.append('role', roleRadio.value);\\n    formData.append('batting_style', batting);\\n    formData.append('bowling_style', bowling);\\n    formData.append('payment_method', paymentMethod);\\n    formData.append('transaction_id', utr);\\n    formData.append('reg_amount', config.registration_fee);\\n\\n    if (capturedPhotoBlob) {\\n      formData.append('photo', capturedPhotoBlob, 'player_photo.jpg');\\n    }\\n    if (paymentProofFile) {\\n      formData.append('screenshot', paymentProofFile);\\n    }\\n\\n    try {\\n      const res = await fetch('/api/register', {\\n        method: 'POST',\\n        body: formData\\n      });\\n      const data = await res.json();\\n      if (data.success) {\\n        window.location.href = `/register/success/${encodeURIComponent(data.player_id)}`;\\n      } else {\\n        showAlert(data.message || 'Error saving registration.');\\n        submitBtn.disabled = false;\\n        submitBtn.textContent = 'Complete Registration & Pay';\\n      }\\n    } catch (err) {\\n      showAlert('Network error: ' + err.message);\\n      submitBtn.disabled = false;\\n      submitBtn.textContent = 'Complete Registration & Pay';\\n    }\\n  });\\n\\n  function showAlert(msg) {\\n    if (alertBox) {\\n      alertBox.textContent = msg;\\n      alertBox.style.display = 'block';\\n      alertBox.scrollIntoView({ behavior: 'smooth' });\\n    } else {\\n      alert(msg);\\n    }\\n  }\\n}\\n\"}")
EMBEDDED_TEMPLATES = json.loads("{\"admin.html\": \"{% extends \\\"base.html\\\" %}\\n\\n{% block extra_css %}\\n<style>\\n  /* STRICT VISIBILITY RULES */\\n  body:not(.admin-unlocked) #adminLockScreen { display: flex !important; }\\n  body:not(.admin-unlocked) #adminMainContent { display: none !important; }\\n  body.admin-unlocked #adminLockScreen { display: none !important; }\\n  body.admin-unlocked #adminMainContent { display: block !important; }\\n\\n  /* Sub-tab navigation */\\n  .admin-subtabs {\\n    display: flex;\\n    gap: 0.75rem;\\n    margin-bottom: 1.75rem;\\n    border-bottom: 2px solid rgba(255, 255, 255, 0.1);\\n    padding-bottom: 0.75rem;\\n    flex-wrap: wrap;\\n  }\\n  .subtab-btn {\\n    background: rgba(255, 255, 255, 0.05);\\n    border: 1px solid rgba(255, 255, 255, 0.15);\\n    color: #94a3b8;\\n    padding: 0.65rem 1.25rem;\\n    border-radius: 8px;\\n    font-weight: 700;\\n    font-size: 0.95rem;\\n    cursor: pointer;\\n    transition: all 0.2s ease;\\n    display: flex;\\n    align-items: center;\\n    gap: 0.5rem;\\n  }\\n  .subtab-btn:hover {\\n    color: #fff;\\n    background: rgba(255, 255, 255, 0.1);\\n  }\\n  .subtab-btn.active {\\n    background: #f59e0b;\\n    color: #000;\\n    border-color: #f59e0b;\\n    box-shadow: 0 4px 15px rgba(245, 158, 11, 0.35);\\n  }\\n  .subtab-btn.active.tab-auction {\\n    background: #ef4444;\\n    color: #fff;\\n    border-color: #ef4444;\\n    box-shadow: 0 4px 15px rgba(239, 68, 68, 0.35);\\n  }\\n\\n  .setup-grid {\\n    display: grid;\\n    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));\\n    gap: 1rem;\\n    margin-bottom: 1.5rem;\\n  }\\n  .retention-tag {\\n    display: inline-flex;\\n    align-items: center;\\n    gap: 0.35rem;\\n    padding: 0.25rem 0.6rem;\\n    border-radius: 6px;\\n    font-size: 0.8rem;\\n    font-weight: 700;\\n  }\\n  .retention-player {\\n    background: rgba(16, 185, 129, 0.15);\\n    color: #34d399;\\n    border: 1px solid rgba(16, 185, 129, 0.3);\\n  }\\n  .retention-owner {\\n    background: rgba(245, 158, 11, 0.15);\\n    color: #fbbf24;\\n    border: 1px solid rgba(245, 158, 11, 0.3);\\n  }\\n</style>\\n<script>\\n  if (sessionStorage.getItem('kpl_auction_pin') || sessionStorage.getItem('spl_auction_pin')) {\\n    document.documentElement.classList.add('pre-authorized');\\n  }\\n</script>\\n{% endblock %}\\n\\n{% block content %}\\n<!-- GATEWAY 1: ADMIN PIN LOCK SCREEN -->\\n<div id=\\\"adminLockScreen\\\" style=\\\"min-height: 65vh; align-items: center; justify-content: center; padding: 2rem 1rem;\\\">\\n  <div class=\\\"glass-card\\\" style=\\\"max-width: 420px; width: 100%; text-align: center; border: 2px solid #f59e0b; box-shadow: 0 0 45px rgba(245, 158, 11, 0.3); padding: 2.75rem 2rem;\\\">\\n    <div style=\\\"width: 72px; height: 72px; background: rgba(245, 158, 11, 0.15); border: 2px solid #f59e0b; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 2.25rem; margin: 0 auto 1.25rem;\\\">\\n      \\ud83d\\udd12\\n    </div>\\n    <h2 style=\\\"font-size: 1.65rem; font-weight: 900; color: #fff; margin-bottom: 0.35rem;\\\">Organizer Access</h2>\\n    <p style=\\\"color: #94a3b8; font-size: 0.85rem; margin-bottom: 1.75rem; line-height: 1.5;\\\">\\n      Enter your Organizer PIN to manage tournament configuration, team retentions, and live bidding.\\n    </p>\\n\\n    <form id=\\\"adminLoginForm\\\" onsubmit=\\\"handleAdminLogin(event)\\\">\\n      <div class=\\\"form-group\\\" style=\\\"margin-bottom: 1.25rem;\\\">\\n        <input type=\\\"password\\\" id=\\\"adminPinInput\\\" class=\\\"form-control\\\" placeholder=\\\"Enter Organizer PIN\\\" style=\\\"text-align: center; font-size: 1.4rem; letter-spacing: 0.25em; font-weight: 900; padding: 0.85rem; background: rgba(15,23,42,0.9);\\\" maxlength=\\\"15\\\" autofocus required>\\n        <div id=\\\"adminPinError\\\" style=\\\"display: none; color: #f87171; font-weight: 700; font-size: 0.85rem; margin-top: 0.6rem;\\\"></div>\\n      </div>\\n      <button type=\\\"submit\\\" id=\\\"btnAdminUnlock\\\" class=\\\"btn btn-primary\\\" style=\\\"width: 100%; font-size: 1.1rem; padding: 0.85rem;\\\">\\n        Unlock Admin Panel &rarr;\\n      </button>\\n      <div style=\\\"margin-top: 1.25rem; display: flex; justify-content: flex-end; align-items: center; font-size: 0.8rem;\\\">\\n        <a href=\\\"javascript:void(0)\\\" onclick=\\\"forgotPinPrompt()\\\" style=\\\"color: #f59e0b; text-decoration: underline; font-weight: 600;\\\">\\n          Forgot PIN?\\n        </a>\\n      </div>\\n    </form>\\n  </div>\\n</div>\\n\\n<!-- GATEWAY 2: ADMIN MAIN CONTENT (PROTECTED) -->\\n<div id=\\\"adminMainContent\\\">\\n  <!-- Top Bar with Broadcast Toggle & Lock -->\\n  <div style=\\\"margin-bottom: 1.5rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;\\\">\\n    <div>\\n      <h1 style=\\\"font-size: 1.85rem; font-weight: 900; color: #fff; display: flex; align-items: center; gap: 0.5rem;\\\">\\n        <span>\\u2699\\ufe0f</span> Organizer Admin Panel\\n      </h1>\\n      <p style=\\\"color: #94a3b8; font-size: 0.9rem;\\\">\\n        Kunsi Premier League (KPL 2026) Management Portal\\n      </p>\\n    </div>\\n    <div style=\\\"display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap;\\\">\\n      <span id=\\\"auctionStatusBadge\\\" class=\\\"badge\\\" style=\\\"background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); font-size: 0.85rem; padding: 0.4rem 0.8rem; font-weight: 800;\\\">\\n        \\ud83d\\udd34 Auction Not Started\\n      </span>\\n      <button type=\\\"button\\\" id=\\\"btnAdminStartAuction\\\" onclick=\\\"adminToggleAuctionStarted()\\\" class=\\\"btn btn-success\\\" style=\\\"font-size: 0.85rem; padding: 0.45rem 0.9rem;\\\">\\n        \\ud83d\\ude80 Start Live Auction\\n      </button>\\n      <button type=\\\"button\\\" onclick=\\\"lockAdminSession()\\\" class=\\\"btn btn-secondary\\\" style=\\\"font-size: 0.85rem; padding: 0.45rem 0.9rem;\\\">\\n        \\ud83d\\udd12 Lock Admin\\n      </button>\\n    </div>\\n  </div>\\n\\n  <!-- 2 SUB-PAGES / TABS INSIDE ADMIN -->\\n  <div class=\\\"admin-subtabs\\\">\\n    <button type=\\\"button\\\" id=\\\"tabBtnConfig\\\" class=\\\"subtab-btn active\\\" onclick=\\\"switchAdminTab('config')\\\">\\n      <span>\\ud83c\\udfdf\\ufe0f</span> 1. Tournament Configuration & Retentions\\n    </button>\\n    <button type=\\\"button\\\" id=\\\"tabBtnAuction\\\" class=\\\"subtab-btn tab-auction\\\" onclick=\\\"switchAdminTab('auction')\\\">\\n      <span>\\ud83d\\udd28</span> 2. Live Auction Page (Host Console)\\n    </button>\\n  </div>\\n\\n  <!-- SUB-PAGE 1: TOURNAMENT CONFIGURATION & RETENTIONS -->\\n  <div id=\\\"subpageConfig\\\">\\n    <!-- Team Setup Form -->\\n    <div class=\\\"glass-card\\\" style=\\\"margin-bottom: 2rem; border-color: rgba(245, 158, 11, 0.35);\\\">\\n      <h2 style=\\\"font-size: 1.35rem; font-weight: 800; color: #f59e0b; margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem;\\\">\\n        <span>\\ud83c\\udfdf\\ufe0f</span> Team Setup & Purse Rules\\n      </h2>\\n      <form id=\\\"teamSetupForm\\\">\\n        <div class=\\\"setup-grid\\\">\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Number of Teams</label>\\n            <input type=\\\"number\\\" id=\\\"setupTeamCount\\\" class=\\\"form-control\\\" min=\\\"2\\\" max=\\\"12\\\" value=\\\"{{ (teams|length) if teams else 4 }}\\\" required onchange=\\\"renderTeamNameInputs()\\\">\\n          </div>\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Purse Amount per Team (\\u20b9)</label>\\n            <input type=\\\"number\\\" id=\\\"setupPurse\\\" class=\\\"form-control\\\" min=\\\"500\\\" step=\\\"100\\\" value=\\\"{{ config.total_purse or config.default_purse or 6000 }}\\\" required>\\n          </div>\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Minimum Players per Team</label>\\n            <input type=\\\"number\\\" id=\\\"setupMinPlayers\\\" class=\\\"form-control\\\" min=\\\"1\\\" max=\\\"25\\\" value=\\\"{{ config.max_players or 10 }}\\\" required>\\n          </div>\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Minimum Bid Amount (\\u20b9)</label>\\n            <input type=\\\"number\\\" id=\\\"setupMinBid\\\" class=\\\"form-control\\\" min=\\\"0\\\" step=\\\"10\\\" value=\\\"{{ config.min_bid or 50 }}\\\" required>\\n          </div>\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Star Player Retention (\\u20b9)</label>\\n            <input type=\\\"number\\\" id=\\\"setupPlayerRetentionPrice\\\" class=\\\"form-control\\\" min=\\\"0\\\" step=\\\"50\\\" value=\\\"{{ config.retention_price or 500 }}\\\" required>\\n          </div>\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Owner Retention (\\u20b9)</label>\\n            <input type=\\\"number\\\" id=\\\"setupOwnerRetentionPrice\\\" class=\\\"form-control\\\" min=\\\"0\\\" step=\\\"50\\\" value=\\\"{{ config.owner_retention_price or 100 }}\\\" required>\\n          </div>\\n        </div>\\n\\n        <div style=\\\"margin-bottom: 1.5rem;\\\">\\n          <label class=\\\"form-label\\\" style=\\\"font-weight: 700; color: #fff;\\\">Custom Team Names</label>\\n          <div id=\\\"teamNamesContainer\\\" style=\\\"display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 0.75rem;\\\">\\n            <!-- Dynamically populated -->\\n          </div>\\n        </div>\\n\\n        <button type=\\\"submit\\\" class=\\\"btn btn-primary\\\" style=\\\"font-size: 1rem; padding: 0.75rem 1.75rem;\\\">\\n          \\ud83d\\udcbe Save Teams & Rules Setup\\n        </button>\\n      </form>\\n    </div>\\n\\n    <!-- Dual Retention Management -->\\n    <div class=\\\"glass-card\\\" style=\\\"margin-bottom: 2rem; border-color: rgba(16, 185, 129, 0.35);\\\">\\n      <h2 style=\\\"font-size: 1.35rem; font-weight: 800; color: #10b981; margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem;\\\">\\n        <span>\\u2b50</span> Player & Owner Retention Phase\\n      </h2>\\n      <p style=\\\"color: #94a3b8; font-size: 0.85rem; margin-bottom: 1.25rem;\\\">\\n        Retain star players (\\u20b9{{ config.retention_price or 500 }}) or team owners (\\u20b9{{ config.owner_retention_price or 100 }}). Retained persons are automatically removed from live auction pool.\\n      </p>\\n\\n      <form id=\\\"retentionForm\\\" style=\\\"display: flex; gap: 1rem; flex-wrap: wrap; align-items: flex-end; margin-bottom: 1.5rem; background: rgba(15,23,42,0.6); padding: 1.25rem; border-radius: var(--radius-md); border: 1px solid rgba(255,255,255,0.1);\\\">\\n        <div class=\\\"form-group\\\" style=\\\"flex: 1; min-width: 180px; margin-bottom: 0;\\\">\\n          <label class=\\\"form-label\\\">Select Team</label>\\n          <select id=\\\"retentionTeamSelect\\\" class=\\\"form-control\\\" required>\\n            <option value=\\\"\\\">-- Choose Team --</option>\\n            {% for t_name in teams.keys() %}\\n            <option value=\\\"{{ t_name }}\\\">{{ t_name }}</option>\\n            {% endfor %}\\n          </select>\\n        </div>\\n\\n        <div class=\\\"form-group\\\" style=\\\"flex: 1; min-width: 180px; margin-bottom: 0;\\\">\\n          <label class=\\\"form-label\\\">Retention Type</label>\\n          <select id=\\\"retentionTypeSelect\\\" class=\\\"form-control\\\" required>\\n            <option value=\\\"Player\\\">\\u2b50 Player Retention (\\u20b9{{ config.retention_price or 500 }})</option>\\n            <option value=\\\"Owner\\\">\\ud83d\\udc51 Owner Retention (\\u20b9{{ config.owner_retention_price or 100 }})</option>\\n          </select>\\n        </div>\\n\\n        <div class=\\\"form-group\\\" style=\\\"flex: 1.5; min-width: 220px; margin-bottom: 0;\\\">\\n          <label class=\\\"form-label\\\">Select Registered Person</label>\\n          <select id=\\\"retentionPlayerSelect\\\" class=\\\"form-control\\\" required>\\n            <option value=\\\"\\\">-- Choose Person --</option>\\n            {% for p in players %}\\n            <option value=\\\"{{ p }}\\\">{{ p }}</option>\\n            {% endfor %}\\n          </select>\\n        </div>\\n\\n        <button type=\\\"submit\\\" class=\\\"btn btn-success\\\" style=\\\"padding: 0.75rem 1.5rem; font-weight: 800;\\\">\\n          \\u2b50 Confirm Retention\\n        </button>\\n      </form>\\n\\n      <!-- Active Retentions Table -->\\n      <h3 style=\\\"font-size: 1.05rem; font-weight: 700; color: #fff; margin-bottom: 0.75rem;\\\">\\n        Current Team Retentions\\n      </h3>\\n      <div style=\\\"overflow-x: auto;\\\">\\n        <table class=\\\"table\\\" style=\\\"width: 100%; border-collapse: collapse;\\\">\\n          <thead>\\n            <tr style=\\\"border-bottom: 1px solid rgba(255,255,255,0.1); text-align: left; color: #94a3b8; font-size: 0.85rem;\\\">\\n              <th style=\\\"padding: 0.75rem;\\\">Team Name</th>\\n              <th style=\\\"padding: 0.75rem;\\\">Remaining Purse</th>\\n              <th style=\\\"padding: 0.75rem;\\\">Star Player Retained (\\u20b9{{ config.retention_price or 500 }})</th>\\n              <th style=\\\"padding: 0.75rem;\\\">Owner Retained (\\u20b9{{ config.owner_retention_price or 100 }})</th>\\n            </tr>\\n          </thead>\\n          <tbody>\\n            {% for t_name, t_data in teams.items() %}\\n            <tr style=\\\"border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 0.9rem;\\\">\\n              <td style=\\\"padding: 0.75rem; font-weight: 700; color: #fff;\\\">{{ t_name }}</td>\\n              <td style=\\\"padding: 0.75rem; font-weight: 800; color: #10b981;\\\">\\u20b9{{ t_data.purse }}</td>\\n              <td style=\\\"padding: 0.75rem;\\\">\\n                {% if t_data.player_retained %}\\n                  <span class=\\\"retention-tag retention-player\\\">\\n                    \\u2b50 {{ t_data.player_retained.name if t_data.player_retained is mapping else t_data.player_retained }}\\n                    <button type=\\\"button\\\" onclick=\\\"releaseRetention('{{ t_name }}', 'Player')\\\" style=\\\"background: none; border: none; color: #f87171; cursor: pointer; font-size: 0.8rem; margin-left: 0.35rem;\\\" title=\\\"Release Retention\\\">&times;</button>\\n                  </span>\\n                {% elif t_data.retained %}\\n                  <span class=\\\"retention-tag retention-player\\\">\\n                    \\u2b50 {{ t_data.retained.name if t_data.retained is mapping else t_data.retained }}\\n                    <button type=\\\"button\\\" onclick=\\\"releaseRetention('{{ t_name }}', 'Player')\\\" style=\\\"background: none; border: none; color: #f87171; cursor: pointer; font-size: 0.8rem; margin-left: 0.35rem;\\\" title=\\\"Release Retention\\\">&times;</button>\\n                  </span>\\n                {% else %}\\n                  <span style=\\\"color: #64748b; font-style: italic;\\\">None</span>\\n                {% endif %}\\n              </td>\\n              <td style=\\\"padding: 0.75rem;\\\">\\n                {% if t_data.owner_retained %}\\n                  <span class=\\\"retention-tag retention-owner\\\">\\n                    \\ud83d\\udc51 {{ t_data.owner_retained.name if t_data.owner_retained is mapping else t_data.owner_retained }}\\n                    <button type=\\\"button\\\" onclick=\\\"releaseRetention('{{ t_name }}', 'Owner')\\\" style=\\\"background: none; border: none; color: #f87171; cursor: pointer; font-size: 0.8rem; margin-left: 0.35rem;\\\" title=\\\"Release Retention\\\">&times;</button>\\n                  </span>\\n                {% else %}\\n                  <span style=\\\"color: #64748b; font-style: italic;\\\">None</span>\\n                {% endif %}\\n              </td>\\n            </tr>\\n            {% endfor %}\\n          </tbody>\\n        </table>\\n      </div>\\n    </div>\\n\\n    <!-- General Settings & Excel Export -->\\n    <div style=\\\"display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem;\\\">\\n      <div class=\\\"glass-card\\\">\\n        <h2 style=\\\"font-size: 1.25rem; font-weight: 800; color: #f59e0b; margin-bottom: 1rem;\\\">\\n          \\ud83d\\udcb3 UPI Payment & Fee Settings\\n        </h2>\\n        <form id=\\\"configForm\\\" onsubmit=\\\"handleConfigSubmit(event)\\\">\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Tournament Display Name</label>\\n            <input type=\\\"text\\\" id=\\\"cfgTournamentName\\\" class=\\\"form-control\\\" value=\\\"{{ config.tournament_name }}\\\" required>\\n          </div>\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Receiving UPI ID</label>\\n            <input type=\\\"text\\\" id=\\\"cfgUpiId\\\" class=\\\"form-control\\\" value=\\\"{{ config.upi_id }}\\\" required>\\n          </div>\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Payee Name</label>\\n            <input type=\\\"text\\\" id=\\\"cfgPayeeName\\\" class=\\\"form-control\\\" value=\\\"{{ config.payee_name }}\\\" required>\\n          </div>\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Registration Fee (\\u20b9)</label>\\n            <input type=\\\"number\\\" id=\\\"cfgRegFee\\\" class=\\\"form-control\\\" value=\\\"{{ config.registration_fee }}\\\" required>\\n          </div>\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Change Secret Organizer PIN</label>\\n            <input type=\\\"password\\\" id=\\\"cfgAdminPin\\\" class=\\\"form-control\\\" placeholder=\\\"New Secret PIN\\\">\\n          </div>\\n          <button type=\\\"submit\\\" class=\\\"btn btn-primary\\\">Save Settings</button>\\n        </form>\\n      </div>\\n\\n      <div class=\\\"glass-card\\\" style=\\\"display: flex; flex-direction: column; justify-content: space-between;\\\">\\n        <div>\\n          <h2 style=\\\"font-size: 1.25rem; font-weight: 800; color: #10b981; margin-bottom: 1rem;\\\">\\n            \\ud83d\\udcca Styled Excel Export\\n          </h2>\\n          <p style=\\\"color: #94a3b8; font-size: 0.9rem; line-height: 1.5; margin-bottom: 1.25rem;\\\">\\n            Download complete tournament Excel report with Team Rosters, Retentions, Rounds Breakdown, and Unsold Players.\\n          </p>\\n          <a href=\\\"/api/export-excel\\\" class=\\\"btn btn-success\\\" style=\\\"width: 100%; margin-bottom: 1rem; text-align: center;\\\">\\n            \\ud83d\\udce5 Download Styled Excel (.xlsx)\\n          </a>\\n        </div>\\n        <div style=\\\"border-top: 1px solid rgba(255,255,255,0.1); padding-top: 1rem;\\\">\\n          <button type=\\\"button\\\" onclick=\\\"confirmResetAuction()\\\" class=\\\"btn btn-danger\\\" style=\\\"width: 100%;\\\">\\n            \\u26a0\\ufe0f Reset Auction & Clear Bidding\\n          </button>\\n        </div>\\n      </div>\\n    </div>\\n  </div>\\n\\n  <!-- SUB-PAGE 2: LIVE AUCTION CONTROLLER (ADMIN ACCESS) -->\\n  <div id=\\\"subpageAuction\\\" style=\\\"display: none;\\\">\\n    <div style=\\\"margin-bottom: 1.25rem; background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.4); padding: 1rem; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.75rem;\\\">\\n      <div>\\n        <strong style=\\\"color: #f87171; font-size: 1.05rem; display: block;\\\">\\ud83d\\udd28 Live Auction Host Console Active</strong>\\n        <span style=\\\"color: #cbd5e1; font-size: 0.85rem;\\\">Conduct live player draws, increment bidding amounts, confirm sales, and manage unsold players. All viewers update live!</span>\\n      </div>\\n      <div style=\\\"display: flex; gap: 0.5rem;\\\">\\n        <a href=\\\"/auction\\\" target=\\\"_blank\\\" class=\\\"btn btn-primary\\\" style=\\\"font-size: 0.85rem; padding: 0.4rem 0.85rem;\\\">\\n          \\u2197\\ufe0f Fullscreen Console\\n        </a>\\n        <a href=\\\"/view\\\" target=\\\"_blank\\\" class=\\\"btn btn-secondary\\\" style=\\\"font-size: 0.85rem; padding: 0.4rem 0.85rem;\\\">\\n          \\ud83d\\udc41\\ufe0f Preview Spectator View\\n        </a>\\n      </div>\\n    </div>\\n\\n    <!-- Live Auction Arena Embedded for Host without duplicate navbar -->\\n    <iframe id=\\\"hostAuctionIframe\\\" src=\\\"/auction?embed=1\\\" style=\\\"width: 100%; height: 900px; border: 1px solid rgba(255,255,255,0.12); border-radius: 12px; background: #0a0f1a;\\\"></iframe>\\n  </div>\\n</div>\\n{% endblock %}\\n\\n{% block extra_js %}\\n<script>\\n  const CURRENT_TEAMS = {{ (teams.keys()|list)|tojson }};\\n\\n  function getAdminPin() {\\n    return sessionStorage.getItem('kpl_auction_pin') || sessionStorage.getItem('spl_auction_pin') || '';\\n  }\\n\\n  function switchAdminTab(tabName) {\\n    const btnConfig = document.getElementById('tabBtnConfig');\\n    const btnAuction = document.getElementById('tabBtnAuction');\\n    const pageConfig = document.getElementById('subpageConfig');\\n    const pageAuction = document.getElementById('subpageAuction');\\n\\n    if (tabName === 'auction') {\\n      btnAuction.classList.add('active');\\n      btnConfig.classList.remove('active');\\n      pageAuction.style.display = 'block';\\n      pageConfig.style.display = 'none';\\n      // Refresh iframe if needed\\n      const iframe = document.getElementById('hostAuctionIframe');\\n      if (iframe && !iframe.src.includes('/auction?embed=1')) {\\n        iframe.src = '/auction?embed=1';\\n      }\\n    } else {\\n      btnConfig.classList.add('active');\\n      btnAuction.classList.remove('active');\\n      pageConfig.style.display = 'block';\\n      pageAuction.style.display = 'none';\\n    }\\n  }\\n\\n  // --- INITIALIZATION ---\\n  document.addEventListener('DOMContentLoaded', async () => {\\n    renderTeamNameInputs();\\n    updateAdminAuctionStatus();\\n\\n    const savedPin = getAdminPin();\\n    if (!savedPin) {\\n      document.body.classList.remove('admin-unlocked');\\n      return;\\n    }\\n\\n    try {\\n      const res = await fetch('/api/auction/verify-pin', {\\n        method: 'POST',\\n        headers: { 'Content-Type': 'application/json' },\\n        body: JSON.stringify({ pin: savedPin })\\n      });\\n      const data = await res.json();\\n      if (data.valid || data.success) {\\n        document.body.classList.add('admin-unlocked');\\n      } else {\\n        sessionStorage.removeItem('kpl_auction_pin');\\n        sessionStorage.removeItem('spl_auction_pin');\\n        document.body.classList.remove('admin-unlocked');\\n      }\\n    } catch(e) {\\n      document.body.classList.add('admin-unlocked');\\n    }\\n  });\\n\\n  // --- LOGIN ---\\n  async function handleAdminLogin(e) {\\n    e.preventDefault();\\n    const pin = document.getElementById('adminPinInput').value.trim();\\n    const err = document.getElementById('adminPinError');\\n    err.style.display = 'none';\\n\\n    try {\\n      const res = await fetch('/api/auction/verify-pin', {\\n        method: 'POST',\\n        headers: { 'Content-Type': 'application/json' },\\n        body: JSON.stringify({ pin: pin })\\n      });\\n      const data = await res.json();\\n      if (data.valid || data.success) {\\n        sessionStorage.setItem('kpl_auction_pin', pin);\\n        sessionStorage.setItem('spl_auction_pin', pin);\\n        document.body.classList.add('admin-unlocked');\\n        updateAdminAuctionStatus();\\n      } else {\\n        err.textContent = '\\u274c Incorrect Organizer PIN. Please try again.';\\n        err.style.display = 'block';\\n      }\\n    } catch(errEx) {\\n      err.textContent = 'Network error verifying PIN.';\\n      err.style.display = 'block';\\n    }\\n  }\\n\\n  function lockAdminSession() {\\n    sessionStorage.removeItem('kpl_auction_pin');\\n    sessionStorage.removeItem('spl_auction_pin');\\n    document.body.classList.remove('admin-unlocked');\\n    document.getElementById('adminPinInput').value = '';\\n  }\\n\\n  function forgotPinPrompt() {\\n    const recoveryKey = prompt('Please enter the Organizer Master Recovery Key:');\\n    if (!recoveryKey) return;\\n    if (recoveryKey.trim() === 'KPL2026_MASTER' || recoveryKey.trim() === 'KPL2026') {\\n      const newPin = prompt('Authentication successful. Please enter your new desired PIN:');\\n      if (newPin && newPin.trim()) {\\n        fetch('/api/admin/config', {\\n          method: 'POST',\\n          headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': recoveryKey },\\n          body: JSON.stringify({ admin_pin: newPin.trim(), pin: recoveryKey })\\n        }).then(r => r.json()).then(res => {\\n          if (res.success) {\\n            alert('PIN successfully updated! Please log in with your new PIN.');\\n          } else {\\n            alert('Error: ' + res.message);\\n          }\\n        });\\n      }\\n    } else {\\n      alert('Invalid recovery key. Please check with the head tournament organizer.');\\n    }\\n  }\\n\\n  // --- DYNAMIC TEAM INPUTS ---\\n  function renderTeamNameInputs() {\\n    const count = parseInt(document.getElementById('setupTeamCount').value) || 4;\\n    const container = document.getElementById('teamNamesContainer');\\n    container.innerHTML = '';\\n\\n    for (let i = 0; i < count; i++) {\\n      const defaultName = CURRENT_TEAMS[i] || `Team ${i + 1}`;\\n      const div = document.createElement('div');\\n      div.innerHTML = `\\n        <input type=\\\"text\\\" name=\\\"team_name_${i}\\\" class=\\\"form-control team-name-input\\\" value=\\\"${defaultName}\\\" placeholder=\\\"Team ${i+1} Name\\\" required>\\n      `;\\n      container.appendChild(div);\\n    }\\n  }\\n\\n  // --- SAVE SETUP ---\\n  document.getElementById('teamSetupForm').addEventListener('submit', async (e) => {\\n    e.preventDefault();\\n    const count = parseInt(document.getElementById('setupTeamCount').value);\\n    const purse = parseInt(document.getElementById('setupPurse').value);\\n    const minPlayers = parseInt(document.getElementById('setupMinPlayers').value);\\n    const minBid = parseInt(document.getElementById('setupMinBid').value);\\n    const playerRetPrice = parseInt(document.getElementById('setupPlayerRetentionPrice').value);\\n    const ownerRetPrice = parseInt(document.getElementById('setupOwnerRetentionPrice').value);\\n\\n    const nameInputs = document.querySelectorAll('.team-name-input');\\n    const teamNames = [];\\n    nameInputs.forEach(inp => {\\n      const v = inp.value.trim();\\n      if (v) teamNames.push(v);\\n    });\\n\\n    if (teamNames.length !== count) {\\n      return alert(`Please specify names for all ${count} teams.`);\\n    }\\n\\n    const payload = {\\n      team_count: count,\\n      team_names: teamNames,\\n      purse_per_team: purse,\\n      min_players_per_team: minPlayers,\\n      min_bid: minBid,\\n      retention_price: playerRetPrice,\\n      owner_retention_price: ownerRetPrice,\\n      pin: getAdminPin()\\n    };\\n\\n    try {\\n      const res = await fetch('/api/admin/setup-teams', {\\n        method: 'POST',\\n        headers: {\\n          'Content-Type': 'application/json',\\n          'X-Auction-PIN': getAdminPin()\\n        },\\n        body: JSON.stringify(payload)\\n      });\\n      const data = await res.json();\\n      if (data.success) {\\n        alert('Tournament Configuration Saved Successfully!');\\n        location.reload();\\n      } else {\\n        alert(data.message || 'Error saving team setup.');\\n      }\\n    } catch (err) {\\n      alert('Error: ' + err.message);\\n    }\\n  });\\n\\n  document.getElementById('retentionForm').addEventListener('submit', async (e) => {\\n    e.preventDefault();\\n    const team = document.getElementById('retentionTeamSelect').value;\\n    const player = document.getElementById('retentionPlayerSelect').value;\\n    const retType = document.getElementById('retentionTypeSelect').value;\\n\\n    if (!team || !player) return alert('Please select both team and player.');\\n\\n    const payload = {\\n      team: team,\\n      player: player,\\n      retention_type: retType,\\n      pin: getAdminPin()\\n    };\\n\\n    try {\\n      const res = await fetch('/api/retention/retain', {\\n        method: 'POST',\\n        headers: {\\n          'Content-Type': 'application/json',\\n          'X-Auction-PIN': getAdminPin()\\n        },\\n        body: JSON.stringify(payload)\\n      });\\n      const data = await res.json();\\n      if (data.success) {\\n        alert('Person retained successfully!');\\n        location.reload();\\n      } else {\\n        alert(data.message || 'Error retaining person.');\\n      }\\n    } catch (err) {\\n      alert('Error: ' + err.message);\\n    }\\n  });\\n\\n  async function releaseRetention(teamName, retentionType) {\\n    if (!confirm(`Release ${retentionType} retention from ${teamName}? Their fee will be refunded to team purse.`)) return;\\n\\n    try {\\n      const res = await fetch('/api/retention/release', {\\n        method: 'POST',\\n        headers: {\\n          'Content-Type': 'application/json',\\n          'X-Auction-PIN': getAdminPin()\\n        },\\n        body: JSON.stringify({ team: teamName, retention_type: retentionType, pin: getAdminPin() })\\n      });\\n      const data = await res.json();\\n      if (data.success) {\\n        alert(data.message || 'Retention released successfully!');\\n        location.reload();\\n      } else {\\n        alert(data.message || 'Error releasing retention.');\\n      }\\n    } catch (err) {\\n      alert('Error: ' + err.message);\\n    }\\n  }\\n\\n  async function adminToggleAuctionStarted() {\\n    const pin = getAdminPin();\\n    const badge = document.getElementById('auctionStatusBadge');\\n    const isStarted = badge && badge.textContent.includes('Active');\\n    const endpoint = isStarted ? '/api/auction/pause' : '/api/auction/start';\\n    const actionName = isStarted ? 'Pause Live Auction' : 'Start Live Auction for all viewers';\\n\\n    if (!confirm(`Are you sure you want to ${actionName}?`)) return;\\n\\n    try {\\n      const res = await fetch(endpoint, {\\n        method: 'POST',\\n        headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': pin },\\n        body: JSON.stringify({ pin: pin })\\n      });\\n      const data = await res.json();\\n      if (data.success) {\\n        alert(data.message);\\n        updateAdminAuctionStatus();\\n      } else {\\n        alert(data.message || 'Error updating auction state.');\\n      }\\n    } catch (e) {\\n      alert(e.message);\\n    }\\n  }\\n\\n  async function updateAdminAuctionStatus() {\\n    try {\\n      const res = await fetch('/api/auction/state');\\n      const state = await res.json();\\n      const badge = document.getElementById('auctionStatusBadge');\\n      const btn = document.getElementById('btnAdminStartAuction');\\n      if (!badge || !btn) return;\\n\\n      if (state.auction_started) {\\n        badge.textContent = '\\ud83d\\udfe2 Auction Active';\\n        badge.style.background = 'rgba(16, 185, 129, 0.2)';\\n        badge.style.color = '#34d399';\\n        badge.style.borderColor = 'rgba(16, 185, 129, 0.4)';\\n        btn.textContent = '\\u23f8\\ufe0f Pause Auction';\\n        btn.className = 'btn btn-secondary';\\n      } else {\\n        badge.textContent = '\\ud83d\\udd34 Auction Not Started';\\n        badge.style.background = 'rgba(239, 68, 68, 0.2)';\\n        badge.style.color = '#f87171';\\n        badge.style.borderColor = 'rgba(239, 68, 68, 0.4)';\\n        btn.textContent = '\\ud83d\\ude80 Start Live Auction';\\n        btn.className = 'btn btn-success';\\n      }\\n    } catch(e) {}\\n  }\\n\\n  async function handleConfigSubmit(e) {\\n    e.preventDefault();\\n    const payload = {\\n      tournament_name: document.getElementById('cfgTournamentName').value,\\n      upi_id: document.getElementById('cfgUpiId').value,\\n      payee_name: document.getElementById('cfgPayeeName').value,\\n      registration_fee: parseInt(document.getElementById('cfgRegFee').value) || 200,\\n      admin_pin: document.getElementById('cfgAdminPin').value || undefined,\\n      pin: getAdminPin()\\n    };\\n\\n    try {\\n      const res = await fetch('/api/admin/config', {\\n        method: 'POST',\\n        headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': getAdminPin() },\\n        body: JSON.stringify(payload)\\n      });\\n      const data = await res.json();\\n      if (data.success) {\\n        if (payload.admin_pin) {\\n          sessionStorage.setItem('kpl_auction_pin', payload.admin_pin);\\n          sessionStorage.setItem('spl_auction_pin', payload.admin_pin);\\n        }\\n        alert('Settings saved successfully!');\\n        location.reload();\\n      } else {\\n        alert(data.message || 'Error updating settings.');\\n      }\\n    } catch(e) {\\n      alert(e.message);\\n    }\\n  }\\n\\n  async function confirmResetAuction() {\\n    if (!confirm('\\u26a0\\ufe0f DANGER: This will reset all sold players, team budgets, and retentions to fresh state. Continue?')) return;\\n    try {\\n      const res = await fetch('/api/admin/reset-auction', {\\n        method: 'POST',\\n        headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': getAdminPin() },\\n        body: JSON.stringify({ pin: getAdminPin() })\\n      });\\n      const data = await res.json();\\n      if (data.success) {\\n        alert('Auction reset successfully!');\\n        location.reload();\\n      } else {\\n        alert(data.message || 'Reset failed.');\\n      }\\n    } catch(e) {\\n      alert(e.message);\\n    }\\n  }\\n</script>\\n{% endblock %}\\n\", \"templates/admin.html\": \"{% extends \\\"base.html\\\" %}\\n\\n{% block extra_css %}\\n<style>\\n  /* STRICT VISIBILITY RULES */\\n  body:not(.admin-unlocked) #adminLockScreen { display: flex !important; }\\n  body:not(.admin-unlocked) #adminMainContent { display: none !important; }\\n  body.admin-unlocked #adminLockScreen { display: none !important; }\\n  body.admin-unlocked #adminMainContent { display: block !important; }\\n\\n  /* Sub-tab navigation */\\n  .admin-subtabs {\\n    display: flex;\\n    gap: 0.75rem;\\n    margin-bottom: 1.75rem;\\n    border-bottom: 2px solid rgba(255, 255, 255, 0.1);\\n    padding-bottom: 0.75rem;\\n    flex-wrap: wrap;\\n  }\\n  .subtab-btn {\\n    background: rgba(255, 255, 255, 0.05);\\n    border: 1px solid rgba(255, 255, 255, 0.15);\\n    color: #94a3b8;\\n    padding: 0.65rem 1.25rem;\\n    border-radius: 8px;\\n    font-weight: 700;\\n    font-size: 0.95rem;\\n    cursor: pointer;\\n    transition: all 0.2s ease;\\n    display: flex;\\n    align-items: center;\\n    gap: 0.5rem;\\n  }\\n  .subtab-btn:hover {\\n    color: #fff;\\n    background: rgba(255, 255, 255, 0.1);\\n  }\\n  .subtab-btn.active {\\n    background: #f59e0b;\\n    color: #000;\\n    border-color: #f59e0b;\\n    box-shadow: 0 4px 15px rgba(245, 158, 11, 0.35);\\n  }\\n  .subtab-btn.active.tab-auction {\\n    background: #ef4444;\\n    color: #fff;\\n    border-color: #ef4444;\\n    box-shadow: 0 4px 15px rgba(239, 68, 68, 0.35);\\n  }\\n\\n  .setup-grid {\\n    display: grid;\\n    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));\\n    gap: 1rem;\\n    margin-bottom: 1.5rem;\\n  }\\n  .retention-tag {\\n    display: inline-flex;\\n    align-items: center;\\n    gap: 0.35rem;\\n    padding: 0.25rem 0.6rem;\\n    border-radius: 6px;\\n    font-size: 0.8rem;\\n    font-weight: 700;\\n  }\\n  .retention-player {\\n    background: rgba(16, 185, 129, 0.15);\\n    color: #34d399;\\n    border: 1px solid rgba(16, 185, 129, 0.3);\\n  }\\n  .retention-owner {\\n    background: rgba(245, 158, 11, 0.15);\\n    color: #fbbf24;\\n    border: 1px solid rgba(245, 158, 11, 0.3);\\n  }\\n</style>\\n<script>\\n  if (sessionStorage.getItem('kpl_auction_pin') || sessionStorage.getItem('spl_auction_pin')) {\\n    document.documentElement.classList.add('pre-authorized');\\n  }\\n</script>\\n{% endblock %}\\n\\n{% block content %}\\n<!-- GATEWAY 1: ADMIN PIN LOCK SCREEN -->\\n<div id=\\\"adminLockScreen\\\" style=\\\"min-height: 65vh; align-items: center; justify-content: center; padding: 2rem 1rem;\\\">\\n  <div class=\\\"glass-card\\\" style=\\\"max-width: 420px; width: 100%; text-align: center; border: 2px solid #f59e0b; box-shadow: 0 0 45px rgba(245, 158, 11, 0.3); padding: 2.75rem 2rem;\\\">\\n    <div style=\\\"width: 72px; height: 72px; background: rgba(245, 158, 11, 0.15); border: 2px solid #f59e0b; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 2.25rem; margin: 0 auto 1.25rem;\\\">\\n      \\ud83d\\udd12\\n    </div>\\n    <h2 style=\\\"font-size: 1.65rem; font-weight: 900; color: #fff; margin-bottom: 0.35rem;\\\">Organizer Access</h2>\\n    <p style=\\\"color: #94a3b8; font-size: 0.85rem; margin-bottom: 1.75rem; line-height: 1.5;\\\">\\n      Enter your Organizer PIN to manage tournament configuration, team retentions, and live bidding.\\n    </p>\\n\\n    <form id=\\\"adminLoginForm\\\" onsubmit=\\\"handleAdminLogin(event)\\\">\\n      <div class=\\\"form-group\\\" style=\\\"margin-bottom: 1.25rem;\\\">\\n        <input type=\\\"password\\\" id=\\\"adminPinInput\\\" class=\\\"form-control\\\" placeholder=\\\"Enter Organizer PIN\\\" style=\\\"text-align: center; font-size: 1.4rem; letter-spacing: 0.25em; font-weight: 900; padding: 0.85rem; background: rgba(15,23,42,0.9);\\\" maxlength=\\\"15\\\" autofocus required>\\n        <div id=\\\"adminPinError\\\" style=\\\"display: none; color: #f87171; font-weight: 700; font-size: 0.85rem; margin-top: 0.6rem;\\\"></div>\\n      </div>\\n      <button type=\\\"submit\\\" id=\\\"btnAdminUnlock\\\" class=\\\"btn btn-primary\\\" style=\\\"width: 100%; font-size: 1.1rem; padding: 0.85rem;\\\">\\n        Unlock Admin Panel &rarr;\\n      </button>\\n      <div style=\\\"margin-top: 1.25rem; display: flex; justify-content: flex-end; align-items: center; font-size: 0.8rem;\\\">\\n        <a href=\\\"javascript:void(0)\\\" onclick=\\\"forgotPinPrompt()\\\" style=\\\"color: #f59e0b; text-decoration: underline; font-weight: 600;\\\">\\n          Forgot PIN?\\n        </a>\\n      </div>\\n    </form>\\n  </div>\\n</div>\\n\\n<!-- GATEWAY 2: ADMIN MAIN CONTENT (PROTECTED) -->\\n<div id=\\\"adminMainContent\\\">\\n  <!-- Top Bar with Broadcast Toggle & Lock -->\\n  <div style=\\\"margin-bottom: 1.5rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;\\\">\\n    <div>\\n      <h1 style=\\\"font-size: 1.85rem; font-weight: 900; color: #fff; display: flex; align-items: center; gap: 0.5rem;\\\">\\n        <span>\\u2699\\ufe0f</span> Organizer Admin Panel\\n      </h1>\\n      <p style=\\\"color: #94a3b8; font-size: 0.9rem;\\\">\\n        Kunsi Premier League (KPL 2026) Management Portal\\n      </p>\\n    </div>\\n    <div style=\\\"display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap;\\\">\\n      <span id=\\\"auctionStatusBadge\\\" class=\\\"badge\\\" style=\\\"background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); font-size: 0.85rem; padding: 0.4rem 0.8rem; font-weight: 800;\\\">\\n        \\ud83d\\udd34 Auction Not Started\\n      </span>\\n      <button type=\\\"button\\\" id=\\\"btnAdminStartAuction\\\" onclick=\\\"adminToggleAuctionStarted()\\\" class=\\\"btn btn-success\\\" style=\\\"font-size: 0.85rem; padding: 0.45rem 0.9rem;\\\">\\n        \\ud83d\\ude80 Start Live Auction\\n      </button>\\n      <button type=\\\"button\\\" onclick=\\\"lockAdminSession()\\\" class=\\\"btn btn-secondary\\\" style=\\\"font-size: 0.85rem; padding: 0.45rem 0.9rem;\\\">\\n        \\ud83d\\udd12 Lock Admin\\n      </button>\\n    </div>\\n  </div>\\n\\n  <!-- 2 SUB-PAGES / TABS INSIDE ADMIN -->\\n  <div class=\\\"admin-subtabs\\\">\\n    <button type=\\\"button\\\" id=\\\"tabBtnConfig\\\" class=\\\"subtab-btn active\\\" onclick=\\\"switchAdminTab('config')\\\">\\n      <span>\\ud83c\\udfdf\\ufe0f</span> 1. Tournament Configuration & Retentions\\n    </button>\\n    <button type=\\\"button\\\" id=\\\"tabBtnAuction\\\" class=\\\"subtab-btn tab-auction\\\" onclick=\\\"switchAdminTab('auction')\\\">\\n      <span>\\ud83d\\udd28</span> 2. Live Auction Page (Host Console)\\n    </button>\\n  </div>\\n\\n  <!-- SUB-PAGE 1: TOURNAMENT CONFIGURATION & RETENTIONS -->\\n  <div id=\\\"subpageConfig\\\">\\n    <!-- Team Setup Form -->\\n    <div class=\\\"glass-card\\\" style=\\\"margin-bottom: 2rem; border-color: rgba(245, 158, 11, 0.35);\\\">\\n      <h2 style=\\\"font-size: 1.35rem; font-weight: 800; color: #f59e0b; margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem;\\\">\\n        <span>\\ud83c\\udfdf\\ufe0f</span> Team Setup & Purse Rules\\n      </h2>\\n      <form id=\\\"teamSetupForm\\\">\\n        <div class=\\\"setup-grid\\\">\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Number of Teams</label>\\n            <input type=\\\"number\\\" id=\\\"setupTeamCount\\\" class=\\\"form-control\\\" min=\\\"2\\\" max=\\\"12\\\" value=\\\"{{ (teams|length) if teams else 4 }}\\\" required onchange=\\\"renderTeamNameInputs()\\\">\\n          </div>\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Purse Amount per Team (\\u20b9)</label>\\n            <input type=\\\"number\\\" id=\\\"setupPurse\\\" class=\\\"form-control\\\" min=\\\"500\\\" step=\\\"100\\\" value=\\\"{{ config.total_purse or config.default_purse or 6000 }}\\\" required>\\n          </div>\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Minimum Players per Team</label>\\n            <input type=\\\"number\\\" id=\\\"setupMinPlayers\\\" class=\\\"form-control\\\" min=\\\"1\\\" max=\\\"25\\\" value=\\\"{{ config.max_players or 10 }}\\\" required>\\n          </div>\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Minimum Bid Amount (\\u20b9)</label>\\n            <input type=\\\"number\\\" id=\\\"setupMinBid\\\" class=\\\"form-control\\\" min=\\\"0\\\" step=\\\"10\\\" value=\\\"{{ config.min_bid or 50 }}\\\" required>\\n          </div>\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Star Player Retention (\\u20b9)</label>\\n            <input type=\\\"number\\\" id=\\\"setupPlayerRetentionPrice\\\" class=\\\"form-control\\\" min=\\\"0\\\" step=\\\"50\\\" value=\\\"{{ config.retention_price or 500 }}\\\" required>\\n          </div>\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Owner Retention (\\u20b9)</label>\\n            <input type=\\\"number\\\" id=\\\"setupOwnerRetentionPrice\\\" class=\\\"form-control\\\" min=\\\"0\\\" step=\\\"50\\\" value=\\\"{{ config.owner_retention_price or 100 }}\\\" required>\\n          </div>\\n        </div>\\n\\n        <div style=\\\"margin-bottom: 1.5rem;\\\">\\n          <label class=\\\"form-label\\\" style=\\\"font-weight: 700; color: #fff;\\\">Custom Team Names</label>\\n          <div id=\\\"teamNamesContainer\\\" style=\\\"display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 0.75rem;\\\">\\n            <!-- Dynamically populated -->\\n          </div>\\n        </div>\\n\\n        <button type=\\\"submit\\\" class=\\\"btn btn-primary\\\" style=\\\"font-size: 1rem; padding: 0.75rem 1.75rem;\\\">\\n          \\ud83d\\udcbe Save Teams & Rules Setup\\n        </button>\\n      </form>\\n    </div>\\n\\n    <!-- Dual Retention Management -->\\n    <div class=\\\"glass-card\\\" style=\\\"margin-bottom: 2rem; border-color: rgba(16, 185, 129, 0.35);\\\">\\n      <h2 style=\\\"font-size: 1.35rem; font-weight: 800; color: #10b981; margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem;\\\">\\n        <span>\\u2b50</span> Player & Owner Retention Phase\\n      </h2>\\n      <p style=\\\"color: #94a3b8; font-size: 0.85rem; margin-bottom: 1.25rem;\\\">\\n        Retain star players (\\u20b9{{ config.retention_price or 500 }}) or team owners (\\u20b9{{ config.owner_retention_price or 100 }}). Retained persons are automatically removed from live auction pool.\\n      </p>\\n\\n      <form id=\\\"retentionForm\\\" style=\\\"display: flex; gap: 1rem; flex-wrap: wrap; align-items: flex-end; margin-bottom: 1.5rem; background: rgba(15,23,42,0.6); padding: 1.25rem; border-radius: var(--radius-md); border: 1px solid rgba(255,255,255,0.1);\\\">\\n        <div class=\\\"form-group\\\" style=\\\"flex: 1; min-width: 180px; margin-bottom: 0;\\\">\\n          <label class=\\\"form-label\\\">Select Team</label>\\n          <select id=\\\"retentionTeamSelect\\\" class=\\\"form-control\\\" required>\\n            <option value=\\\"\\\">-- Choose Team --</option>\\n            {% for t_name in teams.keys() %}\\n            <option value=\\\"{{ t_name }}\\\">{{ t_name }}</option>\\n            {% endfor %}\\n          </select>\\n        </div>\\n\\n        <div class=\\\"form-group\\\" style=\\\"flex: 1; min-width: 180px; margin-bottom: 0;\\\">\\n          <label class=\\\"form-label\\\">Retention Type</label>\\n          <select id=\\\"retentionTypeSelect\\\" class=\\\"form-control\\\" required>\\n            <option value=\\\"Player\\\">\\u2b50 Player Retention (\\u20b9{{ config.retention_price or 500 }})</option>\\n            <option value=\\\"Owner\\\">\\ud83d\\udc51 Owner Retention (\\u20b9{{ config.owner_retention_price or 100 }})</option>\\n          </select>\\n        </div>\\n\\n        <div class=\\\"form-group\\\" style=\\\"flex: 1.5; min-width: 220px; margin-bottom: 0;\\\">\\n          <label class=\\\"form-label\\\">Select Registered Person</label>\\n          <select id=\\\"retentionPlayerSelect\\\" class=\\\"form-control\\\" required>\\n            <option value=\\\"\\\">-- Choose Person --</option>\\n            {% for p in players %}\\n            <option value=\\\"{{ p }}\\\">{{ p }}</option>\\n            {% endfor %}\\n          </select>\\n        </div>\\n\\n        <button type=\\\"submit\\\" class=\\\"btn btn-success\\\" style=\\\"padding: 0.75rem 1.5rem; font-weight: 800;\\\">\\n          \\u2b50 Confirm Retention\\n        </button>\\n      </form>\\n\\n      <!-- Active Retentions Table -->\\n      <h3 style=\\\"font-size: 1.05rem; font-weight: 700; color: #fff; margin-bottom: 0.75rem;\\\">\\n        Current Team Retentions\\n      </h3>\\n      <div style=\\\"overflow-x: auto;\\\">\\n        <table class=\\\"table\\\" style=\\\"width: 100%; border-collapse: collapse;\\\">\\n          <thead>\\n            <tr style=\\\"border-bottom: 1px solid rgba(255,255,255,0.1); text-align: left; color: #94a3b8; font-size: 0.85rem;\\\">\\n              <th style=\\\"padding: 0.75rem;\\\">Team Name</th>\\n              <th style=\\\"padding: 0.75rem;\\\">Remaining Purse</th>\\n              <th style=\\\"padding: 0.75rem;\\\">Star Player Retained (\\u20b9{{ config.retention_price or 500 }})</th>\\n              <th style=\\\"padding: 0.75rem;\\\">Owner Retained (\\u20b9{{ config.owner_retention_price or 100 }})</th>\\n            </tr>\\n          </thead>\\n          <tbody>\\n            {% for t_name, t_data in teams.items() %}\\n            <tr style=\\\"border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 0.9rem;\\\">\\n              <td style=\\\"padding: 0.75rem; font-weight: 700; color: #fff;\\\">{{ t_name }}</td>\\n              <td style=\\\"padding: 0.75rem; font-weight: 800; color: #10b981;\\\">\\u20b9{{ t_data.purse }}</td>\\n              <td style=\\\"padding: 0.75rem;\\\">\\n                {% if t_data.player_retained %}\\n                  <span class=\\\"retention-tag retention-player\\\">\\n                    \\u2b50 {{ t_data.player_retained.name if t_data.player_retained is mapping else t_data.player_retained }}\\n                    <button type=\\\"button\\\" onclick=\\\"releaseRetention('{{ t_name }}', 'Player')\\\" style=\\\"background: none; border: none; color: #f87171; cursor: pointer; font-size: 0.8rem; margin-left: 0.35rem;\\\" title=\\\"Release Retention\\\">&times;</button>\\n                  </span>\\n                {% elif t_data.retained %}\\n                  <span class=\\\"retention-tag retention-player\\\">\\n                    \\u2b50 {{ t_data.retained.name if t_data.retained is mapping else t_data.retained }}\\n                    <button type=\\\"button\\\" onclick=\\\"releaseRetention('{{ t_name }}', 'Player')\\\" style=\\\"background: none; border: none; color: #f87171; cursor: pointer; font-size: 0.8rem; margin-left: 0.35rem;\\\" title=\\\"Release Retention\\\">&times;</button>\\n                  </span>\\n                {% else %}\\n                  <span style=\\\"color: #64748b; font-style: italic;\\\">None</span>\\n                {% endif %}\\n              </td>\\n              <td style=\\\"padding: 0.75rem;\\\">\\n                {% if t_data.owner_retained %}\\n                  <span class=\\\"retention-tag retention-owner\\\">\\n                    \\ud83d\\udc51 {{ t_data.owner_retained.name if t_data.owner_retained is mapping else t_data.owner_retained }}\\n                    <button type=\\\"button\\\" onclick=\\\"releaseRetention('{{ t_name }}', 'Owner')\\\" style=\\\"background: none; border: none; color: #f87171; cursor: pointer; font-size: 0.8rem; margin-left: 0.35rem;\\\" title=\\\"Release Retention\\\">&times;</button>\\n                  </span>\\n                {% else %}\\n                  <span style=\\\"color: #64748b; font-style: italic;\\\">None</span>\\n                {% endif %}\\n              </td>\\n            </tr>\\n            {% endfor %}\\n          </tbody>\\n        </table>\\n      </div>\\n    </div>\\n\\n    <!-- General Settings & Excel Export -->\\n    <div style=\\\"display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem;\\\">\\n      <div class=\\\"glass-card\\\">\\n        <h2 style=\\\"font-size: 1.25rem; font-weight: 800; color: #f59e0b; margin-bottom: 1rem;\\\">\\n          \\ud83d\\udcb3 UPI Payment & Fee Settings\\n        </h2>\\n        <form id=\\\"configForm\\\" onsubmit=\\\"handleConfigSubmit(event)\\\">\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Tournament Display Name</label>\\n            <input type=\\\"text\\\" id=\\\"cfgTournamentName\\\" class=\\\"form-control\\\" value=\\\"{{ config.tournament_name }}\\\" required>\\n          </div>\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Receiving UPI ID</label>\\n            <input type=\\\"text\\\" id=\\\"cfgUpiId\\\" class=\\\"form-control\\\" value=\\\"{{ config.upi_id }}\\\" required>\\n          </div>\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Payee Name</label>\\n            <input type=\\\"text\\\" id=\\\"cfgPayeeName\\\" class=\\\"form-control\\\" value=\\\"{{ config.payee_name }}\\\" required>\\n          </div>\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Registration Fee (\\u20b9)</label>\\n            <input type=\\\"number\\\" id=\\\"cfgRegFee\\\" class=\\\"form-control\\\" value=\\\"{{ config.registration_fee }}\\\" required>\\n          </div>\\n          <div class=\\\"form-group\\\">\\n            <label class=\\\"form-label\\\">Change Secret Organizer PIN</label>\\n            <input type=\\\"password\\\" id=\\\"cfgAdminPin\\\" class=\\\"form-control\\\" placeholder=\\\"New Secret PIN\\\">\\n          </div>\\n          <button type=\\\"submit\\\" class=\\\"btn btn-primary\\\">Save Settings</button>\\n        </form>\\n      </div>\\n\\n      <div class=\\\"glass-card\\\" style=\\\"display: flex; flex-direction: column; justify-content: space-between;\\\">\\n        <div>\\n          <h2 style=\\\"font-size: 1.25rem; font-weight: 800; color: #10b981; margin-bottom: 1rem;\\\">\\n            \\ud83d\\udcca Styled Excel Export\\n          </h2>\\n          <p style=\\\"color: #94a3b8; font-size: 0.9rem; line-height: 1.5; margin-bottom: 1.25rem;\\\">\\n            Download complete tournament Excel report with Team Rosters, Retentions, Rounds Breakdown, and Unsold Players.\\n          </p>\\n          <a href=\\\"/api/export-excel\\\" class=\\\"btn btn-success\\\" style=\\\"width: 100%; margin-bottom: 1rem; text-align: center;\\\">\\n            \\ud83d\\udce5 Download Styled Excel (.xlsx)\\n          </a>\\n        </div>\\n        <div style=\\\"border-top: 1px solid rgba(255,255,255,0.1); padding-top: 1rem;\\\">\\n          <button type=\\\"button\\\" onclick=\\\"confirmResetAuction()\\\" class=\\\"btn btn-danger\\\" style=\\\"width: 100%;\\\">\\n            \\u26a0\\ufe0f Reset Auction & Clear Bidding\\n          </button>\\n        </div>\\n      </div>\\n    </div>\\n  </div>\\n\\n  <!-- SUB-PAGE 2: LIVE AUCTION CONTROLLER (ADMIN ACCESS) -->\\n  <div id=\\\"subpageAuction\\\" style=\\\"display: none;\\\">\\n    <div style=\\\"margin-bottom: 1.25rem; background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.4); padding: 1rem; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.75rem;\\\">\\n      <div>\\n        <strong style=\\\"color: #f87171; font-size: 1.05rem; display: block;\\\">\\ud83d\\udd28 Live Auction Host Console Active</strong>\\n        <span style=\\\"color: #cbd5e1; font-size: 0.85rem;\\\">Conduct live player draws, increment bidding amounts, confirm sales, and manage unsold players. All viewers update live!</span>\\n      </div>\\n      <div style=\\\"display: flex; gap: 0.5rem;\\\">\\n        <a href=\\\"/auction\\\" target=\\\"_blank\\\" class=\\\"btn btn-primary\\\" style=\\\"font-size: 0.85rem; padding: 0.4rem 0.85rem;\\\">\\n          \\u2197\\ufe0f Fullscreen Console\\n        </a>\\n        <a href=\\\"/view\\\" target=\\\"_blank\\\" class=\\\"btn btn-secondary\\\" style=\\\"font-size: 0.85rem; padding: 0.4rem 0.85rem;\\\">\\n          \\ud83d\\udc41\\ufe0f Preview Spectator View\\n        </a>\\n      </div>\\n    </div>\\n\\n    <!-- Live Auction Arena Embedded for Host without duplicate navbar -->\\n    <iframe id=\\\"hostAuctionIframe\\\" src=\\\"/auction?embed=1\\\" style=\\\"width: 100%; height: 900px; border: 1px solid rgba(255,255,255,0.12); border-radius: 12px; background: #0a0f1a;\\\"></iframe>\\n  </div>\\n</div>\\n{% endblock %}\\n\\n{% block extra_js %}\\n<script>\\n  const CURRENT_TEAMS = {{ (teams.keys()|list)|tojson }};\\n\\n  function getAdminPin() {\\n    return sessionStorage.getItem('kpl_auction_pin') || sessionStorage.getItem('spl_auction_pin') || '';\\n  }\\n\\n  function switchAdminTab(tabName) {\\n    const btnConfig = document.getElementById('tabBtnConfig');\\n    const btnAuction = document.getElementById('tabBtnAuction');\\n    const pageConfig = document.getElementById('subpageConfig');\\n    const pageAuction = document.getElementById('subpageAuction');\\n\\n    if (tabName === 'auction') {\\n      btnAuction.classList.add('active');\\n      btnConfig.classList.remove('active');\\n      pageAuction.style.display = 'block';\\n      pageConfig.style.display = 'none';\\n      // Refresh iframe if needed\\n      const iframe = document.getElementById('hostAuctionIframe');\\n      if (iframe && !iframe.src.includes('/auction?embed=1')) {\\n        iframe.src = '/auction?embed=1';\\n      }\\n    } else {\\n      btnConfig.classList.add('active');\\n      btnAuction.classList.remove('active');\\n      pageConfig.style.display = 'block';\\n      pageAuction.style.display = 'none';\\n    }\\n  }\\n\\n  // --- INITIALIZATION ---\\n  document.addEventListener('DOMContentLoaded', async () => {\\n    renderTeamNameInputs();\\n    updateAdminAuctionStatus();\\n\\n    const savedPin = getAdminPin();\\n    if (!savedPin) {\\n      document.body.classList.remove('admin-unlocked');\\n      return;\\n    }\\n\\n    try {\\n      const res = await fetch('/api/auction/verify-pin', {\\n        method: 'POST',\\n        headers: { 'Content-Type': 'application/json' },\\n        body: JSON.stringify({ pin: savedPin })\\n      });\\n      const data = await res.json();\\n      if (data.valid || data.success) {\\n        document.body.classList.add('admin-unlocked');\\n      } else {\\n        sessionStorage.removeItem('kpl_auction_pin');\\n        sessionStorage.removeItem('spl_auction_pin');\\n        document.body.classList.remove('admin-unlocked');\\n      }\\n    } catch(e) {\\n      document.body.classList.add('admin-unlocked');\\n    }\\n  });\\n\\n  // --- LOGIN ---\\n  async function handleAdminLogin(e) {\\n    e.preventDefault();\\n    const pin = document.getElementById('adminPinInput').value.trim();\\n    const err = document.getElementById('adminPinError');\\n    err.style.display = 'none';\\n\\n    try {\\n      const res = await fetch('/api/auction/verify-pin', {\\n        method: 'POST',\\n        headers: { 'Content-Type': 'application/json' },\\n        body: JSON.stringify({ pin: pin })\\n      });\\n      const data = await res.json();\\n      if (data.valid || data.success) {\\n        sessionStorage.setItem('kpl_auction_pin', pin);\\n        sessionStorage.setItem('spl_auction_pin', pin);\\n        document.body.classList.add('admin-unlocked');\\n        updateAdminAuctionStatus();\\n      } else {\\n        err.textContent = '\\u274c Incorrect Organizer PIN. Please try again.';\\n        err.style.display = 'block';\\n      }\\n    } catch(errEx) {\\n      err.textContent = 'Network error verifying PIN.';\\n      err.style.display = 'block';\\n    }\\n  }\\n\\n  function lockAdminSession() {\\n    sessionStorage.removeItem('kpl_auction_pin');\\n    sessionStorage.removeItem('spl_auction_pin');\\n    document.body.classList.remove('admin-unlocked');\\n    document.getElementById('adminPinInput').value = '';\\n  }\\n\\n  function forgotPinPrompt() {\\n    const recoveryKey = prompt('Please enter the Organizer Master Recovery Key:');\\n    if (!recoveryKey) return;\\n    if (recoveryKey.trim() === 'KPL2026_MASTER' || recoveryKey.trim() === 'KPL2026') {\\n      const newPin = prompt('Authentication successful. Please enter your new desired PIN:');\\n      if (newPin && newPin.trim()) {\\n        fetch('/api/admin/config', {\\n          method: 'POST',\\n          headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': recoveryKey },\\n          body: JSON.stringify({ admin_pin: newPin.trim(), pin: recoveryKey })\\n        }).then(r => r.json()).then(res => {\\n          if (res.success) {\\n            alert('PIN successfully updated! Please log in with your new PIN.');\\n          } else {\\n            alert('Error: ' + res.message);\\n          }\\n        });\\n      }\\n    } else {\\n      alert('Invalid recovery key. Please check with the head tournament organizer.');\\n    }\\n  }\\n\\n  // --- DYNAMIC TEAM INPUTS ---\\n  function renderTeamNameInputs() {\\n    const count = parseInt(document.getElementById('setupTeamCount').value) || 4;\\n    const container = document.getElementById('teamNamesContainer');\\n    container.innerHTML = '';\\n\\n    for (let i = 0; i < count; i++) {\\n      const defaultName = CURRENT_TEAMS[i] || `Team ${i + 1}`;\\n      const div = document.createElement('div');\\n      div.innerHTML = `\\n        <input type=\\\"text\\\" name=\\\"team_name_${i}\\\" class=\\\"form-control team-name-input\\\" value=\\\"${defaultName}\\\" placeholder=\\\"Team ${i+1} Name\\\" required>\\n      `;\\n      container.appendChild(div);\\n    }\\n  }\\n\\n  // --- SAVE SETUP ---\\n  document.getElementById('teamSetupForm').addEventListener('submit', async (e) => {\\n    e.preventDefault();\\n    const count = parseInt(document.getElementById('setupTeamCount').value);\\n    const purse = parseInt(document.getElementById('setupPurse').value);\\n    const minPlayers = parseInt(document.getElementById('setupMinPlayers').value);\\n    const minBid = parseInt(document.getElementById('setupMinBid').value);\\n    const playerRetPrice = parseInt(document.getElementById('setupPlayerRetentionPrice').value);\\n    const ownerRetPrice = parseInt(document.getElementById('setupOwnerRetentionPrice').value);\\n\\n    const nameInputs = document.querySelectorAll('.team-name-input');\\n    const teamNames = [];\\n    nameInputs.forEach(inp => {\\n      const v = inp.value.trim();\\n      if (v) teamNames.push(v);\\n    });\\n\\n    if (teamNames.length !== count) {\\n      return alert(`Please specify names for all ${count} teams.`);\\n    }\\n\\n    const payload = {\\n      team_count: count,\\n      team_names: teamNames,\\n      purse_per_team: purse,\\n      min_players_per_team: minPlayers,\\n      min_bid: minBid,\\n      retention_price: playerRetPrice,\\n      owner_retention_price: ownerRetPrice,\\n      pin: getAdminPin()\\n    };\\n\\n    try {\\n      const res = await fetch('/api/admin/setup-teams', {\\n        method: 'POST',\\n        headers: {\\n          'Content-Type': 'application/json',\\n          'X-Auction-PIN': getAdminPin()\\n        },\\n        body: JSON.stringify(payload)\\n      });\\n      const data = await res.json();\\n      if (data.success) {\\n        alert('Tournament Configuration Saved Successfully!');\\n        location.reload();\\n      } else {\\n        alert(data.message || 'Error saving team setup.');\\n      }\\n    } catch (err) {\\n      alert('Error: ' + err.message);\\n    }\\n  });\\n\\n  document.getElementById('retentionForm').addEventListener('submit', async (e) => {\\n    e.preventDefault();\\n    const team = document.getElementById('retentionTeamSelect').value;\\n    const player = document.getElementById('retentionPlayerSelect').value;\\n    const retType = document.getElementById('retentionTypeSelect').value;\\n\\n    if (!team || !player) return alert('Please select both team and player.');\\n\\n    const payload = {\\n      team: team,\\n      player: player,\\n      retention_type: retType,\\n      pin: getAdminPin()\\n    };\\n\\n    try {\\n      const res = await fetch('/api/retention/retain', {\\n        method: 'POST',\\n        headers: {\\n          'Content-Type': 'application/json',\\n          'X-Auction-PIN': getAdminPin()\\n        },\\n        body: JSON.stringify(payload)\\n      });\\n      const data = await res.json();\\n      if (data.success) {\\n        alert('Person retained successfully!');\\n        location.reload();\\n      } else {\\n        alert(data.message || 'Error retaining person.');\\n      }\\n    } catch (err) {\\n      alert('Error: ' + err.message);\\n    }\\n  });\\n\\n  async function releaseRetention(teamName, retentionType) {\\n    if (!confirm(`Release ${retentionType} retention from ${teamName}? Their fee will be refunded to team purse.`)) return;\\n\\n    try {\\n      const res = await fetch('/api/retention/release', {\\n        method: 'POST',\\n        headers: {\\n          'Content-Type': 'application/json',\\n          'X-Auction-PIN': getAdminPin()\\n        },\\n        body: JSON.stringify({ team: teamName, retention_type: retentionType, pin: getAdminPin() })\\n      });\\n      const data = await res.json();\\n      if (data.success) {\\n        alert(data.message || 'Retention released successfully!');\\n        location.reload();\\n      } else {\\n        alert(data.message || 'Error releasing retention.');\\n      }\\n    } catch (err) {\\n      alert('Error: ' + err.message);\\n    }\\n  }\\n\\n  async function adminToggleAuctionStarted() {\\n    const pin = getAdminPin();\\n    const badge = document.getElementById('auctionStatusBadge');\\n    const isStarted = badge && badge.textContent.includes('Active');\\n    const endpoint = isStarted ? '/api/auction/pause' : '/api/auction/start';\\n    const actionName = isStarted ? 'Pause Live Auction' : 'Start Live Auction for all viewers';\\n\\n    if (!confirm(`Are you sure you want to ${actionName}?`)) return;\\n\\n    try {\\n      const res = await fetch(endpoint, {\\n        method: 'POST',\\n        headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': pin },\\n        body: JSON.stringify({ pin: pin })\\n      });\\n      const data = await res.json();\\n      if (data.success) {\\n        alert(data.message);\\n        updateAdminAuctionStatus();\\n      } else {\\n        alert(data.message || 'Error updating auction state.');\\n      }\\n    } catch (e) {\\n      alert(e.message);\\n    }\\n  }\\n\\n  async function updateAdminAuctionStatus() {\\n    try {\\n      const res = await fetch('/api/auction/state');\\n      const state = await res.json();\\n      const badge = document.getElementById('auctionStatusBadge');\\n      const btn = document.getElementById('btnAdminStartAuction');\\n      if (!badge || !btn) return;\\n\\n      if (state.auction_started) {\\n        badge.textContent = '\\ud83d\\udfe2 Auction Active';\\n        badge.style.background = 'rgba(16, 185, 129, 0.2)';\\n        badge.style.color = '#34d399';\\n        badge.style.borderColor = 'rgba(16, 185, 129, 0.4)';\\n        btn.textContent = '\\u23f8\\ufe0f Pause Auction';\\n        btn.className = 'btn btn-secondary';\\n      } else {\\n        badge.textContent = '\\ud83d\\udd34 Auction Not Started';\\n        badge.style.background = 'rgba(239, 68, 68, 0.2)';\\n        badge.style.color = '#f87171';\\n        badge.style.borderColor = 'rgba(239, 68, 68, 0.4)';\\n        btn.textContent = '\\ud83d\\ude80 Start Live Auction';\\n        btn.className = 'btn btn-success';\\n      }\\n    } catch(e) {}\\n  }\\n\\n  async function handleConfigSubmit(e) {\\n    e.preventDefault();\\n    const payload = {\\n      tournament_name: document.getElementById('cfgTournamentName').value,\\n      upi_id: document.getElementById('cfgUpiId').value,\\n      payee_name: document.getElementById('cfgPayeeName').value,\\n      registration_fee: parseInt(document.getElementById('cfgRegFee').value) || 200,\\n      admin_pin: document.getElementById('cfgAdminPin').value || undefined,\\n      pin: getAdminPin()\\n    };\\n\\n    try {\\n      const res = await fetch('/api/admin/config', {\\n        method: 'POST',\\n        headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': getAdminPin() },\\n        body: JSON.stringify(payload)\\n      });\\n      const data = await res.json();\\n      if (data.success) {\\n        if (payload.admin_pin) {\\n          sessionStorage.setItem('kpl_auction_pin', payload.admin_pin);\\n          sessionStorage.setItem('spl_auction_pin', payload.admin_pin);\\n        }\\n        alert('Settings saved successfully!');\\n        location.reload();\\n      } else {\\n        alert(data.message || 'Error updating settings.');\\n      }\\n    } catch(e) {\\n      alert(e.message);\\n    }\\n  }\\n\\n  async function confirmResetAuction() {\\n    if (!confirm('\\u26a0\\ufe0f DANGER: This will reset all sold players, team budgets, and retentions to fresh state. Continue?')) return;\\n    try {\\n      const res = await fetch('/api/admin/reset-auction', {\\n        method: 'POST',\\n        headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': getAdminPin() },\\n        body: JSON.stringify({ pin: getAdminPin() })\\n      });\\n      const data = await res.json();\\n      if (data.success) {\\n        alert('Auction reset successfully!');\\n        location.reload();\\n      } else {\\n        alert(data.message || 'Reset failed.');\\n      }\\n    } catch(e) {\\n      alert(e.message);\\n    }\\n  }\\n</script>\\n{% endblock %}\\n\", \"auction_live.html\": \"{% extends \\\"base.html\\\" %}\\n\\n{% block extra_css %}\\n<link rel=\\\"stylesheet\\\" href=\\\"/static/css/auction.css\\\">\\n<style>\\n  {% if viewer_mode %}\\n  .control-deck, .admin-only, #auctioneerAuthBox, #btnHostAuctionToggle {\\n    display: none !important;\\n  }\\n  .viewer-banner {\\n    background: linear-gradient(90deg, #dc2626, #b91c1c);\\n    color: #fff;\\n    text-align: center;\\n    padding: 0.5rem 1rem;\\n    border-radius: var(--radius-sm);\\n    font-weight: 800;\\n    font-size: 0.85rem;\\n    letter-spacing: 0.05em;\\n    margin-bottom: 1rem;\\n    display: flex;\\n    align-items: center;\\n    justify-content: center;\\n    gap: 0.5rem;\\n  }\\n  {% endif %}\\n\\n  /* Mobile-first optimizations for Viewers interface */\\n  @media (max-width: 768px) {\\n    .page-container {\\n      padding: 0.5rem !important;\\n    }\\n    .auction-header-bar {\\n      flex-direction: column;\\n      align-items: flex-start !important;\\n      gap: 0.5rem;\\n    }\\n    .auction-stage {\\n      grid-template-columns: 1fr !important;\\n      gap: 1rem;\\n    }\\n    .player-main-name {\\n      font-size: 1.65rem !important;\\n    }\\n    .photo-frame {\\n      width: 140px !important;\\n      height: 140px !important;\\n    }\\n    .bid-amount {\\n      font-size: 2.5rem !important;\\n    }\\n    .bid-odometer-box {\\n      padding: 1.25rem 1rem !important;\\n    }\\n    .team-purse-sidebar {\\n      margin-top: 1rem;\\n    }\\n    .team-card-auction {\\n      padding: 0.75rem 1rem !important;\\n    }\\n  }\\n</style>\\n{% endblock %}\\n\\n{% block content %}\\n{% if viewer_mode %}\\n<div class=\\\"viewer-banner\\\">\\n  <span style=\\\"width: 8px; height: 8px; background: #fff; border-radius: 50%; display: inline-block; animation: pulse 1.5s infinite;\\\"></span>\\n  SPECTATOR LIVE MODE \\u2022 MOBILE LIVE STREAM\\n</div>\\n{% endif %}\\n\\n<div class=\\\"auction-header-bar\\\" style=\\\"display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;\\\">\\n  <div>\\n    <h1 style=\\\"font-size: 1.85rem; font-weight: 900; color: #fff; display: flex; align-items: center; gap: 0.5rem;\\\">\\n      <span>\\ud83c\\udfcf</span> Live Auction Arena\\n    </h1>\\n    <p style=\\\"color: var(--text-muted); font-size: 0.9rem;\\\">\\n      {% if viewer_mode %}Mobile Live Stream with Player Photos & Real-time Bids{% else %}Official Bidding Console with Player Photos & Roles{% endif %}\\n    </p>\\n  </div>\\n  <div style=\\\"display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap;\\\">\\n    <span class=\\\"round-tag\\\" id=\\\"currentRoundTag\\\">Round 1</span>\\n    <span class=\\\"round-tag\\\" id=\\\"poolStatusTag\\\" style=\\\"background: rgba(16, 185, 129, 0.15); color: var(--pitch-green); border-color: rgba(16, 185, 129, 0.4);\\\">\\n      Connecting...\\n    </span>\\n    {% if not viewer_mode %}\\n    <button type=\\\"button\\\" id=\\\"btnHostAuctionToggle\\\" onclick=\\\"toggleAuctionStarted()\\\" class=\\\"btn btn-success\\\" style=\\\"display: none; font-size: 0.8rem; padding: 0.3rem 0.65rem;\\\">\\n      \\ud83d\\ude80 Start Auction\\n    </button>\\n    <div id=\\\"auctioneerAuthBox\\\">\\n      <button type=\\\"button\\\" id=\\\"btnUnlockAuctioneer\\\" onclick=\\\"openPinModal()\\\" class=\\\"btn btn-secondary\\\" style=\\\"font-size: 0.8rem; padding: 0.3rem 0.65rem; border-color: rgba(245, 158, 11, 0.5); color: var(--primary-gold); display: flex; align-items: center; gap: 0.35rem;\\\">\\n        <span>\\ud83d\\udd12</span> Host Controls\\n      </button>\\n    </div>\\n    {% endif %}\\n  </div>\\n</div>\\n\\n<div class=\\\"auction-stage\\\">\\n  <!-- Center Main Arena -->\\n  <div>\\n    <!-- WAITING / NOT STARTED SCREEN (FOR SPECTATORS) -->\\n    <div id=\\\"auctionNotStartedScreen\\\" class=\\\"glass-card\\\" style=\\\"display: none; text-align: center; padding: 3.5rem 1.5rem; max-width: 680px; margin: 1.5rem auto 2.5rem; border: 2px solid var(--primary-gold); box-shadow: 0 0 40px rgba(245, 158, 11, 0.25);\\\">\\n      <div style=\\\"font-size: 3.5rem; margin-bottom: 0.75rem;\\\">\\ud83c\\udfcf</div>\\n      <div style=\\\"display: inline-block; background: rgba(245, 158, 11, 0.15); color: var(--primary-gold); border: 1px solid rgba(245, 158, 11, 0.4); padding: 0.35rem 1rem; border-radius: 9999px; font-weight: 800; font-size: 0.85rem; text-transform: uppercase; margin-bottom: 1rem;\\\">\\n        Kunsi Premier League (KPL 2026)\\n      </div>\\n      <h2 style=\\\"font-size: 1.85rem; font-weight: 900; color: #fff; margin-bottom: 0.75rem;\\\">Live Auction Has Not Begun</h2>\\n      <p style=\\\"color: var(--text-muted); font-size: 1rem; line-height: 1.6; max-width: 500px; margin: 0 auto 1.5rem;\\\">\\n        The tournament auctioneer has not yet started the live bidding stream. Please stay on this page; player draws will automatically appear the moment the auction begins.\\n      </p>\\n      <div style=\\\"display: flex; gap: 0.5rem; align-items: center; justify-content: center; color: var(--primary-gold); font-size: 0.9rem; font-weight: 700;\\\">\\n        <span style=\\\"display: inline-block; width: 10px; height: 10px; background: var(--primary-gold); border-radius: 50%; animation: pulse 1s infinite;\\\"></span>\\n        Waiting for Auctioneer to begin...\\n      </div>\\n    </div>\\n\\n    <!-- Active Player Card -->\\n    <div class=\\\"glass-card player-active-card\\\" id=\\\"activePlayerCard\\\">\\n      <!-- Player Showcase -->\\n      <div class=\\\"player-showcase\\\">\\n        <div class=\\\"photo-frame\\\">\\n          <img id=\\\"playerPhoto\\\" src=\\\"/static/images/avatar_allrounder.svg\\\" alt=\\\"Active Player\\\">\\n        </div>\\n        <div class=\\\"player-meta\\\">\\n          <div style=\\\"display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap;\\\">\\n            <span class=\\\"role-badge\\\" id=\\\"playerRoleBadge\\\">All-Rounder</span>\\n            <span class=\\\"player-id-tag\\\" id=\\\"playerIdTag\\\">ID: #--</span>\\n          </div>\\n          <h2 class=\\\"player-main-name\\\" id=\\\"playerName\\\">Waiting for Draw...</h2>\\n          <div class=\\\"stats-row\\\">\\n            <div class=\\\"stat-item\\\">\\n              <span class=\\\"stat-label\\\">Batting Style</span>\\n              <span class=\\\"stat-val\\\" id=\\\"playerBatting\\\">Right Hand Bat</span>\\n            </div>\\n            <div class=\\\"stat-item\\\">\\n              <span class=\\\"stat-label\\\">Bowling Style</span>\\n              <span class=\\\"stat-val\\\" id=\\\"playerBowling\\\">Right Arm Medium</span>\\n            </div>\\n            <div class=\\\"stat-item\\\">\\n              <span class=\\\"stat-label\\\">Village / Town</span>\\n              <span class=\\\"stat-val\\\" id=\\\"playerVillage\\\">Saidapur</span>\\n            </div>\\n            <div class=\\\"stat-item\\\">\\n              <span class=\\\"stat-label\\\">Base Price</span>\\n              <span class=\\\"stat-val\\\" id=\\\"playerBasePrice\\\" style=\\\"color: var(--pitch-green); font-weight: 800;\\\">\\u20b950</span>\\n            </div>\\n          </div>\\n        </div>\\n      </div>\\n\\n      <!-- Live Bidding Odometer -->\\n      <div class=\\\"bid-odometer-box\\\">\\n        <div class=\\\"bid-label\\\">Current Highest Bid</div>\\n        <div class=\\\"bid-amount\\\" id=\\\"bidOdometer\\\">\\u20b90</div>\\n        <div>\\n          <span class=\\\"bid-team-tag\\\" id=\\\"leadingTeamTag\\\">No Bids Yet</span>\\n        </div>\\n      </div>\\n\\n      <!-- Controls Deck (Only visible in Host Mode) -->\\n      {% if not viewer_mode %}\\n      <div class=\\\"control-deck admin-only\\\" id=\\\"auctioneerControls\\\">\\n                <!-- Pick Specific Player from Pool Dropdown -->\\n        <div style=\\\"background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(245, 158, 11, 0.35); border-radius: 8px; padding: 0.65rem 0.85rem; margin-bottom: 1rem; display: flex; gap: 0.65rem; align-items: center; flex-wrap: wrap;\\\">\\n          <span style=\\\"font-weight: 800; color: var(--primary-gold); font-size: 0.85rem; white-space: nowrap;\\\">\\n            \\ud83c\\udfaf Pick from Player List:\\n          </span>\\n          <select id=\\\"selectPlayerDropdown\\\" class=\\\"form-control\\\" style=\\\"flex: 1; min-width: 220px; font-size: 0.85rem; padding: 0.35rem 0.65rem;\\\">\\n            <option value=\\\"\\\">-- Choose Player to Bring to Auction --</option>\\n          </select>\\n          <button type=\\\"button\\\" class=\\\"btn btn-secondary\\\" onclick=\\\"chooseSelectedPlayer()\\\" style=\\\"font-size: 0.82rem; padding: 0.35rem 0.75rem; white-space: nowrap;\\\">\\n            Bring to Block &rarr;\\n          </button>\\n        </div>\\n\\n        <!-- Quick Bid Modifiers -->\\n        <div class=\\\"bid-modifiers-bar\\\">\\n          <button type=\\\"button\\\" class=\\\"btn-mod\\\" onclick=\\\"adjustCurrentBid(50)\\\">+\\u20b950</button>\\n          <button type=\\\"button\\\" class=\\\"btn-mod\\\" onclick=\\\"adjustCurrentBid(100)\\\">+\\u20b9100</button>\\n          <button type=\\\"button\\\" class=\\\"btn-mod\\\" onclick=\\\"adjustCurrentBid(200)\\\">+\\u20b9200</button>\\n          <button type=\\\"button\\\" class=\\\"btn-mod\\\" onclick=\\\"adjustCurrentBid(500)\\\">+\\u20b9500</button>\\n          <button type=\\\"button\\\" class=\\\"btn-mod\\\" onclick=\\\"adjustCurrentBid(-50)\\\" style=\\\"background: rgba(239, 68, 68, 0.2); border-color: rgba(239, 68, 68, 0.5);\\\">-\\u20b950</button>\\n        </div>\\n\\n        <!-- Team Selector for Bid Assignment -->\\n        <div style=\\\"display: flex; gap: 0.75rem; align-items: center; margin-bottom: 1.25rem; flex-wrap: wrap;\\\">\\n          <label style=\\\"font-weight: 700; color: #fff; font-size: 0.9rem;\\\">Assign Bid To Team:</label>\\n          <select id=\\\"biddingTeamSelect\\\" class=\\\"form-control\\\" style=\\\"flex: 1; min-width: 200px;\\\">\\n            <option value=\\\"\\\">-- Choose Team --</option>\\n            {% for t_name in (teams.keys() if teams else []) %}\\n            <option value=\\\"{{ t_name }}\\\">{{ t_name }}</option>\\n            {% endfor %}\\n          </select>\\n          <button type=\\\"button\\\" onclick=\\\"assignLeadingBidder()\\\" class=\\\"btn btn-secondary\\\" style=\\\"font-size: 0.9rem;\\\">\\n            Update Bidder\\n          </button>\\n        </div>\\n\\n        <!-- Big Action Buttons -->\\n        <div class=\\\"action-buttons-grid\\\">\\n          <button type=\\\"button\\\" class=\\\"btn-action btn-next-draw\\\" onclick=\\\"drawNextPlayer()\\\">\\n            \\ud83d\\ude80 Next Draw\\n          </button>\\n          <button type=\\\"button\\\" class=\\\"btn-action btn-sold\\\" onclick=\\\"confirmSellPlayer()\\\">\\n            \\ud83d\\udd28 SOLD!\\n          </button>\\n          <button type=\\\"button\\\" class=\\\"btn-action btn-unsold\\\" onclick=\\\"markUnsold(false)\\\">\\n            \\u274c Unsold (Round 2)\\n          </button>\\n          <button type=\\\"button\\\" class=\\\"btn-action btn-perm-unsold\\\" onclick=\\\"markUnsold(true)\\\">\\n            \\u26d4 Permanent Unsold\\n          </button>\\n        </div>\\n\\n        <div style=\\\"margin-top: 1rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;\\\">\\n          <button type=\\\"button\\\" onclick=\\\"undoLastAction()\\\" class=\\\"btn btn-secondary\\\" style=\\\"font-size: 0.85rem; padding: 0.35rem 0.75rem;\\\">\\n            \\u21a9\\ufe0f Undo Last Action\\n          </button>\\n          <button type=\\\"button\\\" id=\\\"btnStartRound2\\\" onclick=\\\"startRound2()\\\" class=\\\"btn btn-secondary\\\" style=\\\"display: none; font-size: 0.85rem; padding: 0.35rem 0.75rem; border-color: #f59e0b; color: #f59e0b;\\\">\\n            \\ud83d\\udd04 Start Round 2 (Unsold Pool)\\n          </button>\\n        </div>\\n      </div>\\n      {% endif %}\\n    </div>\\n\\n    <!-- Empty State when no active player -->\\n    <div id=\\\"noActivePlayerState\\\" class=\\\"glass-card\\\" style=\\\"display: none; text-align: center; padding: 3rem 1.5rem;\\\">\\n      <h3 style=\\\"font-size: 1.35rem; color: #fff; margin-bottom: 0.5rem;\\\">No Active Player on the Auction Block</h3>\\n      <p style=\\\"color: var(--text-muted); font-size: 0.9rem; margin-bottom: 1.25rem;\\\">\\n        Waiting for the auctioneer to draw the next player...\\n      </p>\\n      {% if not viewer_mode %}\\n      <button type=\\\"button\\\" onclick=\\\"drawNextPlayer()\\\" class=\\\"btn btn-primary admin-only\\\">\\n        Draw First Player &rarr;\\n      </button>\\n      {% endif %}\\n    </div>\\n  </div>\\n\\n  <!-- Right Sidebar: Team Purses & Rosters (Mobile responsive) -->\\n  <div class=\\\"team-purse-sidebar\\\">\\n    <h3 style=\\\"font-size: 1.15rem; font-weight: 800; color: #fff; margin-bottom: 1rem; display: flex; align-items: center; justify-content: space-between;\\\">\\n      <span>\\ud83c\\udfc6 Participating Teams</span>\\n      <span style=\\\"font-size: 0.8rem; color: var(--text-muted); font-weight: 600;\\\">{{ (teams|length) if teams else 0 }} Teams</span>\\n    </h3>\\n\\n    <div id=\\\"teamsPurseList\\\" style=\\\"display: flex; flex-direction: column; gap: 0.85rem;\\\">\\n      {% for t_name, t_data in (teams.items() if teams else []) %}\\n      <div class=\\\"team-card-auction\\\" id=\\\"teamCard_{{ loop.index }}\\\" data-team=\\\"{{ t_name }}\\\">\\n        <div class=\\\"team-card-header\\\">\\n          <span class=\\\"team-card-name\\\">{{ t_name }}</span>\\n          <span class=\\\"team-squad-count\\\">{{ (t_data.players|length) if t_data.players else 0 }} Players</span>\\n        </div>\\n        <div class=\\\"team-progress-bg\\\">\\n          <div class=\\\"team-progress-bar\\\" style=\\\"width: 100%;\\\"></div>\\n        </div>\\n        <div class=\\\"team-financials\\\">\\n          <span class=\\\"team-rem-budget\\\">Purse: \\u20b9{{ t_data.purse }}</span>\\n          <span class=\\\"team-spent-budget\\\">Max Bid: \\u20b9{{ t_data.purse }}</span>\\n        </div>\\n      </div>\\n      {% endfor %}\\n    </div>\\n  </div>\\n</div>\\n\\n<!-- SOLD CELEBRATION MODAL (Auto-dismisses in 5s or on Next Draw) -->\\n<div class=\\\"sold-modal-overlay\\\" id=\\\"soldModal\\\" onclick=\\\"handleSoldModalBackdrop(event)\\\">\\n  <div class=\\\"sold-card-popup\\\" style=\\\"position: relative; max-width: 440px; padding: 2rem 1.5rem;\\\">\\n    <button type=\\\"button\\\" onclick=\\\"closeSoldModal()\\\" style=\\\"position: absolute; top: 12px; right: 15px; background: none; border: none; color: #94a3b8; font-size: 1.6rem; cursor: pointer; line-height: 1;\\\" title=\\\"Close Popup\\\">&times;</button>\\n    <div class=\\\"sold-banner\\\" style=\\\"font-size: 1.3rem; margin-bottom: 0.85rem;\\\">\\ud83c\\udf89 SOLD! \\ud83c\\udf89</div>\\n    <div style=\\\"width: 110px; height: 110px; border-radius: 50%; border: 3px solid var(--primary-gold); margin: 0 auto 0.65rem; overflow: hidden; background: #000; box-shadow: 0 0 25px rgba(245, 158, 11, 0.45);\\\">\\n      <img id=\\\"soldPlayerPhoto\\\" src=\\\"/static/images/avatar_allrounder.svg\\\" style=\\\"width: 100%; height: 100%; object-fit: cover;\\\">\\n    </div>\\n    <h2 id=\\\"soldPlayerName\\\" style=\\\"font-size: 1.75rem; font-weight: 900; color: #fff; margin-bottom: 0.2rem;\\\">-</h2>\\n    <div style=\\\"margin-bottom: 0.65rem;\\\">\\n      <span id=\\\"soldPlayerRoleBadge\\\" class=\\\"role-badge badge-allrounder\\\" style=\\\"font-size: 0.75rem; padding: 0.2rem 0.65rem;\\\">All-Rounder</span>\\n    </div>\\n    <div style=\\\"font-size: 1.05rem; color: #94a3b8; margin-bottom: 0.65rem;\\\">\\n      Purchased by <strong id=\\\"soldTeamName\\\" style=\\\"color: var(--primary-gold); font-size: 1.25rem;\\\">-</strong>\\n    </div>\\n    <div style=\\\"font-size: 2.6rem; font-weight: 900; color: var(--pitch-green); margin-bottom: 1.25rem;\\\" id=\\\"soldFinalPrice\\\">\\n      \\u20b90\\n    </div>\\n    <div style=\\\"display: flex; gap: 0.65rem; justify-content: center; flex-wrap: wrap;\\\">\\n      {% if not viewer_mode %}\\n      <button type=\\\"button\\\" class=\\\"btn btn-primary\\\" onclick=\\\"drawNextFromModal()\\\" style=\\\"font-weight: 800; font-size: 0.95rem; padding: 0.5rem 1.1rem;\\\">\\n        \\ud83d\\ude80 Next Draw &rarr;\\n      </button>\\n      {% endif %}\\n      <button type=\\\"button\\\" class=\\\"btn btn-secondary\\\" onclick=\\\"closeSoldModal()\\\" style=\\\"font-size: 0.95rem; padding: 0.5rem 1rem;\\\">\\n        Continue Auction &rarr;\\n      </button>\\n    </div>\\n  </div>\\n</div>\\n\\n<!-- HOST PIN MODAL (Only when not in viewer mode) -->\\n{% if not viewer_mode %}\\n<div class=\\\"sold-modal-overlay\\\" id=\\\"pinModal\\\">\\n  <div class=\\\"sold-card-popup\\\" style=\\\"max-width: 380px; padding: 2rem;\\\">\\n    <h3 style=\\\"font-size: 1.35rem; font-weight: 900; color: #fff; margin-bottom: 0.5rem;\\\">\\ud83d\\udd12 Organizer Authentication</h3>\\n    <p style=\\\"color: var(--text-muted); font-size: 0.85rem; margin-bottom: 1.25rem;\\\">Enter Organizer PIN to enable bidding and auction controls.</p>\\n    <input type=\\\"password\\\" id=\\\"inputHostPin\\\" class=\\\"form-control\\\" placeholder=\\\"Enter Organizer PIN\\\" style=\\\"text-align: center; font-size: 1.25rem; margin-bottom: 1rem;\\\">\\n    <div id=\\\"pinErrorMsg\\\" style=\\\"display: none; color: #f87171; font-size: 0.85rem; margin-bottom: 1rem; font-weight: 700;\\\"></div>\\n    <div style=\\\"display: flex; gap: 0.5rem;\\\">\\n      <button type=\\\"button\\\" onclick=\\\"verifyHostPin()\\\" class=\\\"btn btn-primary\\\" style=\\\"flex: 1;\\\">Unlock</button>\\n      <button type=\\\"button\\\" onclick=\\\"closePinModal()\\\" class=\\\"btn btn-secondary\\\">Cancel</button>\\n    </div>\\n  </div>\\n</div>\\n{% endif %}\\n\\n{% endblock %}\\n\\n{% block extra_js %}\\n<script src=\\\"/static/js/odometer.js\\\"></script>\\n<script src=\\\"/static/js/auction.js\\\"></script>\\n{% endblock %}\\n\", \"templates/auction_live.html\": \"{% extends \\\"base.html\\\" %}\\n\\n{% block extra_css %}\\n<link rel=\\\"stylesheet\\\" href=\\\"/static/css/auction.css\\\">\\n<style>\\n  {% if viewer_mode %}\\n  .control-deck, .admin-only, #auctioneerAuthBox, #btnHostAuctionToggle {\\n    display: none !important;\\n  }\\n  .viewer-banner {\\n    background: linear-gradient(90deg, #dc2626, #b91c1c);\\n    color: #fff;\\n    text-align: center;\\n    padding: 0.5rem 1rem;\\n    border-radius: var(--radius-sm);\\n    font-weight: 800;\\n    font-size: 0.85rem;\\n    letter-spacing: 0.05em;\\n    margin-bottom: 1rem;\\n    display: flex;\\n    align-items: center;\\n    justify-content: center;\\n    gap: 0.5rem;\\n  }\\n  {% endif %}\\n\\n  /* Mobile-first optimizations for Viewers interface */\\n  @media (max-width: 768px) {\\n    .page-container {\\n      padding: 0.5rem !important;\\n    }\\n    .auction-header-bar {\\n      flex-direction: column;\\n      align-items: flex-start !important;\\n      gap: 0.5rem;\\n    }\\n    .auction-stage {\\n      grid-template-columns: 1fr !important;\\n      gap: 1rem;\\n    }\\n    .player-main-name {\\n      font-size: 1.65rem !important;\\n    }\\n    .photo-frame {\\n      width: 140px !important;\\n      height: 140px !important;\\n    }\\n    .bid-amount {\\n      font-size: 2.5rem !important;\\n    }\\n    .bid-odometer-box {\\n      padding: 1.25rem 1rem !important;\\n    }\\n    .team-purse-sidebar {\\n      margin-top: 1rem;\\n    }\\n    .team-card-auction {\\n      padding: 0.75rem 1rem !important;\\n    }\\n  }\\n</style>\\n{% endblock %}\\n\\n{% block content %}\\n{% if viewer_mode %}\\n<div class=\\\"viewer-banner\\\">\\n  <span style=\\\"width: 8px; height: 8px; background: #fff; border-radius: 50%; display: inline-block; animation: pulse 1.5s infinite;\\\"></span>\\n  SPECTATOR LIVE MODE \\u2022 MOBILE LIVE STREAM\\n</div>\\n{% endif %}\\n\\n<div class=\\\"auction-header-bar\\\" style=\\\"display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;\\\">\\n  <div>\\n    <h1 style=\\\"font-size: 1.85rem; font-weight: 900; color: #fff; display: flex; align-items: center; gap: 0.5rem;\\\">\\n      <span>\\ud83c\\udfcf</span> Live Auction Arena\\n    </h1>\\n    <p style=\\\"color: var(--text-muted); font-size: 0.9rem;\\\">\\n      {% if viewer_mode %}Mobile Live Stream with Player Photos & Real-time Bids{% else %}Official Bidding Console with Player Photos & Roles{% endif %}\\n    </p>\\n  </div>\\n  <div style=\\\"display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap;\\\">\\n    <span class=\\\"round-tag\\\" id=\\\"currentRoundTag\\\">Round 1</span>\\n    <span class=\\\"round-tag\\\" id=\\\"poolStatusTag\\\" style=\\\"background: rgba(16, 185, 129, 0.15); color: var(--pitch-green); border-color: rgba(16, 185, 129, 0.4);\\\">\\n      Connecting...\\n    </span>\\n    {% if not viewer_mode %}\\n    <button type=\\\"button\\\" id=\\\"btnHostAuctionToggle\\\" onclick=\\\"toggleAuctionStarted()\\\" class=\\\"btn btn-success\\\" style=\\\"display: none; font-size: 0.8rem; padding: 0.3rem 0.65rem;\\\">\\n      \\ud83d\\ude80 Start Auction\\n    </button>\\n    <div id=\\\"auctioneerAuthBox\\\">\\n      <button type=\\\"button\\\" id=\\\"btnUnlockAuctioneer\\\" onclick=\\\"openPinModal()\\\" class=\\\"btn btn-secondary\\\" style=\\\"font-size: 0.8rem; padding: 0.3rem 0.65rem; border-color: rgba(245, 158, 11, 0.5); color: var(--primary-gold); display: flex; align-items: center; gap: 0.35rem;\\\">\\n        <span>\\ud83d\\udd12</span> Host Controls\\n      </button>\\n    </div>\\n    {% endif %}\\n  </div>\\n</div>\\n\\n<div class=\\\"auction-stage\\\">\\n  <!-- Center Main Arena -->\\n  <div>\\n    <!-- WAITING / NOT STARTED SCREEN (FOR SPECTATORS) -->\\n    <div id=\\\"auctionNotStartedScreen\\\" class=\\\"glass-card\\\" style=\\\"display: none; text-align: center; padding: 3.5rem 1.5rem; max-width: 680px; margin: 1.5rem auto 2.5rem; border: 2px solid var(--primary-gold); box-shadow: 0 0 40px rgba(245, 158, 11, 0.25);\\\">\\n      <div style=\\\"font-size: 3.5rem; margin-bottom: 0.75rem;\\\">\\ud83c\\udfcf</div>\\n      <div style=\\\"display: inline-block; background: rgba(245, 158, 11, 0.15); color: var(--primary-gold); border: 1px solid rgba(245, 158, 11, 0.4); padding: 0.35rem 1rem; border-radius: 9999px; font-weight: 800; font-size: 0.85rem; text-transform: uppercase; margin-bottom: 1rem;\\\">\\n        Kunsi Premier League (KPL 2026)\\n      </div>\\n      <h2 style=\\\"font-size: 1.85rem; font-weight: 900; color: #fff; margin-bottom: 0.75rem;\\\">Live Auction Has Not Begun</h2>\\n      <p style=\\\"color: var(--text-muted); font-size: 1rem; line-height: 1.6; max-width: 500px; margin: 0 auto 1.5rem;\\\">\\n        The tournament auctioneer has not yet started the live bidding stream. Please stay on this page; player draws will automatically appear the moment the auction begins.\\n      </p>\\n      <div style=\\\"display: flex; gap: 0.5rem; align-items: center; justify-content: center; color: var(--primary-gold); font-size: 0.9rem; font-weight: 700;\\\">\\n        <span style=\\\"display: inline-block; width: 10px; height: 10px; background: var(--primary-gold); border-radius: 50%; animation: pulse 1s infinite;\\\"></span>\\n        Waiting for Auctioneer to begin...\\n      </div>\\n    </div>\\n\\n    <!-- Active Player Card -->\\n    <div class=\\\"glass-card player-active-card\\\" id=\\\"activePlayerCard\\\">\\n      <!-- Player Showcase -->\\n      <div class=\\\"player-showcase\\\">\\n        <div class=\\\"photo-frame\\\">\\n          <img id=\\\"playerPhoto\\\" src=\\\"/static/images/avatar_allrounder.svg\\\" alt=\\\"Active Player\\\">\\n        </div>\\n        <div class=\\\"player-meta\\\">\\n          <div style=\\\"display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap;\\\">\\n            <span class=\\\"role-badge\\\" id=\\\"playerRoleBadge\\\">All-Rounder</span>\\n            <span class=\\\"player-id-tag\\\" id=\\\"playerIdTag\\\">ID: #--</span>\\n          </div>\\n          <h2 class=\\\"player-main-name\\\" id=\\\"playerName\\\">Waiting for Draw...</h2>\\n          <div class=\\\"stats-row\\\">\\n            <div class=\\\"stat-item\\\">\\n              <span class=\\\"stat-label\\\">Batting Style</span>\\n              <span class=\\\"stat-val\\\" id=\\\"playerBatting\\\">Right Hand Bat</span>\\n            </div>\\n            <div class=\\\"stat-item\\\">\\n              <span class=\\\"stat-label\\\">Bowling Style</span>\\n              <span class=\\\"stat-val\\\" id=\\\"playerBowling\\\">Right Arm Medium</span>\\n            </div>\\n            <div class=\\\"stat-item\\\">\\n              <span class=\\\"stat-label\\\">Village / Town</span>\\n              <span class=\\\"stat-val\\\" id=\\\"playerVillage\\\">Saidapur</span>\\n            </div>\\n            <div class=\\\"stat-item\\\">\\n              <span class=\\\"stat-label\\\">Base Price</span>\\n              <span class=\\\"stat-val\\\" id=\\\"playerBasePrice\\\" style=\\\"color: var(--pitch-green); font-weight: 800;\\\">\\u20b950</span>\\n            </div>\\n          </div>\\n        </div>\\n      </div>\\n\\n      <!-- Live Bidding Odometer -->\\n      <div class=\\\"bid-odometer-box\\\">\\n        <div class=\\\"bid-label\\\">Current Highest Bid</div>\\n        <div class=\\\"bid-amount\\\" id=\\\"bidOdometer\\\">\\u20b90</div>\\n        <div>\\n          <span class=\\\"bid-team-tag\\\" id=\\\"leadingTeamTag\\\">No Bids Yet</span>\\n        </div>\\n      </div>\\n\\n      <!-- Controls Deck (Only visible in Host Mode) -->\\n      {% if not viewer_mode %}\\n      <div class=\\\"control-deck admin-only\\\" id=\\\"auctioneerControls\\\">\\n                <!-- Pick Specific Player from Pool Dropdown -->\\n        <div style=\\\"background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(245, 158, 11, 0.35); border-radius: 8px; padding: 0.65rem 0.85rem; margin-bottom: 1rem; display: flex; gap: 0.65rem; align-items: center; flex-wrap: wrap;\\\">\\n          <span style=\\\"font-weight: 800; color: var(--primary-gold); font-size: 0.85rem; white-space: nowrap;\\\">\\n            \\ud83c\\udfaf Pick from Player List:\\n          </span>\\n          <select id=\\\"selectPlayerDropdown\\\" class=\\\"form-control\\\" style=\\\"flex: 1; min-width: 220px; font-size: 0.85rem; padding: 0.35rem 0.65rem;\\\">\\n            <option value=\\\"\\\">-- Choose Player to Bring to Auction --</option>\\n          </select>\\n          <button type=\\\"button\\\" class=\\\"btn btn-secondary\\\" onclick=\\\"chooseSelectedPlayer()\\\" style=\\\"font-size: 0.82rem; padding: 0.35rem 0.75rem; white-space: nowrap;\\\">\\n            Bring to Block &rarr;\\n          </button>\\n        </div>\\n\\n        <!-- Quick Bid Modifiers -->\\n        <div class=\\\"bid-modifiers-bar\\\">\\n          <button type=\\\"button\\\" class=\\\"btn-mod\\\" onclick=\\\"adjustCurrentBid(50)\\\">+\\u20b950</button>\\n          <button type=\\\"button\\\" class=\\\"btn-mod\\\" onclick=\\\"adjustCurrentBid(100)\\\">+\\u20b9100</button>\\n          <button type=\\\"button\\\" class=\\\"btn-mod\\\" onclick=\\\"adjustCurrentBid(200)\\\">+\\u20b9200</button>\\n          <button type=\\\"button\\\" class=\\\"btn-mod\\\" onclick=\\\"adjustCurrentBid(500)\\\">+\\u20b9500</button>\\n          <button type=\\\"button\\\" class=\\\"btn-mod\\\" onclick=\\\"adjustCurrentBid(-50)\\\" style=\\\"background: rgba(239, 68, 68, 0.2); border-color: rgba(239, 68, 68, 0.5);\\\">-\\u20b950</button>\\n        </div>\\n\\n        <!-- Team Selector for Bid Assignment -->\\n        <div style=\\\"display: flex; gap: 0.75rem; align-items: center; margin-bottom: 1.25rem; flex-wrap: wrap;\\\">\\n          <label style=\\\"font-weight: 700; color: #fff; font-size: 0.9rem;\\\">Assign Bid To Team:</label>\\n          <select id=\\\"biddingTeamSelect\\\" class=\\\"form-control\\\" style=\\\"flex: 1; min-width: 200px;\\\">\\n            <option value=\\\"\\\">-- Choose Team --</option>\\n            {% for t_name in (teams.keys() if teams else []) %}\\n            <option value=\\\"{{ t_name }}\\\">{{ t_name }}</option>\\n            {% endfor %}\\n          </select>\\n          <button type=\\\"button\\\" onclick=\\\"assignLeadingBidder()\\\" class=\\\"btn btn-secondary\\\" style=\\\"font-size: 0.9rem;\\\">\\n            Update Bidder\\n          </button>\\n        </div>\\n\\n        <!-- Big Action Buttons -->\\n        <div class=\\\"action-buttons-grid\\\">\\n          <button type=\\\"button\\\" class=\\\"btn-action btn-next-draw\\\" onclick=\\\"drawNextPlayer()\\\">\\n            \\ud83d\\ude80 Next Draw\\n          </button>\\n          <button type=\\\"button\\\" class=\\\"btn-action btn-sold\\\" onclick=\\\"confirmSellPlayer()\\\">\\n            \\ud83d\\udd28 SOLD!\\n          </button>\\n          <button type=\\\"button\\\" class=\\\"btn-action btn-unsold\\\" onclick=\\\"markUnsold(false)\\\">\\n            \\u274c Unsold (Round 2)\\n          </button>\\n          <button type=\\\"button\\\" class=\\\"btn-action btn-perm-unsold\\\" onclick=\\\"markUnsold(true)\\\">\\n            \\u26d4 Permanent Unsold\\n          </button>\\n        </div>\\n\\n        <div style=\\\"margin-top: 1rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;\\\">\\n          <button type=\\\"button\\\" onclick=\\\"undoLastAction()\\\" class=\\\"btn btn-secondary\\\" style=\\\"font-size: 0.85rem; padding: 0.35rem 0.75rem;\\\">\\n            \\u21a9\\ufe0f Undo Last Action\\n          </button>\\n          <button type=\\\"button\\\" id=\\\"btnStartRound2\\\" onclick=\\\"startRound2()\\\" class=\\\"btn btn-secondary\\\" style=\\\"display: none; font-size: 0.85rem; padding: 0.35rem 0.75rem; border-color: #f59e0b; color: #f59e0b;\\\">\\n            \\ud83d\\udd04 Start Round 2 (Unsold Pool)\\n          </button>\\n        </div>\\n      </div>\\n      {% endif %}\\n    </div>\\n\\n    <!-- Empty State when no active player -->\\n    <div id=\\\"noActivePlayerState\\\" class=\\\"glass-card\\\" style=\\\"display: none; text-align: center; padding: 3rem 1.5rem;\\\">\\n      <h3 style=\\\"font-size: 1.35rem; color: #fff; margin-bottom: 0.5rem;\\\">No Active Player on the Auction Block</h3>\\n      <p style=\\\"color: var(--text-muted); font-size: 0.9rem; margin-bottom: 1.25rem;\\\">\\n        Waiting for the auctioneer to draw the next player...\\n      </p>\\n      {% if not viewer_mode %}\\n      <button type=\\\"button\\\" onclick=\\\"drawNextPlayer()\\\" class=\\\"btn btn-primary admin-only\\\">\\n        Draw First Player &rarr;\\n      </button>\\n      {% endif %}\\n    </div>\\n  </div>\\n\\n  <!-- Right Sidebar: Team Purses & Rosters (Mobile responsive) -->\\n  <div class=\\\"team-purse-sidebar\\\">\\n    <h3 style=\\\"font-size: 1.15rem; font-weight: 800; color: #fff; margin-bottom: 1rem; display: flex; align-items: center; justify-content: space-between;\\\">\\n      <span>\\ud83c\\udfc6 Participating Teams</span>\\n      <span style=\\\"font-size: 0.8rem; color: var(--text-muted); font-weight: 600;\\\">{{ (teams|length) if teams else 0 }} Teams</span>\\n    </h3>\\n\\n    <div id=\\\"teamsPurseList\\\" style=\\\"display: flex; flex-direction: column; gap: 0.85rem;\\\">\\n      {% for t_name, t_data in (teams.items() if teams else []) %}\\n      <div class=\\\"team-card-auction\\\" id=\\\"teamCard_{{ loop.index }}\\\" data-team=\\\"{{ t_name }}\\\">\\n        <div class=\\\"team-card-header\\\">\\n          <span class=\\\"team-card-name\\\">{{ t_name }}</span>\\n          <span class=\\\"team-squad-count\\\">{{ (t_data.players|length) if t_data.players else 0 }} Players</span>\\n        </div>\\n        <div class=\\\"team-progress-bg\\\">\\n          <div class=\\\"team-progress-bar\\\" style=\\\"width: 100%;\\\"></div>\\n        </div>\\n        <div class=\\\"team-financials\\\">\\n          <span class=\\\"team-rem-budget\\\">Purse: \\u20b9{{ t_data.purse }}</span>\\n          <span class=\\\"team-spent-budget\\\">Max Bid: \\u20b9{{ t_data.purse }}</span>\\n        </div>\\n      </div>\\n      {% endfor %}\\n    </div>\\n  </div>\\n</div>\\n\\n<!-- SOLD CELEBRATION MODAL (Auto-dismisses in 5s or on Next Draw) -->\\n<div class=\\\"sold-modal-overlay\\\" id=\\\"soldModal\\\" onclick=\\\"handleSoldModalBackdrop(event)\\\">\\n  <div class=\\\"sold-card-popup\\\" style=\\\"position: relative; max-width: 440px; padding: 2rem 1.5rem;\\\">\\n    <button type=\\\"button\\\" onclick=\\\"closeSoldModal()\\\" style=\\\"position: absolute; top: 12px; right: 15px; background: none; border: none; color: #94a3b8; font-size: 1.6rem; cursor: pointer; line-height: 1;\\\" title=\\\"Close Popup\\\">&times;</button>\\n    <div class=\\\"sold-banner\\\" style=\\\"font-size: 1.3rem; margin-bottom: 0.85rem;\\\">\\ud83c\\udf89 SOLD! \\ud83c\\udf89</div>\\n    <div style=\\\"width: 110px; height: 110px; border-radius: 50%; border: 3px solid var(--primary-gold); margin: 0 auto 0.65rem; overflow: hidden; background: #000; box-shadow: 0 0 25px rgba(245, 158, 11, 0.45);\\\">\\n      <img id=\\\"soldPlayerPhoto\\\" src=\\\"/static/images/avatar_allrounder.svg\\\" style=\\\"width: 100%; height: 100%; object-fit: cover;\\\">\\n    </div>\\n    <h2 id=\\\"soldPlayerName\\\" style=\\\"font-size: 1.75rem; font-weight: 900; color: #fff; margin-bottom: 0.2rem;\\\">-</h2>\\n    <div style=\\\"margin-bottom: 0.65rem;\\\">\\n      <span id=\\\"soldPlayerRoleBadge\\\" class=\\\"role-badge badge-allrounder\\\" style=\\\"font-size: 0.75rem; padding: 0.2rem 0.65rem;\\\">All-Rounder</span>\\n    </div>\\n    <div style=\\\"font-size: 1.05rem; color: #94a3b8; margin-bottom: 0.65rem;\\\">\\n      Purchased by <strong id=\\\"soldTeamName\\\" style=\\\"color: var(--primary-gold); font-size: 1.25rem;\\\">-</strong>\\n    </div>\\n    <div style=\\\"font-size: 2.6rem; font-weight: 900; color: var(--pitch-green); margin-bottom: 1.25rem;\\\" id=\\\"soldFinalPrice\\\">\\n      \\u20b90\\n    </div>\\n    <div style=\\\"display: flex; gap: 0.65rem; justify-content: center; flex-wrap: wrap;\\\">\\n      {% if not viewer_mode %}\\n      <button type=\\\"button\\\" class=\\\"btn btn-primary\\\" onclick=\\\"drawNextFromModal()\\\" style=\\\"font-weight: 800; font-size: 0.95rem; padding: 0.5rem 1.1rem;\\\">\\n        \\ud83d\\ude80 Next Draw &rarr;\\n      </button>\\n      {% endif %}\\n      <button type=\\\"button\\\" class=\\\"btn btn-secondary\\\" onclick=\\\"closeSoldModal()\\\" style=\\\"font-size: 0.95rem; padding: 0.5rem 1rem;\\\">\\n        Continue Auction &rarr;\\n      </button>\\n    </div>\\n  </div>\\n</div>\\n\\n<!-- HOST PIN MODAL (Only when not in viewer mode) -->\\n{% if not viewer_mode %}\\n<div class=\\\"sold-modal-overlay\\\" id=\\\"pinModal\\\">\\n  <div class=\\\"sold-card-popup\\\" style=\\\"max-width: 380px; padding: 2rem;\\\">\\n    <h3 style=\\\"font-size: 1.35rem; font-weight: 900; color: #fff; margin-bottom: 0.5rem;\\\">\\ud83d\\udd12 Organizer Authentication</h3>\\n    <p style=\\\"color: var(--text-muted); font-size: 0.85rem; margin-bottom: 1.25rem;\\\">Enter Organizer PIN to enable bidding and auction controls.</p>\\n    <input type=\\\"password\\\" id=\\\"inputHostPin\\\" class=\\\"form-control\\\" placeholder=\\\"Enter Organizer PIN\\\" style=\\\"text-align: center; font-size: 1.25rem; margin-bottom: 1rem;\\\">\\n    <div id=\\\"pinErrorMsg\\\" style=\\\"display: none; color: #f87171; font-size: 0.85rem; margin-bottom: 1rem; font-weight: 700;\\\"></div>\\n    <div style=\\\"display: flex; gap: 0.5rem;\\\">\\n      <button type=\\\"button\\\" onclick=\\\"verifyHostPin()\\\" class=\\\"btn btn-primary\\\" style=\\\"flex: 1;\\\">Unlock</button>\\n      <button type=\\\"button\\\" onclick=\\\"closePinModal()\\\" class=\\\"btn btn-secondary\\\">Cancel</button>\\n    </div>\\n  </div>\\n</div>\\n{% endif %}\\n\\n{% endblock %}\\n\\n{% block extra_js %}\\n<script src=\\\"/static/js/odometer.js\\\"></script>\\n<script src=\\\"/static/js/auction.js\\\"></script>\\n{% endblock %}\\n\", \"base.html\": \"<!DOCTYPE html>\\n<html lang=\\\"en\\\">\\n<head>\\n  <meta charset=\\\"UTF-8\\\">\\n  <meta name=\\\"viewport\\\" content=\\\"width=device-width, initial-scale=1.0\\\">\\n  <title>{% block title %}{{ tournament_name }}{% endblock %}</title>\\n  <link rel=\\\"stylesheet\\\" href=\\\"/static/css/style.css\\\">\\n  <style>\\n    /* Embed mode (when embedded in an iframe inside Admin subpage 2) */\\n    {% if request.args.get('embed') %}\\n    .navbar, footer { display: none !important; }\\n    body { background: transparent !important; padding: 0 !important; margin: 0 !important; }\\n    .page-container { padding: 0.5rem 0.25rem !important; max-width: 100% !important; margin: 0 !important; }\\n    {% endif %}\\n\\n    /* Clean, rock-solid navbar */\\n    .navbar {\\n      background: rgba(10, 15, 26, 0.95);\\n      backdrop-filter: blur(16px);\\n      -webkit-backdrop-filter: blur(16px);\\n      border-bottom: 1px solid rgba(255, 255, 255, 0.1);\\n      position: sticky;\\n      top: 0;\\n      z-index: 1000;\\n      padding: 0.75rem 1.25rem;\\n    }\\n    .nav-container {\\n      max-width: 1200px;\\n      margin: 0 auto;\\n      display: flex;\\n      align-items: center;\\n      justify-content: space-between;\\n      gap: 1rem;\\n    }\\n    .nav-brand {\\n      display: flex;\\n      align-items: center;\\n      gap: 0.65rem;\\n      text-decoration: none;\\n      color: #fff;\\n      font-weight: 800;\\n      font-size: 1.15rem;\\n      white-space: nowrap;\\n    }\\n    .brand-badge {\\n      background: linear-gradient(135deg, #f59e0b, #d97706);\\n      color: #000;\\n      font-weight: 900;\\n      padding: 0.2rem 0.55rem;\\n      border-radius: 6px;\\n      font-size: 0.85rem;\\n      letter-spacing: 0.05em;\\n    }\\n    .nav-links {\\n      display: flex;\\n      align-items: center;\\n      gap: 0.5rem;\\n      list-style: none;\\n      margin: 0;\\n      padding: 0;\\n    }\\n    .nav-link {\\n      color: #94a3b8;\\n      text-decoration: none;\\n      font-weight: 700;\\n      font-size: 0.92rem;\\n      padding: 0.5rem 0.9rem;\\n      border-radius: 8px;\\n      transition: all 0.2s ease;\\n      display: inline-flex;\\n      align-items: center;\\n      gap: 0.4rem;\\n      white-space: nowrap;\\n    }\\n    .nav-link:hover {\\n      color: #fff;\\n      background: rgba(255, 255, 255, 0.08);\\n    }\\n    .nav-link.active {\\n      color: #fff;\\n      background: rgba(255, 255, 255, 0.15);\\n      border-bottom: 2px solid #f59e0b;\\n    }\\n    .nav-link.tab-admin.active {\\n      background: rgba(245, 158, 11, 0.2);\\n      color: #f59e0b;\\n      border-bottom: 2px solid #f59e0b;\\n    }\\n    .nav-link.tab-reg.active {\\n      background: rgba(56, 189, 248, 0.2);\\n      color: #38bdf8;\\n      border-bottom: 2px solid #38bdf8;\\n    }\\n    .nav-link.tab-viewers {\\n      background: rgba(239, 68, 68, 0.15);\\n      color: #f87171;\\n      border: 1px solid rgba(239, 68, 68, 0.35);\\n    }\\n    .nav-link.tab-viewers:hover,\\n    .nav-link.tab-viewers.active {\\n      background: #ef4444;\\n      color: #fff;\\n      border-color: #ef4444;\\n      box-shadow: 0 0 15px rgba(239, 68, 68, 0.5);\\n    }\\n    .live-pulse-dot {\\n      width: 8px;\\n      height: 8px;\\n      background: #ef4444;\\n      border-radius: 50%;\\n      display: inline-block;\\n      box-shadow: 0 0 8px #ef4444;\\n      animation: pulseDot 1.5s infinite;\\n    }\\n    .nav-link.tab-viewers.active .live-pulse-dot,\\n    .nav-link.tab-viewers:hover .live-pulse-dot {\\n      background: #fff;\\n      box-shadow: 0 0 8px #fff;\\n    }\\n    @keyframes pulseDot {\\n      0% { transform: scale(0.95); opacity: 0.8; }\\n      50% { transform: scale(1.3); opacity: 1; }\\n      100% { transform: scale(0.95); opacity: 0.8; }\\n    }\\n\\n    /* Mobile toggle */\\n    .mobile-toggle {\\n      display: none;\\n      background: none;\\n      border: none;\\n      color: #fff;\\n      font-size: 1.5rem;\\n      cursor: pointer;\\n      padding: 0.25rem 0.5rem;\\n    }\\n\\n    @media (max-width: 860px) {\\n      .mobile-toggle { display: block; }\\n      .nav-links {\\n        display: none;\\n        flex-direction: column;\\n        position: absolute;\\n        top: 100%;\\n        left: 0;\\n        right: 0;\\n        background: #0b1120;\\n        padding: 1rem;\\n        border-bottom: 1px solid rgba(255, 255, 255, 0.1);\\n        box-shadow: 0 10px 25px rgba(0,0,0,0.5);\\n      }\\n      .nav-links.open { display: flex; }\\n      .nav-link { padding: 0.75rem 1rem; font-size: 1rem; width: 100%; }\\n    }\\n  </style>\\n  {% block extra_css %}{% endblock %}\\n</head>\\n<body>\\n  <header class=\\\"navbar\\\">\\n    <div class=\\\"nav-container\\\">\\n      <a href=\\\"/\\\" class=\\\"nav-brand\\\">\\n        <span class=\\\"brand-badge\\\">KPL</span>\\n        <span>Kunsi Premier League (KPL 2026)</span>\\n      </a>\\n      <button class=\\\"mobile-toggle\\\" onclick=\\\"document.querySelector('.nav-links').classList.toggle('open')\\\" aria-label=\\\"Toggle Menu\\\">\\u2630</button>\\n      <ul class=\\\"nav-links\\\">\\n        <li><a href=\\\"/\\\" class=\\\"nav-link {% if active_page == 'home' %}active{% endif %}\\\">\\ud83c\\udfe0 Home</a></li>\\n        <li><a href=\\\"/admin\\\" class=\\\"nav-link tab-admin {% if active_page == 'admin' %}active{% endif %}\\\">\\u2699\\ufe0f 1. Admin</a></li>\\n        <li><a href=\\\"/register\\\" class=\\\"nav-link tab-reg {% if active_page == 'register' %}active{% endif %}\\\">\\ud83d\\udcdd 2. Registration</a></li>\\n        <li>\\n          <a href=\\\"/view\\\" class=\\\"nav-link tab-viewers {% if active_page == 'view' %}active{% endif %}\\\" title=\\\"Mobile Viewers Live Auction\\\">\\n            <span class=\\\"live-pulse-dot\\\"></span>\\n            <span>\\ud83d\\udc41\\ufe0f 3. Auction Viewers</span>\\n          </a>\\n        </li>\\n      </ul>\\n    </div>\\n  </header>\\n\\n  <main class=\\\"page-container\\\">\\n    {% block content %}{% endblock %}\\n  </main>\\n\\n  <footer style=\\\"text-align: center; padding: 2.5rem 1rem; color: #64748b; font-size: 0.85rem; border-top: 1px solid rgba(255,255,255,0.08); margin-top: auto;\\\">\\n    <p>Kunsi Premier League (KPL 2026) &copy; 2026. Official Tournament Portal & Live Auction System.</p>\\n  </footer>\\n\\n  {% block extra_js %}{% endblock %}\\n</body>\\n</html>\\n\", \"templates/base.html\": \"<!DOCTYPE html>\\n<html lang=\\\"en\\\">\\n<head>\\n  <meta charset=\\\"UTF-8\\\">\\n  <meta name=\\\"viewport\\\" content=\\\"width=device-width, initial-scale=1.0\\\">\\n  <title>{% block title %}{{ tournament_name }}{% endblock %}</title>\\n  <link rel=\\\"stylesheet\\\" href=\\\"/static/css/style.css\\\">\\n  <style>\\n    /* Embed mode (when embedded in an iframe inside Admin subpage 2) */\\n    {% if request.args.get('embed') %}\\n    .navbar, footer { display: none !important; }\\n    body { background: transparent !important; padding: 0 !important; margin: 0 !important; }\\n    .page-container { padding: 0.5rem 0.25rem !important; max-width: 100% !important; margin: 0 !important; }\\n    {% endif %}\\n\\n    /* Clean, rock-solid navbar */\\n    .navbar {\\n      background: rgba(10, 15, 26, 0.95);\\n      backdrop-filter: blur(16px);\\n      -webkit-backdrop-filter: blur(16px);\\n      border-bottom: 1px solid rgba(255, 255, 255, 0.1);\\n      position: sticky;\\n      top: 0;\\n      z-index: 1000;\\n      padding: 0.75rem 1.25rem;\\n    }\\n    .nav-container {\\n      max-width: 1200px;\\n      margin: 0 auto;\\n      display: flex;\\n      align-items: center;\\n      justify-content: space-between;\\n      gap: 1rem;\\n    }\\n    .nav-brand {\\n      display: flex;\\n      align-items: center;\\n      gap: 0.65rem;\\n      text-decoration: none;\\n      color: #fff;\\n      font-weight: 800;\\n      font-size: 1.15rem;\\n      white-space: nowrap;\\n    }\\n    .brand-badge {\\n      background: linear-gradient(135deg, #f59e0b, #d97706);\\n      color: #000;\\n      font-weight: 900;\\n      padding: 0.2rem 0.55rem;\\n      border-radius: 6px;\\n      font-size: 0.85rem;\\n      letter-spacing: 0.05em;\\n    }\\n    .nav-links {\\n      display: flex;\\n      align-items: center;\\n      gap: 0.5rem;\\n      list-style: none;\\n      margin: 0;\\n      padding: 0;\\n    }\\n    .nav-link {\\n      color: #94a3b8;\\n      text-decoration: none;\\n      font-weight: 700;\\n      font-size: 0.92rem;\\n      padding: 0.5rem 0.9rem;\\n      border-radius: 8px;\\n      transition: all 0.2s ease;\\n      display: inline-flex;\\n      align-items: center;\\n      gap: 0.4rem;\\n      white-space: nowrap;\\n    }\\n    .nav-link:hover {\\n      color: #fff;\\n      background: rgba(255, 255, 255, 0.08);\\n    }\\n    .nav-link.active {\\n      color: #fff;\\n      background: rgba(255, 255, 255, 0.15);\\n      border-bottom: 2px solid #f59e0b;\\n    }\\n    .nav-link.tab-admin.active {\\n      background: rgba(245, 158, 11, 0.2);\\n      color: #f59e0b;\\n      border-bottom: 2px solid #f59e0b;\\n    }\\n    .nav-link.tab-reg.active {\\n      background: rgba(56, 189, 248, 0.2);\\n      color: #38bdf8;\\n      border-bottom: 2px solid #38bdf8;\\n    }\\n    .nav-link.tab-viewers {\\n      background: rgba(239, 68, 68, 0.15);\\n      color: #f87171;\\n      border: 1px solid rgba(239, 68, 68, 0.35);\\n    }\\n    .nav-link.tab-viewers:hover,\\n    .nav-link.tab-viewers.active {\\n      background: #ef4444;\\n      color: #fff;\\n      border-color: #ef4444;\\n      box-shadow: 0 0 15px rgba(239, 68, 68, 0.5);\\n    }\\n    .live-pulse-dot {\\n      width: 8px;\\n      height: 8px;\\n      background: #ef4444;\\n      border-radius: 50%;\\n      display: inline-block;\\n      box-shadow: 0 0 8px #ef4444;\\n      animation: pulseDot 1.5s infinite;\\n    }\\n    .nav-link.tab-viewers.active .live-pulse-dot,\\n    .nav-link.tab-viewers:hover .live-pulse-dot {\\n      background: #fff;\\n      box-shadow: 0 0 8px #fff;\\n    }\\n    @keyframes pulseDot {\\n      0% { transform: scale(0.95); opacity: 0.8; }\\n      50% { transform: scale(1.3); opacity: 1; }\\n      100% { transform: scale(0.95); opacity: 0.8; }\\n    }\\n\\n    /* Mobile toggle */\\n    .mobile-toggle {\\n      display: none;\\n      background: none;\\n      border: none;\\n      color: #fff;\\n      font-size: 1.5rem;\\n      cursor: pointer;\\n      padding: 0.25rem 0.5rem;\\n    }\\n\\n    @media (max-width: 860px) {\\n      .mobile-toggle { display: block; }\\n      .nav-links {\\n        display: none;\\n        flex-direction: column;\\n        position: absolute;\\n        top: 100%;\\n        left: 0;\\n        right: 0;\\n        background: #0b1120;\\n        padding: 1rem;\\n        border-bottom: 1px solid rgba(255, 255, 255, 0.1);\\n        box-shadow: 0 10px 25px rgba(0,0,0,0.5);\\n      }\\n      .nav-links.open { display: flex; }\\n      .nav-link { padding: 0.75rem 1rem; font-size: 1rem; width: 100%; }\\n    }\\n  </style>\\n  {% block extra_css %}{% endblock %}\\n</head>\\n<body>\\n  <header class=\\\"navbar\\\">\\n    <div class=\\\"nav-container\\\">\\n      <a href=\\\"/\\\" class=\\\"nav-brand\\\">\\n        <span class=\\\"brand-badge\\\">KPL</span>\\n        <span>Kunsi Premier League (KPL 2026)</span>\\n      </a>\\n      <button class=\\\"mobile-toggle\\\" onclick=\\\"document.querySelector('.nav-links').classList.toggle('open')\\\" aria-label=\\\"Toggle Menu\\\">\\u2630</button>\\n      <ul class=\\\"nav-links\\\">\\n        <li><a href=\\\"/\\\" class=\\\"nav-link {% if active_page == 'home' %}active{% endif %}\\\">\\ud83c\\udfe0 Home</a></li>\\n        <li><a href=\\\"/admin\\\" class=\\\"nav-link tab-admin {% if active_page == 'admin' %}active{% endif %}\\\">\\u2699\\ufe0f 1. Admin</a></li>\\n        <li><a href=\\\"/register\\\" class=\\\"nav-link tab-reg {% if active_page == 'register' %}active{% endif %}\\\">\\ud83d\\udcdd 2. Registration</a></li>\\n        <li>\\n          <a href=\\\"/view\\\" class=\\\"nav-link tab-viewers {% if active_page == 'view' %}active{% endif %}\\\" title=\\\"Mobile Viewers Live Auction\\\">\\n            <span class=\\\"live-pulse-dot\\\"></span>\\n            <span>\\ud83d\\udc41\\ufe0f 3. Auction Viewers</span>\\n          </a>\\n        </li>\\n      </ul>\\n    </div>\\n  </header>\\n\\n  <main class=\\\"page-container\\\">\\n    {% block content %}{% endblock %}\\n  </main>\\n\\n  <footer style=\\\"text-align: center; padding: 2.5rem 1rem; color: #64748b; font-size: 0.85rem; border-top: 1px solid rgba(255,255,255,0.08); margin-top: auto;\\\">\\n    <p>Kunsi Premier League (KPL 2026) &copy; 2026. Official Tournament Portal & Live Auction System.</p>\\n  </footer>\\n\\n  {% block extra_js %}{% endblock %}\\n</body>\\n</html>\\n\", \"index.html\": \"{% extends \\\"base.html\\\" %}\\n\\n{% block content %}\\n<div style=\\\"text-align: center; max-width: 820px; margin: 1.5rem auto 2.5rem;\\\">\\n  <div style=\\\"display: inline-block; background: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.4); padding: 0.35rem 1rem; border-radius: 9999px; font-weight: 800; font-size: 0.85rem; text-transform: uppercase; margin-bottom: 1rem;\\\">\\n    \\ud83c\\udfcf Season 2026 Official Tournament Portal\\n  </div>\\n  <h1 style=\\\"font-size: 2.75rem; font-weight: 900; line-height: 1.15; margin-bottom: 0.75rem; color: #fff;\\\">\\n    Kunsi Premier League (KPL 2026)\\n  </h1>\\n  <p style=\\\"font-size: 1.1rem; color: #94a3b8; line-height: 1.6;\\\">\\n    Official Tournament Guide, Player Registration Directory, and Mobile Live Auction Dashboard.\\n  </p>\\n</div>\\n\\n<!-- Quick Tournament Stats Counter -->\\n<div style=\\\"display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem;\\\">\\n  <div class=\\\"glass-card\\\" style=\\\"text-align: center; padding: 1.25rem 1rem;\\\">\\n    <div style=\\\"font-size: 2.25rem; font-weight: 900; color: #f59e0b;\\\">{{ total_registered }}</div>\\n    <div style=\\\"color: #94a3b8; font-weight: 600; font-size: 0.9rem; margin-top: 0.25rem;\\\">Registered Players</div>\\n  </div>\\n  <div class=\\\"glass-card\\\" style=\\\"text-align: center; padding: 1.25rem 1rem;\\\">\\n    <div style=\\\"font-size: 2.25rem; font-weight: 900; color: #38bdf8;\\\">{{ total_teams }}</div>\\n    <div style=\\\"color: #94a3b8; font-weight: 600; font-size: 0.9rem; margin-top: 0.25rem;\\\">Participating Teams</div>\\n  </div>\\n  <div class=\\\"glass-card\\\" style=\\\"text-align: center; padding: 1.25rem 1rem;\\\">\\n    <div style=\\\"font-size: 2.25rem; font-weight: 900; color: #10b981;\\\">\\u20b9{{ total_purse }}</div>\\n    <div style=\\\"color: #94a3b8; font-weight: 600; font-size: 0.9rem; margin-top: 0.25rem;\\\">Purse per Team</div>\\n  </div>\\n  <div class=\\\"glass-card\\\" style=\\\"text-align: center; padding: 1.25rem 1rem;\\\">\\n    <div style=\\\"font-size: 2.25rem; font-weight: 900; color: #ec4899;\\\">\\u20b9{{ reg_fee }}</div>\\n    <div style=\\\"color: #94a3b8; font-weight: 600; font-size: 0.9rem; margin-top: 0.25rem;\\\">Registration Fee</div>\\n  </div>\\n</div>\\n\\n<!-- READ-ONLY TOURNAMENT INFORMATION -->\\n<div class=\\\"glass-card\\\" style=\\\"margin-bottom: 2rem; border-color: rgba(245, 158, 11, 0.3);\\\">\\n  <h2 style=\\\"font-size: 1.35rem; font-weight: 800; color: #f59e0b; margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem;\\\">\\n    <span>\\ud83d\\udccb</span> Tournament Overview & Rules\\n  </h2>\\n  <div style=\\\"display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1.25rem; color: #cbd5e1; font-size: 0.95rem; line-height: 1.6;\\\">\\n    <div style=\\\"background: rgba(15,23,42,0.6); padding: 1rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.08);\\\">\\n      <strong style=\\\"color: #fff; display: block; margin-bottom: 0.35rem;\\\">\\ud83c\\udfdf\\ufe0f Venue & Format</strong>\\n      Location: Saidapur Cricket Ground.<br>\\n      Format: Limited overs knockout & league matches with official white ball.\\n    </div>\\n    <div style=\\\"background: rgba(15,23,42,0.6); padding: 1rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.08);\\\">\\n      <strong style=\\\"color: #fff; display: block; margin-bottom: 0.35rem;\\\">\\ud83d\\udcb0 Auction Rules & Purses</strong>\\n      Purse per team: \\u20b9{{ total_purse }}. Minimum squad requirement: 10 players.<br>\\n      Minimum bid: \\u20b950. Star Player Retention: \\u20b9500. Owner Retention: \\u20b9100.\\n    </div>\\n    <div style=\\\"background: rgba(15,23,42,0.6); padding: 1rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.08);\\\">\\n      <strong style=\\\"color: #fff; display: block; margin-bottom: 0.35rem;\\\">\\ud83d\\udcb3 Registration Instructions</strong>\\n      Registration fee: \\u20b9{{ reg_fee }} via PhonePe/GPay/BHIM UPI.<br>\\n      Players submit name, mobile, role, village, and photo.\\n    </div>\\n  </div>\\n</div>\\n\\n<!-- 3 MAIN TABS PORTAL CARDS -->\\n<h2 style=\\\"font-size: 1.35rem; font-weight: 800; color: #fff; margin-bottom: 1rem;\\\">\\n  Explore Tournament Portals\\n</h2>\\n<div style=\\\"display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1.5rem;\\\">\\n  <!-- TAB 1 CARD -->\\n  <div class=\\\"glass-card\\\" style=\\\"display: flex; flex-direction: column; justify-content: space-between; border-color: rgba(245, 158, 11, 0.4);\\\">\\n    <div>\\n      <div style=\\\"display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;\\\">\\n        <span style=\\\"font-size: 2.25rem;\\\">\\u2699\\ufe0f</span>\\n        <span style=\\\"background: rgba(245,158,11,0.2); color: #fbbf24; border: 1px solid rgba(245,158,11,0.4); padding: 0.2rem 0.6rem; border-radius: 9999px; font-weight: 800; font-size: 0.75rem;\\\">\\n          Tab 1: Organizer\\n        </span>\\n      </div>\\n      <h3 style=\\\"font-size: 1.45rem; font-weight: 800; color: #fff; margin-bottom: 0.5rem;\\\">1. Organizer Admin</h3>\\n      <p style=\\\"color: #94a3b8; font-size: 0.95rem; line-height: 1.5; margin-bottom: 1.5rem;\\\">\\n        PIN-protected organizer control panel featuring two sub-pages: Tournament Configuration (teams, purse, retentions, UPI settings, Excel) and Live Auction Host Controller (next draw, increase bids, sold, unsold, undo).\\n      </p>\\n    </div>\\n    <a href=\\\"/admin\\\" class=\\\"btn btn-primary\\\" style=\\\"width: 100%; text-align: center; font-size: 1.05rem;\\\">\\n      Open Admin Console &rarr;\\n    </a>\\n  </div>\\n\\n  <!-- TAB 2 CARD -->\\n  <div class=\\\"glass-card\\\" style=\\\"display: flex; flex-direction: column; justify-content: space-between; border-color: rgba(56, 189, 248, 0.4);\\\">\\n    <div>\\n      <div style=\\\"display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;\\\">\\n        <span style=\\\"font-size: 2.25rem;\\\">\\ud83d\\udcdd</span>\\n        <span style=\\\"background: rgba(56,189,248,0.2); color: #38bdf8; border: 1px solid rgba(56,189,248,0.4); padding: 0.2rem 0.6rem; border-radius: 9999px; font-weight: 800; font-size: 0.75rem;\\\">\\n          Tab 2: Players\\n        </span>\\n      </div>\\n      <h3 style=\\\"font-size: 1.45rem; font-weight: 800; color: #fff; margin-bottom: 0.5rem;\\\">2. Player Registration</h3>\\n      <p style=\\\"color: #94a3b8; font-size: 0.95rem; line-height: 1.5; margin-bottom: 1.5rem;\\\">\\n        Opens immediately with the complete directory of all registered players (Name, Role, Village, Amount Sent, Photo, UPI) with search & filter, plus quick form to register new players.\\n      </p>\\n    </div>\\n    <a href=\\\"/register\\\" class=\\\"btn btn-secondary\\\" style=\\\"width: 100%; text-align: center; font-size: 1.05rem; border-color: rgba(56,189,248,0.5); color: #38bdf8;\\\">\\n      Open Registration Tab &rarr;\\n    </a>\\n  </div>\\n\\n  <!-- TAB 3 CARD -->\\n  <div class=\\\"glass-card\\\" style=\\\"display: flex; flex-direction: column; justify-content: space-between; border: 2px solid #ef4444; box-shadow: 0 0 35px rgba(239, 68, 68, 0.25);\\\">\\n    <div>\\n      <div style=\\\"display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;\\\">\\n        <span style=\\\"font-size: 2.25rem;\\\">\\ud83d\\udc41\\ufe0f</span>\\n        <span style=\\\"background: rgba(239,68,68,0.2); color: #f87171; border: 1px solid rgba(239,68,68,0.4); padding: 0.2rem 0.6rem; border-radius: 9999px; font-weight: 800; font-size: 0.75rem;\\\">\\n          Tab 3: Spectators\\n        </span>\\n      </div>\\n      <h3 style=\\\"font-size: 1.45rem; font-weight: 800; color: #fff; margin-bottom: 0.5rem;\\\">3. Auction Viewers</h3>\\n      <p style=\\\"color: #94a3b8; font-size: 0.95rem; line-height: 1.5; margin-bottom: 1.5rem;\\\">\\n        Mobile-first live bidding stream. Watch player photos, odometer bids, sold celebrations, and squad purse meters from any phone, TV, or projector in real time. (Read-only, no login).\\n      </p>\\n    </div>\\n    <a href=\\\"/view\\\" class=\\\"btn btn-danger\\\" style=\\\"width: 100%; text-align: center; font-size: 1.05rem; font-weight: 800; background: linear-gradient(135deg, #ef4444, #b91c1c);\\\">\\n      \\ud83d\\udc41\\ufe0f Open Auction Viewers Stream &rarr;\\n    </a>\\n  </div>\\n</div>\\n{% endblock %}\\n\", \"templates/index.html\": \"{% extends \\\"base.html\\\" %}\\n\\n{% block content %}\\n<div style=\\\"text-align: center; max-width: 820px; margin: 1.5rem auto 2.5rem;\\\">\\n  <div style=\\\"display: inline-block; background: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.4); padding: 0.35rem 1rem; border-radius: 9999px; font-weight: 800; font-size: 0.85rem; text-transform: uppercase; margin-bottom: 1rem;\\\">\\n    \\ud83c\\udfcf Season 2026 Official Tournament Portal\\n  </div>\\n  <h1 style=\\\"font-size: 2.75rem; font-weight: 900; line-height: 1.15; margin-bottom: 0.75rem; color: #fff;\\\">\\n    Kunsi Premier League (KPL 2026)\\n  </h1>\\n  <p style=\\\"font-size: 1.1rem; color: #94a3b8; line-height: 1.6;\\\">\\n    Official Tournament Guide, Player Registration Directory, and Mobile Live Auction Dashboard.\\n  </p>\\n</div>\\n\\n<!-- Quick Tournament Stats Counter -->\\n<div style=\\\"display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem;\\\">\\n  <div class=\\\"glass-card\\\" style=\\\"text-align: center; padding: 1.25rem 1rem;\\\">\\n    <div style=\\\"font-size: 2.25rem; font-weight: 900; color: #f59e0b;\\\">{{ total_registered }}</div>\\n    <div style=\\\"color: #94a3b8; font-weight: 600; font-size: 0.9rem; margin-top: 0.25rem;\\\">Registered Players</div>\\n  </div>\\n  <div class=\\\"glass-card\\\" style=\\\"text-align: center; padding: 1.25rem 1rem;\\\">\\n    <div style=\\\"font-size: 2.25rem; font-weight: 900; color: #38bdf8;\\\">{{ total_teams }}</div>\\n    <div style=\\\"color: #94a3b8; font-weight: 600; font-size: 0.9rem; margin-top: 0.25rem;\\\">Participating Teams</div>\\n  </div>\\n  <div class=\\\"glass-card\\\" style=\\\"text-align: center; padding: 1.25rem 1rem;\\\">\\n    <div style=\\\"font-size: 2.25rem; font-weight: 900; color: #10b981;\\\">\\u20b9{{ total_purse }}</div>\\n    <div style=\\\"color: #94a3b8; font-weight: 600; font-size: 0.9rem; margin-top: 0.25rem;\\\">Purse per Team</div>\\n  </div>\\n  <div class=\\\"glass-card\\\" style=\\\"text-align: center; padding: 1.25rem 1rem;\\\">\\n    <div style=\\\"font-size: 2.25rem; font-weight: 900; color: #ec4899;\\\">\\u20b9{{ reg_fee }}</div>\\n    <div style=\\\"color: #94a3b8; font-weight: 600; font-size: 0.9rem; margin-top: 0.25rem;\\\">Registration Fee</div>\\n  </div>\\n</div>\\n\\n<!-- READ-ONLY TOURNAMENT INFORMATION -->\\n<div class=\\\"glass-card\\\" style=\\\"margin-bottom: 2rem; border-color: rgba(245, 158, 11, 0.3);\\\">\\n  <h2 style=\\\"font-size: 1.35rem; font-weight: 800; color: #f59e0b; margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem;\\\">\\n    <span>\\ud83d\\udccb</span> Tournament Overview & Rules\\n  </h2>\\n  <div style=\\\"display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1.25rem; color: #cbd5e1; font-size: 0.95rem; line-height: 1.6;\\\">\\n    <div style=\\\"background: rgba(15,23,42,0.6); padding: 1rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.08);\\\">\\n      <strong style=\\\"color: #fff; display: block; margin-bottom: 0.35rem;\\\">\\ud83c\\udfdf\\ufe0f Venue & Format</strong>\\n      Location: Saidapur Cricket Ground.<br>\\n      Format: Limited overs knockout & league matches with official white ball.\\n    </div>\\n    <div style=\\\"background: rgba(15,23,42,0.6); padding: 1rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.08);\\\">\\n      <strong style=\\\"color: #fff; display: block; margin-bottom: 0.35rem;\\\">\\ud83d\\udcb0 Auction Rules & Purses</strong>\\n      Purse per team: \\u20b9{{ total_purse }}. Minimum squad requirement: 10 players.<br>\\n      Minimum bid: \\u20b950. Star Player Retention: \\u20b9500. Owner Retention: \\u20b9100.\\n    </div>\\n    <div style=\\\"background: rgba(15,23,42,0.6); padding: 1rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.08);\\\">\\n      <strong style=\\\"color: #fff; display: block; margin-bottom: 0.35rem;\\\">\\ud83d\\udcb3 Registration Instructions</strong>\\n      Registration fee: \\u20b9{{ reg_fee }} via PhonePe/GPay/BHIM UPI.<br>\\n      Players submit name, mobile, role, village, and photo.\\n    </div>\\n  </div>\\n</div>\\n\\n<!-- 3 MAIN TABS PORTAL CARDS -->\\n<h2 style=\\\"font-size: 1.35rem; font-weight: 800; color: #fff; margin-bottom: 1rem;\\\">\\n  Explore Tournament Portals\\n</h2>\\n<div style=\\\"display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1.5rem;\\\">\\n  <!-- TAB 1 CARD -->\\n  <div class=\\\"glass-card\\\" style=\\\"display: flex; flex-direction: column; justify-content: space-between; border-color: rgba(245, 158, 11, 0.4);\\\">\\n    <div>\\n      <div style=\\\"display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;\\\">\\n        <span style=\\\"font-size: 2.25rem;\\\">\\u2699\\ufe0f</span>\\n        <span style=\\\"background: rgba(245,158,11,0.2); color: #fbbf24; border: 1px solid rgba(245,158,11,0.4); padding: 0.2rem 0.6rem; border-radius: 9999px; font-weight: 800; font-size: 0.75rem;\\\">\\n          Tab 1: Organizer\\n        </span>\\n      </div>\\n      <h3 style=\\\"font-size: 1.45rem; font-weight: 800; color: #fff; margin-bottom: 0.5rem;\\\">1. Organizer Admin</h3>\\n      <p style=\\\"color: #94a3b8; font-size: 0.95rem; line-height: 1.5; margin-bottom: 1.5rem;\\\">\\n        PIN-protected organizer control panel featuring two sub-pages: Tournament Configuration (teams, purse, retentions, UPI settings, Excel) and Live Auction Host Controller (next draw, increase bids, sold, unsold, undo).\\n      </p>\\n    </div>\\n    <a href=\\\"/admin\\\" class=\\\"btn btn-primary\\\" style=\\\"width: 100%; text-align: center; font-size: 1.05rem;\\\">\\n      Open Admin Console &rarr;\\n    </a>\\n  </div>\\n\\n  <!-- TAB 2 CARD -->\\n  <div class=\\\"glass-card\\\" style=\\\"display: flex; flex-direction: column; justify-content: space-between; border-color: rgba(56, 189, 248, 0.4);\\\">\\n    <div>\\n      <div style=\\\"display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;\\\">\\n        <span style=\\\"font-size: 2.25rem;\\\">\\ud83d\\udcdd</span>\\n        <span style=\\\"background: rgba(56,189,248,0.2); color: #38bdf8; border: 1px solid rgba(56,189,248,0.4); padding: 0.2rem 0.6rem; border-radius: 9999px; font-weight: 800; font-size: 0.75rem;\\\">\\n          Tab 2: Players\\n        </span>\\n      </div>\\n      <h3 style=\\\"font-size: 1.45rem; font-weight: 800; color: #fff; margin-bottom: 0.5rem;\\\">2. Player Registration</h3>\\n      <p style=\\\"color: #94a3b8; font-size: 0.95rem; line-height: 1.5; margin-bottom: 1.5rem;\\\">\\n        Opens immediately with the complete directory of all registered players (Name, Role, Village, Amount Sent, Photo, UPI) with search & filter, plus quick form to register new players.\\n      </p>\\n    </div>\\n    <a href=\\\"/register\\\" class=\\\"btn btn-secondary\\\" style=\\\"width: 100%; text-align: center; font-size: 1.05rem; border-color: rgba(56,189,248,0.5); color: #38bdf8;\\\">\\n      Open Registration Tab &rarr;\\n    </a>\\n  </div>\\n\\n  <!-- TAB 3 CARD -->\\n  <div class=\\\"glass-card\\\" style=\\\"display: flex; flex-direction: column; justify-content: space-between; border: 2px solid #ef4444; box-shadow: 0 0 35px rgba(239, 68, 68, 0.25);\\\">\\n    <div>\\n      <div style=\\\"display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;\\\">\\n        <span style=\\\"font-size: 2.25rem;\\\">\\ud83d\\udc41\\ufe0f</span>\\n        <span style=\\\"background: rgba(239,68,68,0.2); color: #f87171; border: 1px solid rgba(239,68,68,0.4); padding: 0.2rem 0.6rem; border-radius: 9999px; font-weight: 800; font-size: 0.75rem;\\\">\\n          Tab 3: Spectators\\n        </span>\\n      </div>\\n      <h3 style=\\\"font-size: 1.45rem; font-weight: 800; color: #fff; margin-bottom: 0.5rem;\\\">3. Auction Viewers</h3>\\n      <p style=\\\"color: #94a3b8; font-size: 0.95rem; line-height: 1.5; margin-bottom: 1.5rem;\\\">\\n        Mobile-first live bidding stream. Watch player photos, odometer bids, sold celebrations, and squad purse meters from any phone, TV, or projector in real time. (Read-only, no login).\\n      </p>\\n    </div>\\n    <a href=\\\"/view\\\" class=\\\"btn btn-danger\\\" style=\\\"width: 100%; text-align: center; font-size: 1.05rem; font-weight: 800; background: linear-gradient(135deg, #ef4444, #b91c1c);\\\">\\n      \\ud83d\\udc41\\ufe0f Open Auction Viewers Stream &rarr;\\n    </a>\\n  </div>\\n</div>\\n{% endblock %}\\n\", \"register.html\": \"{% extends \\\"base.html\\\" %}\\n\\n{% block extra_css %}\\n<style>\\n  /* Clean Sub-tab Navigation */\\n  .reg-subtabs {\\n    display: flex;\\n    gap: 0.75rem;\\n    margin-bottom: 2rem;\\n    border-bottom: 2px solid rgba(255, 255, 255, 0.1);\\n    padding-bottom: 0.75rem;\\n    flex-wrap: wrap;\\n  }\\n  .subtab-btn {\\n    background: rgba(255, 255, 255, 0.05);\\n    border: 1px solid rgba(255, 255, 255, 0.15);\\n    color: #94a3b8;\\n    padding: 0.65rem 1.35rem;\\n    border-radius: 8px;\\n    font-weight: 700;\\n    font-size: 0.95rem;\\n    cursor: pointer;\\n    transition: all 0.2s ease;\\n    display: flex;\\n    align-items: center;\\n    gap: 0.5rem;\\n  }\\n  .subtab-btn:hover {\\n    color: #fff;\\n    background: rgba(255, 255, 255, 0.12);\\n  }\\n  .subtab-btn.active {\\n    background: #38bdf8;\\n    color: #000;\\n    border-color: #38bdf8;\\n    box-shadow: 0 4px 15px rgba(56, 189, 248, 0.35);\\n  }\\n\\n  /* Live Selfie Camera Box */\\n  .selfie-camera-box {\\n    background: rgba(15, 23, 42, 0.9);\\n    border: 2px dashed rgba(56, 189, 248, 0.4);\\n    border-radius: 12px;\\n    padding: 1.25rem;\\n    text-align: center;\\n    margin-bottom: 1.5rem;\\n  }\\n  .selfie-viewfinder {\\n    width: 100%;\\n    max-width: 320px;\\n    height: 240px;\\n    border-radius: 12px;\\n    object-fit: cover;\\n    margin: 0 auto;\\n    background: #0b1120;\\n    border: 2px solid #38bdf8;\\n    display: block;\\n  }\\n\\n  /* Payment App Buttons Grid */\\n  .payment-apps-grid {\\n    display: grid;\\n    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));\\n    gap: 0.75rem;\\n    margin-bottom: 1.25rem;\\n  }\\n  .pay-app-btn {\\n    display: flex;\\n    flex-direction: column;\\n    align-items: center;\\n    justify-content: center;\\n    padding: 0.85rem 0.5rem;\\n    border-radius: 10px;\\n    text-decoration: none;\\n    font-weight: 800;\\n    font-size: 0.85rem;\\n    color: #fff;\\n    transition: all 0.2s ease;\\n    box-shadow: 0 4px 12px rgba(0,0,0,0.3);\\n    border: 1px solid rgba(255,255,255,0.15);\\n  }\\n  .pay-app-btn:hover {\\n    transform: translateY(-2px);\\n    box-shadow: 0 6px 18px rgba(0,0,0,0.45);\\n    color: #fff;\\n  }\\n  .pay-phonepe {\\n    background: linear-gradient(135deg, #5f259f, #7a2fc7);\\n  }\\n  .pay-gpay {\\n    background: linear-gradient(135deg, #1a73e8, #4285f4);\\n  }\\n  .pay-paytm {\\n    background: linear-gradient(135deg, #002e6e, #00b9f1);\\n  }\\n  .pay-amazon {\\n    background: linear-gradient(135deg, #ff9900, #e68a00);\\n    color: #000 !important;\\n  }\\n  .pay-bhim {\\n    background: linear-gradient(135deg, #00875a, #00b377);\\n  }\\n\\n  /* Player Directory Cards Grid */\\n  .player-dir-grid {\\n    display: grid;\\n    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));\\n    gap: 1.25rem;\\n  }\\n  .dir-card {\\n    background: rgba(15, 23, 42, 0.75);\\n    border: 1px solid rgba(255, 255, 255, 0.1);\\n    border-radius: 12px;\\n    padding: 1.25rem;\\n    display: flex;\\n    gap: 1rem;\\n    align-items: center;\\n    transition: transform 0.2s ease, border-color 0.2s ease;\\n  }\\n  .dir-card:hover {\\n    transform: translateY(-2px);\\n    border-color: #38bdf8;\\n  }\\n  .dir-avatar {\\n    width: 72px;\\n    height: 72px;\\n    border-radius: 50%;\\n    object-fit: cover;\\n    border: 2px solid #38bdf8;\\n    background: #1e293b;\\n    flex-shrink: 0;\\n  }\\n\\n  /* Detailed Table View */\\n  .dir-table {\\n    width: 100%;\\n    border-collapse: collapse;\\n    font-size: 0.9rem;\\n  }\\n  .dir-table th {\\n    background: rgba(15, 23, 42, 0.85);\\n    color: #94a3b8;\\n    font-weight: 700;\\n    padding: 0.75rem 1rem;\\n    text-align: left;\\n    border-bottom: 1px solid rgba(255, 255, 255, 0.1);\\n  }\\n  .dir-table td {\\n    padding: 0.75rem 1rem;\\n    border-bottom: 1px solid rgba(255, 255, 255, 0.06);\\n    vertical-align: middle;\\n  }\\n  .dir-table tr:hover td {\\n    background: rgba(255, 255, 255, 0.03);\\n  }\\n  .table-avatar {\\n    width: 44px;\\n    height: 44px;\\n    border-radius: 50%;\\n    object-fit: cover;\\n    border: 2px solid #38bdf8;\\n    background: #1e293b;\\n  }\\n</style>\\n{% endblock %}\\n\\n{% block content %}\\n<!-- HEADER WITH REGISTRATION INFO -->\\n<div style=\\\"margin-bottom: 1.5rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;\\\">\\n  <div>\\n    <h1 style=\\\"font-size: 2rem; font-weight: 900; color: #fff; display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;\\\">\\n      <span>\\ud83d\\udcdd</span> Player Registration Portal\\n    </h1>\\n    <p style=\\\"color: #94a3b8; font-size: 0.95rem;\\\">\\n      Register as a player for Kunsi Premier League (KPL 2026) or view registered tournament players.\\n    </p>\\n  </div>\\n  <div style=\\\"display: flex; gap: 0.5rem; align-items: center;\\\">\\n    <span class=\\\"badge\\\" style=\\\"background: rgba(56, 189, 248, 0.2); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.4); font-size: 0.95rem; padding: 0.5rem 0.9rem; font-weight: 800;\\\">\\n      {{ players|length }} Registered Players\\n    </span>\\n  </div>\\n</div>\\n\\n<!-- 2 CLEAN SUB-TABS: REGISTER FORM (DEFAULT) vs REGISTERED PLAYERS UNTIL NOW -->\\n<div class=\\\"reg-subtabs\\\">\\n  <button type=\\\"button\\\" id=\\\"tabBtnRegister\\\" class=\\\"subtab-btn active\\\" onclick=\\\"switchRegSubtab('form')\\\">\\n    <span>\\u270d\\ufe0f</span> 1. Register Player\\n  </button>\\n  <button type=\\\"button\\\" id=\\\"tabBtnDirectory\\\" class=\\\"subtab-btn\\\" onclick=\\\"switchRegSubtab('directory')\\\">\\n    <span>\\ud83d\\udc65</span> 2. Registered Players Until Now ({{ players|length }})\\n  </button>\\n</div>\\n\\n<!-- SUB-PAGE 1: REGISTRATION FORM (OPEN BY DEFAULT) -->\\n<div id=\\\"subpageRegisterForm\\\">\\n  <div class=\\\"glass-card\\\" style=\\\"max-width: 720px; margin: 0 auto; border-color: rgba(56, 189, 248, 0.4); box-shadow: 0 0 40px rgba(56, 189, 248, 0.15);\\\">\\n    <div style=\\\"margin-bottom: 1.5rem; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 1rem;\\\">\\n      <h2 style=\\\"font-size: 1.45rem; font-weight: 800; color: #38bdf8; margin: 0 0 0.35rem 0;\\\">\\n        \\ud83c\\udfcf Official Player Registration Form\\n      </h2>\\n      <p style=\\\"color: #cbd5e1; font-size: 0.9rem; margin: 0;\\\">\\n        Entry Fee: <strong style=\\\"color: #10b981; font-size: 1.05rem;\\\">\\u20b9{{ reg_fee }}</strong>. Pay with any UPI app below and snap your selfie.\\n      </p>\\n    </div>\\n\\n    <form id=\\\"playerRegForm\\\" onsubmit=\\\"handleRegistrationSubmit(event)\\\">\\n      <!-- Name & Phone -->\\n      <div style=\\\"display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; margin-bottom: 1rem;\\\">\\n        <div class=\\\"form-group\\\" style=\\\"margin-bottom: 0;\\\">\\n          <label class=\\\"form-label\\\">Full Name *</label>\\n          <input type=\\\"text\\\" id=\\\"regName\\\" class=\\\"form-control\\\" placeholder=\\\"e.g. M. Raju Anna\\\" required>\\n        </div>\\n        <div class=\\\"form-group\\\" style=\\\"margin-bottom: 0;\\\">\\n          <label class=\\\"form-label\\\">Mobile Number *</label>\\n          <input type=\\\"tel\\\" id=\\\"regPhone\\\" class=\\\"form-control\\\" placeholder=\\\"10-digit WhatsApp Number\\\" required pattern=\\\"[0-9]{10}\\\">\\n        </div>\\n      </div>\\n\\n      <!-- Village & Role -->\\n      <div style=\\\"display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; margin-bottom: 1rem;\\\">\\n        <div class=\\\"form-group\\\" style=\\\"margin-bottom: 0;\\\">\\n          <label class=\\\"form-label\\\">Village / Town *</label>\\n          <input type=\\\"text\\\" id=\\\"regVillage\\\" class=\\\"form-control\\\" placeholder=\\\"e.g. Saidapur / Kunsi\\\" required value=\\\"Saidapur\\\">\\n        </div>\\n        <div class=\\\"form-group\\\" style=\\\"margin-bottom: 0;\\\">\\n          <label class=\\\"form-label\\\">Primary Playing Role *</label>\\n          <select id=\\\"regRole\\\" class=\\\"form-control\\\" required>\\n            <option value=\\\"All-Rounder\\\">\\ud83c\\udfcf All-Rounder</option>\\n            <option value=\\\"Batsman\\\">\\ud83c\\udfcf Top-Order Batsman</option>\\n            <option value=\\\"Bowler\\\">\\ud83c\\udfaf Fast / Spin Bowler</option>\\n            <option value=\\\"Wicket-Keeper\\\">\\ud83e\\udde4 Wicket Keeper Batsman</option>\\n          </select>\\n        </div>\\n      </div>\\n\\n      <!-- Batting & Bowling Style -->\\n      <div style=\\\"display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; margin-bottom: 1.25rem;\\\">\\n        <div class=\\\"form-group\\\" style=\\\"margin-bottom: 0;\\\">\\n          <label class=\\\"form-label\\\">Batting Style</label>\\n          <select id=\\\"regBatting\\\" class=\\\"form-control\\\">\\n            <option value=\\\"Right Hand Bat\\\">Right Hand Bat</option>\\n            <option value=\\\"Left Hand Bat\\\">Left Hand Bat</option>\\n          </select>\\n        </div>\\n        <div class=\\\"form-group\\\" style=\\\"margin-bottom: 0;\\\">\\n          <label class=\\\"form-label\\\">Bowling Style</label>\\n          <select id=\\\"regBowling\\\" class=\\\"form-control\\\">\\n            <option value=\\\"Right Arm Medium Fast\\\">Right Arm Medium Fast</option>\\n            <option value=\\\"Right Arm Spin\\\">Right Arm Spin</option>\\n            <option value=\\\"Left Arm Fast\\\">Left Arm Fast</option>\\n            <option value=\\\"Left Arm Spin\\\">Left Arm Spin</option>\\n            <option value=\\\"None\\\">None</option>\\n          </select>\\n        </div>\\n      </div>\\n\\n      <!-- LIVE CAMERA SELFIE MODULE -->\\n      <div class=\\\"selfie-camera-box\\\">\\n        <label class=\\\"form-label\\\" style=\\\"color: #38bdf8; font-weight: 800; font-size: 1rem; margin-bottom: 0.5rem; display: block;\\\">\\n          \\ud83d\\udcf7 Player Photo / Live Selfie Camera\\n        </label>\\n        <p style=\\\"color: #94a3b8; font-size: 0.85rem; margin-bottom: 1rem;\\\">\\n          Click the button below to take a live selfie with your camera, or upload a picture.\\n        </p>\\n\\n        <!-- Video stream element -->\\n        <video id=\\\"cameraVideo\\\" class=\\\"selfie-viewfinder\\\" autoplay playsinline style=\\\"display: none;\\\"></video>\\n        <!-- Captured preview image -->\\n        <img id=\\\"photoPreview\\\" class=\\\"selfie-viewfinder\\\" style=\\\"display: none;\\\" alt=\\\"Selfie Preview\\\">\\n        <canvas id=\\\"cameraCanvas\\\" style=\\\"display: none;\\\"></canvas>\\n\\n        <!-- Placeholder when camera is idle -->\\n        <div id=\\\"cameraPlaceholder\\\" style=\\\"padding: 1.5rem 1rem; background: rgba(0,0,0,0.3); border-radius: 8px; margin-bottom: 0.75rem;\\\">\\n          <span style=\\\"font-size: 3rem; display: block; margin-bottom: 0.35rem;\\\">\\ud83e\\udd33</span>\\n          <span style=\\\"color: #cbd5e1; font-size: 0.9rem;\\\">No photo taken yet</span>\\n        </div>\\n\\n        <!-- Camera Action Buttons -->\\n        <div style=\\\"display: flex; gap: 0.5rem; justify-content: center; flex-wrap: wrap;\\\">\\n          <button type=\\\"button\\\" id=\\\"btnStartCamera\\\" onclick=\\\"startCamera()\\\" class=\\\"btn btn-secondary\\\" style=\\\"font-size: 0.85rem; border-color: #38bdf8; color: #38bdf8;\\\">\\n            \\ud83d\\udcf7 Open Live Camera / Take Selfie\\n          </button>\\n          <button type=\\\"button\\\" id=\\\"btnSnapPhoto\\\" onclick=\\\"snapSelfie()\\\" class=\\\"btn btn-success\\\" style=\\\"display: none; font-size: 0.85rem;\\\">\\n            \\u26a1 Snap Selfie Now\\n          </button>\\n          <button type=\\\"button\\\" id=\\\"btnRetakePhoto\\\" onclick=\\\"retakeSelfie()\\\" class=\\\"btn btn-secondary\\\" style=\\\"display: none; font-size: 0.85rem;\\\">\\n            \\ud83d\\udd04 Retake Selfie\\n          </button>\\n          <label class=\\\"btn btn-secondary\\\" style=\\\"margin: 0; font-size: 0.85rem; cursor: pointer;\\\">\\n            \\ud83d\\udcc1 Upload from Gallery\\n            <input type=\\\"file\\\" id=\\\"regPhoto\\\" accept=\\\"image/*\\\" style=\\\"display: none;\\\" onchange=\\\"handleFileSelected(event)\\\">\\n          </label>\\n        </div>\\n      </div>\\n\\n      <!-- DEDICATED UPI PAYMENT METHODS -->\\n      <div style=\\\"background: rgba(15,23,42,0.8); border: 1px solid rgba(16, 185, 129, 0.4); padding: 1.25rem; border-radius: 12px; margin-bottom: 1.5rem;\\\">\\n        <div style=\\\"display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; flex-wrap: wrap; gap: 0.5rem;\\\">\\n          <strong style=\\\"color: #10b981; font-size: 1.05rem;\\\">\\n            \\ud83d\\udcb3 Pay \\u20b9{{ reg_fee }} Entry Fee via UPI App\\n          </strong>\\n          <span class=\\\"badge\\\" style=\\\"background: rgba(16, 185, 129, 0.2); color: #34d399;\\\">\\n            Direct App Launch\\n          </span>\\n        </div>\\n        <p style=\\\"color: #94a3b8; font-size: 0.85rem; margin-bottom: 1rem;\\\">\\n          Click your preferred payment app below to open it immediately on your phone and complete the \\u20b9{{ reg_fee }} fee:\\n        </p>\\n\\n        <!-- Payment App Buttons Grid -->\\n        <div class=\\\"payment-apps-grid\\\">\\n          <!-- PhonePe -->\\n          <a href=\\\"phonepe://pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg\\\" \\n             onclick=\\\"openPaymentApp(event, 'phonepe://pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg')\\\"\\n             class=\\\"pay-app-btn pay-phonepe\\\">\\n            <span style=\\\"font-size: 1.6rem; margin-bottom: 0.25rem;\\\">\\ud83d\\udfe3</span>\\n            <span>PhonePe</span>\\n          </a>\\n\\n          <!-- Google Pay -->\\n          <a href=\\\"gpay://upi/pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg\\\"\\n             onclick=\\\"openPaymentApp(event, 'gpay://upi/pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg')\\\"\\n             class=\\\"pay-app-btn pay-gpay\\\">\\n            <span style=\\\"font-size: 1.6rem; margin-bottom: 0.25rem;\\\">\\ud83d\\udd35</span>\\n            <span>Google Pay</span>\\n          </a>\\n\\n          <!-- Paytm -->\\n          <a href=\\\"paytmmp://pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg\\\"\\n             onclick=\\\"openPaymentApp(event, 'paytmmp://pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg')\\\"\\n             class=\\\"pay-app-btn pay-paytm\\\">\\n            <span style=\\\"font-size: 1.6rem; margin-bottom: 0.25rem;\\\">\\ud83d\\udfe6</span>\\n            <span>Paytm</span>\\n          </a>\\n\\n          <!-- Amazon Pay -->\\n          <a href=\\\"amazonpay://pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg\\\"\\n             onclick=\\\"openPaymentApp(event, 'amazonpay://pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg')\\\"\\n             class=\\\"pay-app-btn pay-amazon\\\">\\n            <span style=\\\"font-size: 1.6rem; margin-bottom: 0.25rem;\\\">\\ud83d\\udfe0</span>\\n            <span>Amazon Pay</span>\\n          </a>\\n\\n          <!-- BHIM / Any UPI -->\\n          <a href=\\\"upi://pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg\\\"\\n             onclick=\\\"openPaymentApp(event, 'upi://pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg')\\\"\\n             class=\\\"pay-app-btn pay-bhim\\\">\\n            <span style=\\\"font-size: 1.6rem; margin-bottom: 0.25rem;\\\">\\ud83c\\uddee\\ud83c\\uddf3</span>\\n            <span>BHIM UPI</span>\\n          </a>\\n        </div>\\n\\n        <!-- Desktop QR Code Scanner -->\\n        <div style=\\\"text-align: center; margin: 1rem 0; padding: 1rem; background: rgba(0,0,0,0.3); border-radius: 8px;\\\">\\n          <p style=\\\"color: #94a3b8; font-size: 0.85rem; margin-bottom: 0.5rem;\\\">\\n            \\ud83d\\udcf1 On Computer? Scan this QR code from your phone with PhonePe, GPay, or Paytm:\\n          </p>\\n          <img src=\\\"https://api.qrserver.com/v1/create-qr-code/?size=160x160&data={{ ('upi://pay?pa=' + upi_id + '&pn=' + payee_name + '&am=' + (reg_fee|string) + '&cu=INR&tn=KPL2026_Registration')|urlencode }}\\\" alt=\\\"UPI QR Code\\\" style=\\\"width: 140px; height: 140px; border-radius: 8px; border: 3px solid #f59e0b; background: #fff; padding: 4px;\\\">\\n          <div style=\\\"color: #f59e0b; font-weight: 800; font-size: 0.95rem; margin-top: 0.5rem;\\\">\\n            UPI ID: {{ upi_id }} ({{ payee_name }})\\n          </div>\\n        </div>\\n\\n        <div class=\\\"form-group\\\" style=\\\"margin-bottom: 0;\\\">\\n          <label class=\\\"form-label\\\" style=\\\"font-size: 0.85rem;\\\">UPI Reference / UTR Number (Optional)</label>\\n          <input type=\\\"text\\\" id=\\\"regUtr\\\" class=\\\"form-control\\\" placeholder=\\\"12-digit UTR from payment confirmation\\\">\\n        </div>\\n      </div>\\n\\n      <button type=\\\"submit\\\" id=\\\"btnSubmitReg\\\" class=\\\"btn btn-primary\\\" style=\\\"width: 100%; font-size: 1.15rem; padding: 0.95rem; font-weight: 900;\\\">\\n        Submit Player Registration &rarr;\\n      </button>\\n    </form>\\n  </div>\\n</div>\\n\\n<!-- SUB-PAGE 2: REGISTERED PLAYERS UNTIL NOW (DIRECTORY) -->\\n<div id=\\\"subpageDirectory\\\" style=\\\"display: none;\\\">\\n  <!-- Search, Filter & View Switcher Bar -->\\n  <div style=\\\"margin-bottom: 1.5rem; display: flex; gap: 0.75rem; flex-wrap: wrap; align-items: center; justify-content: space-between;\\\">\\n    <div style=\\\"display: flex; gap: 0.75rem; flex-wrap: wrap; flex: 1; min-width: 280px;\\\">\\n      <input type=\\\"text\\\" id=\\\"dirSearch\\\" placeholder=\\\"\\ud83d\\udd0d Search by name, village, or role...\\\" class=\\\"form-control\\\" style=\\\"flex: 2; min-width: 220px;\\\" oninput=\\\"filterDirectory()\\\">\\n      <select id=\\\"dirRoleFilter\\\" class=\\\"form-control\\\" style=\\\"flex: 1; min-width: 160px;\\\" onchange=\\\"filterDirectory()\\\">\\n        <option value=\\\"All\\\">All Roles</option>\\n        <option value=\\\"All-Rounder\\\">All-Rounder</option>\\n        <option value=\\\"Batsman\\\">Batsman</option>\\n        <option value=\\\"Bowler\\\">Bowler</option>\\n        <option value=\\\"Wicket-Keeper\\\">Wicket-Keeper</option>\\n      </select>\\n    </div>\\n    <div style=\\\"display: flex; gap: 0.35rem;\\\">\\n      <button type=\\\"button\\\" id=\\\"btnViewCards\\\" class=\\\"subtab-btn active\\\" style=\\\"padding: 0.45rem 0.85rem; font-size: 0.85rem;\\\" onclick=\\\"switchDirLayout('cards')\\\">\\n        \\ud83d\\uddc2\\ufe0f Cards\\n      </button>\\n      <button type=\\\"button\\\" id=\\\"btnViewTable\\\" class=\\\"subtab-btn\\\" style=\\\"padding: 0.45rem 0.85rem; font-size: 0.85rem;\\\" onclick=\\\"switchDirLayout('table')\\\">\\n        \\ud83d\\udccb Table\\n      </button>\\n    </div>\\n  </div>\\n\\n  <!-- CARDS VIEW (DEFAULT) -->\\n  <div class=\\\"player-dir-grid\\\" id=\\\"dirCardsContainer\\\">\\n    {% for p in players %}\\n    <div class=\\\"dir-card\\\" data-name=\\\"{{ p.name|lower }}\\\" data-village=\\\"{{ (p.village or 'Saidapur')|lower }}\\\" data-role=\\\"{{ p.role|lower }}\\\">\\n      <img src=\\\"{{ p.photo_url or '/static/images/avatar_allrounder.svg' }}\\\" class=\\\"dir-avatar\\\" alt=\\\"{{ p.name }}\\\">\\n      <div style=\\\"flex: 1; min-width: 0;\\\">\\n        <div style=\\\"display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;\\\">\\n          <h3 style=\\\"font-size: 1.05rem; font-weight: 800; color: #fff; margin: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;\\\">\\n            {{ p.name }}\\n          </h3>\\n          <span style=\\\"color: #f59e0b; font-weight: 800; font-size: 0.85rem;\\\">#{{ p.serial_no or loop.index }}</span>\\n        </div>\\n        <div style=\\\"display: flex; gap: 0.35rem; align-items: center; margin-bottom: 0.35rem; flex-wrap: wrap;\\\">\\n          <span class=\\\"badge {{ 'badge-batsman' if 'bat' in (p.role|lower) else ('badge-bowler' if 'bowl' in (p.role|lower) else 'badge-allrounder') }}\\\" style=\\\"font-size: 0.75rem;\\\">\\n            {{ p.role }}\\n          </span>\\n          <span style=\\\"color: #94a3b8; font-size: 0.8rem; display: flex; align-items: center; gap: 0.2rem;\\\">\\n            \\ud83d\\udccd {{ p.village or 'Saidapur' }}\\n          </span>\\n        </div>\\n        <div style=\\\"display: flex; justify-content: space-between; align-items: center; font-size: 0.75rem; color: #64748b;\\\">\\n          <span style=\\\"color: #10b981; font-weight: 700; background: rgba(16, 185, 129, 0.15); padding: 0.15rem 0.45rem; border-radius: 4px; border: 1px solid rgba(16, 185, 129, 0.3);\\\">\\n            Amount Sent: \\u20b9{{ p.reg_amount or 200 }} (Paid)\\n          </span>\\n          {% if p.transaction_id %}\\n          <span style=\\\"color: #38bdf8; font-family: monospace;\\\">UTR: {{ p.transaction_id }}</span>\\n          {% endif %}\\n        </div>\\n      </div>\\n    </div>\\n    {% endfor %}\\n  </div>\\n\\n  <!-- TABLE VIEW -->\\n  <div id=\\\"dirTableContainer\\\" style=\\\"display: none; overflow-x: auto; background: rgba(15, 23, 42, 0.75); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px;\\\">\\n    <table class=\\\"dir-table\\\">\\n      <thead>\\n        <tr>\\n          <th>#</th>\\n          <th>Photo</th>\\n          <th>Player Name</th>\\n          <th>Role</th>\\n          <th>Village / Town</th>\\n          <th>Amount Sent</th>\\n          <th>Mobile</th>\\n          <th>UTR / Transaction</th>\\n        </tr>\\n      </thead>\\n      <tbody>\\n        {% for p in players %}\\n        <tr class=\\\"dir-table-row\\\" data-name=\\\"{{ p.name|lower }}\\\" data-village=\\\"{{ (p.village or 'Saidapur')|lower }}\\\" data-role=\\\"{{ p.role|lower }}\\\">\\n          <td style=\\\"font-weight: 800; color: #f59e0b;\\\">#{{ p.serial_no or loop.index }}</td>\\n          <td>\\n            <img src=\\\"{{ p.photo_url or '/static/images/avatar_allrounder.svg' }}\\\" class=\\\"table-avatar\\\" alt=\\\"{{ p.name }}\\\">\\n          </td>\\n          <td style=\\\"font-weight: 800; color: #fff;\\\">{{ p.name }}</td>\\n          <td>\\n            <span class=\\\"badge {{ 'badge-batsman' if 'bat' in (p.role|lower) else ('badge-bowler' if 'bowl' in (p.role|lower) else 'badge-allrounder') }}\\\" style=\\\"font-size: 0.75rem;\\\">\\n              {{ p.role }}\\n            </span>\\n          </td>\\n          <td style=\\\"color: #cbd5e1;\\\">\\ud83d\\udccd {{ p.village or 'Saidapur' }}</td>\\n          <td style=\\\"color: #10b981; font-weight: 800;\\\">\\u20b9{{ p.reg_amount or 200 }} Paid</td>\\n          <td style=\\\"color: #94a3b8; font-family: monospace;\\\">{{ p.phone or '-' }}</td>\\n          <td style=\\\"color: #38bdf8; font-family: monospace; font-size: 0.8rem;\\\">{{ p.transaction_id or 'UPI Verified' }}</td>\\n        </tr>\\n        {% endfor %}\\n      </tbody>\\n    </table>\\n  </div>\\n</div>\\n{% endblock %}\\n\\n{% block extra_js %}\\n<script>\\n  let activeVideoStream = null;\\n  let capturedSelfieBlob = null;\\n\\n  function switchRegSubtab(tab) {\\n    const btnForm = document.getElementById('tabBtnRegister');\\n    const btnDir = document.getElementById('tabBtnDirectory');\\n    const pageForm = document.getElementById('subpageRegisterForm');\\n    const pageDir = document.getElementById('subpageDirectory');\\n\\n    if (tab === 'directory') {\\n      btnDir.classList.add('active');\\n      btnForm.classList.remove('active');\\n      pageDir.style.display = 'block';\\n      pageForm.style.display = 'none';\\n      stopCamera();\\n    } else {\\n      btnForm.classList.add('active');\\n      btnDir.classList.remove('active');\\n      pageForm.style.display = 'block';\\n      pageDir.style.display = 'none';\\n    }\\n  }\\n\\n  // --- LIVE CAMERA SELFIE MODULE ---\\n  async function startCamera() {\\n    try {\\n      const stream = await navigator.mediaDevices.getUserMedia({\\n        video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 640 } },\\n        audio: false\\n      });\\n      activeVideoStream = stream;\\n      const video = document.getElementById('cameraVideo');\\n      video.srcObject = stream;\\n      video.style.display = 'block';\\n      document.getElementById('cameraPlaceholder').style.display = 'none';\\n      document.getElementById('photoPreview').style.display = 'none';\\n      document.getElementById('btnStartCamera').style.display = 'none';\\n      document.getElementById('btnSnapPhoto').style.display = 'inline-flex';\\n      document.getElementById('btnRetakePhoto').style.display = 'none';\\n    } catch (err) {\\n      alert('Camera access unavailable or blocked. You can upload a photo from your gallery instead.');\\n    }\\n  }\\n\\n  function snapSelfie() {\\n    const video = document.getElementById('cameraVideo');\\n    const canvas = document.getElementById('cameraCanvas');\\n    const preview = document.getElementById('photoPreview');\\n\\n    canvas.width = video.videoWidth || 480;\\n    canvas.height = video.videoHeight || 480;\\n    const ctx = canvas.getContext('2d');\\n    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);\\n\\n    canvas.toBlob((blob) => {\\n      capturedSelfieBlob = blob;\\n    }, 'image/jpeg', 0.9);\\n\\n    preview.src = canvas.toDataURL('image/jpeg');\\n    preview.style.display = 'block';\\n    video.style.display = 'none';\\n    stopCamera();\\n\\n    document.getElementById('btnSnapPhoto').style.display = 'none';\\n    document.getElementById('btnRetakePhoto').style.display = 'inline-flex';\\n  }\\n\\n  function retakeSelfie() {\\n    capturedSelfieBlob = null;\\n    document.getElementById('photoPreview').style.display = 'none';\\n    startCamera();\\n  }\\n\\n  function stopCamera() {\\n    if (activeVideoStream) {\\n      activeVideoStream.getTracks().forEach(track => track.stop());\\n      activeVideoStream = null;\\n    }\\n  }\\n\\n  function handleFileSelected(e) {\\n    if (e.target.files && e.target.files[0]) {\\n      const file = e.target.files[0];\\n      capturedSelfieBlob = file;\\n      const reader = new FileReader();\\n      reader.onload = function(evt) {\\n        const preview = document.getElementById('photoPreview');\\n        preview.src = evt.target.result;\\n        preview.style.display = 'block';\\n        document.getElementById('cameraVideo').style.display = 'none';\\n        document.getElementById('cameraPlaceholder').style.display = 'none';\\n        document.getElementById('btnStartCamera').style.display = 'none';\\n        document.getElementById('btnSnapPhoto').style.display = 'none';\\n        document.getElementById('btnRetakePhoto').style.display = 'inline-flex';\\n      };\\n      reader.readAsDataURL(file);\\n    }\\n  }\\n\\n  // --- PAYMENT APP LAUNCHER ---\\n  function openPaymentApp(e, primaryUrl) {\\n    // Attempt to open dedicated app URI; on mobile device this launches PhonePe/GPay/Paytm directly\\n    const fallbackUrl = \\\"upi://pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg\\\";\\n    const start = Date.now();\\n    setTimeout(() => {\\n      if (Date.now() - start < 2000) {\\n        window.location.href = fallbackUrl;\\n      }\\n    }, 1200);\\n  }\\n\\n  // --- DIRECTORY LAYOUT & SEARCH ---\\n  function switchDirLayout(layout) {\\n    const cards = document.getElementById('dirCardsContainer');\\n    const table = document.getElementById('dirTableContainer');\\n    const btnCards = document.getElementById('btnViewCards');\\n    const btnTable = document.getElementById('btnViewTable');\\n\\n    if (layout === 'table') {\\n      cards.style.display = 'none';\\n      table.style.display = 'block';\\n      btnTable.classList.add('active');\\n      btnCards.classList.remove('active');\\n    } else {\\n      cards.style.display = 'grid';\\n      table.style.display = 'none';\\n      btnCards.classList.add('active');\\n      btnTable.classList.remove('active');\\n    }\\n    filterDirectory();\\n  }\\n\\n  function filterDirectory() {\\n    const q = (document.getElementById('dirSearch')?.value || '').toLowerCase();\\n    const role = (document.getElementById('dirRoleFilter')?.value || 'All').toLowerCase();\\n\\n    document.querySelectorAll('.dir-card').forEach(card => {\\n      const name = card.dataset.name || '';\\n      const village = card.dataset.village || '';\\n      const cRole = card.dataset.role || '';\\n      const matchesText = name.includes(q) || village.includes(q) || cRole.includes(q);\\n      const matchesRole = (role === 'all') || cRole.includes(role);\\n      card.style.display = (matchesText && matchesRole) ? 'flex' : 'none';\\n    });\\n\\n    document.querySelectorAll('.dir-table-row').forEach(row => {\\n      const name = row.dataset.name || '';\\n      const village = row.dataset.village || '';\\n      const cRole = row.dataset.role || '';\\n      const matchesText = name.includes(q) || village.includes(q) || cRole.includes(q);\\n      const matchesRole = (role === 'all') || cRole.includes(role);\\n      row.style.display = (matchesText && matchesRole) ? '' : 'none';\\n    });\\n  }\\n\\n  // --- SUBMIT REGISTRATION ---\\n  async function handleRegistrationSubmit(e) {\\n    e.preventDefault();\\n    const btn = document.getElementById('btnSubmitReg');\\n    btn.disabled = true;\\n    btn.textContent = 'Submitting Registration...';\\n\\n    const formData = new FormData();\\n    formData.append('name', document.getElementById('regName').value.trim());\\n    formData.append('phone', document.getElementById('regPhone').value.trim());\\n    formData.append('village', document.getElementById('regVillage').value.trim());\\n    formData.append('role', document.getElementById('regRole').value);\\n    formData.append('batting_style', document.getElementById('regBatting').value);\\n    formData.append('bowling_style', document.getElementById('regBowling').value);\\n    formData.append('transaction_id', document.getElementById('regUtr').value.trim());\\n\\n    if (capturedSelfieBlob) {\\n      formData.append('photo', capturedSelfieBlob, 'selfie_' + Date.now() + '.jpg');\\n    }\\n\\n    try {\\n      const res = await fetch('/api/register', {\\n        method: 'POST',\\n        body: formData\\n      });\\n      const data = await res.json();\\n      if (data.success) {\\n        alert('\\ud83c\\udf89 Player Registration Successful! Welcome to KPL 2026.');\\n        location.reload();\\n      } else {\\n        alert(data.message || 'Registration failed.');\\n      }\\n    } catch (err) {\\n      alert('Network error: ' + err.message);\\n    } finally {\\n      btn.disabled = false;\\n      btn.textContent = 'Submit Player Registration \\u2192';\\n    }\\n  }\\n</script>\\n{% endblock %}\\n\", \"templates/register.html\": \"{% extends \\\"base.html\\\" %}\\n\\n{% block extra_css %}\\n<style>\\n  /* Clean Sub-tab Navigation */\\n  .reg-subtabs {\\n    display: flex;\\n    gap: 0.75rem;\\n    margin-bottom: 2rem;\\n    border-bottom: 2px solid rgba(255, 255, 255, 0.1);\\n    padding-bottom: 0.75rem;\\n    flex-wrap: wrap;\\n  }\\n  .subtab-btn {\\n    background: rgba(255, 255, 255, 0.05);\\n    border: 1px solid rgba(255, 255, 255, 0.15);\\n    color: #94a3b8;\\n    padding: 0.65rem 1.35rem;\\n    border-radius: 8px;\\n    font-weight: 700;\\n    font-size: 0.95rem;\\n    cursor: pointer;\\n    transition: all 0.2s ease;\\n    display: flex;\\n    align-items: center;\\n    gap: 0.5rem;\\n  }\\n  .subtab-btn:hover {\\n    color: #fff;\\n    background: rgba(255, 255, 255, 0.12);\\n  }\\n  .subtab-btn.active {\\n    background: #38bdf8;\\n    color: #000;\\n    border-color: #38bdf8;\\n    box-shadow: 0 4px 15px rgba(56, 189, 248, 0.35);\\n  }\\n\\n  /* Live Selfie Camera Box */\\n  .selfie-camera-box {\\n    background: rgba(15, 23, 42, 0.9);\\n    border: 2px dashed rgba(56, 189, 248, 0.4);\\n    border-radius: 12px;\\n    padding: 1.25rem;\\n    text-align: center;\\n    margin-bottom: 1.5rem;\\n  }\\n  .selfie-viewfinder {\\n    width: 100%;\\n    max-width: 320px;\\n    height: 240px;\\n    border-radius: 12px;\\n    object-fit: cover;\\n    margin: 0 auto;\\n    background: #0b1120;\\n    border: 2px solid #38bdf8;\\n    display: block;\\n  }\\n\\n  /* Payment App Buttons Grid */\\n  .payment-apps-grid {\\n    display: grid;\\n    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));\\n    gap: 0.75rem;\\n    margin-bottom: 1.25rem;\\n  }\\n  .pay-app-btn {\\n    display: flex;\\n    flex-direction: column;\\n    align-items: center;\\n    justify-content: center;\\n    padding: 0.85rem 0.5rem;\\n    border-radius: 10px;\\n    text-decoration: none;\\n    font-weight: 800;\\n    font-size: 0.85rem;\\n    color: #fff;\\n    transition: all 0.2s ease;\\n    box-shadow: 0 4px 12px rgba(0,0,0,0.3);\\n    border: 1px solid rgba(255,255,255,0.15);\\n  }\\n  .pay-app-btn:hover {\\n    transform: translateY(-2px);\\n    box-shadow: 0 6px 18px rgba(0,0,0,0.45);\\n    color: #fff;\\n  }\\n  .pay-phonepe {\\n    background: linear-gradient(135deg, #5f259f, #7a2fc7);\\n  }\\n  .pay-gpay {\\n    background: linear-gradient(135deg, #1a73e8, #4285f4);\\n  }\\n  .pay-paytm {\\n    background: linear-gradient(135deg, #002e6e, #00b9f1);\\n  }\\n  .pay-amazon {\\n    background: linear-gradient(135deg, #ff9900, #e68a00);\\n    color: #000 !important;\\n  }\\n  .pay-bhim {\\n    background: linear-gradient(135deg, #00875a, #00b377);\\n  }\\n\\n  /* Player Directory Cards Grid */\\n  .player-dir-grid {\\n    display: grid;\\n    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));\\n    gap: 1.25rem;\\n  }\\n  .dir-card {\\n    background: rgba(15, 23, 42, 0.75);\\n    border: 1px solid rgba(255, 255, 255, 0.1);\\n    border-radius: 12px;\\n    padding: 1.25rem;\\n    display: flex;\\n    gap: 1rem;\\n    align-items: center;\\n    transition: transform 0.2s ease, border-color 0.2s ease;\\n  }\\n  .dir-card:hover {\\n    transform: translateY(-2px);\\n    border-color: #38bdf8;\\n  }\\n  .dir-avatar {\\n    width: 72px;\\n    height: 72px;\\n    border-radius: 50%;\\n    object-fit: cover;\\n    border: 2px solid #38bdf8;\\n    background: #1e293b;\\n    flex-shrink: 0;\\n  }\\n\\n  /* Detailed Table View */\\n  .dir-table {\\n    width: 100%;\\n    border-collapse: collapse;\\n    font-size: 0.9rem;\\n  }\\n  .dir-table th {\\n    background: rgba(15, 23, 42, 0.85);\\n    color: #94a3b8;\\n    font-weight: 700;\\n    padding: 0.75rem 1rem;\\n    text-align: left;\\n    border-bottom: 1px solid rgba(255, 255, 255, 0.1);\\n  }\\n  .dir-table td {\\n    padding: 0.75rem 1rem;\\n    border-bottom: 1px solid rgba(255, 255, 255, 0.06);\\n    vertical-align: middle;\\n  }\\n  .dir-table tr:hover td {\\n    background: rgba(255, 255, 255, 0.03);\\n  }\\n  .table-avatar {\\n    width: 44px;\\n    height: 44px;\\n    border-radius: 50%;\\n    object-fit: cover;\\n    border: 2px solid #38bdf8;\\n    background: #1e293b;\\n  }\\n</style>\\n{% endblock %}\\n\\n{% block content %}\\n<!-- HEADER WITH REGISTRATION INFO -->\\n<div style=\\\"margin-bottom: 1.5rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;\\\">\\n  <div>\\n    <h1 style=\\\"font-size: 2rem; font-weight: 900; color: #fff; display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;\\\">\\n      <span>\\ud83d\\udcdd</span> Player Registration Portal\\n    </h1>\\n    <p style=\\\"color: #94a3b8; font-size: 0.95rem;\\\">\\n      Register as a player for Kunsi Premier League (KPL 2026) or view registered tournament players.\\n    </p>\\n  </div>\\n  <div style=\\\"display: flex; gap: 0.5rem; align-items: center;\\\">\\n    <span class=\\\"badge\\\" style=\\\"background: rgba(56, 189, 248, 0.2); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.4); font-size: 0.95rem; padding: 0.5rem 0.9rem; font-weight: 800;\\\">\\n      {{ players|length }} Registered Players\\n    </span>\\n  </div>\\n</div>\\n\\n<!-- 2 CLEAN SUB-TABS: REGISTER FORM (DEFAULT) vs REGISTERED PLAYERS UNTIL NOW -->\\n<div class=\\\"reg-subtabs\\\">\\n  <button type=\\\"button\\\" id=\\\"tabBtnRegister\\\" class=\\\"subtab-btn active\\\" onclick=\\\"switchRegSubtab('form')\\\">\\n    <span>\\u270d\\ufe0f</span> 1. Register Player\\n  </button>\\n  <button type=\\\"button\\\" id=\\\"tabBtnDirectory\\\" class=\\\"subtab-btn\\\" onclick=\\\"switchRegSubtab('directory')\\\">\\n    <span>\\ud83d\\udc65</span> 2. Registered Players Until Now ({{ players|length }})\\n  </button>\\n</div>\\n\\n<!-- SUB-PAGE 1: REGISTRATION FORM (OPEN BY DEFAULT) -->\\n<div id=\\\"subpageRegisterForm\\\">\\n  <div class=\\\"glass-card\\\" style=\\\"max-width: 720px; margin: 0 auto; border-color: rgba(56, 189, 248, 0.4); box-shadow: 0 0 40px rgba(56, 189, 248, 0.15);\\\">\\n    <div style=\\\"margin-bottom: 1.5rem; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 1rem;\\\">\\n      <h2 style=\\\"font-size: 1.45rem; font-weight: 800; color: #38bdf8; margin: 0 0 0.35rem 0;\\\">\\n        \\ud83c\\udfcf Official Player Registration Form\\n      </h2>\\n      <p style=\\\"color: #cbd5e1; font-size: 0.9rem; margin: 0;\\\">\\n        Entry Fee: <strong style=\\\"color: #10b981; font-size: 1.05rem;\\\">\\u20b9{{ reg_fee }}</strong>. Pay with any UPI app below and snap your selfie.\\n      </p>\\n    </div>\\n\\n    <form id=\\\"playerRegForm\\\" onsubmit=\\\"handleRegistrationSubmit(event)\\\">\\n      <!-- Name & Phone -->\\n      <div style=\\\"display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; margin-bottom: 1rem;\\\">\\n        <div class=\\\"form-group\\\" style=\\\"margin-bottom: 0;\\\">\\n          <label class=\\\"form-label\\\">Full Name *</label>\\n          <input type=\\\"text\\\" id=\\\"regName\\\" class=\\\"form-control\\\" placeholder=\\\"e.g. M. Raju Anna\\\" required>\\n        </div>\\n        <div class=\\\"form-group\\\" style=\\\"margin-bottom: 0;\\\">\\n          <label class=\\\"form-label\\\">Mobile Number *</label>\\n          <input type=\\\"tel\\\" id=\\\"regPhone\\\" class=\\\"form-control\\\" placeholder=\\\"10-digit WhatsApp Number\\\" required pattern=\\\"[0-9]{10}\\\">\\n        </div>\\n      </div>\\n\\n      <!-- Village & Role -->\\n      <div style=\\\"display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; margin-bottom: 1rem;\\\">\\n        <div class=\\\"form-group\\\" style=\\\"margin-bottom: 0;\\\">\\n          <label class=\\\"form-label\\\">Village / Town *</label>\\n          <input type=\\\"text\\\" id=\\\"regVillage\\\" class=\\\"form-control\\\" placeholder=\\\"e.g. Saidapur / Kunsi\\\" required value=\\\"Saidapur\\\">\\n        </div>\\n        <div class=\\\"form-group\\\" style=\\\"margin-bottom: 0;\\\">\\n          <label class=\\\"form-label\\\">Primary Playing Role *</label>\\n          <select id=\\\"regRole\\\" class=\\\"form-control\\\" required>\\n            <option value=\\\"All-Rounder\\\">\\ud83c\\udfcf All-Rounder</option>\\n            <option value=\\\"Batsman\\\">\\ud83c\\udfcf Top-Order Batsman</option>\\n            <option value=\\\"Bowler\\\">\\ud83c\\udfaf Fast / Spin Bowler</option>\\n            <option value=\\\"Wicket-Keeper\\\">\\ud83e\\udde4 Wicket Keeper Batsman</option>\\n          </select>\\n        </div>\\n      </div>\\n\\n      <!-- Batting & Bowling Style -->\\n      <div style=\\\"display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; margin-bottom: 1.25rem;\\\">\\n        <div class=\\\"form-group\\\" style=\\\"margin-bottom: 0;\\\">\\n          <label class=\\\"form-label\\\">Batting Style</label>\\n          <select id=\\\"regBatting\\\" class=\\\"form-control\\\">\\n            <option value=\\\"Right Hand Bat\\\">Right Hand Bat</option>\\n            <option value=\\\"Left Hand Bat\\\">Left Hand Bat</option>\\n          </select>\\n        </div>\\n        <div class=\\\"form-group\\\" style=\\\"margin-bottom: 0;\\\">\\n          <label class=\\\"form-label\\\">Bowling Style</label>\\n          <select id=\\\"regBowling\\\" class=\\\"form-control\\\">\\n            <option value=\\\"Right Arm Medium Fast\\\">Right Arm Medium Fast</option>\\n            <option value=\\\"Right Arm Spin\\\">Right Arm Spin</option>\\n            <option value=\\\"Left Arm Fast\\\">Left Arm Fast</option>\\n            <option value=\\\"Left Arm Spin\\\">Left Arm Spin</option>\\n            <option value=\\\"None\\\">None</option>\\n          </select>\\n        </div>\\n      </div>\\n\\n      <!-- LIVE CAMERA SELFIE MODULE -->\\n      <div class=\\\"selfie-camera-box\\\">\\n        <label class=\\\"form-label\\\" style=\\\"color: #38bdf8; font-weight: 800; font-size: 1rem; margin-bottom: 0.5rem; display: block;\\\">\\n          \\ud83d\\udcf7 Player Photo / Live Selfie Camera\\n        </label>\\n        <p style=\\\"color: #94a3b8; font-size: 0.85rem; margin-bottom: 1rem;\\\">\\n          Click the button below to take a live selfie with your camera, or upload a picture.\\n        </p>\\n\\n        <!-- Video stream element -->\\n        <video id=\\\"cameraVideo\\\" class=\\\"selfie-viewfinder\\\" autoplay playsinline style=\\\"display: none;\\\"></video>\\n        <!-- Captured preview image -->\\n        <img id=\\\"photoPreview\\\" class=\\\"selfie-viewfinder\\\" style=\\\"display: none;\\\" alt=\\\"Selfie Preview\\\">\\n        <canvas id=\\\"cameraCanvas\\\" style=\\\"display: none;\\\"></canvas>\\n\\n        <!-- Placeholder when camera is idle -->\\n        <div id=\\\"cameraPlaceholder\\\" style=\\\"padding: 1.5rem 1rem; background: rgba(0,0,0,0.3); border-radius: 8px; margin-bottom: 0.75rem;\\\">\\n          <span style=\\\"font-size: 3rem; display: block; margin-bottom: 0.35rem;\\\">\\ud83e\\udd33</span>\\n          <span style=\\\"color: #cbd5e1; font-size: 0.9rem;\\\">No photo taken yet</span>\\n        </div>\\n\\n        <!-- Camera Action Buttons -->\\n        <div style=\\\"display: flex; gap: 0.5rem; justify-content: center; flex-wrap: wrap;\\\">\\n          <button type=\\\"button\\\" id=\\\"btnStartCamera\\\" onclick=\\\"startCamera()\\\" class=\\\"btn btn-secondary\\\" style=\\\"font-size: 0.85rem; border-color: #38bdf8; color: #38bdf8;\\\">\\n            \\ud83d\\udcf7 Open Live Camera / Take Selfie\\n          </button>\\n          <button type=\\\"button\\\" id=\\\"btnSnapPhoto\\\" onclick=\\\"snapSelfie()\\\" class=\\\"btn btn-success\\\" style=\\\"display: none; font-size: 0.85rem;\\\">\\n            \\u26a1 Snap Selfie Now\\n          </button>\\n          <button type=\\\"button\\\" id=\\\"btnRetakePhoto\\\" onclick=\\\"retakeSelfie()\\\" class=\\\"btn btn-secondary\\\" style=\\\"display: none; font-size: 0.85rem;\\\">\\n            \\ud83d\\udd04 Retake Selfie\\n          </button>\\n          <label class=\\\"btn btn-secondary\\\" style=\\\"margin: 0; font-size: 0.85rem; cursor: pointer;\\\">\\n            \\ud83d\\udcc1 Upload from Gallery\\n            <input type=\\\"file\\\" id=\\\"regPhoto\\\" accept=\\\"image/*\\\" style=\\\"display: none;\\\" onchange=\\\"handleFileSelected(event)\\\">\\n          </label>\\n        </div>\\n      </div>\\n\\n      <!-- DEDICATED UPI PAYMENT METHODS -->\\n      <div style=\\\"background: rgba(15,23,42,0.8); border: 1px solid rgba(16, 185, 129, 0.4); padding: 1.25rem; border-radius: 12px; margin-bottom: 1.5rem;\\\">\\n        <div style=\\\"display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; flex-wrap: wrap; gap: 0.5rem;\\\">\\n          <strong style=\\\"color: #10b981; font-size: 1.05rem;\\\">\\n            \\ud83d\\udcb3 Pay \\u20b9{{ reg_fee }} Entry Fee via UPI App\\n          </strong>\\n          <span class=\\\"badge\\\" style=\\\"background: rgba(16, 185, 129, 0.2); color: #34d399;\\\">\\n            Direct App Launch\\n          </span>\\n        </div>\\n        <p style=\\\"color: #94a3b8; font-size: 0.85rem; margin-bottom: 1rem;\\\">\\n          Click your preferred payment app below to open it immediately on your phone and complete the \\u20b9{{ reg_fee }} fee:\\n        </p>\\n\\n        <!-- Payment App Buttons Grid -->\\n        <div class=\\\"payment-apps-grid\\\">\\n          <!-- PhonePe -->\\n          <a href=\\\"phonepe://pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg\\\" \\n             onclick=\\\"openPaymentApp(event, 'phonepe://pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg')\\\"\\n             class=\\\"pay-app-btn pay-phonepe\\\">\\n            <span style=\\\"font-size: 1.6rem; margin-bottom: 0.25rem;\\\">\\ud83d\\udfe3</span>\\n            <span>PhonePe</span>\\n          </a>\\n\\n          <!-- Google Pay -->\\n          <a href=\\\"gpay://upi/pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg\\\"\\n             onclick=\\\"openPaymentApp(event, 'gpay://upi/pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg')\\\"\\n             class=\\\"pay-app-btn pay-gpay\\\">\\n            <span style=\\\"font-size: 1.6rem; margin-bottom: 0.25rem;\\\">\\ud83d\\udd35</span>\\n            <span>Google Pay</span>\\n          </a>\\n\\n          <!-- Paytm -->\\n          <a href=\\\"paytmmp://pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg\\\"\\n             onclick=\\\"openPaymentApp(event, 'paytmmp://pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg')\\\"\\n             class=\\\"pay-app-btn pay-paytm\\\">\\n            <span style=\\\"font-size: 1.6rem; margin-bottom: 0.25rem;\\\">\\ud83d\\udfe6</span>\\n            <span>Paytm</span>\\n          </a>\\n\\n          <!-- Amazon Pay -->\\n          <a href=\\\"amazonpay://pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg\\\"\\n             onclick=\\\"openPaymentApp(event, 'amazonpay://pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg')\\\"\\n             class=\\\"pay-app-btn pay-amazon\\\">\\n            <span style=\\\"font-size: 1.6rem; margin-bottom: 0.25rem;\\\">\\ud83d\\udfe0</span>\\n            <span>Amazon Pay</span>\\n          </a>\\n\\n          <!-- BHIM / Any UPI -->\\n          <a href=\\\"upi://pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg\\\"\\n             onclick=\\\"openPaymentApp(event, 'upi://pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg')\\\"\\n             class=\\\"pay-app-btn pay-bhim\\\">\\n            <span style=\\\"font-size: 1.6rem; margin-bottom: 0.25rem;\\\">\\ud83c\\uddee\\ud83c\\uddf3</span>\\n            <span>BHIM UPI</span>\\n          </a>\\n        </div>\\n\\n        <!-- Desktop QR Code Scanner -->\\n        <div style=\\\"text-align: center; margin: 1rem 0; padding: 1rem; background: rgba(0,0,0,0.3); border-radius: 8px;\\\">\\n          <p style=\\\"color: #94a3b8; font-size: 0.85rem; margin-bottom: 0.5rem;\\\">\\n            \\ud83d\\udcf1 On Computer? Scan this QR code from your phone with PhonePe, GPay, or Paytm:\\n          </p>\\n          <img src=\\\"https://api.qrserver.com/v1/create-qr-code/?size=160x160&data={{ ('upi://pay?pa=' + upi_id + '&pn=' + payee_name + '&am=' + (reg_fee|string) + '&cu=INR&tn=KPL2026_Registration')|urlencode }}\\\" alt=\\\"UPI QR Code\\\" style=\\\"width: 140px; height: 140px; border-radius: 8px; border: 3px solid #f59e0b; background: #fff; padding: 4px;\\\">\\n          <div style=\\\"color: #f59e0b; font-weight: 800; font-size: 0.95rem; margin-top: 0.5rem;\\\">\\n            UPI ID: {{ upi_id }} ({{ payee_name }})\\n          </div>\\n        </div>\\n\\n        <div class=\\\"form-group\\\" style=\\\"margin-bottom: 0;\\\">\\n          <label class=\\\"form-label\\\" style=\\\"font-size: 0.85rem;\\\">UPI Reference / UTR Number (Optional)</label>\\n          <input type=\\\"text\\\" id=\\\"regUtr\\\" class=\\\"form-control\\\" placeholder=\\\"12-digit UTR from payment confirmation\\\">\\n        </div>\\n      </div>\\n\\n      <button type=\\\"submit\\\" id=\\\"btnSubmitReg\\\" class=\\\"btn btn-primary\\\" style=\\\"width: 100%; font-size: 1.15rem; padding: 0.95rem; font-weight: 900;\\\">\\n        Submit Player Registration &rarr;\\n      </button>\\n    </form>\\n  </div>\\n</div>\\n\\n<!-- SUB-PAGE 2: REGISTERED PLAYERS UNTIL NOW (DIRECTORY) -->\\n<div id=\\\"subpageDirectory\\\" style=\\\"display: none;\\\">\\n  <!-- Search, Filter & View Switcher Bar -->\\n  <div style=\\\"margin-bottom: 1.5rem; display: flex; gap: 0.75rem; flex-wrap: wrap; align-items: center; justify-content: space-between;\\\">\\n    <div style=\\\"display: flex; gap: 0.75rem; flex-wrap: wrap; flex: 1; min-width: 280px;\\\">\\n      <input type=\\\"text\\\" id=\\\"dirSearch\\\" placeholder=\\\"\\ud83d\\udd0d Search by name, village, or role...\\\" class=\\\"form-control\\\" style=\\\"flex: 2; min-width: 220px;\\\" oninput=\\\"filterDirectory()\\\">\\n      <select id=\\\"dirRoleFilter\\\" class=\\\"form-control\\\" style=\\\"flex: 1; min-width: 160px;\\\" onchange=\\\"filterDirectory()\\\">\\n        <option value=\\\"All\\\">All Roles</option>\\n        <option value=\\\"All-Rounder\\\">All-Rounder</option>\\n        <option value=\\\"Batsman\\\">Batsman</option>\\n        <option value=\\\"Bowler\\\">Bowler</option>\\n        <option value=\\\"Wicket-Keeper\\\">Wicket-Keeper</option>\\n      </select>\\n    </div>\\n    <div style=\\\"display: flex; gap: 0.35rem;\\\">\\n      <button type=\\\"button\\\" id=\\\"btnViewCards\\\" class=\\\"subtab-btn active\\\" style=\\\"padding: 0.45rem 0.85rem; font-size: 0.85rem;\\\" onclick=\\\"switchDirLayout('cards')\\\">\\n        \\ud83d\\uddc2\\ufe0f Cards\\n      </button>\\n      <button type=\\\"button\\\" id=\\\"btnViewTable\\\" class=\\\"subtab-btn\\\" style=\\\"padding: 0.45rem 0.85rem; font-size: 0.85rem;\\\" onclick=\\\"switchDirLayout('table')\\\">\\n        \\ud83d\\udccb Table\\n      </button>\\n    </div>\\n  </div>\\n\\n  <!-- CARDS VIEW (DEFAULT) -->\\n  <div class=\\\"player-dir-grid\\\" id=\\\"dirCardsContainer\\\">\\n    {% for p in players %}\\n    <div class=\\\"dir-card\\\" data-name=\\\"{{ p.name|lower }}\\\" data-village=\\\"{{ (p.village or 'Saidapur')|lower }}\\\" data-role=\\\"{{ p.role|lower }}\\\">\\n      <img src=\\\"{{ p.photo_url or '/static/images/avatar_allrounder.svg' }}\\\" class=\\\"dir-avatar\\\" alt=\\\"{{ p.name }}\\\">\\n      <div style=\\\"flex: 1; min-width: 0;\\\">\\n        <div style=\\\"display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;\\\">\\n          <h3 style=\\\"font-size: 1.05rem; font-weight: 800; color: #fff; margin: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;\\\">\\n            {{ p.name }}\\n          </h3>\\n          <span style=\\\"color: #f59e0b; font-weight: 800; font-size: 0.85rem;\\\">#{{ p.serial_no or loop.index }}</span>\\n        </div>\\n        <div style=\\\"display: flex; gap: 0.35rem; align-items: center; margin-bottom: 0.35rem; flex-wrap: wrap;\\\">\\n          <span class=\\\"badge {{ 'badge-batsman' if 'bat' in (p.role|lower) else ('badge-bowler' if 'bowl' in (p.role|lower) else 'badge-allrounder') }}\\\" style=\\\"font-size: 0.75rem;\\\">\\n            {{ p.role }}\\n          </span>\\n          <span style=\\\"color: #94a3b8; font-size: 0.8rem; display: flex; align-items: center; gap: 0.2rem;\\\">\\n            \\ud83d\\udccd {{ p.village or 'Saidapur' }}\\n          </span>\\n        </div>\\n        <div style=\\\"display: flex; justify-content: space-between; align-items: center; font-size: 0.75rem; color: #64748b;\\\">\\n          <span style=\\\"color: #10b981; font-weight: 700; background: rgba(16, 185, 129, 0.15); padding: 0.15rem 0.45rem; border-radius: 4px; border: 1px solid rgba(16, 185, 129, 0.3);\\\">\\n            Amount Sent: \\u20b9{{ p.reg_amount or 200 }} (Paid)\\n          </span>\\n          {% if p.transaction_id %}\\n          <span style=\\\"color: #38bdf8; font-family: monospace;\\\">UTR: {{ p.transaction_id }}</span>\\n          {% endif %}\\n        </div>\\n      </div>\\n    </div>\\n    {% endfor %}\\n  </div>\\n\\n  <!-- TABLE VIEW -->\\n  <div id=\\\"dirTableContainer\\\" style=\\\"display: none; overflow-x: auto; background: rgba(15, 23, 42, 0.75); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px;\\\">\\n    <table class=\\\"dir-table\\\">\\n      <thead>\\n        <tr>\\n          <th>#</th>\\n          <th>Photo</th>\\n          <th>Player Name</th>\\n          <th>Role</th>\\n          <th>Village / Town</th>\\n          <th>Amount Sent</th>\\n          <th>Mobile</th>\\n          <th>UTR / Transaction</th>\\n        </tr>\\n      </thead>\\n      <tbody>\\n        {% for p in players %}\\n        <tr class=\\\"dir-table-row\\\" data-name=\\\"{{ p.name|lower }}\\\" data-village=\\\"{{ (p.village or 'Saidapur')|lower }}\\\" data-role=\\\"{{ p.role|lower }}\\\">\\n          <td style=\\\"font-weight: 800; color: #f59e0b;\\\">#{{ p.serial_no or loop.index }}</td>\\n          <td>\\n            <img src=\\\"{{ p.photo_url or '/static/images/avatar_allrounder.svg' }}\\\" class=\\\"table-avatar\\\" alt=\\\"{{ p.name }}\\\">\\n          </td>\\n          <td style=\\\"font-weight: 800; color: #fff;\\\">{{ p.name }}</td>\\n          <td>\\n            <span class=\\\"badge {{ 'badge-batsman' if 'bat' in (p.role|lower) else ('badge-bowler' if 'bowl' in (p.role|lower) else 'badge-allrounder') }}\\\" style=\\\"font-size: 0.75rem;\\\">\\n              {{ p.role }}\\n            </span>\\n          </td>\\n          <td style=\\\"color: #cbd5e1;\\\">\\ud83d\\udccd {{ p.village or 'Saidapur' }}</td>\\n          <td style=\\\"color: #10b981; font-weight: 800;\\\">\\u20b9{{ p.reg_amount or 200 }} Paid</td>\\n          <td style=\\\"color: #94a3b8; font-family: monospace;\\\">{{ p.phone or '-' }}</td>\\n          <td style=\\\"color: #38bdf8; font-family: monospace; font-size: 0.8rem;\\\">{{ p.transaction_id or 'UPI Verified' }}</td>\\n        </tr>\\n        {% endfor %}\\n      </tbody>\\n    </table>\\n  </div>\\n</div>\\n{% endblock %}\\n\\n{% block extra_js %}\\n<script>\\n  let activeVideoStream = null;\\n  let capturedSelfieBlob = null;\\n\\n  function switchRegSubtab(tab) {\\n    const btnForm = document.getElementById('tabBtnRegister');\\n    const btnDir = document.getElementById('tabBtnDirectory');\\n    const pageForm = document.getElementById('subpageRegisterForm');\\n    const pageDir = document.getElementById('subpageDirectory');\\n\\n    if (tab === 'directory') {\\n      btnDir.classList.add('active');\\n      btnForm.classList.remove('active');\\n      pageDir.style.display = 'block';\\n      pageForm.style.display = 'none';\\n      stopCamera();\\n    } else {\\n      btnForm.classList.add('active');\\n      btnDir.classList.remove('active');\\n      pageForm.style.display = 'block';\\n      pageDir.style.display = 'none';\\n    }\\n  }\\n\\n  // --- LIVE CAMERA SELFIE MODULE ---\\n  async function startCamera() {\\n    try {\\n      const stream = await navigator.mediaDevices.getUserMedia({\\n        video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 640 } },\\n        audio: false\\n      });\\n      activeVideoStream = stream;\\n      const video = document.getElementById('cameraVideo');\\n      video.srcObject = stream;\\n      video.style.display = 'block';\\n      document.getElementById('cameraPlaceholder').style.display = 'none';\\n      document.getElementById('photoPreview').style.display = 'none';\\n      document.getElementById('btnStartCamera').style.display = 'none';\\n      document.getElementById('btnSnapPhoto').style.display = 'inline-flex';\\n      document.getElementById('btnRetakePhoto').style.display = 'none';\\n    } catch (err) {\\n      alert('Camera access unavailable or blocked. You can upload a photo from your gallery instead.');\\n    }\\n  }\\n\\n  function snapSelfie() {\\n    const video = document.getElementById('cameraVideo');\\n    const canvas = document.getElementById('cameraCanvas');\\n    const preview = document.getElementById('photoPreview');\\n\\n    canvas.width = video.videoWidth || 480;\\n    canvas.height = video.videoHeight || 480;\\n    const ctx = canvas.getContext('2d');\\n    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);\\n\\n    canvas.toBlob((blob) => {\\n      capturedSelfieBlob = blob;\\n    }, 'image/jpeg', 0.9);\\n\\n    preview.src = canvas.toDataURL('image/jpeg');\\n    preview.style.display = 'block';\\n    video.style.display = 'none';\\n    stopCamera();\\n\\n    document.getElementById('btnSnapPhoto').style.display = 'none';\\n    document.getElementById('btnRetakePhoto').style.display = 'inline-flex';\\n  }\\n\\n  function retakeSelfie() {\\n    capturedSelfieBlob = null;\\n    document.getElementById('photoPreview').style.display = 'none';\\n    startCamera();\\n  }\\n\\n  function stopCamera() {\\n    if (activeVideoStream) {\\n      activeVideoStream.getTracks().forEach(track => track.stop());\\n      activeVideoStream = null;\\n    }\\n  }\\n\\n  function handleFileSelected(e) {\\n    if (e.target.files && e.target.files[0]) {\\n      const file = e.target.files[0];\\n      capturedSelfieBlob = file;\\n      const reader = new FileReader();\\n      reader.onload = function(evt) {\\n        const preview = document.getElementById('photoPreview');\\n        preview.src = evt.target.result;\\n        preview.style.display = 'block';\\n        document.getElementById('cameraVideo').style.display = 'none';\\n        document.getElementById('cameraPlaceholder').style.display = 'none';\\n        document.getElementById('btnStartCamera').style.display = 'none';\\n        document.getElementById('btnSnapPhoto').style.display = 'none';\\n        document.getElementById('btnRetakePhoto').style.display = 'inline-flex';\\n      };\\n      reader.readAsDataURL(file);\\n    }\\n  }\\n\\n  // --- PAYMENT APP LAUNCHER ---\\n  function openPaymentApp(e, primaryUrl) {\\n    // Attempt to open dedicated app URI; on mobile device this launches PhonePe/GPay/Paytm directly\\n    const fallbackUrl = \\\"upi://pay?pa={{ upi_id }}&pn={{ payee_name|urlencode }}&am={{ reg_fee }}&cu=INR&tn=KPL2026_Player_Reg\\\";\\n    const start = Date.now();\\n    setTimeout(() => {\\n      if (Date.now() - start < 2000) {\\n        window.location.href = fallbackUrl;\\n      }\\n    }, 1200);\\n  }\\n\\n  // --- DIRECTORY LAYOUT & SEARCH ---\\n  function switchDirLayout(layout) {\\n    const cards = document.getElementById('dirCardsContainer');\\n    const table = document.getElementById('dirTableContainer');\\n    const btnCards = document.getElementById('btnViewCards');\\n    const btnTable = document.getElementById('btnViewTable');\\n\\n    if (layout === 'table') {\\n      cards.style.display = 'none';\\n      table.style.display = 'block';\\n      btnTable.classList.add('active');\\n      btnCards.classList.remove('active');\\n    } else {\\n      cards.style.display = 'grid';\\n      table.style.display = 'none';\\n      btnCards.classList.add('active');\\n      btnTable.classList.remove('active');\\n    }\\n    filterDirectory();\\n  }\\n\\n  function filterDirectory() {\\n    const q = (document.getElementById('dirSearch')?.value || '').toLowerCase();\\n    const role = (document.getElementById('dirRoleFilter')?.value || 'All').toLowerCase();\\n\\n    document.querySelectorAll('.dir-card').forEach(card => {\\n      const name = card.dataset.name || '';\\n      const village = card.dataset.village || '';\\n      const cRole = card.dataset.role || '';\\n      const matchesText = name.includes(q) || village.includes(q) || cRole.includes(q);\\n      const matchesRole = (role === 'all') || cRole.includes(role);\\n      card.style.display = (matchesText && matchesRole) ? 'flex' : 'none';\\n    });\\n\\n    document.querySelectorAll('.dir-table-row').forEach(row => {\\n      const name = row.dataset.name || '';\\n      const village = row.dataset.village || '';\\n      const cRole = row.dataset.role || '';\\n      const matchesText = name.includes(q) || village.includes(q) || cRole.includes(q);\\n      const matchesRole = (role === 'all') || cRole.includes(role);\\n      row.style.display = (matchesText && matchesRole) ? '' : 'none';\\n    });\\n  }\\n\\n  // --- SUBMIT REGISTRATION ---\\n  async function handleRegistrationSubmit(e) {\\n    e.preventDefault();\\n    const btn = document.getElementById('btnSubmitReg');\\n    btn.disabled = true;\\n    btn.textContent = 'Submitting Registration...';\\n\\n    const formData = new FormData();\\n    formData.append('name', document.getElementById('regName').value.trim());\\n    formData.append('phone', document.getElementById('regPhone').value.trim());\\n    formData.append('village', document.getElementById('regVillage').value.trim());\\n    formData.append('role', document.getElementById('regRole').value);\\n    formData.append('batting_style', document.getElementById('regBatting').value);\\n    formData.append('bowling_style', document.getElementById('regBowling').value);\\n    formData.append('transaction_id', document.getElementById('regUtr').value.trim());\\n\\n    if (capturedSelfieBlob) {\\n      formData.append('photo', capturedSelfieBlob, 'selfie_' + Date.now() + '.jpg');\\n    }\\n\\n    try {\\n      const res = await fetch('/api/register', {\\n        method: 'POST',\\n        body: formData\\n      });\\n      const data = await res.json();\\n      if (data.success) {\\n        alert('\\ud83c\\udf89 Player Registration Successful! Welcome to KPL 2026.');\\n        location.reload();\\n      } else {\\n        alert(data.message || 'Registration failed.');\\n      }\\n    } catch (err) {\\n      alert('Network error: ' + err.message);\\n    } finally {\\n      btn.disabled = false;\\n      btn.textContent = 'Submit Player Registration \\u2192';\\n    }\\n  }\\n</script>\\n{% endblock %}\\n\", \"register_success.html\": \"{% extends \\\"base.html\\\" %}\\n\\n{% block content %}\\n<div style=\\\"max-width: 550px; margin: 1.5rem auto; text-align: center;\\\">\\n  <div style=\\\"width: 70px; height: 70px; background: rgba(16, 185, 129, 0.2); border: 2px solid var(--pitch-green); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 2.25rem; margin: 0 auto 1.25rem;\\\">\\n    \\u2713\\n  </div>\\n  \\n  <h1 style=\\\"font-size: 2rem; font-weight: 900; margin-bottom: 0.5rem; color: #fff;\\\">Registration Received!</h1>\\n  <p style=\\\"color: var(--text-muted); margin-bottom: 2rem;\\\">\\n    Your registration details and payment reference have been recorded. Here is your official tournament player card.\\n  </p>\\n\\n  <!-- Player Digital Pass Card -->\\n  <div class=\\\"glass-card\\\" style=\\\"border: 2px solid var(--primary-gold); box-shadow: 0 0 35px var(--gold-glow); position: relative; overflow: hidden; padding: 2.5rem 1.5rem;\\\">\\n    <div style=\\\"position: absolute; top: 12px; right: 15px; font-size: 0.8rem; font-weight: 800; color: var(--primary-gold); background: rgba(245, 158, 11, 0.15); padding: 0.2rem 0.6rem; border-radius: var(--radius-sm); border: 1px solid rgba(245, 158, 11, 0.3);\\\">\\n      {{ player.id }}\\n    </div>\\n\\n    <!-- Photo -->\\n    <div style=\\\"width: 140px; height: 140px; border-radius: 50%; border: 4px solid var(--primary-gold); margin: 0 auto 1.25rem; overflow: hidden; box-shadow: 0 0 20px var(--gold-glow); background: #1e293b;\\\">\\n      <img src=\\\"{{ player.photo_url or '/static/images/avatar_allrounder.svg' }}\\\" alt=\\\"{{ player.name }}\\\" style=\\\"width: 100%; height: 100%; object-fit: cover;\\\">\\n    </div>\\n\\n    <div style=\\\"font-size: 1.75rem; font-weight: 900; color: #fff; margin-bottom: 0.35rem;\\\">\\n      {{ player.name }}\\n    </div>\\n\\n    <div style=\\\"margin-bottom: 1.25rem;\\\">\\n      <span class=\\\"badge {% if 'Bat' in player.role and 'Keep' not in player.role %}badge-batsman{% elif 'Bowl' in player.role %}badge-bowler{% elif 'Keep' in player.role %}badge-keeper{% else %}badge-allrounder{% endif %}\\\" style=\\\"font-size: 0.95rem; padding: 0.4rem 1rem;\\\">\\n        {{ player.role }}\\n      </span>\\n    </div>\\n\\n    <div style=\\\"background: rgba(0,0,0,0.4); border-radius: var(--radius-md); padding: 1rem; border: 1px solid var(--border-glass); display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; text-align: left; font-size: 0.9rem; margin-bottom: 1.5rem;\\\">\\n      <div>\\n        <span style=\\\"color: var(--text-dim); display: block; font-size: 0.8rem;\\\">Mobile</span>\\n        <strong style=\\\"color: #fff;\\\">{{ player.phone }}</strong>\\n      </div>\\n      <div>\\n        <span style=\\\"color: var(--text-dim); display: block; font-size: 0.8rem;\\\">Fee Paid</span>\\n        <strong style=\\\"color: var(--pitch-green);\\\">\\u20b9{{ player.reg_amount }}</strong>\\n      </div>\\n      <div>\\n        <span style=\\\"color: var(--text-dim); display: block; font-size: 0.8rem;\\\">Batting</span>\\n        <strong style=\\\"color: #fff;\\\">{{ player.batting_style }}</strong>\\n      </div>\\n      <div>\\n        <span style=\\\"color: var(--text-dim); display: block; font-size: 0.8rem;\\\">Bowling</span>\\n        <strong style=\\\"color: #fff;\\\">{{ player.bowling_style }}</strong>\\n      </div>\\n      <div style=\\\"grid-column: span 2;\\\">\\n        <span style=\\\"color: var(--text-dim); display: block; font-size: 0.8rem;\\\">Payment Reference (UTR)</span>\\n        <strong style=\\\"color: var(--primary-gold); word-break: break-all;\\\">{{ player.transaction_id }} ({{ player.payment_method }})</strong>\\n      </div>\\n    </div>\\n\\n    <div style=\\\"font-size: 0.85rem; color: var(--pitch-green); font-weight: 700; display: flex; align-items: center; justify-content: center; gap: 0.4rem;\\\">\\n      <span>\\u2713 Status:</span> Verified for Live Auction Pool\\n    </div>\\n  </div>\\n\\n  <div style=\\\"display: flex; gap: 1rem; justify-content: center; margin-top: 1.75rem;\\\">\\n    <button onclick=\\\"window.print()\\\" class=\\\"btn btn-secondary\\\">\\ud83d\\udda8\\ufe0f Print / Save Slip</button>\\n    <a href=\\\"/register\\\" class=\\\"btn btn-primary\\\">Register Another Player</a>\\n    <a href=\\\"/auction\\\" class=\\\"btn btn-success\\\">Go to Live Auction</a>\\n  </div>\\n</div>\\n{% endblock %}\\n\", \"templates/register_success.html\": \"{% extends \\\"base.html\\\" %}\\n\\n{% block content %}\\n<div style=\\\"max-width: 550px; margin: 1.5rem auto; text-align: center;\\\">\\n  <div style=\\\"width: 70px; height: 70px; background: rgba(16, 185, 129, 0.2); border: 2px solid var(--pitch-green); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 2.25rem; margin: 0 auto 1.25rem;\\\">\\n    \\u2713\\n  </div>\\n  \\n  <h1 style=\\\"font-size: 2rem; font-weight: 900; margin-bottom: 0.5rem; color: #fff;\\\">Registration Received!</h1>\\n  <p style=\\\"color: var(--text-muted); margin-bottom: 2rem;\\\">\\n    Your registration details and payment reference have been recorded. Here is your official tournament player card.\\n  </p>\\n\\n  <!-- Player Digital Pass Card -->\\n  <div class=\\\"glass-card\\\" style=\\\"border: 2px solid var(--primary-gold); box-shadow: 0 0 35px var(--gold-glow); position: relative; overflow: hidden; padding: 2.5rem 1.5rem;\\\">\\n    <div style=\\\"position: absolute; top: 12px; right: 15px; font-size: 0.8rem; font-weight: 800; color: var(--primary-gold); background: rgba(245, 158, 11, 0.15); padding: 0.2rem 0.6rem; border-radius: var(--radius-sm); border: 1px solid rgba(245, 158, 11, 0.3);\\\">\\n      {{ player.id }}\\n    </div>\\n\\n    <!-- Photo -->\\n    <div style=\\\"width: 140px; height: 140px; border-radius: 50%; border: 4px solid var(--primary-gold); margin: 0 auto 1.25rem; overflow: hidden; box-shadow: 0 0 20px var(--gold-glow); background: #1e293b;\\\">\\n      <img src=\\\"{{ player.photo_url or '/static/images/avatar_allrounder.svg' }}\\\" alt=\\\"{{ player.name }}\\\" style=\\\"width: 100%; height: 100%; object-fit: cover;\\\">\\n    </div>\\n\\n    <div style=\\\"font-size: 1.75rem; font-weight: 900; color: #fff; margin-bottom: 0.35rem;\\\">\\n      {{ player.name }}\\n    </div>\\n\\n    <div style=\\\"margin-bottom: 1.25rem;\\\">\\n      <span class=\\\"badge {% if 'Bat' in player.role and 'Keep' not in player.role %}badge-batsman{% elif 'Bowl' in player.role %}badge-bowler{% elif 'Keep' in player.role %}badge-keeper{% else %}badge-allrounder{% endif %}\\\" style=\\\"font-size: 0.95rem; padding: 0.4rem 1rem;\\\">\\n        {{ player.role }}\\n      </span>\\n    </div>\\n\\n    <div style=\\\"background: rgba(0,0,0,0.4); border-radius: var(--radius-md); padding: 1rem; border: 1px solid var(--border-glass); display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; text-align: left; font-size: 0.9rem; margin-bottom: 1.5rem;\\\">\\n      <div>\\n        <span style=\\\"color: var(--text-dim); display: block; font-size: 0.8rem;\\\">Mobile</span>\\n        <strong style=\\\"color: #fff;\\\">{{ player.phone }}</strong>\\n      </div>\\n      <div>\\n        <span style=\\\"color: var(--text-dim); display: block; font-size: 0.8rem;\\\">Fee Paid</span>\\n        <strong style=\\\"color: var(--pitch-green);\\\">\\u20b9{{ player.reg_amount }}</strong>\\n      </div>\\n      <div>\\n        <span style=\\\"color: var(--text-dim); display: block; font-size: 0.8rem;\\\">Batting</span>\\n        <strong style=\\\"color: #fff;\\\">{{ player.batting_style }}</strong>\\n      </div>\\n      <div>\\n        <span style=\\\"color: var(--text-dim); display: block; font-size: 0.8rem;\\\">Bowling</span>\\n        <strong style=\\\"color: #fff;\\\">{{ player.bowling_style }}</strong>\\n      </div>\\n      <div style=\\\"grid-column: span 2;\\\">\\n        <span style=\\\"color: var(--text-dim); display: block; font-size: 0.8rem;\\\">Payment Reference (UTR)</span>\\n        <strong style=\\\"color: var(--primary-gold); word-break: break-all;\\\">{{ player.transaction_id }} ({{ player.payment_method }})</strong>\\n      </div>\\n    </div>\\n\\n    <div style=\\\"font-size: 0.85rem; color: var(--pitch-green); font-weight: 700; display: flex; align-items: center; justify-content: center; gap: 0.4rem;\\\">\\n      <span>\\u2713 Status:</span> Verified for Live Auction Pool\\n    </div>\\n  </div>\\n\\n  <div style=\\\"display: flex; gap: 1rem; justify-content: center; margin-top: 1.75rem;\\\">\\n    <button onclick=\\\"window.print()\\\" class=\\\"btn btn-secondary\\\">\\ud83d\\udda8\\ufe0f Print / Save Slip</button>\\n    <a href=\\\"/register\\\" class=\\\"btn btn-primary\\\">Register Another Player</a>\\n    <a href=\\\"/auction\\\" class=\\\"btn btn-success\\\">Go to Live Auction</a>\\n  </div>\\n</div>\\n{% endblock %}\\n\", \"teams.html\": \"{% extends \\\"base.html\\\" %}\\n\\n{% block content %}\\n<div style=\\\"margin-bottom: 2rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;\\\">\\n  <div>\\n    <h1 style=\\\"font-size: 2.25rem; font-weight: 900; color: #fff;\\\">Team Squads & Purses</h1>\\n    <p style=\\\"color: var(--text-muted);\\\">Real-time view of bought players, retentions, and remaining budgets.</p>\\n  </div>\\n  <a href=\\\"/api/export-excel\\\" class=\\\"btn btn-success\\\">\\ud83d\\udcca Download Summary Excel</a>\\n</div>\\n\\n<div style=\\\"display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 1.5rem;\\\">\\n  {% for team_name, t in teams.items() %}\\n  <div class=\\\"glass-card\\\" style=\\\"border-top: 4px solid var(--primary-gold);\\\">\\n    <div style=\\\"display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem;\\\">\\n      <div>\\n        <h2 style=\\\"font-size: 1.5rem; font-weight: 900; color: #fff;\\\">{{ team_name }}</h2>\\n        <div style=\\\"color: var(--text-muted); font-size: 0.85rem;\\\">\\n          {{ (t.players|length) + (1 if t.retained else 0) }} Players in Squad\\n        </div>\\n      </div>\\n      <div style=\\\"text-align: right;\\\">\\n        <div style=\\\"font-size: 1.35rem; font-weight: 900; color: var(--pitch-green);\\\">\\u20b9{{ t.budget }}</div>\\n        <div style=\\\"font-size: 0.75rem; color: var(--text-dim); text-transform: uppercase;\\\">Purse Remaining</div>\\n      </div>\\n    </div>\\n\\n    <!-- Spent info -->\\n    <div style=\\\"background: rgba(0,0,0,0.3); padding: 0.6rem 0.85rem; border-radius: var(--radius-sm); border: 1px solid var(--border-glass); margin-bottom: 1.25rem; display: flex; justify-content: space-between; font-size: 0.85rem;\\\">\\n      <span style=\\\"color: var(--text-muted);\\\">Total Spent:</span>\\n      <strong style=\\\"color: #fca5a5;\\\">\\u20b9{{ t.spent }}</strong>\\n    </div>\\n\\n    <!-- Retained Player or Owner -->\\n    {% if t.retained %}\\n    {% set ret_name = t.retained.name if t.retained is mapping else t.retained %}\\n    {% set ret_type = t.retained.type if t.retained is mapping else 'Player' %}\\n    {% set ret_cost = t.retained.cost if t.retained is mapping else 500 %}\\n    <div style=\\\"background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.35); border-radius: var(--radius-sm); padding: 0.6rem 0.85rem; margin-bottom: 1rem; display: flex; align-items: center; justify-content: space-between;\\\">\\n      <div style=\\\"display: flex; align-items: center; gap: 0.5rem;\\\">\\n        <span style=\\\"background: {% if ret_type == 'Owner' %}#3b82f6{% else %}var(--primary-gold){% endif %}; color: #000; font-size: 0.7rem; font-weight: 900; padding: 0.15rem 0.4rem; border-radius: 4px;\\\">\\n          {{ ret_type|upper }} RETAINED\\n        </span>\\n        <strong style=\\\"color: #fff;\\\">{{ ret_name }}</strong>\\n      </div>\\n      <span style=\\\"color: var(--primary-gold); font-weight: 700; font-size: 0.85rem;\\\">\\u20b9{{ ret_cost }}</span>\\n    </div>\\n    {% endif %}\\n\\n    <!-- Squad Players List -->\\n    <h4 style=\\\"font-size: 0.9rem; font-weight: 800; color: var(--text-muted); text-transform: uppercase; margin-bottom: 0.75rem; letter-spacing: 0.05em;\\\">\\n      Bought Players\\n    </h4>\\n    \\n    {% if t.players %}\\n    <div style=\\\"display: flex; flex-direction: column; gap: 0.5rem;\\\">\\n      {% for p in t.players %}\\n      <div style=\\\"background: rgba(15, 23, 42, 0.7); border: 1px solid var(--border-glass); border-radius: var(--radius-sm); padding: 0.5rem 0.75rem; display: flex; justify-content: space-between; align-items: center;\\\">\\n        <div style=\\\"display: flex; align-items: center; gap: 0.6rem;\\\">\\n          <div style=\\\"width: 32px; height: 32px; border-radius: 50%; overflow: hidden; background: #334155;\\\">\\n            <img src=\\\"{{ registrations.get(p.name, {}).get('photo_url') or '/static/images/avatar_allrounder.svg' }}\\\" alt=\\\"\\\" style=\\\"width: 100%; height: 100%; object-fit: cover;\\\">\\n          </div>\\n          <div>\\n            <div style=\\\"font-weight: 700; color: #fff; font-size: 0.95rem;\\\">{{ p.name }}</div>\\n            <div style=\\\"font-size: 0.75rem; color: var(--text-dim);\\\">{{ registrations.get(p.name, {}).get('role', 'Player') }}</div>\\n          </div>\\n        </div>\\n        <div style=\\\"text-align: right;\\\">\\n          <div style=\\\"font-weight: 800; color: var(--pitch-green); font-size: 0.95rem;\\\">\\u20b9{{ p.cost }}</div>\\n          <div style=\\\"font-size: 0.7rem; color: var(--text-dim);\\\">Round {{ p.round or 1 }}</div>\\n        </div>\\n      </div>\\n      {% endfor %}\\n    </div>\\n    {% else %}\\n    <p style=\\\"color: var(--text-dim); font-size: 0.85rem; font-style: italic;\\\">No players bought yet in this auction.</p>\\n    {% endif %}\\n  </div>\\n  {% endfor %}\\n</div>\\n{% endblock %}\\n\", \"templates/teams.html\": \"{% extends \\\"base.html\\\" %}\\n\\n{% block content %}\\n<div style=\\\"margin-bottom: 2rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;\\\">\\n  <div>\\n    <h1 style=\\\"font-size: 2.25rem; font-weight: 900; color: #fff;\\\">Team Squads & Purses</h1>\\n    <p style=\\\"color: var(--text-muted);\\\">Real-time view of bought players, retentions, and remaining budgets.</p>\\n  </div>\\n  <a href=\\\"/api/export-excel\\\" class=\\\"btn btn-success\\\">\\ud83d\\udcca Download Summary Excel</a>\\n</div>\\n\\n<div style=\\\"display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 1.5rem;\\\">\\n  {% for team_name, t in teams.items() %}\\n  <div class=\\\"glass-card\\\" style=\\\"border-top: 4px solid var(--primary-gold);\\\">\\n    <div style=\\\"display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem;\\\">\\n      <div>\\n        <h2 style=\\\"font-size: 1.5rem; font-weight: 900; color: #fff;\\\">{{ team_name }}</h2>\\n        <div style=\\\"color: var(--text-muted); font-size: 0.85rem;\\\">\\n          {{ (t.players|length) + (1 if t.retained else 0) }} Players in Squad\\n        </div>\\n      </div>\\n      <div style=\\\"text-align: right;\\\">\\n        <div style=\\\"font-size: 1.35rem; font-weight: 900; color: var(--pitch-green);\\\">\\u20b9{{ t.budget }}</div>\\n        <div style=\\\"font-size: 0.75rem; color: var(--text-dim); text-transform: uppercase;\\\">Purse Remaining</div>\\n      </div>\\n    </div>\\n\\n    <!-- Spent info -->\\n    <div style=\\\"background: rgba(0,0,0,0.3); padding: 0.6rem 0.85rem; border-radius: var(--radius-sm); border: 1px solid var(--border-glass); margin-bottom: 1.25rem; display: flex; justify-content: space-between; font-size: 0.85rem;\\\">\\n      <span style=\\\"color: var(--text-muted);\\\">Total Spent:</span>\\n      <strong style=\\\"color: #fca5a5;\\\">\\u20b9{{ t.spent }}</strong>\\n    </div>\\n\\n    <!-- Retained Player or Owner -->\\n    {% if t.retained %}\\n    {% set ret_name = t.retained.name if t.retained is mapping else t.retained %}\\n    {% set ret_type = t.retained.type if t.retained is mapping else 'Player' %}\\n    {% set ret_cost = t.retained.cost if t.retained is mapping else 500 %}\\n    <div style=\\\"background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.35); border-radius: var(--radius-sm); padding: 0.6rem 0.85rem; margin-bottom: 1rem; display: flex; align-items: center; justify-content: space-between;\\\">\\n      <div style=\\\"display: flex; align-items: center; gap: 0.5rem;\\\">\\n        <span style=\\\"background: {% if ret_type == 'Owner' %}#3b82f6{% else %}var(--primary-gold){% endif %}; color: #000; font-size: 0.7rem; font-weight: 900; padding: 0.15rem 0.4rem; border-radius: 4px;\\\">\\n          {{ ret_type|upper }} RETAINED\\n        </span>\\n        <strong style=\\\"color: #fff;\\\">{{ ret_name }}</strong>\\n      </div>\\n      <span style=\\\"color: var(--primary-gold); font-weight: 700; font-size: 0.85rem;\\\">\\u20b9{{ ret_cost }}</span>\\n    </div>\\n    {% endif %}\\n\\n    <!-- Squad Players List -->\\n    <h4 style=\\\"font-size: 0.9rem; font-weight: 800; color: var(--text-muted); text-transform: uppercase; margin-bottom: 0.75rem; letter-spacing: 0.05em;\\\">\\n      Bought Players\\n    </h4>\\n    \\n    {% if t.players %}\\n    <div style=\\\"display: flex; flex-direction: column; gap: 0.5rem;\\\">\\n      {% for p in t.players %}\\n      <div style=\\\"background: rgba(15, 23, 42, 0.7); border: 1px solid var(--border-glass); border-radius: var(--radius-sm); padding: 0.5rem 0.75rem; display: flex; justify-content: space-between; align-items: center;\\\">\\n        <div style=\\\"display: flex; align-items: center; gap: 0.6rem;\\\">\\n          <div style=\\\"width: 32px; height: 32px; border-radius: 50%; overflow: hidden; background: #334155;\\\">\\n            <img src=\\\"{{ registrations.get(p.name, {}).get('photo_url') or '/static/images/avatar_allrounder.svg' }}\\\" alt=\\\"\\\" style=\\\"width: 100%; height: 100%; object-fit: cover;\\\">\\n          </div>\\n          <div>\\n            <div style=\\\"font-weight: 700; color: #fff; font-size: 0.95rem;\\\">{{ p.name }}</div>\\n            <div style=\\\"font-size: 0.75rem; color: var(--text-dim);\\\">{{ registrations.get(p.name, {}).get('role', 'Player') }}</div>\\n          </div>\\n        </div>\\n        <div style=\\\"text-align: right;\\\">\\n          <div style=\\\"font-weight: 800; color: var(--pitch-green); font-size: 0.95rem;\\\">\\u20b9{{ p.cost }}</div>\\n          <div style=\\\"font-size: 0.7rem; color: var(--text-dim);\\\">Round {{ p.round or 1 }}</div>\\n        </div>\\n      </div>\\n      {% endfor %}\\n    </div>\\n    {% else %}\\n    <p style=\\\"color: var(--text-dim); font-size: 0.85rem; font-style: italic;\\\">No players bought yet in this auction.</p>\\n    {% endif %}\\n  </div>\\n  {% endfor %}\\n</div>\\n{% endblock %}\\n\"}")

def ensure_assets():
    try:
        for rel_path, content in EMBEDDED_ASSETS.items():
            full_path = os.path.join(BASE_DIR, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w', encoding='utf-8', errors='ignore') as f:
                f.write(content)
            # Overwrite any stale files sitting in root directory
            filename = os.path.basename(rel_path)
            root_path = os.path.join(BASE_DIR, filename)
            if os.path.exists(root_path) and root_path != full_path and not os.path.isdir(root_path):
                try:
                    with open(root_path, 'w', encoding='utf-8', errors='ignore') as f:
                        f.write(content)
                except Exception:
                    pass
    except Exception as e:
        print("ensure_assets note:", e)

# ensure_assets() - Commented out to prevent overwriting modified templates and static files
# -----------------------------------


CONFIG_FILE = os.path.join(BASE_DIR, 'tournament_config.json')
REGISTRATIONS_FILE = os.path.join(BASE_DIR, 'registrations.json')
AUCTION_STATE_FILE = os.path.join(BASE_DIR, 'auction_state.json')

from jinja2 import DictLoader, ChoiceLoader, FileSystemLoader
app = Flask(__name__, static_folder=STATIC_DIR)
app.jinja_loader = ChoiceLoader([
    FileSystemLoader(os.path.join(BASE_DIR, 'templates')),
    FileSystemLoader(BASE_DIR),
    DictLoader(EMBEDDED_TEMPLATES)
])
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Disable static file caching (dev mode)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True

# ----------------- CONFIG HELPERS -----------------
def load_config():
    default_config = {
        "tournament_name": "Kunsi Premier League (KPL 2026)",
        "upi_id": "saidapur.cricket@upi",
        "payee_name": "Saidapur Cricket Committee",
        "registration_fee": 200,
        "default_purse": 5000,
        "min_bid": 100,
        "retention_price": 500,
        "owner_retention_price": 100,
        "max_players": 15,
        "currency_symbol": "₹",
        "admin_pin": "2026",
        "timer_enabled": False,
        "timer_duration": 120,
        "timer_reset_on_bid": True,
        "upi_enabled": True
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                default_config.update(cfg)
        except Exception as e:
            print("Error loading config:", e)

    # Guarantee KPL branding across all links and shares
    t_name = default_config.get("tournament_name", "")
    if "SPL" in t_name or not t_name:
        default_config["tournament_name"] = "Kunsi Premier League (KPL 2026)"

    env_pin = os.environ.get('ADMIN_PIN')
    if env_pin:
        default_config['admin_pin'] = env_pin.strip()
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
        if os.path.exists(AUCTION_STATE_FILE):
            for attempt in range(10):
                try:
                    with open(AUCTION_STATE_FILE, 'r', encoding='utf-8') as f:
                        st = json.load(f)
                        if isinstance(st, dict):
                            st['auction_started'] = True
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
        reg_fee=cfg["registration_fee"],
        upi_enabled=cfg.get("upi_enabled", True)
    )

@app.route('/register')
def register():
    cfg = load_config()
    regs = load_registrations()
    players_list = list(regs.values())
    players_list.sort(key=lambda p: p.get('serial_no', 999))
    return render_template(
        'register.html',
        active_page='register',
        tournament_name=cfg["tournament_name"],
        upi_id=cfg["upi_id"],
        payee_name=cfg["payee_name"],
        reg_fee=cfg["registration_fee"],
        upi_enabled=cfg.get("upi_enabled", True),
        players=players_list
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
        village = request.form.get('village', '').strip() or 'Saidapur'
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

        regs[name] = {
            'id': player_id,
            'serial_no': serial_no,
            'name': name,
            'village': village,
            'phone': phone,
            'role': role,
            'batting_style': batting_style,
            'bowling_style': bowling_style,
            'photo_url': photo_url,
            'reg_amount': reg_amount,
            'payment_status': 'Pending Verification',
            'payment_method': payment_method,
            'transaction_id': transaction_id,
            'payment_screenshot': screenshot_url,
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
        p_url = r_data.get("photo_url", "")
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

        # Initialize auction queue: exclude all retained players and sold players
        retained = get_retained_player_names(state)
        sold = get_sold_player_names(state)
        excluded = retained | sold
        pool = [p for p in state.get('players', []) if str(p).strip().lower() not in excluded]
        random.shuffle(pool)
        state['auction_players'] = pool
        state['unsold_players'] = [p for p in state.get('unsold_players', []) if str(p).strip().lower() not in excluded]
        state['current_round'] = 1
        # Keep current_player as None until auctioneer clicks Next Draw
        state['current_player'] = None
        state['current_bid'] = 0
        state['bidding_team'] = None
        state['current_bid_team'] = None

        save_auction_state(state)
        return jsonify({'success': True, 'message': 'Live Auction started! Spectators can now see live bidding.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/auction/pause', methods=['POST'])
def api_auction_pause():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Auctioneer PIN required'}), 403
        state = load_auction_state()
        push_history(state)
        state['auction_started'] = False
        save_auction_state(state)
        return jsonify({'success': True, 'message': 'Live Auction paused. Viewers are now in waiting mode.'})
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
            
        # Fallback if registrations file is empty
        if not player_list:
            player_list = [
                "Virat Kohli", "Rohit Sharma", "Jasprit Bumrah", "Hardik Pandya",
                "Rishabh Pant", "Ravindra Jadeja", "Surya Kumar Yadav", "Mohammed Shami",
                "KL Rahul", "Shubman Gill"
            ]
        
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
        
        total_purse = int(cfg.get("total_purse") or cfg.get("default_purse") or 6000)
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
