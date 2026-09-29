
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

# --- SELF-HEALING ASSET RESTORER ---
EMBEDDED_ASSETS = {"templates/base.html": "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\">\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n  <title>{% block title %}{{ tournament_name }}{% endblock %}</title>\n  <link rel=\"stylesheet\" href=\"/static/css/style.css\">\n  {% block extra_css %}{% endblock %}\n</head>\n<body>\n  <header class=\"navbar\">\n    <div class=\"nav-container\">\n      <a href=\"/\" class=\"nav-brand\">\n        <span class=\"brand-badge\">KPL</span>\n        <div class=\"brand-text\">{{ tournament_name }}</div>\n      </a>\n      <button class=\"mobile-toggle\" onclick=\"document.querySelector('.nav-links').classList.toggle('open')\">\u2630</button>\n      <ul class=\"nav-links\">\n        <li><a href=\"/\" class=\"nav-link {% if active_page == 'home' %}active{% endif %}\">\ud83c\udfe0 Home</a></li>\n        <li><a href=\"/register\" class=\"nav-link highlight {% if active_page == 'register' %}active{% endif %}\">\ud83d\udcdd Register Player</a></li>\n        <li><a href=\"/auction\" class=\"nav-link {% if active_page == 'auction' %}active{% endif %}\">\ud83c\udfcf Live Auction</a></li>\n        <li><a href=\"/teams\" class=\"nav-link {% if active_page == 'teams' %}active{% endif %}\">\ud83d\udc65 Team Squads</a></li>\n        <li><a href=\"/admin\" class=\"nav-link {% if active_page == 'admin' %}active{% endif %}\">\u2699\ufe0f Admin</a></li>\n      </ul>\n    </div>\n  </header>\n\n  <main class=\"page-container\">\n    {% block content %}{% endblock %}\n  </main>\n\n  <footer style=\"text-align: center; padding: 2rem 1rem; color: var(--text-dim); font-size: 0.85rem; border-top: 1px solid var(--border-glass); margin-top: auto;\">\n    <p>{{ tournament_name }} &copy; 2026. Official Player Registration & Live Auction Management System.</p>\n  </footer>\n\n  {% block extra_js %}{% endblock %}\n</body>\n</html>\n", "templates/index.html": "{% extends \"base.html\" %}\n\n{% block content %}\n<div style=\"text-align: center; max-width: 800px; margin: 2rem auto 3rem;\">\n  <div style=\"dikplay: inline-block; background: rgba(245, 158, 11, 0.15); color: var(--primary-gold); border: 1px solid rgba(245, 158, 11, 0.4); padding: 0.4rem 1rem; border-radius: 9999px; font-weight: 700; font-size: 0.9rem; text-transform: uppercase; margin-bottom: 1.25rem;\">\n    \ud83c\udfcf Season 2026 Official Portal\n  </div>\n  <h1 style=\"font-size: 3rem; font-weight: 900; line-height: 1.1; margin-bottom: 1rem; letter-spacing: -0.02em;\">\n    {{ tournament_name }}\n  </h1>\n  <p style=\"font-size: 1.2rem; color: var(--text-muted); line-height: 1.6;\">\n    Player Registration with Instant UPI Payments & Live Big-Screen Player Auction Engine with Photos, Roles, and Real-Time Purses.\n  </p>\n</div>\n\n<!-- Quick Stats Grid -->\n<div style=\"dikplay: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.25rem; margin-bottom: 2.5rem;\">\n  <div class=\"glass-card\" style=\"text-align: center; padding: 1.5rem 1rem;\">\n    <div style=\"font-size: 2.5rem; font-weight: 900; color: var(--primary-gold);\">{{ total_registered }}</div>\n    <div style=\"color: var(--text-muted); font-weight: 600; font-size: 0.95rem; margin-top: 0.25rem;\">Registered Players</div>\n  </div>\n  <div class=\"glass-card\" style=\"text-align: center; padding: 1.5rem 1rem;\">\n    <div style=\"font-size: 2.5rem; font-weight: 900; color: var(--electric-blue);\">{{ total_teams }}</div>\n    <div style=\"color: var(--text-muted); font-weight: 600; font-size: 0.95rem; margin-top: 0.25rem;\">Participating Teams</div>\n  </div>\n  <div class=\"glass-card\" style=\"text-align: center; padding: 1.5rem 1rem;\">\n    <div style=\"font-size: 2.5rem; font-weight: 900; color: var(--pitch-green);\">\u20b9{{ total_purse }}</div>\n    <div style=\"color: var(--text-muted); font-weight: 600; font-size: 0.95rem; margin-top: 0.25rem;\">Purse per Team</div>\n  </div>\n  <div class=\"glass-card\" style=\"text-align: center; padding: 1.5rem 1rem;\">\n    <div style=\"font-size: 2.5rem; font-weight: 900; color: #ec4899;\">\u20b9{{ reg_fee }}</div>\n    <div style=\"color: var(--text-muted); font-weight: 600; font-size: 0.95rem; margin-top: 0.25rem;\">Registration Fee</div>\n  </div>\n</div>\n\n<!-- Main Action Navigation Cards -->\n<div style=\"dikplay: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1.5rem;\">\n  <div class=\"glass-card\" style=\"dikplay: flex; flex-direction: column; justify-content: space-between; border-color: rgba(245, 158, 11, 0.4);\">\n    <div>\n      <div style=\"font-size: 2.5rem; margin-bottom: 0.75rem;\">\ud83d\udcdd</div>\n      <h2 style=\"font-size: 1.5rem; font-weight: 800; margin-bottom: 0.5rem; color: #fff;\">Player Registration</h2>\n      <p style=\"color: var(--text-muted); line-height: 1.5; margin-bottom: 1.5rem;\">\n        Players can register their name, mobile, role (Batsman, Bowler, All-Rounder, WK), take/upload photo, and pay registration fee instantly via PhonePe, Google Pay, or BHIM UPI.\n      </p>\n    </div>\n    <a href=\"/register\" class=\"btn btn-primary\" style=\"width: 100%;\">Register Now & Pay UPI &rarr;</a>\n  </div>\n\n  <div class=\"glass-card\" style=\"dikplay: flex; flex-direction: column; justify-content: space-between; border-color: rgba(16, 185, 129, 0.4);\">\n    <div>\n      <div style=\"font-size: 2.5rem; margin-bottom: 0.75rem;\">\ud83c\udfcf</div>\n      <h2 style=\"font-size: 1.5rem; font-weight: 800; margin-bottom: 0.5rem; color: #fff;\">Live Auction Arena</h2>\n      <p style=\"color: var(--text-muted); line-height: 1.5; margin-bottom: 1.5rem;\">\n        Projector & big-screen auction dashboard! Shows player photo, role, stats, registration status, live bidding counters, sound effects, sold celebration, and team purse meters.\n      </p>\n    </div>\n    <a href=\"/auction\" class=\"btn btn-success\" style=\"width: 100%;\">Enter Live Auction &rarr;</a>\n  </div>\n\n  <div class=\"glass-card\" style=\"dikplay: flex; flex-direction: column; justify-content: space-between; border-color: rgba(59, 130, 246, 0.4);\">\n    <div>\n      <div style=\"font-size: 2.5rem; margin-bottom: 0.75rem;\">\ud83d\udc65</div>\n      <h2 style=\"font-size: 1.5rem; font-weight: 800; margin-bottom: 0.5rem; color: #fff;\">Teams & Squads</h2>\n      <p style=\"color: var(--text-muted); line-height: 1.5; margin-bottom: 1.5rem;\">\n        Live mobile-friendly squad tracker for team captains and spectators to view bought players, prices, remaining purse, and team rosters in real time.\n      </p>\n    </div>\n    <a href=\"/teams\" class=\"btn btn-secondary\" style=\"width: 100%;\">View Team Rosters &rarr;</a>\n  </div>\n</div>\n{% endblock %}\n", "templates/register.html": "{% extends \"base.html\" %}\n\n{% block content %}\n<div style=\"max-width: 680px; margin: 0 auto;\">\n  <div style=\"text-align: center; margin-bottom: 2rem;\">\n    <h1 style=\"font-size: 2.25rem; font-weight: 900; margin-bottom: 0.5rem;\">Cricketer Registration</h1>\n    <p style=\"color: var(--text-muted); font-size: 1rem;\">\n      Fill in your details, take or upload your photo, and complete registration payment via PhonePe, Google Pay, or BHIM UPI.\n    </p>\n  </div>\n\n  <div id=\"formAlert\" style=\"dikplay: none; background: rgba(239, 68, 68, 0.2); border: 1px solid var(--crimson-red); color: #fca5a5; padding: 1rem; border-radius: var(--radius-md); margin-bottom: 1.5rem; font-weight: 600;\"></div>\n\n  <form id=\"registrationForm\" class=\"glass-card\" enctype=\"multipart/form-data\">\n    <!-- Step 1: Basic Info -->\n    <h3 style=\"font-size: 1.25rem; font-weight: 800; color: var(--primary-gold); margin-bottom: 1.25rem; dikplay: flex; align-items: center; gap: 0.5rem;\">\n      <span>1.</span> Player Details\n    </h3>\n\n    <div class=\"form-group\">\n      <label class=\"form-label\">Full Name <span class=\"req\">*</span></label>\n      <input type=\"text\" id=\"playerName\" class=\"form-control\" placeholder=\"e.g. M. Raju Anna\" required autocomplete=\"name\">\n    </div>\n\n    <div class=\"form-group\">\n      <label class=\"form-label\">Mobile / WhatsApp Number <span class=\"req\">*</span></label>\n      <input type=\"tel\" id=\"playerPhone\" class=\"form-control\" placeholder=\"e.g. 9876543210\" required pattern=\"[0-9]{10}\" maxlength=\"10\">\n    </div>\n\n    <!-- Step 2: Role Selection -->\n    <div class=\"form-group\">\n      <label class=\"form-label\">Playing Role <span class=\"req\">*</span></label>\n      <div class=\"role-grid\">\n        <label class=\"role-card-opt\">\n          <input type=\"radio\" name=\"playerRole\" value=\"Batsman\" required>\n          <div class=\"role-box\">\n            <span class=\"icon\">\ud83c\udfcf</span>\n            <span class=\"title\">Batsman</span>\n          </div>\n        </label>\n        <label class=\"role-card-opt\">\n          <input type=\"radio\" name=\"playerRole\" value=\"Bowler\">\n          <div class=\"role-box\">\n            <span class=\"icon\">\u26a1</span>\n            <span class=\"title\">Bowler</span>\n          </div>\n        </label>\n        <label class=\"role-card-opt\">\n          <input type=\"radio\" name=\"playerRole\" value=\"All-Rounder\" checked>\n          <div class=\"role-box\">\n            <span class=\"icon\">\u2b50</span>\n            <span class=\"title\">All-Rounder</span>\n          </div>\n        </label>\n        <label class=\"role-card-opt\">\n          <input type=\"radio\" name=\"playerRole\" value=\"Wicket Keeper / Batsman\">\n          <div class=\"role-box\">\n            <span class=\"icon\">\ud83e\udde4</span>\n            <span class=\"title\">WK-Batsman</span>\n          </div>\n        </label>\n      </div>\n    </div>\n\n    <div style=\"dikplay: grid; grid-template-columns: 1fr 1fr; gap: 1rem;\">\n      <div class=\"form-group\">\n        <label class=\"form-label\">Batting Style</label>\n        <select id=\"battingStyle\" class=\"form-control\">\n          <option value=\"Right Hand Bat\">Right Hand Bat</option>\n          <option value=\"Left Hand Bat\">Left Hand Bat</option>\n        </select>\n      </div>\n      <div class=\"form-group\">\n        <label class=\"form-label\">Bowling Style</label>\n        <select id=\"bowlingStyle\" class=\"form-control\">\n          <option value=\"Right Arm Fast\">Right Arm Fast</option>\n          <option value=\"Right Arm Medium\">Right Arm Medium</option>\n          <option value=\"Right Arm Spin\">Right Arm Spin</option>\n          <option value=\"Left Arm Fast\">Left Arm Fast</option>\n          <option value=\"Left Arm Spin\">Left Arm Spin</option>\n          <option value=\"None\">None (Pure Batsman)</option>\n        </select>\n      </div>\n    </div>\n\n    <!-- Step 3: Photo Capture / Upload -->\n    <div class=\"form-group\" style=\"margin-top: 1.5rem;\">\n      <h3 style=\"font-size: 1.25rem; font-weight: 800; color: var(--primary-gold); margin-bottom: 0.5rem; dikplay: flex; align-items: center; gap: 0.5rem;\">\n        <span>2.</span> Player Photo (Appears on Auction Screen) <span class=\"req\">*</span>\n      </h3>\n      <p style=\"color: var(--text-muted); font-size: 0.85rem; margin-bottom: 1rem;\">\n        Take a clear selfie with your camera or upload a photo from your gallery.\n      </p>\n\n      <div class=\"photo-uploader\">\n        <div class=\"photo-preview-wrap\">\n          <img id=\"photoPreview\" src=\"/static/images/avatar_allrounder.svg\" class=\"photo-preview-img\" alt=\"Player Preview\">\n        </div>\n        <div class=\"upload-actions\">\n          <!-- Mobile direct camera capture -->\n          <button type=\"button\" id=\"btnCameraMobile\" class=\"btn btn-secondary\">\n            \ud83d\udcf7 Take Photo (Camera)\n          </button>\n          <!-- Desktop webcam capture -->\n          <button type=\"button\" id=\"btnWebcamDesktop\" class=\"btn btn-secondary\" style=\"dikplay: none;\">\n            \ud83c\udfa5 Live Camera Snapshot\n          </button>\n          <!-- File upload from gallery -->\n          <button type=\"button\" id=\"btnUploadFile\" class=\"btn btn-secondary\">\n            \ud83d\udcc1 Upload from Gallery\n          </button>\n        </div>\n        \n        <!-- Hidden Inputs -->\n        <input type=\"file\" id=\"photoFileInput\" accept=\"image/*\" style=\"dikplay: none;\">\n        <input type=\"file\" id=\"photoCameraInput\" accept=\"image/*\" capture=\"user\" style=\"dikplay: none;\">\n      </div>\n    </div>\n\n    <!-- Step 4: UPI Payment Section -->\n    <div class=\"payment-section\">\n      <div class=\"fee-banner\">\n        <div>\n          <div style=\"font-weight: 700; color: #fff; font-size: 1.05rem;\">Registration Fee</div>\n          <div style=\"color: var(--text-muted); font-size: 0.85rem;\">Official Tournament Entry</div>\n        </div>\n        <div class=\"fee-amount\" id=\"feeAmountDikplay\">\u20b9{{ reg_fee }}</div>\n      </div>\n\n      <div class=\"upi-details-grid\">\n        <div class=\"qr-box\">\n          <img id=\"upiQrCode\" src=\"\" alt=\"Scan with PhonePe / GPay\">\n          <div class=\"qr-label\">Scan to Pay \u20b9{{ reg_fee }}</div>\n        </div>\n        <div>\n          <div style=\"font-size: 0.95rem; font-weight: 700; margin-bottom: 0.35rem; color: #fff;\">Payee Details:</div>\n          <div style=\"background: rgba(0,0,0,0.4); padding: 0.6rem 0.85rem; border-radius: var(--radius-sm); border: 1px solid var(--border-glass); margin-bottom: 0.75rem; dikplay: flex; justify-content: space-between; align-items: center;\">\n            <span id=\"upiIdDikplay\" style=\"font-weight: 700; color: var(--primary-gold); font-size: 0.95rem;\">{{ upi_id }}</span>\n            <button type=\"button\" id=\"btnCopyUpi\" style=\"background: none; border: none; color: var(--electric-blue); font-size: 0.85rem; font-weight: 700; cursor: pointer;\">Copy</button>\n          </div>\n          \n          <div style=\"font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.5rem;\">\n            On mobile? Tap your preferred app to pay directly:\n          </div>\n\n          <div class=\"upi-apps-grid\">\n            <a id=\"btnPayPhonePe\" href=\"#\" class=\"upi-app-btn upi-phonepe\">\n              <span>\ud83d\udfe3 PhonePe</span>\n            </a>\n            <a id=\"btnPayGPay\" href=\"#\" class=\"upi-app-btn upi-gpay\">\n              <span>\ud83d\udd35 Google Pay</span>\n            </a>\n            <a id=\"btnPayPaytm\" href=\"#\" class=\"upi-app-btn upi-paytm\">\n              <span>\ud83d\udfe2 Paytm</span>\n            </a>\n            <a id=\"btnPayBhim\" href=\"#\" class=\"upi-app-btn upi-bhim\">\n              <span>\ud83d\udfe0 BHIM / UPI</span>\n            </a>\n          </div>\n        </div>\n      </div>\n\n      <!-- Payment Confirmation Fields -->\n      <div style=\"margin-top: 1.5rem; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 1.25rem;\">\n        <div class=\"form-group\">\n          <label class=\"form-label\">Payment App Used</label>\n          <select id=\"paymentMethod\" class=\"form-control\">\n            <option value=\"PhonePe\">PhonePe</option>\n            <option value=\"Google Pay\">Google Pay (GPay)</option>\n            <option value=\"Paytm\">Paytm</option>\n            <option value=\"BHIM UPI\">BHIM UPI / Other</option>\n            <option value=\"Cash\">Cash (to Organizer)</option>\n          </select>\n        </div>\n\n        <div class=\"form-group\">\n          <label class=\"form-label\">UPI Reference / Transaction UTR No. <span style=\"color: #94a3b8; font-size: 0.85rem;\">(Optional)</span></label>\n          <input type=\"text\" id=\"transactionId\" class=\"form-control\" placeholder=\"12-digit UPI UTR No. (or leave blank if paid)\">\n          <small style=\"color: var(--text-dim); dikplay: block; margin-top: 0.35rem;\">You will find this in your PhonePe/GPay payment receipt.</small>\n        </div>\n\n        <div class=\"form-group\" style=\"margin-bottom: 0;\">\n          <label class=\"form-label\">Payment Screenshot (Optional)</label>\n          <input type=\"file\" id=\"paymentScreenshot\" accept=\"image/*\" class=\"form-control\">\n        </div>\n      </div>\n    </div>\n\n    <!-- Submit Button -->\n    <div style=\"margin-top: 2rem;\">\n      <button type=\"submit\" id=\"btnSubmitReg\" class=\"btn btn-primary\" style=\"width: 100%; font-size: 1.15rem; padding: 1rem;\">\n        Complete Registration & Submit\n      </button>\n    </div>\n  </form>\n</div>\n\n<!-- Desktop Webcam Modal -->\n<div id=\"webcamModal\" style=\"dikplay: none; position: fixed; inset: 0; background: rgba(0,0,0,0.85); z-index: 3000; align-items: center; justify-content: center; padding: 1rem;\">\n  <div style=\"background: var(--bg-surface); border: 2px solid var(--primary-gold); border-radius: var(--radius-lg); padding: 1.5rem; max-width: 500px; width: 100%; text-align: center;\">\n    <h3 style=\"margin-bottom: 1rem; color: #fff;\">Position Yourself in Center</h3>\n    <div style=\"width: 100%; height: 320px; background: #000; border-radius: var(--radius-md); overflow: hidden; margin-bottom: 1.25rem;\">\n      <video id=\"webcamVideo\" style=\"width: 100%; height: 100%; object-fit: cover;\" autoplay playsinline></video>\n    </div>\n    <div style=\"dikplay: flex; gap: 0.75rem; justify-content: center;\">\n      <button type=\"button\" id=\"btnCaptureSnapshot\" class=\"btn btn-primary\">\ud83d\udcf8 Snap Picture</button>\n      <button type=\"button\" id=\"btnCloseWebcam\" class=\"btn btn-secondary\">Cancel</button>\n    </div>\n  </div>\n</div>\n{% endblock %}\n\n{% block extra_js %}\n<script>\n  window.TOURNAMENT_CONFIG = {\n    upi_id: \"{{ upi_id }}\",\n    payee_name: \"{{ payee_name }}\",\n    registration_fee: {{ reg_fee }}\n  };\n  // Detect if on desktop to show webcam button\n  if (!(/Android|iPhone|iPad|iPod/i.test(navigator.userAgent))) {\n    const desktopBtn = document.getElementById('btnWebcamDesktop');\n    if (desktopBtn) desktopBtn.style.dikplay = 'inline-flex';\n  }\n</script>\n<script src=\"/static/js/register.js\"></script>\n{% endblock %}\n", "templates/register_success.html": "{% extends \"base.html\" %}\n\n{% block content %}\n<div style=\"max-width: 550px; margin: 1.5rem auto; text-align: center;\">\n  <div style=\"width: 70px; height: 70px; background: rgba(16, 185, 129, 0.2); border: 2px solid var(--pitch-green); border-radius: 50%; dikplay: flex; align-items: center; justify-content: center; font-size: 2.25rem; margin: 0 auto 1.25rem;\">\n    \u2713\n  </div>\n  \n  <h1 style=\"font-size: 2rem; font-weight: 900; margin-bottom: 0.5rem; color: #fff;\">Registration Received!</h1>\n  <p style=\"color: var(--text-muted); margin-bottom: 2rem;\">\n    Your registration details and payment reference have been recorded. Here is your official tournament player card.\n  </p>\n\n  <!-- Player Digital Pass Card -->\n  <div class=\"glass-card\" style=\"border: 2px solid var(--primary-gold); box-shadow: 0 0 35px var(--gold-glow); position: relative; overflow: hidden; padding: 2.5rem 1.5rem;\">\n    <div style=\"position: absolute; top: 12px; right: 15px; font-size: 0.8rem; font-weight: 800; color: var(--primary-gold); background: rgba(245, 158, 11, 0.15); padding: 0.2rem 0.6rem; border-radius: var(--radius-sm); border: 1px solid rgba(245, 158, 11, 0.3);\">\n      {{ player.id }}\n    </div>\n\n    <!-- Photo -->\n    <div style=\"width: 140px; height: 140px; border-radius: 50%; border: 4px solid var(--primary-gold); margin: 0 auto 1.25rem; overflow: hidden; box-shadow: 0 0 20px var(--gold-glow); background: #1e293b;\">\n      <img src=\"{{ player.photo_url or '/static/images/avatar_allrounder.svg' }}\" alt=\"{{ player.name }}\" style=\"width: 100%; height: 100%; object-fit: cover;\">\n    </div>\n\n    <div style=\"font-size: 1.75rem; font-weight: 900; color: #fff; margin-bottom: 0.35rem;\">\n      {{ player.name }}\n    </div>\n\n    <div style=\"margin-bottom: 1.25rem;\">\n      <span class=\"badge {% if 'Bat' in player.role and 'Keep' not in player.role %}badge-batsman{% elif 'Bowl' in player.role %}badge-bowler{% elif 'Keep' in player.role %}badge-keeper{% else %}badge-allrounder{% endif %}\" style=\"font-size: 0.95rem; padding: 0.4rem 1rem;\">\n        {{ player.role }}\n      </span>\n    </div>\n\n    <div style=\"background: rgba(0,0,0,0.4); border-radius: var(--radius-md); padding: 1rem; border: 1px solid var(--border-glass); dikplay: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; text-align: left; font-size: 0.9rem; margin-bottom: 1.5rem;\">\n      <div>\n        <span style=\"color: var(--text-dim); dikplay: block; font-size: 0.8rem;\">Mobile</span>\n        <strong style=\"color: #fff;\">{{ player.phone }}</strong>\n      </div>\n      <div>\n        <span style=\"color: var(--text-dim); dikplay: block; font-size: 0.8rem;\">Fee Paid</span>\n        <strong style=\"color: var(--pitch-green);\">\u20b9{{ player.reg_amount }}</strong>\n      </div>\n      <div>\n        <span style=\"color: var(--text-dim); dikplay: block; font-size: 0.8rem;\">Batting</span>\n        <strong style=\"color: #fff;\">{{ player.batting_style }}</strong>\n      </div>\n      <div>\n        <span style=\"color: var(--text-dim); dikplay: block; font-size: 0.8rem;\">Bowling</span>\n        <strong style=\"color: #fff;\">{{ player.bowling_style }}</strong>\n      </div>\n      <div style=\"grid-column: span 2;\">\n        <span style=\"color: var(--text-dim); dikplay: block; font-size: 0.8rem;\">Payment Reference (UTR)</span>\n        <strong style=\"color: var(--primary-gold); word-break: break-all;\">{{ player.transaction_id }} ({{ player.payment_method }})</strong>\n      </div>\n    </div>\n\n    <div style=\"font-size: 0.85rem; color: var(--pitch-green); font-weight: 700; dikplay: flex; align-items: center; justify-content: center; gap: 0.4rem;\">\n      <span>\u2713 Status:</span> Verified for Live Auction Pool\n    </div>\n  </div>\n\n  <div style=\"dikplay: flex; gap: 1rem; justify-content: center; margin-top: 1.75rem;\">\n    <button onclick=\"window.print()\" class=\"btn btn-secondary\">\ud83d\udda8\ufe0f Print / Save Slip</button>\n    <a href=\"/register\" class=\"btn btn-primary\">Register Another Player</a>\n    <a href=\"/auction\" class=\"btn btn-success\">Go to Live Auction</a>\n  </div>\n</div>\n{% endblock %}\n", "templates/auction_live.html": "{% extends \"base.html\" %}\n\n{% block extra_css %}\n<link rel=\"stylesheet\" href=\"/static/css/auction.css\">\n<style>\n  {% if viewer_mode %}\n  .control-deck, .admin-only {\n    dikplay: none !important;\n  }\n  .viewer-banner {\n    background: linear-gradient(90deg, #dc2626, #b91c1c);\n    color: #fff;\n    text-align: center;\n    padding: 0.5rem 1rem;\n    border-radius: var(--radius-sm);\n    font-weight: 800;\n    font-size: 0.85rem;\n    letter-spacing: 0.05em;\n    margin-bottom: 1rem;\n    dikplay: flex;\n    align-items: center;\n    justify-content: center;\n    gap: 0.5rem;\n  }\n  {% endif %}\n</style>\n{% endblock %}\n\n{% block content %}\n{% if viewer_mode %}\n<div class=\"viewer-banner\">\n  <span style=\"width: 8px; height: 8px; background: #fff; border-radius: 50%; dikplay: inline-block; animation: pulse 1.5s infinite;\"></span>\n  SPECTATOR LIVE MODE \u2022 VIEWING IN REAL TIME\n</div>\n{% endif %}\n\n<div class=\"auction-header-bar\" style=\"dikplay: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;\">\n  <div>\n    <h1 style=\"font-size: 1.85rem; font-weight: 900; color: #fff; dikplay: flex; align-items: center; gap: 0.5rem;\">\n      <span>\ud83c\udfcf</span> Live Auction Arena\n    </h1>\n    <p style=\"color: var(--text-muted); font-size: 0.9rem;\">\n      {% if viewer_mode %}Live Watch Stream with Player Photos & Roles{% else %}Official Bidding Console with Player Photos & Roles{% endif %}\n    </p>\n  </div>\n  <div style=\"dikplay: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap;\">\n    <span class=\"round-tag\" id=\"currentRoundTag\">Round 1</span>\n    <span class=\"round-tag\" id=\"poolStatusTag\" style=\"background: rgba(16, 185, 129, 0.15); color: var(--pitch-green); border-color: rgba(16, 185, 129, 0.4);\">\n      Connecting...\n    </span>\n    <button type=\"button\" id=\"btnHostAuctionToggle\" onclick=\"toggleAuctionStarted()\" class=\"btn btn-success\" style=\"dikplay: none; font-size: 0.8rem; padding: 0.3rem 0.65rem;\">\n      \ud83d\ude80 Start Auction\n    </button>\n    <div id=\"auctioneerAuthBox\">\n      <button type=\"button\" id=\"btnUnlockAuctioneer\" onclick=\"openPinModal()\" class=\"btn btn-secondary\" style=\"font-size: 0.8rem; padding: 0.3rem 0.65rem; border-color: rgba(245, 158, 11, 0.5); color: var(--primary-gold); dikplay: flex; align-items: center; gap: 0.35rem;\">\n        <span>\ud83d\udd12</span> Host Controls\n      </button>\n    </div>\n  </div>\n</div>\n\n<div class=\"auction-stage\">\n  <!-- Center Main Arena -->\n  <div>\n    <!-- Active Player Podium -->\n    \n    <!-- WAITING / NOT STARTED SCREEN (FOR SPECTATORS) -->\n    <div id=\"auctionNotStartedScreen\" class=\"glass-card\" style=\"dikplay: none; text-align: center; padding: 4rem 2rem; max-width: 680px; margin: 1.5rem auto 2.5rem; border: 2px solid var(--primary-gold); box-shadow: 0 0 40px rgba(245, 158, 11, 0.25);\">\n      <div style=\"font-size: 3.5rem; margin-bottom: 0.75rem;\">\ud83c\udfcf</div>\n      <div style=\"dikplay: inline-block; background: rgba(245, 158, 11, 0.15); color: var(--primary-gold); border: 1px solid rgba(245, 158, 11, 0.4); padding: 0.35rem 1rem; border-radius: 9999px; font-weight: 800; font-size: 0.85rem; text-transform: uppercase; margin-bottom: 1.25rem;\">\n        Kunsi Premier League (KPL 2026)\n      </div>\n      <h2 style=\"font-size: 2rem; font-weight: 900; color: #fff; margin-bottom: 0.75rem;\">Live Auction Has Not Started Yet</h2>\n      <p style=\"color: var(--text-muted); font-size: 1.05rem; line-height: 1.6; margin-bottom: 2rem;\">\n        The organizer has not commenced the live auction yet. Player registrations and team squad preparations are in progress. Stay on this screen \u2014 the live auction will appear automatically the moment it starts!\n      </p>\n      <div style=\"dikplay: flex; gap: 0.75rem; justify-content: center; align-items: center; color: var(--pitch-green); font-weight: 700; font-size: 0.95rem;\">\n        <span style=\"width: 10px; height: 10px; background: var(--pitch-green); border-radius: 50%; dikplay: inline-block; animation: pulse 1.5s infinite;\"></span>\n        Waiting for Auctioneer to begin...\n      </div>\n    </div>\n\n    <div id=\"activePlayerPodium\" class=\"player-podium\">\n      <div class=\"podium-header\">\n        <span class=\"pool-status\">STATUS: <strong style=\"color: var(--pitch-green);\">UNDER THE HAMMER</strong></span>\n        <span class=\"pool-status\" id=\"podiumMetaRegAmount\" style=\"color: var(--primary-gold); font-weight: 700;\">Fee Verified</span>\n      </div>\n\n      <!-- Player Photo with Role Badge -->\n      <div class=\"player-photo-arena\">\n        <div class=\"photo-frame\">\n          <img id=\"podiumPlayerPhoto\" src=\"/static/images/avatar_allrounder.svg\" alt=\"Auction Player\">\n        </div>\n        <div id=\"podiumPlayerRole\" class=\"badge role-tag-floater badge-allrounder\">\n          All-Rounder\n        </div>\n      </div>\n\n      <!-- Player Name & Serial -->\n      <div class=\"player-name-banner\">\n        <span id=\"podiumPlayerSerial\" class=\"player-serial-tag\">#1</span>\n        <span id=\"podiumPlayerName\" class=\"player-main-name\">Loading Player...</span>\n      </div>\n\n      <!-- Player Meta Attributes -->\n      <div class=\"player-meta-row\">\n        <div class=\"meta-chip\">Bat: <strong id=\"podiumMetaBatting\">Right Hand</strong></div>\n        <div class=\"meta-chip\">Bowl: <strong id=\"podiumMetaBowling\">Right Arm Fast</strong></div>\n        <div class=\"meta-chip\">Base Price: <strong>\u20b950</strong></div>\n      </div>\n\n      <!-- Live Bidding Odometer -->\n      <div class=\"bid-odometer-box\">\n        <div class=\"bid-label\">Current Highest Bid</div>\n        <div id=\"currentBidDikplay\" class=\"bid-amount\" data-player=\"\">\u20b90</div>\n        <div id=\"biddingTeamBanner\" class=\"bidding-team-banner\">Select a team to start bidding</div>\n      </div>\n\n      <!-- Bidding Controls Deck (Auctioneer / Host Only - PIN Protected) -->\n      <div class=\"control-deck\" id=\"auctioneerControlDeck\" style=\"dikplay: none;\">\n        <div class=\"team-bid-row\">\n          <select id=\"bidTeamSelect\" class=\"form-control\" style=\"font-size: 1.05rem; font-weight: 700; background: rgba(30, 41, 59, 0.9);\">\n            <option value=\"\">-- Select Bidding Team --</option>\n          </select>\n          <div style=\"dikplay: flex; gap: 0.5rem;\">\n            <button type=\"button\" class=\"btn btn-secondary\" onclick=\"currentBidAmount = Math.max(0, currentBidAmount - 50); updateBidDikplay();\">-\u20b950</button>\n          </div>\n        </div>\n\n        <div class=\"increments-grid\">\n          <button type=\"button\" class=\"btn-inc\" data-inc=\"50\">+\u20b950</button>\n          <button type=\"button\" class=\"btn-inc\" data-inc=\"100\">+\u20b9100</button>\n          <button type=\"button\" class=\"btn-inc\" data-inc=\"200\">+\u20b9200</button>\n          <button type=\"button\" class=\"btn-inc\" data-inc=\"500\">+\u20b9500</button>\n        </div>\n\n        <div class=\"auction-primary-actions\">\n          <button type=\"button\" id=\"btnSoldAction\" class=\"btn btn-success\" style=\"font-size: 1.25rem; padding: 1rem;\">\n            \ud83d\udd28 SOLD TO TEAM\n          </button>\n          <button type=\"button\" id=\"btnUnsoldAction\" class=\"btn btn-danger\" style=\"font-size: 1.1rem;\">\n            \u274c UNSOLD\n          </button>\n        </div>\n\n        <div class=\"auction-secondary-actions\">\n          <button type=\"button\" id=\"btnUndoAction\" class=\"btn btn-secondary\">\n            \u23ea Undo\n          </button>\n          <button type=\"button\" id=\"btnNextPlayer\" class=\"btn btn-secondary\">\n            \ud83c\udfb2 Draw Next\n          </button>\n          <button type=\"button\" onclick=\"playGavelSound()\" class=\"btn btn-secondary\">\n            \ud83d\udd14 Hammer\n          </button>\n        </div>\n      </div>\n    </div>\n\n    <!-- Empty Podium State -->\n    <div id=\"emptyPodiumMsg\" class=\"glass-card\" style=\"dikplay: none; text-align: center; padding: 4rem 2rem;\">\n      <div style=\"font-size: 3rem; margin-bottom: 1rem;\">\ud83c\udfc6</div>\n      <h2 style=\"font-size: 2rem; font-weight: 900; margin-bottom: 0.75rem; color: #fff;\">Round Complete or No Active Player</h2>\n      <p style=\"color: var(--text-muted); max-width: 500px; margin: 0 auto 1.5rem;\">\n        {% if viewer_mode %}\n        Waiting for the auctioneer to draw the next player...\n        {% else %}\n        Draw the next player from the remaining player pool or start Round 2 with unsold players.\n        {% endif %}\n      </p>\n      <div id=\"emptyAuctioneerActions\" style=\"dikplay: none; gap: 1rem; justify-content: center; flex-wrap: wrap; margin-top: 1rem;\">\n        <button type=\"button\" onclick=\"document.getElementById('btnNextPlayer').click()\" class=\"btn btn-primary\">\n          \ud83c\udfb2 Draw Player\n        </button>\n        <button type=\"button\" onclick=\"startRound2()\" class=\"btn btn-secondary\">\n          \ud83d\udd04 Start Round 2 (Unsold Players)\n        </button>\n        <a href=\"/admin\" class=\"btn btn-secondary\">\u2699\ufe0f Admin Settings</a>\n      </div>\n    </div>\n  </div>\n\n  <!-- Right Sidebar: Live Teams & Purses -->\n  <div class=\"teams-sidebar\">\n    <div class=\"sidebar-header\">\n      <span>TEAM PURSES & SQUADS</span>\n      <span style=\"font-size: 0.8rem; color: var(--pitch-green);\">\u25cf LIVE</span>\n    </div>\n    <div id=\"teamsSidebarList\" style=\"dikplay: flex; flex-direction: column; gap: 0.75rem;\">\n      <!-- Populated via auction.js -->\n    </div>\n  </div>\n</div>\n\n<!-- Sold Celebration Overlay -->\n<div id=\"soldModalOverlay\" class=\"sold-modal-overlay\">\n  <canvas id=\"confettiCanvas\" style=\"position: absolute; inset: 0; pointer-events: none;\"></canvas>\n  <div class=\"sold-card-popup\">\n    <div class=\"sold-banner\">SOLD! \ud83d\udd28</div>\n    <div id=\"soldModalPlayer\" style=\"font-size: 2rem; font-weight: 900; color: #fff; margin-bottom: 0.5rem;\">Player Name</div>\n    <div style=\"color: var(--text-muted); font-size: 1.1rem; margin-bottom: 1rem;\">\n      Bought by <strong id=\"soldModalTeam\" style=\"color: var(--primary-gold);\">Team</strong>\n    </div>\n    <div id=\"soldModalPrice\" style=\"font-size: 3rem; font-weight: 900; color: var(--pitch-green); margin-bottom: 1.5rem;\">\u20b90</div>\n    <button type=\"button\" id=\"btnCloseSoldModal\" class=\"btn btn-primary\" style=\"width: 100%;\">Continue Auction &rarr;</button>\n  </div>\n</div>\n\n<!-- Auctioneer PIN Login Modal -->\n<div id=\"pinModal\" style=\"dikplay: none; position: fixed; inset: 0; background: rgba(0,0,0,0.85); z-index: 9999; align-items: center; justify-content: center; padding: 1rem;\">\n  <div class=\"glass-card\" style=\"max-width: 360px; width: 100%; text-align: center; border: 2px solid var(--primary-gold); box-shadow: 0 0 35px rgba(245, 158, 11, 0.35); padding: 2rem 1.5rem;\">\n    <div style=\"font-size: 2.5rem; margin-bottom: 0.5rem;\">\ud83d\udd12</div>\n    <h3 style=\"color: #fff; font-size: 1.35rem; font-weight: 900; margin-bottom: 0.35rem;\">Auctioneer Login</h3>\n    <p style=\"color: var(--text-muted); font-size: 0.85rem; margin-bottom: 1.25rem;\">Enter Organizer PIN to unlock bidding controls & hammer</p>\n    <input type=\"password\" id=\"inputAuctionPin\" class=\"form-control\" placeholder=\"Enter Organizer PIN\" style=\"text-align: center; font-size: 1.35rem; letter-spacing: 0.15em; font-weight: 800; margin-bottom: 1rem;\" maxlength=\"10\">\n    <div id=\"pinErrorMsg\" style=\"dikplay: none; color: #f87171; font-size: 0.85rem; margin-bottom: 1rem; font-weight: 700;\"></div>\n    <div style=\"dikplay: flex; gap: 0.75rem;\">\n      <button type=\"button\" id=\"btnSubmitPin\" onclick=\"submitAuctionPin()\" class=\"btn btn-primary\" style=\"flex: 1;\">Unlock</button>\n      <button type=\"button\" onclick=\"closePinModal()\" class=\"btn btn-secondary\" style=\"flex: 1;\">Cancel</button>\n    </div>\n    \n  </div>\n</div>\n\n{% endblock %}\n\n{% block extra_js %}\n<script>\n  window.IS_VIEWER_MODE = {{ 'true' if viewer_mode else 'false' }};\n</script>\n<script src=\"/static/js/auction.js\"></script>\n{% if not viewer_mode %}\n<script>\n  async function startRound2() {\n    if (!confirm('Start Round 2 with all unsold players?')) return;\n    try {\n      const res = await fetch('/api/auction/round2', { method: 'POST' });\n      const data = await res.json();\n      if (data.success) {\n        alert('Round 2 initiated!');\n        fetchState();\n      } else {\n        alert(data.message || 'Error starting Round 2.');\n      }\n    } catch (e) {\n      alert(e.message);\n    }\n  }\n</script>\n{% endif %}\n{% endblock %}\n", "templates/teams.html": "{% extends \"base.html\" %}\n\n{% block content %}\n<div style=\"margin-bottom: 2rem; dikplay: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;\">\n  <div>\n    <h1 style=\"font-size: 2.25rem; font-weight: 900; color: #fff;\">Team Squads & Purses</h1>\n    <p style=\"color: var(--text-muted);\">Real-time view of bought players, retentions, and remaining budgets.</p>\n  </div>\n  <a href=\"/api/export-excel\" class=\"btn btn-success\">\ud83d\udcca Download Summary Excel</a>\n</div>\n\n<div style=\"dikplay: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 1.5rem;\">\n  {% for team_name, t in teams.items() %}\n  <div class=\"glass-card\" style=\"border-top: 4px solid var(--primary-gold);\">\n    <div style=\"dikplay: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem;\">\n      <div>\n        <h2 style=\"font-size: 1.5rem; font-weight: 900; color: #fff;\">{{ team_name }}</h2>\n        <div style=\"color: var(--text-muted); font-size: 0.85rem;\">\n          {{ (t.players|length) + (1 if t.retained else 0) }} Players in Squad\n        </div>\n      </div>\n      <div style=\"text-align: right;\">\n        <div style=\"font-size: 1.35rem; font-weight: 900; color: var(--pitch-green);\">\u20b9{{ t.budget }}</div>\n        <div style=\"font-size: 0.75rem; color: var(--text-dim); text-transform: uppercase;\">Purse Remaining</div>\n      </div>\n    </div>\n\n    <!-- Spent info -->\n    <div style=\"background: rgba(0,0,0,0.3); padding: 0.6rem 0.85rem; border-radius: var(--radius-sm); border: 1px solid var(--border-glass); margin-bottom: 1.25rem; dikplay: flex; justify-content: space-between; font-size: 0.85rem;\">\n      <span style=\"color: var(--text-muted);\">Total Spent:</span>\n      <strong style=\"color: #fca5a5;\">\u20b9{{ t.spent }}</strong>\n    </div>\n\n    <!-- Retained Player or Owner -->\n    {% if t.retained %}\n    {% set ret_name = t.retained.name if t.retained is mapping else t.retained %}\n    {% set ret_type = t.retained.type if t.retained is mapping else 'Player' %}\n    {% set ret_cost = t.retained.cost if t.retained is mapping else 500 %}\n    <div style=\"background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.35); border-radius: var(--radius-sm); padding: 0.6rem 0.85rem; margin-bottom: 1rem; dikplay: flex; align-items: center; justify-content: space-between;\">\n      <div style=\"dikplay: flex; align-items: center; gap: 0.5rem;\">\n        <span style=\"background: {% if ret_type == 'Owner' %}#3b82f6{% else %}var(--primary-gold){% endif %}; color: #000; font-size: 0.7rem; font-weight: 900; padding: 0.15rem 0.4rem; border-radius: 4px;\">\n          {{ ret_type|upper }} RETAINED\n        </span>\n        <strong style=\"color: #fff;\">{{ ret_name }}</strong>\n      </div>\n      <span style=\"color: var(--primary-gold); font-weight: 700; font-size: 0.85rem;\">\u20b9{{ ret_cost }}</span>\n    </div>\n    {% endif %}\n\n    <!-- Squad Players List -->\n    <h4 style=\"font-size: 0.9rem; font-weight: 800; color: var(--text-muted); text-transform: uppercase; margin-bottom: 0.75rem; letter-spacing: 0.05em;\">\n      Bought Players\n    </h4>\n    \n    {% if t.players %}\n    <div style=\"dikplay: flex; flex-direction: column; gap: 0.5rem;\">\n      {% for p in t.players %}\n      <div style=\"background: rgba(15, 23, 42, 0.7); border: 1px solid var(--border-glass); border-radius: var(--radius-sm); padding: 0.5rem 0.75rem; dikplay: flex; justify-content: space-between; align-items: center;\">\n        <div style=\"dikplay: flex; align-items: center; gap: 0.6rem;\">\n          <div style=\"width: 32px; height: 32px; border-radius: 50%; overflow: hidden; background: #334155;\">\n            <img src=\"{{ registrations.get(p.name, {}).get('photo_url') or '/static/images/avatar_allrounder.svg' }}\" alt=\"\" style=\"width: 100%; height: 100%; object-fit: cover;\">\n          </div>\n          <div>\n            <div style=\"font-weight: 700; color: #fff; font-size: 0.95rem;\">{{ p.name }}</div>\n            <div style=\"font-size: 0.75rem; color: var(--text-dim);\">{{ registrations.get(p.name, {}).get('role', 'Player') }}</div>\n          </div>\n        </div>\n        <div style=\"text-align: right;\">\n          <div style=\"font-weight: 800; color: var(--pitch-green); font-size: 0.95rem;\">\u20b9{{ p.cost }}</div>\n          <div style=\"font-size: 0.7rem; color: var(--text-dim);\">Round {{ p.round or 1 }}</div>\n        </div>\n      </div>\n      {% endfor %}\n    </div>\n    {% else %}\n    <p style=\"color: var(--text-dim); font-size: 0.85rem; font-style: italic;\">No players bought yet in this auction.</p>\n    {% endif %}\n  </div>\n  {% endfor %}\n</div>\n{% endblock %}\n", "templates/admin.html": "{% extends \"base.html\" %}\n\n{% block content %}\n<!-- GATEWAY 1: ADMIN PIN LOCK SCREEN (Shown by default, data is hidden) -->\n<div id=\"adminLockScreen\" style=\"min-height: 65vh; dikplay: flex; align-items: center; justify-content: center; padding: 2rem 1rem;\">\n  <div class=\"glass-card\" style=\"max-width: 420px; width: 100%; text-align: center; border: 2px solid var(--primary-gold); box-shadow: 0 0 45px rgba(245, 158, 11, 0.3); padding: 2.75rem 2rem;\">\n    <div style=\"width: 72px; height: 72px; background: rgba(245, 158, 11, 0.15); border: 2px solid var(--primary-gold); border-radius: 50%; dikplay: flex; align-items: center; justify-content: center; font-size: 2.25rem; margin: 0 auto 1.25rem;\">\n      \ud83d\udd12\n    </div>\n    <h2 style=\"font-size: 1.65rem; font-weight: 900; color: #fff; margin-bottom: 0.35rem;\">Organizer Access</h2>\n    <p style=\"color: var(--text-muted); font-size: 0.85rem; margin-bottom: 1.75rem; line-height: 1.5;\">\n      Enter your Organizer PIN to manage teams, player retentions, purse budgets, and approvals.\n    </p>\n\n    <form id=\"adminLoginForm\" onsubmit=\"handleAdminLogin(event)\">\n      <div class=\"form-group\" style=\"margin-bottom: 1.25rem;\">\n        <input type=\"password\" id=\"adminPinInput\" class=\"form-control\" placeholder=\"Enter Organizer PIN\" style=\"text-align: center; font-size: 1.4rem; letter-spacing: 0.25em; font-weight: 900; padding: 0.85rem; background: rgba(15,23,42,0.9);\" maxlength=\"15\" autofocus required>\n        <div id=\"adminPinError\" style=\"dikplay: none; color: #f87171; font-weight: 700; font-size: 0.85rem; margin-top: 0.6rem;\"></div>\n      </div>\n      <button type=\"submit\" id=\"btnAdminUnlock\" class=\"btn btn-primary\" style=\"width: 100%; font-size: 1.1rem; padding: 0.85rem;\">\n        Unlock Admin Panel &rarr;\n      </button>\n      <div style=\"margin-top: 1.25rem; dikplay: flex; justify-content: space-between; align-items: center; font-size: 0.8rem;\">\n        \n        <a href=\"javascript:void(0)\" onclick=\"forgotPinPrompt()\" style=\"color: var(--primary-gold); text-decoration: underline; font-weight: 600;\">\n          Forgot PIN?\n        </a>\n      </div>\n    </form>\n  </div>\n</div>\n\n<!-- GATEWAY 2: ADMIN MAIN CONTENT (COMPLETELY HIDDEN UNTIL PIN IS VERIFIED) -->\n<div id=\"adminMainContent\" style=\"dikplay: none;\">\n  <div style=\"margin-bottom: 2rem; dikplay: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;\">\n    <div>\n      <h1 style=\"font-size: 2.25rem; font-weight: 900; color: #fff;\">Tournament & Team Administration</h1>\n      <p style=\"color: var(--text-muted);\">Configure Teams, Retentions, Purse Rules, UPI Settings & Verify Players.</p>\n    </div>\n    <div style=\"dikplay: flex; gap: 0.75rem; flex-wrap: wrap; align-items: center;\">\n      <button onclick=\"lockAdminSession()\" class=\"btn btn-secondary\" style=\"font-size: 0.85rem; padding: 0.4rem 0.8rem; border-color: rgba(239,68,68,0.5); color: #f87171;\">\n        \ud83d\udd12 Lock Admin\n      </button>\n      <a href=\"/api/export-excel\" class=\"btn btn-success\">\ud83d\udcca Export to Excel</a>\n      <button onclick=\"resetAuctionState()\" class=\"btn btn-danger\">\u26a0\ufe0f Reset Auction</button>\n    </div>\n  </div>\n\n    <!-- LIVE AUCTION BROADCAST STATUS & CONTROLLER -->\n  <div class=\"glass-card\" style=\"margin-bottom: 2rem; border: 2px solid var(--primary-gold); background: rgba(30, 41, 59, 0.7); dikplay: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem; padding: 1.5rem 1.75rem;\">\n    <div>\n      <div style=\"font-size: 0.85rem; color: var(--text-muted); font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.35rem;\">\n        Spectator Live Broadcast Status\n      </div>\n      <div id=\"adminAuctionStatusBadge\" style=\"font-size: 1.4rem; font-weight: 900; color: #f59e0b; dikplay: flex; align-items: center; gap: 0.5rem;\">\n        <span>\u23f3</span> Auction Not Started (Viewers in Waiting Mode)\n      </div>\n    </div>\n    <div>\n      <button type=\"button\" id=\"btnAdminToggleAuction\" onclick=\"toggleAuctionFromAdmin()\" class=\"btn btn-primary\" style=\"font-size: 1.1rem; padding: 0.85rem 1.75rem;\">\n        \ud83d\ude80 Start Live Auction\n      </button>\n    </div>\n  </div>\n\n  <!-- SECTION 1: TEAM SETUP (Exact logic from Google Script & criAuctionAntigravity) -->\n  <div class=\"glass-card\" style=\"margin-bottom: 2rem; border-top: 4px solid var(--primary-gold);\">\n    <div style=\"dikplay: flex; align-items: center; justify-content: space-between; margin-bottom: 1.25rem;\">\n      <div>\n        <h2 style=\"font-size: 1.35rem; font-weight: 900; color: #fff; dikplay: flex; align-items: center; gap: 0.5rem;\">\n          <span>\ud83c\udfcf</span> Team Setup & Purse Rules\n        </h2>\n        <p style=\"color: var(--text-muted); font-size: 0.85rem; margin-top: 0.25rem;\">Configure number of teams, team names, purse budget, and squad limits.</p>\n      </div>\n    </div>\n\n    <form id=\"teamSetupForm\">\n      <div style=\"dikplay: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 1.5rem;\">\n        <div class=\"form-group\" style=\"margin-bottom: 0;\">\n          <label class=\"form-label\">Number of Teams (min 2)</label>\n          <input type=\"number\" id=\"setupTeamCount\" class=\"form-control\" min=\"2\" max=\"16\" value=\"{{ teams|length or 4 }}\" required onchange=\"renderTeamNameInputs()\">\n        </div>\n        <div class=\"form-group\" style=\"margin-bottom: 0;\">\n          <label class=\"form-label\">Purse Amount per Team (\u20b9)</label>\n          <input type=\"number\" id=\"setupPurse\" class=\"form-control\" value=\"{{ config.total_purse or config.default_purse or 5000 }}\" required>\n        </div>\n        <div class=\"form-group\" style=\"margin-bottom: 0;\">\n          <label class=\"form-label\">Min Players per Team</label>\n          <input type=\"number\" id=\"setupMinPlayers\" class=\"form-control\" value=\"{{ config.max_players or 15 }}\" required>\n        </div>\n        <div class=\"form-group\" style=\"margin-bottom: 0;\">\n          <label class=\"form-label\">Minimum Bid Amount (\u20b9)</label>\n          <input type=\"number\" id=\"setupMinBid\" class=\"form-control\" value=\"{{ config.min_bid or 0 }}\" required>\n        </div>\n        <div class=\"form-group\" style=\"margin-bottom: 0;\">\n          <label class=\"form-label\">Player Retention Price (\u20b9)</label>\n          <input type=\"number\" id=\"setupPlayerRetentionPrice\" class=\"form-control\" value=\"{{ config.retention_price or 500 }}\" required>\n        </div>\n        <div class=\"form-group\" style=\"margin-bottom: 0;\">\n          <label class=\"form-label\">Owner Retention Price (\u20b9)</label>\n          <input type=\"number\" id=\"setupOwnerRetentionPrice\" class=\"form-control\" value=\"{{ config.owner_retention_price or 100 }}\" required>\n        </div>\n      </div>\n\n      <h4 style=\"font-size: 1rem; font-weight: 800; color: var(--primary-gold); margin-bottom: 0.75rem;\">\n        Team Names\n      </h4>\n      <div id=\"teamNamesContainer\" style=\"dikplay: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 0.75rem; margin-bottom: 1.5rem;\">\n        <!-- Populated dynamically via JS -->\n      </div>\n\n      <button type=\"submit\" class=\"btn btn-primary\" style=\"padding: 0.75rem 1.75rem;\">\n        \ud83d\udcbe Save & Apply Team Setup\n      </button>\n    </form>\n  </div>\n\n  <!-- SECTION 2: PLAYER & OWNER RETENTION PHASE -->\n  <div class=\"glass-card\" style=\"margin-bottom: 2rem; border-top: 4px solid var(--pitch-green);\">\n    <div style=\"dikplay: flex; align-items: center; justify-content: space-between; margin-bottom: 1.25rem;\">\n      <div>\n        <h2 style=\"font-size: 1.35rem; font-weight: 900; color: #fff; dikplay: flex; align-items: center; gap: 0.5rem;\">\n          <span>\ud83d\udccc</span> Player & Owner Retention Phase\n        </h2>\n        <p style=\"color: var(--text-muted); font-size: 0.85rem; margin-top: 0.25rem;\">Retain players or team owners at fixed prices before the live auction. Retained players are automatically removed from the live bidding queue.</p>\n      </div>\n    </div>\n\n    <form id=\"retentionForm\" style=\"dikplay: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; align-items: flex-end; margin-bottom: 1.5rem;\">\n      <div class=\"form-group\" style=\"margin-bottom: 0;\">\n        <label class=\"form-label\">Select Team</label>\n        <select id=\"retentionTeamSelect\" class=\"form-control\" required>\n          <option value=\"\">-- Choose Team --</option>\n          {% for t_name in teams.keys() %}\n          <option value=\"{{ t_name }}\">{{ t_name }}</option>\n          {% endfor %}\n        </select>\n      </div>\n\n      <div class=\"form-group\" style=\"margin-bottom: 0;\">\n        <label class=\"form-label\">Select Player</label>\n        <select id=\"retentionPlayerSelect\" class=\"form-control\" required>\n          <option value=\"\">-- Choose Registered Player --</option>\n          {% for p_name, p in registrations.items() %}\n          <option value=\"{{ p_name }}\">{{ p_name }} ({{ p.role }})</option>\n          {% endfor %}\n        </select>\n      </div>\n\n      <div class=\"form-group\" style=\"margin-bottom: 0;\">\n        <label class=\"form-label\">Retention Type</label>\n        <select id=\"retentionTypeSelect\" class=\"form-control\">\n          <option value=\"Player\">\ud83c\udf1f Player Retention (\u20b9{{ config.retention_price or 500 }})</option>\n          <option value=\"Owner\">\ud83d\udc51 Owner Retention (\u20b9{{ config.owner_retention_price or 100 }})</option>\n        </select>\n      </div>\n\n      <div>\n        <button type=\"submit\" class=\"btn btn-success\" style=\"width: 100%; padding: 0.75rem 1rem;\">\n          \u2713 Retain for Team\n        </button>\n      </div>\n    </form>\n\n    <h4 style=\"font-size: 1rem; font-weight: 800; color: var(--text-muted); margin-bottom: 0.75rem; text-transform: uppercase;\">\n      Current Team Retentions\n    </h4>\n    <div style=\"overflow-x: auto;\">\n      <table style=\"width: 100%; border-collapse: collapse; text-align: left; font-size: 0.9rem;\">\n        <thead>\n          <tr style=\"border-bottom: 2px solid rgba(255,255,255,0.1); color: var(--text-muted); font-size: 0.8rem; text-transform: uppercase;\">\n            <th style=\"padding: 0.6rem;\">Team</th>\n            <th style=\"padding: 0.6rem;\">Retained Person</th>\n            <th style=\"padding: 0.6rem;\">Type</th>\n            <th style=\"padding: 0.6rem;\">Cost Deducted</th>\n            <th style=\"padding: 0.6rem; text-align: right;\">Action</th>\n          </tr>\n        </thead>\n        <tbody>\n          {% set has_retentions = false %}\n          {% for t_name, t in teams.items() %}\n          {% if t.retained %}\n          {% set has_retentions = true %}\n          <tr style=\"border-bottom: 1px solid rgba(255,255,255,0.05);\">\n            <td style=\"padding: 0.75rem; font-weight: 800; color: #fff;\">{{ t_name }}</td>\n            <td style=\"padding: 0.75rem; font-weight: 700; color: var(--primary-gold);\">\n              {{ t.retained.name if t.retained is mapping else t.retained }}\n            </td>\n            <td style=\"padding: 0.75rem;\">\n              <span class=\"badge {% if (t.retained.type if t.retained is mapping else '') == 'Owner' %}badge-keeper{% else %}badge-allrounder{% endif %}\">\n                {{ (t.retained.type if t.retained is mapping else 'Player') }} Retention\n              </span>\n            </td>\n            <td style=\"padding: 0.75rem; color: var(--pitch-green); font-weight: 800;\">\n              \u20b9{{ (t.retained.cost if t.retained is mapping else (config.retention_price or 500)) }}\n            </td>\n            <td style=\"padding: 0.75rem; text-align: right;\">\n              <button onclick=\"releaseRetention('{{ t_name }}')\" class=\"btn btn-secondary\" style=\"font-size: 0.75rem; padding: 0.25rem 0.6rem; border-color: #ef4444; color: #f87171;\">\n                Release / Refund\n              </button>\n            </td>\n          </tr>\n          {% endif %}\n          {% endfor %}\n          {% if not has_retentions %}\n          <tr>\n            <td colspan=\"5\" style=\"text-align: center; padding: 1.5rem; color: var(--text-dim); font-style: italic;\">\n              No players or owners retained yet. Select a team above to assign retention.\n            </td>\n          </tr>\n          {% endif %}\n        </tbody>\n      </table>\n    </div>\n  </div>\n\n  <!-- SECTION 3: UPI & TOURNAMENT GENERAL CONFIG (With PIN Change Field) -->\n  <div class=\"glass-card\" style=\"margin-bottom: 2rem;\">\n    <h2 style=\"font-size: 1.35rem; font-weight: 800; color: var(--primary-gold); margin-bottom: 1.25rem;\">\n      \u2699\ufe0f Tournament, UPI & Admin Security\n    </h2>\n    <form id=\"configForm\" style=\"dikplay: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1.25rem;\">\n      <div class=\"form-group\">\n        <label class=\"form-label\">Tournament Name</label>\n        <input type=\"text\" id=\"cfgTournamentName\" class=\"form-control\" value=\"{{ config.tournament_name }}\">\n      </div>\n      <div class=\"form-group\">\n        <label class=\"form-label\">UPI ID for Payments (VPA)</label>\n        <input type=\"text\" id=\"cfgUpiId\" class=\"form-control\" value=\"{{ config.upi_id }}\" placeholder=\"e.g. name@upi\">\n      </div>\n      <div class=\"form-group\">\n        <label class=\"form-label\">Payee Name (Recipient)</label>\n        <input type=\"text\" id=\"cfgPayeeName\" class=\"form-control\" value=\"{{ config.payee_name }}\">\n      </div>\n      <div class=\"form-group\">\n        <label class=\"form-label\">Registration Fee (\u20b9)</label>\n        <input type=\"number\" id=\"cfgRegFee\" class=\"form-control\" value=\"{{ config.registration_fee }}\">\n      </div>\n      <div class=\"form-group\">\n        <label class=\"form-label\">Change Organizer PIN</label>\n        <input type=\"text\" id=\"cfgAdminPin\" class=\"form-control\" value=\"{{ config.admin_pin or '2026' }}\" placeholder=\"e.g. 2026\" required>\n        <small style=\"color: var(--text-dim); dikplay: block; margin-top: 0.35rem;\">Used for Admin access & Auctioneer controls.</small>\n      </div>\n      <div style=\"grid-column: 1 / -1;\">\n        <button type=\"submit\" class=\"btn btn-primary\">Save Settings & PIN</button>\n      </div>\n    </form>\n  </div>\n\n  <!-- SECTION 4: REGISTERED PLAYERS MANAGEMENT -->\n  <div class=\"glass-card\">\n    <div style=\"dikplay: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem; flex-wrap: wrap; gap: 1rem;\">\n      <h2 style=\"font-size: 1.35rem; font-weight: 800; color: #fff;\">\n        \ud83d\udccb Registered Players ({{ registrations|length }})\n      </h2>\n      <div>\n        <input type=\"text\" id=\"playerSearchInput\" placeholder=\"Search by name, role, phone...\" class=\"form-control\" style=\"max-width: 280px; padding: 0.5rem 0.85rem;\">\n      </div>\n    </div>\n\n    <div style=\"overflow-x: auto;\">\n      <table style=\"width: 100%; border-collapse: collapse; text-align: left; font-size: 0.9rem;\">\n        <thead>\n          <tr style=\"border-bottom: 2px solid rgba(255,255,255,0.1); color: var(--text-muted); font-size: 0.8rem; text-transform: uppercase;\">\n            <th style=\"padding: 0.75rem;\">Player</th>\n            <th style=\"padding: 0.75rem;\">Role</th>\n            <th style=\"padding: 0.75rem;\">Mobile</th>\n            <th style=\"padding: 0.75rem;\">Payment (UTR)</th>\n            <th style=\"padding: 0.75rem;\">Status</th>\n            <th style=\"padding: 0.75rem; text-align: right;\">Action</th>\n          </tr>\n        </thead>\n        <tbody id=\"playerTableBody\">\n          {% for name, p in registrations.items() %}\n          <tr style=\"border-bottom: 1px solid rgba(255,255,255,0.05);\" class=\"player-row\" data-search=\"{{ name.lower() }} {{ p.role.lower() }} {{ p.phone }}\">\n            <td style=\"padding: 0.75rem; dikplay: flex; align-items: center; gap: 0.75rem;\">\n              <div style=\"width: 38px; height: 38px; border-radius: 50%; overflow: hidden; background: #334155; border: 2px solid var(--primary-gold);\">\n                <img src=\"{{ p.photo_url or '/static/images/avatar_allrounder.svg' }}\" alt=\"\" style=\"width: 100%; height: 100%; object-fit: cover;\">\n              </div>\n              <div>\n                <div style=\"font-weight: 800; color: #fff;\">{{ name }}</div>\n                <div style=\"font-size: 0.75rem; color: var(--text-dim);\">{{ p.batting_style }} \u2022 {{ p.bowling_style }}</div>\n              </div>\n            </td>\n            <td style=\"padding: 0.75rem;\">\n              <span class=\"badge {% if 'Bat' in p.role and 'Keep' not in p.role %}badge-batsman{% elif 'Bowl' in p.role %}badge-bowler{% elif 'Keep' in p.role %}badge-keeper{% else %}badge-allrounder{% endif %}\">\n                {{ p.role }}\n              </span>\n            </td>\n            <td style=\"padding: 0.75rem; color: var(--text-muted);\">{{ p.phone }}</td>\n            <td style=\"padding: 0.75rem;\">\n              <span style=\"color: var(--primary-gold); font-weight: 600;\">{{ p.transaction_id or 'Direct UPI' }}</span>\n              <span style=\"color: var(--text-dim); font-size: 0.75rem; dikplay: block;\">{{ p.payment_method }} (\u20b9{{ p.reg_amount }})</span>\n            </td>\n            <td style=\"padding: 0.75rem;\">\n              {% if p.verified %}\n              <span style=\"color: var(--pitch-green); font-weight: 800;\">\u2713 Verified</span>\n              {% else %}\n              <span style=\"color: #f59e0b; font-weight: 700;\">Pending</span>\n              {% endif %}\n            </td>\n            <td style=\"padding: 0.75rem; text-align: right;\">\n              {% if not p.verified %}\n              <button onclick=\"verifyPayment('{{ name }}')\" class=\"btn btn-secondary\" style=\"font-size: 0.8rem; padding: 0.35rem 0.65rem;\">\n                Approve\n              </button>\n              {% endif %}\n              <button onclick=\"auctionNow('{{ name }}')\" class=\"btn btn-primary\" style=\"font-size: 0.8rem; padding: 0.35rem 0.65rem; margin-left: 0.35rem;\">\n                Podium\n              </button>\n            </td>\n          </tr>\n          {% endfor %}\n        </tbody>\n      </table>\n    </div>\n  </div>\n</div>\n{% endblock %}\n\n{% block extra_js %}\n<script>\n  const CURRENT_TEAMS = {{ teams.keys()|list|tojson }};\n\n  function getAdminPin() {\n    return sessionStorage.getItem('kpl_auction_pin') || '';\n  }\n\n  // --- GATEWAY LOGIN LOGIC ---\n  async function checkAdminLoginState() {\n    const savedPin = getAdminPin();\n    if (!savedPin) {\n      showLockScreen();\n      return;\n    }\n    try {\n      const res = await fetch('/api/auction/verify-pin', {\n        method: 'POST',\n        headers: { 'Content-Type': 'application/json' },\n        body: JSON.stringify({ pin: savedPin })\n      });\n      const data = await res.json();\n      if (data.success) {\n        showAdminContent();\n        fetch('/api/auction/state').then(r => r.json()).then(st => {\n          updateAuctionStatusBadge(st.auction_started);\n        }).catch(() => {});\n      } else {\n        sessionStorage.removeItem('kpl_auction_pin');\n        showLockScreen();\n      }\n    } catch (e) {\n      showLockScreen();\n    }\n  }\n\n  function showLockScreen() {\n    document.getElementById('adminLockScreen').style.dikplay = 'flex';\n    document.getElementById('adminMainContent').style.dikplay = 'none';\n    setTimeout(() => {\n      const input = document.getElementById('adminPinInput');\n      if (input) input.focus();\n    }, 100);\n  }\n\n  function showAdminContent() {\n    document.getElementById('adminLockScreen').style.dikplay = 'none';\n    document.getElementById('adminMainContent').style.dikplay = 'block';\n    renderTeamNameInputs();\n  }\n\n  function lockAdminSession() {\n    sessionStorage.removeItem('kpl_auction_pin');\n    showLockScreen();\n  }\n\n  async function handleAdminLogin(e) {\n    e.preventDefault();\n    const pin = document.getElementById('adminPinInput').value.trim();\n    const err = document.getElementById('adminPinError');\n    err.style.dikplay = 'none';\n\n    try {\n      const res = await fetch('/api/auction/verify-pin', {\n        method: 'POST',\n        headers: { 'Content-Type': 'application/json' },\n        body: JSON.stringify({ pin: pin })\n      });\n      const data = await res.json();\n      if (data.success) {\n        sessionStorage.setItem('kpl_auction_pin', pin);\n        showAdminContent();\n        fetch('/api/auction/state').then(r => r.json()).then(st => {\n          updateAuctionStatusBadge(st.auction_started);\n        }).catch(() => {});\n      } else {\n        err.textContent = '\u274c Incorrect PIN. Please try again.';\n        err.style.dikplay = 'block';\n      }\n    } catch (err) {\n      alert('Verification error: ' + err.message);\n    }\n  }\n\n  // --- FORGOT PIN & EMERGENCY RESET ---\n  async function forgotPinPrompt() {\n    const key = prompt(\n      \"\ud83d\udd11 EMERGENCY PIN RECOVERY\\n\\n\" +\n      \"If you forgot your PIN, enter the Emergency Master Recovery Key:\\n\" +\n      \"(Default Master Key: KPL-RECOVER-2026)\\n\\n\" +\n      \"Or set ADMIN_PIN in your Render dashboard environment variables.\"\n    );\n    if (!key) return;\n\n    try {\n      const res = await fetch('/api/admin/emergency-reset-pin', {\n        method: 'POST',\n        headers: { 'Content-Type': 'application/json' },\n        body: JSON.stringify({ recovery_key: key.trim() })\n      });\n      const data = await res.json();\n      if (data.success) {\n        alert(data.message || 'PIN has been reset to 2026!');\n        sessionStorage.setItem('kpl_auction_pin', '2026');\n        showAdminContent();\n        fetch('/api/auction/state').then(r => r.json()).then(st => {\n          updateAuctionStatusBadge(st.auction_started);\n        }).catch(() => {});\n      } else {\n        alert(data.message || 'Invalid Master Recovery Key.');\n      }\n    } catch (e) {\n      alert('Recovery error: ' + e.message);\n    }\n  }\n\n  // --- TEAM SETUP RENDERING ---\n  function renderTeamNameInputs() {\n    const count = parseInt(document.getElementById('setupTeamCount').value) || 2;\n    const container = document.getElementById('teamNamesContainer');\n    if (!container) return;\n    container.innerHTML = '';\n    for (let i = 0; i < count; i++) {\n      const defaultName = CURRENT_TEAMS[i] || `Team ${i + 1}`;\n      const div = document.createElement('div');\n      div.className = 'form-group';\n      div.style.marginBottom = '0';\n      div.innerHTML = `\n        <label class=\"form-label\" style=\"font-size: 0.8rem;\">Team ${i + 1} Name</label>\n        <input type=\"text\" name=\"teamName_${i}\" class=\"form-control team-name-input\" value=\"${defaultName}\" required>\n      `;\n      container.appendChild(div);\n    }\n  }\n\n  // Handle Team Setup Submit\n  document.getElementById('teamSetupForm').addEventListener('submit', async (e) => {\n    e.preventDefault();\n    const teamCount = parseInt(document.getElementById('setupTeamCount').value);\n    const inputs = document.querySelectorAll('.team-name-input');\n    const teamNames = Array.from(inputs).map(inp => inp.value.trim()).filter(Boolean);\n\n    if (teamNames.length < 2) return alert('Please enter at least 2 teams.');\n\n    const payload = {\n      team_count: teamCount,\n      team_names: teamNames,\n      total_purse: parseInt(document.getElementById('setupPurse').value) || 5000,\n      max_players: parseInt(document.getElementById('setupMinPlayers').value) || 15,\n      min_bid: parseInt(document.getElementById('setupMinBid').value) || 0,\n      retention_price: parseInt(document.getElementById('setupPlayerRetentionPrice').value) || 500,\n      owner_retention_price: parseInt(document.getElementById('setupOwnerRetentionPrice').value) || 100,\n      pin: getAdminPin()\n    };\n\n    try {\n      const res = await fetch('/api/setup-teams', {\n        method: 'POST',\n        headers: {\n          'Content-Type': 'application/json',\n          'X-Auction-PIN': getAdminPin()\n        },\n        body: JSON.stringify(payload)\n      });\n      const data = await res.json();\n      if (data.success) {\n        alert('Team Setup Saved Successfully! Teams, Purses, and Retention rules are ready.');\n        location.reload();\n      } else {\n        alert(data.message || 'Error saving team setup.');\n      }\n    } catch (err) {\n      alert('Error: ' + err.message);\n    }\n  });\n\n  // Handle Retention Submit\n  document.getElementById('retentionForm').addEventListener('submit', async (e) => {\n    e.preventDefault();\n    const team = document.getElementById('retentionTeamSelect').value;\n    const player = document.getElementById('retentionPlayerSelect').value;\n    const retType = document.getElementById('retentionTypeSelect').value;\n\n    if (!team || !player) return alert('Please select both team and player.');\n\n    const payload = {\n      team: team,\n      player: player,\n      retention_type: retType,\n      pin: getAdminPin()\n    };\n\n    try {\n      const res = await fetch('/api/retention/retain', {\n        method: 'POST',\n        headers: {\n          'Content-Type': 'application/json',\n          'X-Auction-PIN': getAdminPin()\n        },\n        body: JSON.stringify(payload)\n      });\n      const data = await res.json();\n      if (data.success) {\n        alert(data.message || 'Player retained successfully!');\n        location.reload();\n      } else {\n        alert(data.message || 'Error retaining player.');\n      }\n    } catch (err) {\n      alert('Error: ' + err.message);\n    }\n  });\n\n  async function releaseRetention(teamName) {\n    if (!confirm(`Release retention for ${teamName}? Budget will be refunded and player returned to auction pool.`)) return;\n    try {\n      const res = await fetch('/api/retention/release', {\n        method: 'POST',\n        headers: {\n          'Content-Type': 'application/json',\n          'X-Auction-PIN': getAdminPin()\n        },\n        body: JSON.stringify({ team: teamName, pin: getAdminPin() })\n      });\n      const data = await res.json();\n      if (data.success) {\n        alert('Retention released and budget refunded.');\n        location.reload();\n      } else {\n        alert(data.message || 'Error releasing retention.');\n      }\n    } catch (err) {\n      alert('Error: ' + err.message);\n    }\n  }\n\n  // Handle General Config & PIN Change Submit\n  document.getElementById('configForm').addEventListener('submit', async (e) => {\n    e.preventDefault();\n    const newPin = document.getElementById('cfgAdminPin').value.trim();\n    const payload = {\n      tournament_name: document.getElementById('cfgTournamentName').value,\n      upi_id: document.getElementById('cfgUpiId').value,\n      payee_name: document.getElementById('cfgPayeeName').value,\n      registration_fee: parseInt(document.getElementById('cfgRegFee').value),\n      admin_pin: newPin,\n      pin: getAdminPin()\n    };\n\n    try {\n      const res = await fetch('/api/admin/config', {\n        method: 'POST',\n        headers: {\n          'Content-Type': 'application/json',\n          'X-Auction-PIN': getAdminPin()\n        },\n        body: JSON.stringify(payload)\n      });\n      const data = await res.json();\n      if (data.success) {\n        sessionStorage.setItem('kpl_auction_pin', newPin);\n        alert('Settings & New PIN Saved Successfully!');\n        location.reload();\n      }\n    } catch (err) {\n      alert('Error saving settings: ' + err.message);\n    }\n  });\n\n  // Search filter\n  document.getElementById('playerSearchInput').addEventListener('input', (e) => {\n    const q = e.target.value.toLowerCase().trim();\n    document.querySelectorAll('.player-row').forEach(row => {\n      const str = row.getAttribute('data-search') || '';\n      row.style.dikplay = str.includes(q) ? '' : 'none';\n    });\n  });\n\n  async function auctionNow(name) {\n    if (!confirm(`Bring ${name} to the auction podium right now?`)) return;\n    try {\n      const res = await fetch('/api/auction/select-player', {\n        method: 'POST',\n        headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': getAdminPin() },\n        body: JSON.stringify({ player: name, pin: getAdminPin() })\n      });\n      const data = await res.json();\n      if (data.success) {\n        window.location.href = '/auction';\n      } else {\n        alert(data.message);\n      }\n    } catch (err) {\n      alert(err.message);\n    }\n  }\n\n  async function verifyPayment(name) {\n    try {\n      const res = await fetch('/api/admin/verify-player', {\n        method: 'POST',\n        headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': getAdminPin() },\n        body: JSON.stringify({ name: name, pin: getAdminPin() })\n      });\n      const data = await res.json();\n      if (data.success) location.reload();\n    } catch (err) {\n      alert(err.message);\n    }\n  }\n\n  async function resetAuctionState() {\n    if (!confirm('Are you SURE you want to reset the auction? Squads and bids will be reset to start clean.')) return;\n    try {\n      const res = await fetch('/api/admin/reset-auction', {\n        method: 'POST',\n        headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': getAdminPin() }\n      });\n      const data = await res.json();\n      if (data.success) {\n        alert('Auction reset successfully!');\n        location.reload();\n      }\n    } catch (err) {\n      alert(err.message);\n    }\n  }\n\n  // Check login on startup\n  checkAdminLoginState();\n</script>\n{% endblock %}\n", "static/css/style.css": "/* Modern Stadium Dark Glassmorphic Design System */\n@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&family=Inter:wght@400;500;600;700&dikplay=swap');\n\n:root {\n  --bg-main: #0a0e17;\n  --bg-surface: #111827;\n  --bg-card: rgba(17, 24, 39, 0.85);\n  --bg-card-hover: rgba(31, 41, 55, 0.9);\n  --border-glass: rgba(255, 255, 255, 0.1);\n  --border-gold: rgba(245, 158, 11, 0.4);\n  \n  --primary-gold: #f59e0b;\n  --gold-glow: rgba(245, 158, 11, 0.35);\n  --pitch-green: #10b981;\n  --green-glow: rgba(16, 185, 129, 0.35);\n  --crimson-red: #ef4444;\n  --red-glow: rgba(239, 68, 68, 0.35);\n  --electric-blue: #3b82f6;\n  --blue-glow: rgba(59, 130, 246, 0.35);\n  --purple-accent: #8b5cf6;\n  \n  --text-main: #f9fafb;\n  --text-muted: #9ca3af;\n  --text-dim: #6b7280;\n  \n  --radius-sm: 8px;\n  --radius-md: 14px;\n  --radius-lg: 20px;\n  --radius-full: 9999px;\n  \n  --shadow-card: 0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.4);\n  --shadow-glow: 0 0 25px var(--gold-glow);\n}\n\n* {\n  margin: 0;\n  padding: 0;\n  box-sizing: border-box;\n}\n\nbody {\n  font-family: 'Outfit', 'Inter', -apple-system, sans-serif;\n  background-color: var(--bg-main);\n  background-image: \n    radial-gradient(circle at 10% 20%, rgba(16, 185, 129, 0.12) 0%, transparent 40%),\n    radial-gradient(circle at 90% 80%, rgba(245, 158, 11, 0.12) 0%, transparent 40%),\n    radial-gradient(circle at 50% 50%, rgba(59, 130, 246, 0.08) 0%, transparent 60%);\n  background-attachment: fixed;\n  color: var(--text-main);\n  min-height: 100vh;\n  dikplay: flex;\n  flex-direction: column;\n  line-height: 1.5;\n  -webkit-font-smoothing: antialiased;\n}\n\n/* Header & Navbar */\n.navbar {\n  background: rgba(10, 14, 23, 0.85);\n  backdrop-filter: blur(16px);\n  -webkit-backdrop-filter: blur(16px);\n  border-bottom: 1px solid var(--border-glass);\n  position: sticky;\n  top: 0;\n  z-index: 1000;\n  padding: 0.75rem 1.5rem;\n}\n\n.nav-container {\n  max-width: 1200px;\n  margin: 0 auto;\n  dikplay: flex;\n  align-items: center;\n  justify-content: space-between;\n}\n\n.nav-brand {\n  dikplay: flex;\n  align-items: center;\n  gap: 0.75rem;\n  text-decoration: none;\n  color: var(--text-main);\n  font-weight: 800;\n  font-size: 1.35rem;\n  letter-spacing: -0.02em;\n}\n\n.brand-badge {\n  background: linear-gradient(135deg, var(--primary-gold), #d97706);\n  color: #000;\n  font-weight: 900;\n  padding: 0.25rem 0.6rem;\n  border-radius: var(--radius-sm);\n  font-size: 0.85rem;\n  text-transform: uppercase;\n  box-shadow: 0 2px 8px var(--gold-glow);\n}\n\n.brand-text span {\n  color: var(--primary-gold);\n}\n\n.nav-links {\n  dikplay: flex;\n  align-items: center;\n  gap: 0.5rem;\n  list-style: none;\n}\n\n.nav-link {\n  color: var(--text-muted);\n  text-decoration: none;\n  font-weight: 600;\n  padding: 0.5rem 0.9rem;\n  border-radius: var(--radius-sm);\n  transition: all 0.2s ease;\n  dikplay: flex;\n  align-items: center;\n  gap: 0.4rem;\n  font-size: 0.95rem;\n}\n\n.nav-link:hover, .nav-link.active {\n  color: var(--text-main);\n  background: rgba(255, 255, 255, 0.08);\n}\n\n.nav-link.highlight {\n  background: linear-gradient(135deg, #f59e0b, #d97706);\n  color: #000;\n  font-weight: 700;\n}\n.nav-link.highlight:hover {\n  transform: translateY(-2px);\n  box-shadow: 0 4px 12px var(--gold-glow);\n}\n\n/* Mobile Menu Toggle */\n.mobile-toggle {\n  dikplay: none;\n  background: none;\n  border: 1px solid var(--border-glass);\n  color: var(--text-main);\n  padding: 0.4rem 0.75rem;\n  border-radius: var(--radius-sm);\n  font-size: 1.25rem;\n  cursor: pointer;\n}\n\n/* Page Container */\n.page-container {\n  max-width: 1200px;\n  width: 100%;\n  margin: 0 auto;\n  padding: 2rem 1.25rem;\n  flex: 1;\n}\n\n/* Glass Cards */\n.glass-card {\n  background: var(--bg-card);\n  backdrop-filter: blur(12px);\n  -webkit-backdrop-filter: blur(12px);\n  border: 1px solid var(--border-glass);\n  border-radius: var(--radius-lg);\n  padding: 2rem;\n  box-shadow: var(--shadow-card);\n}\n\n/* Buttons */\n.btn {\n  dikplay: inline-flex;\n  align-items: center;\n  justify-content: center;\n  gap: 0.5rem;\n  padding: 0.75rem 1.5rem;\n  font-size: 1rem;\n  font-weight: 700;\n  font-family: inherit;\n  border-radius: var(--radius-md);\n  border: none;\n  cursor: pointer;\n  text-decoration: none;\n  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);\n}\n\n.btn-primary {\n  background: linear-gradient(135deg, #f59e0b, #d97706);\n  color: #000;\n  box-shadow: 0 4px 14px var(--gold-glow);\n}\n.btn-primary:hover {\n  transform: translateY(-2px);\n  box-shadow: 0 6px 20px rgba(245, 158, 11, 0.5);\n}\n\n.btn-success {\n  background: linear-gradient(135deg, #10b981, #059669);\n  color: #fff;\n  box-shadow: 0 4px 14px var(--green-glow);\n}\n.btn-success:hover {\n  transform: translateY(-2px);\n  box-shadow: 0 6px 20px rgba(16, 185, 129, 0.5);\n}\n\n.btn-danger {\n  background: linear-gradient(135deg, #ef4444, #dc2626);\n  color: #fff;\n  box-shadow: 0 4px 14px var(--red-glow);\n}\n.btn-danger:hover {\n  transform: translateY(-2px);\n  box-shadow: 0 6px 20px rgba(239, 68, 68, 0.5);\n}\n\n.btn-secondary {\n  background: rgba(255, 255, 255, 0.08);\n  color: var(--text-main);\n  border: 1px solid var(--border-glass);\n}\n.btn-secondary:hover {\n  background: rgba(255, 255, 255, 0.14);\n}\n\n/* Badges */\n.badge {\n  dikplay: inline-flex;\n  align-items: center;\n  gap: 0.35rem;\n  padding: 0.35rem 0.75rem;\n  border-radius: var(--radius-full);\n  font-size: 0.85rem;\n  font-weight: 700;\n  text-transform: uppercase;\n  letter-spacing: 0.03em;\n}\n\n.badge-batsman {\n  background: rgba(239, 68, 68, 0.15);\n  color: #fca5a5;\n  border: 1px solid rgba(239, 68, 68, 0.35);\n}\n.badge-bowler {\n  background: rgba(59, 130, 246, 0.15);\n  color: #93c5fd;\n  border: 1px solid rgba(59, 130, 246, 0.35);\n}\n.badge-allrounder {\n  background: rgba(245, 158, 11, 0.15);\n  color: #fde68a;\n  border: 1px solid rgba(245, 158, 11, 0.35);\n}\n.badge-keeper {\n  background: rgba(16, 185, 129, 0.15);\n  color: #6ee7b7;\n  border: 1px solid rgba(16, 185, 129, 0.35);\n}\n\n/* Form Styles */\n.form-group {\n  margin-bottom: 1.5rem;\n}\n\n.form-label {\n  dikplay: block;\n  font-size: 0.95rem;\n  font-weight: 600;\n  margin-bottom: 0.5rem;\n  color: var(--text-main);\n}\n\n.form-label span.req {\n  color: var(--crimson-red);\n}\n\n.form-control {\n  width: 100%;\n  padding: 0.85rem 1.15rem;\n  background: rgba(15, 23, 42, 0.7);\n  border: 1px solid rgba(255, 255, 255, 0.15);\n  border-radius: var(--radius-md);\n  color: #fff;\n  font-size: 1rem;\n  font-family: inherit;\n  transition: all 0.2s ease;\n}\n\n.form-control:focus {\n  outline: none;\n  border-color: var(--primary-gold);\n  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.2);\n  background: rgba(15, 23, 42, 0.9);\n}\n\n/* Role Selector Grid */\n.role-grid {\n  dikplay: grid;\n  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));\n  gap: 0.85rem;\n}\n\n.role-card-opt {\n  position: relative;\n  cursor: pointer;\n}\n\n.role-card-opt input[type=\"radio\"] {\n  position: absolute;\n  opacity: 0;\n}\n\n.role-box {\n  dikplay: flex;\n  flex-direction: column;\n  align-items: center;\n  text-align: center;\n  padding: 1.15rem 0.75rem;\n  background: rgba(15, 23, 42, 0.6);\n  border: 2px solid rgba(255, 255, 255, 0.1);\n  border-radius: var(--radius-md);\n  transition: all 0.25s ease;\n}\n\n.role-box .icon {\n  font-size: 2rem;\n  margin-bottom: 0.5rem;\n}\n\n.role-box .title {\n  font-weight: 700;\n  font-size: 0.9rem;\n}\n\n.role-card-opt input:checked + .role-box {\n  border-color: var(--primary-gold);\n  background: rgba(245, 158, 11, 0.12);\n  box-shadow: 0 0 15px var(--gold-glow);\n  transform: translateY(-2px);\n}\n\n/* Photo Upload Box */\n.photo-uploader {\n  border: 2px dashed rgba(255, 255, 255, 0.2);\n  border-radius: var(--radius-lg);\n  padding: 1.75rem 1rem;\n  text-align: center;\n  background: rgba(15, 23, 42, 0.4);\n  transition: all 0.25s ease;\n}\n\n.photo-uploader:hover {\n  border-color: var(--primary-gold);\n}\n\n.photo-preview-wrap {\n  width: 140px;\n  height: 140px;\n  border-radius: 50%;\n  margin: 0 auto 1.25rem;\n  border: 3px solid var(--primary-gold);\n  overflow: hidden;\n  box-shadow: 0 0 20px var(--gold-glow);\n  background: #1e293b;\n  dikplay: flex;\n  align-items: center;\n  justify-content: center;\n}\n\n.photo-preview-img {\n  width: 100%;\n  height: 100%;\n  object-fit: cover;\n}\n\n.upload-actions {\n  dikplay: flex;\n  gap: 0.75rem;\n  justify-content: center;\n  flex-wrap: wrap;\n}\n\n/* UPI Payment Block */\n.payment-section {\n  background: linear-gradient(135deg, rgba(30, 41, 59, 0.8), rgba(15, 23, 42, 0.95));\n  border: 1px solid var(--border-gold);\n  border-radius: var(--radius-lg);\n  padding: 1.75rem;\n  margin-top: 1.5rem;\n  box-shadow: 0 0 20px rgba(245, 158, 11, 0.15);\n}\n\n.fee-banner {\n  dikplay: flex;\n  align-items: center;\n  justify-content: space-between;\n  background: rgba(245, 158, 11, 0.12);\n  border: 1px solid rgba(245, 158, 11, 0.3);\n  padding: 1rem 1.25rem;\n  border-radius: var(--radius-md);\n  margin-bottom: 1.5rem;\n}\n\n.fee-amount {\n  font-size: 1.85rem;\n  font-weight: 900;\n  color: var(--primary-gold);\n}\n\n.upi-details-grid {\n  dikplay: grid;\n  grid-template-columns: 220px 1fr;\n  gap: 1.5rem;\n  align-items: center;\n}\n\n.qr-box {\n  background: #ffffff;\n  padding: 0.75rem;\n  border-radius: var(--radius-md);\n  text-align: center;\n  box-shadow: 0 4px 15px rgba(0,0,0,0.4);\n}\n\n.qr-box img {\n  width: 100%;\n  max-width: 190px;\n  height: auto;\n  dikplay: block;\n  margin: 0 auto;\n}\n\n.qr-label {\n  color: #111;\n  font-weight: 700;\n  font-size: 0.8rem;\n  margin-top: 0.4rem;\n}\n\n.upi-apps-grid {\n  dikplay: grid;\n  grid-template-columns: repeat(2, 1fr);\n  gap: 0.75rem;\n  margin-top: 1rem;\n}\n\n.upi-app-btn {\n  dikplay: flex;\n  align-items: center;\n  gap: 0.6rem;\n  padding: 0.75rem 1rem;\n  border-radius: var(--radius-md);\n  color: #fff;\n  font-weight: 700;\n  text-decoration: none;\n  font-size: 0.95rem;\n  transition: all 0.2s ease;\n  border: 1px solid rgba(255, 255, 255, 0.1);\n}\n\n.upi-phonepe { background: #5f259f; }\n.upi-phonepe:hover { background: #6f2eb8; transform: translateY(-2px); }\n\n.upi-gpay { background: #1a73e8; }\n.upi-gpay:hover { background: #2b7de9; transform: translateY(-2px); }\n\n.upi-paytm { background: #002e6e; }\n.upi-paytm:hover { background: #003a8c; transform: translateY(-2px); }\n\n.upi-bhim { background: #ff6f00; }\n.upi-bhim:hover { background: #ff7d1a; transform: translateY(-2px); }\n\n/* Responsive adjustments */\n@media (max-width: 768px) {\n  .nav-links {\n    dikplay: none;\n    position: absolute;\n    top: 100%;\n    left: 0;\n    right: 0;\n    background: var(--bg-surface);\n    flex-direction: column;\n    padding: 1rem;\n    border-bottom: 1px solid var(--border-glass);\n  }\n  .nav-links.open {\n    dikplay: flex;\n  }\n  .mobile-toggle {\n    dikplay: block;\n  }\n  .upi-details-grid {\n    grid-template-columns: 1fr;\n    text-align: center;\n  }\n  .qr-box {\n    max-width: 230px;\n    margin: 0 auto;\n  }\n  .upi-apps-grid {\n    grid-template-columns: 1fr;\n  }\n  .page-container {\n    padding: 1rem 0.75rem;\n  }\n  .glass-card {\n    padding: 1.25rem 1rem;\n  }\n}\n", "static/css/auction.css": "/* Live Auction Arena CSS */\n.auction-stage {\n  dikplay: grid;\n  grid-template-columns: 1fr 340px;\n  gap: 1.5rem;\n  margin-top: 1rem;\n}\n\n/* Center Stage Player Dikplay */\n.player-podium {\n  background: radial-gradient(circle at 50% 30%, rgba(30, 41, 59, 0.95), rgba(15, 23, 42, 0.98));\n  border: 2px solid var(--border-gold);\n  border-radius: var(--radius-lg);\n  padding: 2.25rem 2rem;\n  box-shadow: 0 15px 35px rgba(0, 0, 0, 0.6), 0 0 35px rgba(245, 158, 11, 0.15);\n  dikplay: flex;\n  flex-direction: column;\n  align-items: center;\n  position: relative;\n  overflow: hidden;\n}\n\n.podium-header {\n  width: 100%;\n  dikplay: flex;\n  justify-content: space-between;\n  align-items: center;\n  margin-bottom: 1.5rem;\n}\n\n.round-tag {\n  background: rgba(255, 255, 255, 0.08);\n  border: 1px solid var(--border-glass);\n  padding: 0.35rem 0.85rem;\n  border-radius: var(--radius-full);\n  font-size: 0.85rem;\n  font-weight: 700;\n  color: var(--primary-gold);\n}\n\n.pool-status {\n  font-size: 0.85rem;\n  color: var(--text-muted);\n}\n\n/* Player Photo Spotlight */\n.player-photo-arena {\n  position: relative;\n  margin-bottom: 1.5rem;\n}\n\n.photo-frame {\n  width: 220px;\n  height: 220px;\n  border-radius: 50%;\n  border: 5px solid var(--primary-gold);\n  overflow: hidden;\n  box-shadow: 0 0 35px var(--gold-glow), 0 10px 25px rgba(0,0,0,0.7);\n  background: #1e293b;\n  position: relative;\n  transition: all 0.3s ease;\n}\n\n.photo-frame img {\n  width: 100%;\n  height: 100%;\n  object-fit: cover;\n}\n\n.role-tag-floater {\n  position: absolute;\n  bottom: 0;\n  left: 50%;\n  transform: translateX(-50%);\n  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.6);\n  white-space: nowrap;\n}\n\n.player-name-banner {\n  text-align: center;\n  margin-bottom: 1rem;\n}\n\n.player-main-name {\n  font-size: 2.25rem;\n  font-weight: 900;\n  letter-spacing: -0.02em;\n  color: #fff;\n  text-shadow: 0 2px 10px rgba(0,0,0,0.5);\n}\n\n.player-serial-tag {\n  dikplay: inline-block;\n  background: rgba(245, 158, 11, 0.15);\n  color: var(--primary-gold);\n  border: 1px solid rgba(245, 158, 11, 0.4);\n  font-weight: 800;\n  padding: 0.2rem 0.6rem;\n  border-radius: var(--radius-sm);\n  font-size: 0.95rem;\n  margin-right: 0.5rem;\n}\n\n/* Player Meta Badges */\n.player-meta-row {\n  dikplay: flex;\n  gap: 0.75rem;\n  flex-wrap: wrap;\n  justify-content: center;\n  margin-bottom: 1.75rem;\n}\n\n.meta-chip {\n  background: rgba(15, 23, 42, 0.8);\n  border: 1px solid var(--border-glass);\n  padding: 0.4rem 0.85rem;\n  border-radius: var(--radius-md);\n  font-size: 0.85rem;\n  color: var(--text-muted);\n}\n.meta-chip strong {\n  color: #fff;\n  margin-left: 0.25rem;\n}\n\n/* Bid Dikplay Box */\n.bid-odometer-box {\n  width: 100%;\n  background: rgba(0, 0, 0, 0.5);\n  border: 1px solid rgba(255, 255, 255, 0.1);\n  border-radius: var(--radius-lg);\n  padding: 1.5rem;\n  text-align: center;\n  margin-bottom: 1.75rem;\n  box-shadow: inset 0 2px 10px rgba(0,0,0,0.5);\n}\n\n.bid-label {\n  font-size: 0.9rem;\n  font-weight: 700;\n  color: var(--text-muted);\n  text-transform: uppercase;\n  letter-spacing: 0.05em;\n  margin-bottom: 0.25rem;\n}\n\n.bid-amount {\n  font-size: 3.5rem;\n  font-weight: 900;\n  color: var(--pitch-green);\n  font-variant-numeric: tabular-nums;\n  line-height: 1;\n  text-shadow: 0 0 25px var(--green-glow);\n}\n\n.bidding-team-banner {\n  margin-top: 0.6rem;\n  font-size: 1.15rem;\n  font-weight: 700;\n  color: var(--primary-gold);\n}\n\n/* Bid Control Deck */\n.control-deck {\n  width: 100%;\n  dikplay: flex;\n  flex-direction: column;\n  gap: 1rem;\n}\n\n.team-bid-row {\n  dikplay: grid;\n  grid-template-columns: 1fr auto;\n  gap: 0.75rem;\n}\n\n.increments-grid {\n  dikplay: grid;\n  grid-template-columns: repeat(4, 1fr);\n  gap: 0.5rem;\n}\n\n.btn-inc {\n  background: rgba(255, 255, 255, 0.08);\n  border: 1px solid var(--border-glass);\n  color: #fff;\n  font-weight: 700;\n  padding: 0.65rem 0.25rem;\n  border-radius: var(--radius-md);\n  font-size: 0.95rem;\n  cursor: pointer;\n  transition: all 0.2s ease;\n}\n.btn-inc:hover {\n  background: rgba(245, 158, 11, 0.2);\n  border-color: var(--primary-gold);\n  color: var(--primary-gold);\n}\n\n.auction-primary-actions {\n  dikplay: grid;\n  grid-template-columns: 2fr 1fr;\n  gap: 0.75rem;\n}\n\n.auction-secondary-actions {\n  dikplay: grid;\n  grid-template-columns: 1fr 1fr 1fr;\n  gap: 0.5rem;\n}\n\n/* Sidebar - Teams & Purses */\n.teams-sidebar {\n  dikplay: flex;\n  flex-direction: column;\n  gap: 0.85rem;\n}\n\n.sidebar-header {\n  font-size: 1.1rem;\n  font-weight: 800;\n  color: #fff;\n  dikplay: flex;\n  justify-content: space-between;\n  align-items: center;\n  padding-bottom: 0.5rem;\n  border-bottom: 1px solid var(--border-glass);\n}\n\n.team-card {\n  background: var(--bg-card);\n  border: 1px solid var(--border-glass);\n  border-radius: var(--radius-md);\n  padding: 1rem;\n  transition: all 0.2s ease;\n  cursor: pointer;\n}\n.team-card:hover {\n  border-color: var(--border-gold);\n  background: var(--bg-card-hover);\n}\n.team-card.current-bidder {\n  border-color: var(--pitch-green);\n  box-shadow: 0 0 15px var(--green-glow);\n  background: rgba(16, 185, 129, 0.1);\n}\n\n.team-card-header {\n  dikplay: flex;\n  justify-content: space-between;\n  align-items: center;\n  margin-bottom: 0.5rem;\n}\n\n.team-name {\n  font-weight: 800;\n  font-size: 1.1rem;\n  color: #fff;\n}\n\n.team-squad-count {\n  font-size: 0.85rem;\n  font-weight: 700;\n  padding: 0.15rem 0.5rem;\n  border-radius: var(--radius-full);\n  background: rgba(255, 255, 255, 0.1);\n}\n\n.team-budget-bar-wrap {\n  width: 100%;\n  height: 6px;\n  background: rgba(255, 255, 255, 0.1);\n  border-radius: var(--radius-full);\n  overflow: hidden;\n  margin-bottom: 0.5rem;\n}\n\n.team-budget-fill {\n  height: 100%;\n  background: linear-gradient(90deg, var(--pitch-green), #34d399);\n  border-radius: var(--radius-full);\n}\n\n.team-financials {\n  dikplay: flex;\n  justify-content: space-between;\n  font-size: 0.85rem;\n}\n.team-rem-budget {\n  font-weight: 800;\n  color: var(--pitch-green);\n}\n.team-spent-budget {\n  color: var(--text-dim);\n}\n\n/* Sold Celebration Overlay */\n.sold-modal-overlay {\n  position: fixed;\n  inset: 0;\n  background: rgba(0, 0, 0, 0.85);\n  backdrop-filter: blur(10px);\n  z-index: 2000;\n  dikplay: none;\n  align-items: center;\n  justify-content: center;\n  padding: 1.5rem;\n}\n.sold-modal-overlay.active {\n  dikplay: flex;\n  animation: fadeIn 0.3s ease;\n}\n\n.sold-card-popup {\n  background: linear-gradient(135deg, #1e293b, #0f172a);\n  border: 3px solid var(--primary-gold);\n  border-radius: var(--radius-lg);\n  padding: 2.5rem;\n  text-align: center;\n  max-width: 480px;\n  width: 100%;\n  box-shadow: 0 0 50px var(--gold-glow);\n  animation: popIn 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);\n}\n\n.sold-banner {\n  font-size: 3rem;\n  font-weight: 900;\n  color: var(--pitch-green);\n  text-shadow: 0 0 20px var(--green-glow);\n  letter-spacing: 0.05em;\n  margin-bottom: 0.75rem;\n}\n\n@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }\n@keyframes popIn { from { transform: scale(0.7); opacity: 0; } to { transform: scale(1); opacity: 1; } }\n\n@media (max-width: 900px) {\n  .auction-stage {\n    grid-template-columns: 1fr;\n  }\n  .player-main-name {\n    font-size: 1.75rem;\n  }\n  .bid-amount {\n    font-size: 2.5rem;\n  }\n  .photo-frame {\n    width: 170px;\n    height: 170px;\n  }\n}\n", "static/js/register.js": "// Player Registration & UPI Payment Handling\nlet capturedPhotoBlob = null;\nlet webcamStream = null;\n\n// Tournament config passed from template\nconst config = window.TOURNAMENT_CONFIG || {\n  upi_id: 'saidapur.cricket@upi',\n  payee_name: 'Saidapur Premier League',\n  registration_fee: 200\n};\n\ndocument.addEventListener('DOMContentLoaded', () => {\n  initPhotoHandling();\n  initUPIPayments();\n  initFormSubmission();\n});\n\nfunction initPhotoHandling() {\n  const fileInput = document.getElementById('photoFileInput');\n  const cameraInput = document.getElementById('photoCameraInput');\n  const previewImg = document.getElementById('photoPreview');\n  const webcamModal = document.getElementById('webcamModal');\n  const webcamVideo = document.getElementById('webcamVideo');\n\n  // Trigger file picker\n  document.getElementById('btnUploadFile')?.addEventListener('click', () => {\n    fileInput.click();\n  });\n\n  // Mobile camera capture trigger\n  document.getElementById('btnCameraMobile')?.addEventListener('click', () => {\n    // If mobile or has camera input\n    if (cameraInput) {\n      cameraInput.click();\n    }\n  });\n\n  // Desktop webcam modal trigger\n  document.getElementById('btnWebcamDesktop')?.addEventListener('click', async () => {\n    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {\n      try {\n        webcamStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: 640, height: 480 } });\n        webcamVideo.srcObject = webcamStream;\n        webcamVideo.play();\n        webcamModal.style.dikplay = 'flex';\n      } catch (err) {\n        alert('Could not access camera: ' + err.message + '. Please use the Upload File button.');\n      }\n    } else {\n      alert('Camera access is not supported by your browser. Please upload a photo.');\n    }\n  });\n\n  // Capture snapshot from webcam\n  document.getElementById('btnCaptureSnapshot')?.addEventListener('click', () => {\n    const canvas = document.createElement('canvas');\n    canvas.width = webcamVideo.videoWidth || 480;\n    canvas.height = webcamVideo.videoHeight || 480;\n    const ctx = canvas.getContext('2d');\n    ctx.drawImage(webcamVideo, 0, 0, canvas.width, canvas.height);\n    \n    canvas.toBlob((blob) => {\n      capturedPhotoBlob = blob;\n      previewImg.src = URL.createObjectURL(blob);\n      closeWebcam();\n    }, 'image/jpeg', 0.9);\n  });\n\n  document.getElementById('btnCloseWebcam')?.addEventListener('click', closeWebcam);\n\n  function closeWebcam() {\n    if (webcamStream) {\n      webcamStream.getTracks().forEach(track => track.stop());\n      webcamStream = null;\n    }\n    webcamModal.style.dikplay = 'none';\n  }\n\n  // Handle file uploads (both file picker & mobile capture)\n  function handleFileSelected(e) {\n    const file = e.target.files[0];\n    if (file) {\n      capturedPhotoBlob = file;\n      const reader = new FileReader();\n      reader.onload = (evt) => {\n        previewImg.src = evt.target.result;\n      };\n      reader.readAsDataURL(file);\n    }\n  }\n\n  fileInput?.addEventListener('change', handleFileSelected);\n  cameraInput?.addEventListener('change', handleFileSelected);\n}\n\nfunction initUPIPayments() {\n  const nameInput = document.getElementById('playerName');\n  const qrImg = document.getElementById('upiQrCode');\n  const upiIdDikplay = document.getElementById('upiIdDikplay');\n  const feeDikplay = document.getElementById('feeAmountDikplay');\n  \n  if (feeDikplay) feeDikplay.textContent = '\u20b9' + config.registration_fee;\n  if (upiIdDikplay) upiIdDikplay.textContent = config.upi_id;\n\n  function updateUPIUrls() {\n    const playerName = (nameInput?.value.trim()) || 'Player';\n    const note = encodeURIComponent(`KPL Fee - ${playerName}`);\n    const upiUri = `upi://pay?pa=${config.upi_id}&pn=${encodeURIComponent(config.payee_name)}&am=${config.registration_fee}&cu=INR&tn=${note}`;\n    \n    // Update QR Code\n    if (qrImg) {\n      qrImg.src = `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(upiUri)}`;\n    }\n\n    // Update Deep-Link buttons\n    const btnPhonePe = document.getElementById('btnPayPhonePe');\n    const btnGPay = document.getElementById('btnPayGPay');\n    const btnPaytm = document.getElementById('btnPayPaytm');\n    const btnBhim = document.getElementById('btnPayBhim');\n\n    if (btnPhonePe) btnPhonePe.href = `phonepe://pay?pa=${config.upi_id}&pn=${encodeURIComponent(config.payee_name)}&am=${config.registration_fee}&cu=INR&tn=${note}`;\n    if (btnGPay) btnGPay.href = `gpay://upi/pay?pa=${config.upi_id}&pn=${encodeURIComponent(config.payee_name)}&am=${config.registration_fee}&cu=INR&tn=${note}`;\n    if (btnPaytm) btnPaytm.href = `paytmmp://pay?pa=${config.upi_id}&pn=${encodeURIComponent(config.payee_name)}&am=${config.registration_fee}&cu=INR&tn=${note}`;\n    if (btnBhim) btnBhim.href = upiUri;\n  }\n\n  nameInput?.addEventListener('input', updateUPIUrls);\n  updateUPIUrls();\n\n  // Copy UPI ID button\n  document.getElementById('btnCopyUpi')?.addEventListener('click', () => {\n    navigator.clipboard.writeText(config.upi_id);\n    const copyBtn = document.getElementById('btnCopyUpi');\n    copyBtn.textContent = '\u2713 Copied!';\n    setTimeout(() => { copyBtn.textContent = 'Copy UPI ID'; }, 2000);\n  });\n}\n\nfunction initFormSubmission() {\n  const form = document.getElementById('registrationForm');\n  const submitBtn = document.getElementById('btnSubmitReg');\n  const alertBox = document.getElementById('formAlert');\n\n  form?.addEventListener('submit', async (e) => {\n    e.preventDefault();\n    alertBox.style.dikplay = 'none';\n\n    const name = document.getElementById('playerName').value.trim();\n    const phone = document.getElementById('playerPhone').value.trim();\n    const roleRadio = document.querySelector('input[name=\"playerRole\"]:checked');\n    const batting = document.getElementById('battingStyle').value;\n    const bowling = document.getElementById('bowlingStyle').value;\n    const paymentMethod = document.getElementById('paymentMethod').value;\n    const utr = document.getElementById('transactionId').value.trim();\n    const paymentProofFile = document.getElementById('paymentScreenshot')?.files[0];\n\n    if (!name) return showAlert('Please enter player name.');\n    if (!phone || phone.length < 10) return showAlert('Please enter a valid 10-digit mobile number.');\n    if (!roleRadio) return showAlert('Please select player role (Batsman, Bowler, All-Rounder, Wicket Keeper).');\n    // UTR is optional\n\n    submitBtn.disabled = true;\n    submitBtn.innerHTML = '<span class=\"spinner\"></span> Submitting Registration...';\n\n    const formData = new FormData();\n    formData.append('name', name);\n    formData.append('phone', phone);\n    formData.append('role', roleRadio.value);\n    formData.append('batting_style', batting);\n    formData.append('bowling_style', bowling);\n    formData.append('payment_method', paymentMethod);\n    formData.append('transaction_id', utr);\n    formData.append('reg_amount', config.registration_fee);\n\n    if (capturedPhotoBlob) {\n      formData.append('photo', capturedPhotoBlob, 'player_photo.jpg');\n    }\n    if (paymentProofFile) {\n      formData.append('screenshot', paymentProofFile);\n    }\n\n    try {\n      const res = await fetch('/api/register', {\n        method: 'POST',\n        body: formData\n      });\n      const data = await res.json();\n      if (data.success) {\n        window.location.href = `/register/success/${encodeURIComponent(data.player_id)}`;\n      } else {\n        showAlert(data.message || 'Error saving registration.');\n        submitBtn.disabled = false;\n        submitBtn.textContent = 'Complete Registration & Pay';\n      }\n    } catch (err) {\n      showAlert('Network error: ' + err.message);\n      submitBtn.disabled = false;\n      submitBtn.textContent = 'Complete Registration & Pay';\n    }\n  });\n\n  function showAlert(msg) {\n    if (alertBox) {\n      alertBox.textContent = msg;\n      alertBox.style.dikplay = 'block';\n      alertBox.scrollIntoView({ behavior: 'smooth' });\n    } else {\n      alert(msg);\n    }\n  }\n}\n", "static/js/auction.js": "\nasync function toggleAuctionStarted() {\n  const pin = getAuctioneerPin();\n  if (!pin) {\n    openPinModal();\n    return;\n  }\n\n  const willStart = !currentAppState || !currentAppState.auction_started;\n  const endpoint = willStart ? '/api/auction/start' : '/api/auction/pause';\n  const actionName = willStart ? 'Start Live Auction for all viewers' : 'Pause Live Auction';\n\n  if (!confirm(`Are you sure you want to ${actionName}?`)) return;\n\n  try {\n    const res = await fetch(endpoint, {\n      method: 'POST',\n      headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': pin },\n      body: JSON.stringify({ pin: pin })\n    });\n    const data = await res.json();\n    if (data.success) {\n      alert(data.message);\n      fetchState();\n    } else {\n      alert(data.message || 'Error updating auction state.');\n    }\n  } catch (e) {\n    alert(e.message);\n  }\n}\n\n\n// ==================== AUCTIONEER PIN SECURITY ====================\nfunction getAuctioneerPin() {\n  return sessionStorage.getItem('kpl_auction_pin') || '';\n}\n\nfunction openPinModal() {\n  const modal = document.getElementById('pinModal');\n  const input = document.getElementById('inputAuctionPin');\n  const err = document.getElementById('pinErrorMsg');\n  if (err) err.style.dikplay = 'none';\n  if (input) { input.value = ''; }\n  if (modal) {\n    modal.style.dikplay = 'flex';\n    setTimeout(() => { if (input) input.focus(); }, 100);\n  }\n}\n\nfunction closePinModal() {\n  const modal = document.getElementById('pinModal');\n  if (modal) modal.style.dikplay = 'none';\n}\n\nasync function submitAuctionPin() {\n  const input = document.getElementById('inputAuctionPin');\n  const err = document.getElementById('pinErrorMsg');\n  const pin = input ? input.value.trim() : '';\n\n  if (!pin) {\n    if (err) { err.textContent = 'Please enter the PIN.'; err.style.dikplay = 'block'; }\n    return;\n  }\n\n  try {\n    const res = await fetch('/api/auction/verify-pin', {\n      method: 'POST',\n      headers: { 'Content-Type': 'application/json' },\n      body: JSON.stringify({ pin: pin })\n    });\n    const data = await res.json();\n    if (data.success) {\n      sessionStorage.setItem('kpl_auction_pin', pin);\n      applyAuctioneerMode(true);\n      closePinModal();\n    } else {\n      if (err) { err.textContent = data.message || 'Incorrect PIN.'; err.style.dikplay = 'block'; }\n    }\n  } catch (e) {\n    if (err) { err.textContent = 'Verification error: ' + e.message; err.style.dikplay = 'block'; }\n  }\n}\n\nfunction lockAuctioneer() {\n  sessionStorage.removeItem('kpl_auction_pin');\n  applyAuctioneerMode(false);\n}\n\nfunction applyAuctioneerMode(isHost) {\n  const deck = document.getElementById('auctioneerControlDeck');\n  const emptyActions = document.getElementById('emptyAuctioneerActions');\n  const authBox = document.getElementById('auctioneerAuthBox');\n\n  if (deck) deck.style.dikplay = isHost ? 'block' : 'none';\n  if (emptyActions) emptyActions.style.dikplay = isHost ? 'flex' : 'none';\n\n  if (authBox) {\n    if (isHost) {\n      authBox.innerHTML = `\n        <span style=\"color: var(--pitch-green); font-size: 0.85rem; font-weight: 700; dikplay: inline-flex; align-items: center; gap: 0.3rem;\">\n          <span>\ud83d\udd13</span> Host Active\n        </span>\n        <button type=\"button\" onclick=\"lockAuctioneer()\" class=\"btn btn-secondary\" style=\"font-size: 0.75rem; padding: 0.2rem 0.5rem; margin-left: 0.35rem;\">Lock</button>\n      `;\n    } else {\n      authBox.innerHTML = `\n        <button type=\"button\" id=\"btnUnlockAuctioneer\" onclick=\"openPinModal()\" class=\"btn btn-secondary\" style=\"font-size: 0.8rem; padding: 0.3rem 0.65rem; border-color: rgba(245, 158, 11, 0.5); color: var(--primary-gold); dikplay: flex; align-items: center; gap: 0.35rem;\">\n          <span>\ud83d\udd12</span> Host Controls\n        </button>\n      `;\n    }\n  }\n}\n\n// Check saved PIN on startup\nasync function checkSavedPin() {\n  const saved = getAuctioneerPin();\n  if (!saved) {\n    applyAuctioneerMode(false);\n    return;\n  }\n  try {\n    const res = await fetch('/api/auction/verify-pin', {\n      method: 'POST',\n      headers: { 'Content-Type': 'application/json' },\n      body: JSON.stringify({ pin: saved })\n    });\n    const data = await res.json();\n    if (data.success) {\n      applyAuctioneerMode(true);\n    } else {\n      sessionStorage.removeItem('kpl_auction_pin');\n      applyAuctioneerMode(false);\n    }\n  } catch (e) {\n    applyAuctioneerMode(false);\n  }\n}\n\n// Allow Enter key to submit PIN\ndocument.addEventListener('keydown', (e) => {\n  if (e.key === 'Enter') {\n    const modal = document.getElementById('pinModal');\n    if (modal && modal.style.dikplay === 'flex') {\n      submitAuctionPin();\n    }\n  }\n});\n// =================================================================\n\n// Cricket Auction Live Bidding System & Audio Synthesizer\nlet auctionState = null;\nlet currentBidAmount = 0;\nlet currentBiddingTeam = null;\nlet pollTimer = null;\nlet isAuctioneerActing = false;\n\n// Web Audio API Synthesizer for 100% reliable sound effects without any external files\nconst audioCtx = new (window.AudioContext || window.webkitAudioContext)();\n\nfunction playGavelSound() {\n  if (audioCtx.state === 'suspended') audioCtx.resume();\n  // Double sharp wooden knock\n  [0, 0.12].forEach(delay => {\n    const osc = audioCtx.createOscillator();\n    const gain = audioCtx.createGain();\n    osc.type = 'triangle';\n    osc.frequency.setValueAtTime(140, audioCtx.currentTime + delay);\n    osc.frequency.exponentialRampToValueAtTime(30, audioCtx.currentTime + delay + 0.08);\n    gain.gain.setValueAtTime(1, audioCtx.currentTime + delay);\n    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + delay + 0.08);\n    osc.connect(gain);\n    gain.connect(audioCtx.destination);\n    osc.start(audioCtx.currentTime + delay);\n    osc.stop(audioCtx.currentTime + delay + 0.09);\n  });\n}\n\nfunction playFanfareSound() {\n  if (audioCtx.state === 'suspended') audioCtx.resume();\n  // Celebratory trumpet chords\n  const notes = [523.25, 659.25, 783.99, 1046.50]; // C5, E5, G5, C6\n  notes.forEach((freq, idx) => {\n    const osc = audioCtx.createOscillator();\n    const gain = audioCtx.createGain();\n    osc.type = 'sawtooth';\n    osc.frequency.setValueAtTime(freq, audioCtx.currentTime + idx * 0.1);\n    gain.gain.setValueAtTime(0.3, audioCtx.currentTime + idx * 0.1);\n    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + idx * 0.1 + 0.4);\n    osc.connect(gain);\n    gain.connect(audioCtx.destination);\n    osc.start(audioCtx.currentTime + idx * 0.1);\n    osc.stop(audioCtx.currentTime + idx * 0.1 + 0.45);\n  });\n}\n\nfunction playBuzzerSound() {\n  if (audioCtx.state === 'suspended') audioCtx.resume();\n  const osc = audioCtx.createOscillator();\n  const gain = audioCtx.createGain();\n  osc.type = 'sawtooth';\n  osc.frequency.setValueAtTime(120, audioCtx.currentTime);\n  osc.frequency.linearRampToValueAtTime(80, audioCtx.currentTime + 0.4);\n  gain.gain.setValueAtTime(0.4, audioCtx.currentTime);\n  gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.4);\n  osc.connect(gain);\n  gain.connect(audioCtx.destination);\n  osc.start();\n  osc.stop(audioCtx.currentTime + 0.4);\n}\n\nfunction playChimeSound() {\n  if (audioCtx.state === 'suspended') audioCtx.resume();\n  const osc = audioCtx.createOscillator();\n  const gain = audioCtx.createGain();\n  osc.type = 'sine';\n  osc.frequency.setValueAtTime(880, audioCtx.currentTime);\n  gain.gain.setValueAtTime(0.3, audioCtx.currentTime);\n  gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.2);\n  osc.connect(gain);\n  gain.connect(audioCtx.destination);\n  osc.start();\n  osc.stop(audioCtx.currentTime + 0.2);\n}\n\ndocument.addEventListener('DOMContentLoaded', () => {\n  initAuctionPage();\n  startStatePolling();\n});\n\nfunction initAuctionPage() {\n  // Bid Increment buttons\n  document.querySelectorAll('.btn-inc').forEach(btn => {\n    btn.addEventListener('click', () => {\n      const inc = parseInt(btn.dataset.inc || '100');\n      const teamSelect = document.getElementById('bidTeamSelect');\n      const selectedTeam = teamSelect?.value;\n      if (!selectedTeam) {\n        alert('Please select a bidding team first.');\n        return;\n      }\n      playChimeSound();\n      currentBidAmount += inc;\n      currentBiddingTeam = selectedTeam;\n      updateBidDikplay();\n    });\n  });\n\n  // Team select change\n  document.getElementById('bidTeamSelect')?.addEventListener('change', (e) => {\n    currentBiddingTeam = e.target.value;\n    updateBidDikplay();\n  });\n\n  // Primary Action: SOLD\n  document.getElementById('btnSoldAction')?.addEventListener('click', async () => {\n    if (!auctionState?.current_player) {\n      alert('No player is currently on the auction block!');\n      return;\n    }\n    const teamSelect = document.getElementById('bidTeamSelect');\n    const team = teamSelect?.value || currentBiddingTeam;\n    if (!team) {\n      alert('Please select the winning team before clicking SOLD.');\n      return;\n    }\n    if (currentBidAmount <= 0) {\n      alert('Current bid must be greater than 0.');\n      return;\n    }\n\n    if (!confirm(`Confirm sale of ${auctionState.current_player} to ${team} for \u20b9${currentBidAmount}?`)) {\n      return;\n    }\n\n    isAuctioneerActing = true;\n    playGavelSound();\n    playFanfareSound();\n    triggerCelebrationModal(auctionState.current_player, team, currentBidAmount);\n\n    try {\n      const res = await fetch('/api/auction/sell', {\n        method: 'POST',\n        headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': getAuctioneerPin() },\n        body: JSON.stringify({\n          team: team,\n          price: currentBidAmount,\n          pin: getAuctioneerPin()\n        })\n      });\n      const data = await res.json();\n      if (!data.success) {\n        alert(data.message || 'Error executing sale.');\n      } else {\n        setTimeout(fetchState, 1200);\n      }\n    } catch (e) {\n      console.error(e);\n    } finally {\n      setTimeout(() => { isAuctioneerActing = false; }, 2000);\n    }\n  });\n\n  // Primary Action: UNSOLD\n  document.getElementById('btnUnsoldAction')?.addEventListener('click', async () => {\n    if (!auctionState?.current_player) return;\n    if (!confirm(`Mark ${auctionState.current_player} as UNSOLD?`)) return;\n\n    playBuzzerSound();\n    isAuctioneerActing = true;\n    try {\n      const res = await fetch('/api/auction/unsold', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': getAuctioneerPin() }, body: JSON.stringify({ pin: getAuctioneerPin() }) });\n      const data = await res.json();\n      if (data.success) {\n        setTimeout(fetchState, 500);\n      } else {\n        alert(data.message || 'Error marking unsold.');\n      }\n    } catch (e) {\n      console.error(e);\n    } finally {\n      isAuctioneerActing = false;\n    }\n  });\n\n  // Primary Action: UNDO\n  document.getElementById('btnUndoAction')?.addEventListener('click', async () => {\n    if (!confirm('Undo the last auction action?')) return;\n    try {\n      const res = await fetch('/api/auction/undo', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': getAuctioneerPin() }, body: JSON.stringify({ pin: getAuctioneerPin() }) });\n      const data = await res.json();\n      if (data.success) {\n        playChimeSound();\n        checkSavedPin();\n  fetchState();\n      } else {\n        alert(data.message || 'Nothing to undo.');\n      }\n    } catch (e) {\n      console.error(e);\n    }\n  });\n\n  // Next Player\n  document.getElementById('btnNextPlayer')?.addEventListener('click', async () => {\n    try {\n      const res = await fetch('/api/auction/next', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': getAuctioneerPin() }, body: JSON.stringify({ pin: getAuctioneerPin() }) });\n      const data = await res.json();\n      if (data.success) {\n        playChimeSound();\n        fetchState();\n      } else {\n        alert(data.message || 'No more players available in current round.');\n      }\n    } catch (e) {\n      console.error(e);\n    }\n  });\n\n  // Close celebration modal\n  document.getElementById('btnCloseSoldModal')?.addEventListener('click', () => {\n    document.getElementById('soldModalOverlay').classList.remove('active');\n  });\n}\n\nfunction updateBidDikplay() {\n  const amountEl = document.getElementById('currentBidDikplay');\n  const bannerEl = document.getElementById('biddingTeamBanner');\n  if (amountEl) amountEl.textContent = '\u20b9' + currentBidAmount.toLocaleString('en-IN');\n  if (bannerEl) {\n    if (currentBiddingTeam) {\n      bannerEl.innerHTML = `Bidding Leader: <strong>${currentBiddingTeam}</strong>`;\n    } else {\n      bannerEl.innerHTML = `Select a team to start bidding`;\n    }\n  }\n}\n\nasync function fetchState() {\n  if (isAuctioneerActing) return;\n  try {\n    const res = await fetch('/api/auction/state');\n    const data = await res.json();\n    renderAuctionState(data);\n  } catch (e) {\n    console.error('Error fetching state:', e);\n  }\n}\n\nfunction startStatePolling() {\n  fetchState();\n  pollTimer = setInterval(fetchState, 2000);\n}\n\nfunction renderAuctionState(state) {\n  auctionState = state;\n  \n  // Render Round & Pool counts\n  document.getElementById('currentRoundTag').textContent = `Round ${state.current_round}`;\n  document.getElementById('poolStatusTag').textContent = \n    `Remaining in Round: ${state.auction_players?.length || 0} | Total Unsold: ${state.unsold_players?.length || 0}`;\n\n  const playerPodium = document.getElementById('activePlayerPodium');\n  const emptyPodium = document.getElementById('emptyPodiumMsg');\n\n  if (state.current_player) {\n    playerPodium.style.dikplay = 'flex';\n    emptyPodium.style.dikplay = 'none';\n\n    const p = state.player_details || {};\n    const photoEl = document.getElementById('podiumPlayerPhoto');\n    const nameEl = document.getElementById('podiumPlayerName');\n    const serialEl = document.getElementById('podiumPlayerSerial');\n    const roleBadge = document.getElementById('podiumPlayerRole');\n    const metaBatting = document.getElementById('podiumMetaBatting');\n    const metaBowling = document.getElementById('podiumMetaBowling');\n    const metaRegAmount = document.getElementById('podiumMetaRegAmount');\n\n    // Photo\n    if (p.photo_url) {\n      photoEl.src = p.photo_url;\n    } else {\n      // Default SVG based on role\n      const role = (p.role || '').toLowerCase();\n      if (role.includes('bat')) photoEl.src = '/static/images/avatar_batsman.svg';\n      else if (role.includes('bowl')) photoEl.src = '/static/images/avatar_bowler.svg';\n      else if (role.includes('keep')) photoEl.src = '/static/images/avatar_keeper.svg';\n      else photoEl.src = '/static/images/avatar_allrounder.svg';\n    }\n\n    nameEl.textContent = state.current_player;\n    serialEl.textContent = '#' + (state.player_serials?.[state.current_player] || '-');\n    \n    // Role Badge & Styling\n    const roleName = p.role || 'All-Rounder';\n    roleBadge.textContent = roleName;\n    roleBadge.className = 'badge role-tag-floater ' + getRoleBadgeClass(roleName);\n\n    metaBatting.textContent = p.batting_style || 'Right Hand';\n    metaBowling.textContent = p.bowling_style || 'Medium Fast';\n    metaRegAmount.textContent = p.reg_amount ? `Fee Paid: \u20b9${p.reg_amount}` : 'Registration Verified';\n\n    // If starting a fresh player, reset current bid to min_bid or base price\n    if (currentBidAmount === 0 || document.getElementById('currentBidDikplay').dataset.player !== state.current_player) {\n      currentBidAmount = state.min_bid || 50;\n      currentBiddingTeam = null;\n      document.getElementById('currentBidDikplay').dataset.player = state.current_player;\n      updateBidDikplay();\n    }\n  } else {\n    playerPodium.style.dikplay = 'none';\n    emptyPodium.style.dikplay = 'block';\n  }\n\n  // Render Team List & Select Options\n  renderTeams(state.teams);\n}\n\nfunction getRoleBadgeClass(role) {\n  const r = (role || '').toLowerCase();\n  if (r.includes('bat') && !r.includes('keep')) return 'badge-batsman';\n  if (r.includes('bowl')) return 'badge-bowler';\n  if (r.includes('keep')) return 'badge-keeper';\n  return 'badge-allrounder';\n}\n\nfunction renderTeams(teams) {\n  const sidebar = document.getElementById('teamsSidebarList');\n  const select = document.getElementById('bidTeamSelect');\n  \n  if (!teams) return;\n\n  const currentSelectedTeam = select.value;\n  select.innerHTML = '<option value=\"\">-- Select Bidding Team --</option>';\n\n  let html = '';\n  for (const [name, t] of Object.entries(teams)) {\n    // Add to select\n    const opt = document.createElement('option');\n    opt.value = name;\n    opt.textContent = `${name} (Rem: \u20b9${t.budget})`;\n    if (name === currentSelectedTeam || name === currentBiddingTeam) opt.selected = true;\n    select.appendChild(opt);\n\n    const isCurrent = (name === currentBiddingTeam);\n    const playerCount = (t.players ? t.players.length : 0) + (t.retained ? 1 : 0);\n    const pursePercentage = Math.max(0, Math.min(100, (t.budget / (t.budget + t.spent)) * 100));\n\n    html += `\n      <div class=\"team-card ${isCurrent ? 'current-bidder' : ''}\" onclick=\"selectBiddingTeam('${name}')\">\n        <div class=\"team-card-header\">\n          <span class=\"team-name\">${name}</span>\n          <span class=\"team-squad-count\">${playerCount} Squad</span>\n        </div>\n        <div class=\"team-budget-bar-wrap\">\n          <div class=\"team-budget-fill\" style=\"width: ${pursePercentage}%\"></div>\n        </div>\n        <div class=\"team-financials\">\n          <span class=\"team-rem-budget\">\u20b9${t.budget.toLocaleString('en-IN')} Left</span>\n          <span class=\"team-spent-budget\">\u20b9${t.spent.toLocaleString('en-IN')} Spent</span>\n        </div>\n      </div>\n    `;\n  }\n  sidebar.innerHTML = html;\n}\n\nwindow.selectBiddingTeam = function(name) {\n  const select = document.getElementById('bidTeamSelect');\n  if (select) {\n    select.value = name;\n    currentBiddingTeam = name;\n    updateBidDikplay();\n  }\n};\n\nfunction triggerCelebrationModal(player, team, price) {\n  const modal = document.getElementById('soldModalOverlay');\n  document.getElementById('soldModalPlayer').textContent = player;\n  document.getElementById('soldModalTeam').textContent = team;\n  document.getElementById('soldModalPrice').textContent = '\u20b9' + price.toLocaleString('en-IN');\n  modal.classList.add('active');\n  launchConfetti();\n}\n\nfunction launchConfetti() {\n  const canvas = document.getElementById('confettiCanvas');\n  if (!canvas) return;\n  const ctx = canvas.getContext('2d');\n  canvas.width = window.innerWidth;\n  canvas.height = window.innerHeight;\n\n  const particles = [];\n  const colors = ['#f59e0b', '#10b981', '#ef4444', '#3b82f6', '#ec4899', '#ffffff'];\n  \n  for (let i = 0; i < 120; i++) {\n    particles.push({\n      x: canvas.width / 2,\n      y: canvas.height / 2,\n      vx: (Math.random() - 0.5) * 16,\n      vy: (Math.random() - 0.5) * 16 - 4,\n      size: Math.random() * 8 + 4,\n      color: colors[Math.floor(Math.random() * colors.length)],\n      rotation: Math.random() * 360,\n      dr: (Math.random() - 0.5) * 10\n    });\n  }\n\n  let frames = 0;\n  function animate() {\n    ctx.clearRect(0, 0, canvas.width, canvas.height);\n    particles.forEach(p => {\n      p.x += p.vx;\n      p.y += p.vy;\n      p.vy += 0.3; // gravity\n      p.rotation += p.dr;\n      ctx.save();\n      ctx.translate(p.x, p.y);\n      ctx.rotate((p.rotation * Math.PI) / 180);\n      ctx.fillStyle = p.color;\n      ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size);\n      ctx.restore();\n    });\n\n    frames++;\n    if (frames < 90) {\n      requestAnimationFrame(animate);\n    } else {\n      ctx.clearRect(0, 0, canvas.width, canvas.height);\n    }\n  }\n  animate();\n}\n", "static/images/avatar_batsman.svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 200 200\" width=\"100%\" height=\"100%\">\n  <defs>\n    <radialGradient id=\"bg_bat\" cx=\"50%\" cy=\"30%\" r=\"70%\">\n      <stop offset=\"0%\" stop-color=\"#ef4444\"/>\n      <stop offset=\"100%\" stop-color=\"#7f1d1d\"/>\n    </radialGradient>\n  </defs>\n  <circle cx=\"100\" cy=\"100\" r=\"96\" fill=\"url(#bg_bat)\" stroke=\"#fca5a5\" stroke-width=\"4\"/>\n  <circle cx=\"100\" cy=\"65\" r=\"26\" fill=\"#fef2f2\"/>\n  <path d=\"M100 95 C 60 95, 45 130, 45 180 L 155 180 C 155 130, 140 95, 100 95 Z\" fill=\"#fef2f2\"/>\n  <polygon points=\"135,45 150,35 180,135 165,145\" fill=\"#fbbf24\" stroke=\"#b45309\" stroke-width=\"3\"/>\n  <text x=\"100\" y=\"175\" font-family=\"sans-serif\" font-size=\"14\" font-weight=\"900\" fill=\"#7f1d1d\" text-anchor=\"middle\">BATSMAN</text>\n</svg>", "static/images/avatar_bowler.svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 200 200\" width=\"100%\" height=\"100%\">\n  <defs>\n    <radialGradient id=\"bg_bowl\" cx=\"50%\" cy=\"30%\" r=\"70%\">\n      <stop offset=\"0%\" stop-color=\"#3b82f6\"/>\n      <stop offset=\"100%\" stop-color=\"#1e3a8a\"/>\n    </radialGradient>\n  </defs>\n  <circle cx=\"100\" cy=\"100\" r=\"96\" fill=\"url(#bg_bowl)\" stroke=\"#93c5fd\" stroke-width=\"4\"/>\n  <circle cx=\"100\" cy=\"65\" r=\"26\" fill=\"#eff6ff\"/>\n  <path d=\"M100 95 C 60 95, 45 130, 45 180 L 155 180 C 155 130, 140 95, 100 95 Z\" fill=\"#eff6ff\"/>\n  <circle cx=\"155\" cy=\"60\" r=\"18\" fill=\"#dc2626\" stroke=\"#ffffff\" stroke-width=\"2\"/>\n  <text x=\"100\" y=\"175\" font-family=\"sans-serif\" font-size=\"14\" font-weight=\"900\" fill=\"#1e3a8a\" text-anchor=\"middle\">BOWLER</text>\n</svg>", "static/images/avatar_allrounder.svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 200 200\" width=\"100%\" height=\"100%\">\n  <defs>\n    <radialGradient id=\"bg_all\" cx=\"50%\" cy=\"30%\" r=\"70%\">\n      <stop offset=\"0%\" stop-color=\"#f59e0b\"/>\n      <stop offset=\"100%\" stop-color=\"#78350f\"/>\n    </radialGradient>\n  </defs>\n  <circle cx=\"100\" cy=\"100\" r=\"96\" fill=\"url(#bg_all)\" stroke=\"#fde68a\" stroke-width=\"4\"/>\n  <circle cx=\"100\" cy=\"65\" r=\"26\" fill=\"#fffbeb\"/>\n  <path d=\"M100 95 C 60 95, 45 130, 45 180 L 155 180 C 155 130, 140 95, 100 95 Z\" fill=\"#fffbeb\"/>\n  <polygon points=\"65,55 75,45 95,115 85,125\" fill=\"#fbbf24\" stroke=\"#78350f\" stroke-width=\"2\"/>\n  <circle cx=\"145\" cy=\"70\" r=\"14\" fill=\"#dc2626\" stroke=\"#ffffff\" stroke-width=\"2\"/>\n  <text x=\"100\" y=\"175\" font-family=\"sans-serif\" font-size=\"13\" font-weight=\"900\" fill=\"#78350f\" text-anchor=\"middle\">ALL-ROUNDER</text>\n</svg>", "static/images/avatar_keeper.svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 200 200\" width=\"100%\" height=\"100%\">\n  <defs>\n    <radialGradient id=\"bg_keep\" cx=\"50%\" cy=\"30%\" r=\"70%\">\n      <stop offset=\"0%\" stop-color=\"#10b981\"/>\n      <stop offset=\"100%\" stop-color=\"#064e3b\"/>\n    </radialGradient>\n  </defs>\n  <circle cx=\"100\" cy=\"100\" r=\"96\" fill=\"url(#bg_keep)\" stroke=\"#6ee7b7\" stroke-width=\"4\"/>\n  <circle cx=\"100\" cy=\"65\" r=\"26\" fill=\"#ecfdf5\"/>\n  <path d=\"M100 95 C 60 95, 45 130, 45 180 L 155 180 C 155 130, 140 95, 100 95 Z\" fill=\"#ecfdf5\"/>\n  <path d=\"M 65 110 C 65 90, 85 90, 85 110 C 85 130, 65 130, 65 110 Z\" fill=\"#f59e0b\" stroke=\"#78350f\" stroke-width=\"2\"/>\n  <path d=\"M 115 110 C 115 90, 135 90, 135 110 C 135 130, 115 130, 115 110 Z\" fill=\"#f59e0b\" stroke=\"#78350f\" stroke-width=\"2\"/>\n  <text x=\"100\" y=\"175\" font-family=\"sans-serif\" font-size=\"14\" font-weight=\"900\" fill=\"#064e3b\" text-anchor=\"middle\">WK-BATSMAN</text>\n</svg>", "static/images/avatar_default.svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 200 200\" width=\"100%\" height=\"100%\">\n  <defs>\n    <radialGradient id=\"bg_all\" cx=\"50%\" cy=\"30%\" r=\"70%\">\n      <stop offset=\"0%\" stop-color=\"#f59e0b\"/>\n      <stop offset=\"100%\" stop-color=\"#78350f\"/>\n    </radialGradient>\n  </defs>\n  <circle cx=\"100\" cy=\"100\" r=\"96\" fill=\"url(#bg_all)\" stroke=\"#fde68a\" stroke-width=\"4\"/>\n  <circle cx=\"100\" cy=\"65\" r=\"26\" fill=\"#fffbeb\"/>\n  <path d=\"M100 95 C 60 95, 45 130, 45 180 L 155 180 C 155 130, 140 95, 100 95 Z\" fill=\"#fffbeb\"/>\n  <polygon points=\"65,55 75,45 95,115 85,125\" fill=\"#fbbf24\" stroke=\"#78350f\" stroke-width=\"2\"/>\n  <circle cx=\"145\" cy=\"70\" r=\"14\" fill=\"#dc2626\" stroke=\"#ffffff\" stroke-width=\"2\"/>\n  <text x=\"100\" y=\"175\" font-family=\"sans-serif\" font-size=\"13\" font-weight=\"900\" fill=\"#78350f\" text-anchor=\"middle\">ALL-ROUNDER</text>\n</svg>"}

def ensure_assets():
    try:
        for rel_path, content in EMBEDDED_ASSETS.items():
            full_path = os.path.join(BASE_DIR, rel_path)
            if not os.path.exists(full_path):
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, 'w', encoding='utf-8', errors='ignore') as f:
                    f.write(content)
    except Exception as e:
        print("ensure_assets note:", e)

ensure_assets()
# -----------------------------------


CONFIG_FILE = os.path.join(BASE_DIR, 'tournament_config.json')
REGISTRATIONS_FILE = os.path.join(BASE_DIR, 'registrations.json')
AUCTION_STATE_FILE = os.path.join(BASE_DIR, 'auction_state.json')

from jinja2 import ChoiceLoader, FileSystemLoader
app = Flask(__name__, static_folder=STATIC_DIR)
app.jinja_loader = ChoiceLoader([
    FileSystemLoader(os.path.join(BASE_DIR, 'templates')),
    FileSystemLoader(BASE_DIR)
])
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload

# ----------------- CONFIG HELPERS -----------------
def load_config():
    default_config = {
        "tournament_name": "Kunsi Premier League (KPL 2026)",
        "upi_id": "saidapur.cricket@upi",
        "payee_name": "Saidapur Cricket Committee",
        "registration_fee": 200,
        "default_purse": 5000,
        "min_bid": 50,
        "retention_price": 500,
        "owner_retention_price": 100,
        "max_players": 15,
        "currency_symbol": "₹",
        "admin_pin": "2026"
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                default_config.update(cfg)
        except Exception as e:
            print("Error loading config:", e)
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
        "auction_started": False,
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
        village = request.form.get('village', '').strip() or 'Saidapur'
        role = request.form.get('role', 'All-Rounder')
        batting_style = request.form.get('batting_style', 'Right Hand Bat')
        bowling_style = request.form.get('bowling_style', 'None')
        payment_method = request.form.get('payment_method', 'PhonePe')
        transaction_id = request.form.get('transaction_id', '').strip() or 'Direct UPI / Paid'
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
            'payment_status': 'Verified',
            'payment_method': payment_method,
            'transaction_id': transaction_id,
            'payment_screenshot': screenshot_url,
            'created_at': datetime.utcnow().isoformat() + 'Z',
            'approved': True
        }

        save_registrations(regs)
        sync_player_to_auction(name, serial_no)
        
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


def check_auctioneer_pin(req):
    cfg = load_config()
    correct_pin = str(cfg.get('admin_pin', '2026')).strip()
    pin = req.headers.get('X-Auction-PIN')
    if not pin and req.is_json and req.json:
        pin = req.json.get('pin')
    if not pin:
        pin = req.args.get('pin') or req.form.get('pin')
    return str(pin or '').strip() == correct_pin


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
        team_names = data.get('team_names', [])
        if len(team_names) < 2:
            return jsonify({'success': False, 'message': 'At least 2 team names required'}), 400

        cfg = load_config()
        total_purse = int(data.get('total_purse', cfg.get('total_purse', 5000)))
        max_players = int(data.get('max_players', cfg.get('max_players', 15)))
        min_bid = int(data.get('min_bid', cfg.get('min_bid', 0)))
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
                new_teams[t_name] = old_teams[t_name]
            else:
                new_teams[t_name] = {
                    'budget': total_purse,
                    'spent': 0,
                    'players': [],
                    'retained': None
                }

        state['teams'] = new_teams
        state['total_purse'] = total_purse
        state['max_players'] = max_players
        state['min_bid'] = min_bid
        state['retention_price'] = retention_price
        state['owner_retention_price'] = owner_retention_price
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
        ret_type = data.get('retention_type', 'Player')

        state = load_auction_state()
        cfg = load_config()
        teams = state.get('teams', {})

        if team_name not in teams:
            return jsonify({'success': False, 'message': 'Invalid team selected'}), 400

        price = int(cfg.get('owner_retention_price', 100)) if ret_type == 'Owner' else int(cfg.get('retention_price', 500))

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
        ret_type = data.get('retention_type', 'Player')

        state = load_auction_state()
        teams = state.get('teams', {})
        if team_name not in teams:
            return jsonify({'success': False, 'message': 'Team not found'}), 400

        team = teams[team_name]
        target_slot = 'owner_retained' if ret_type == 'Owner' else 'player_retained'
        target_data = team.get(target_slot) or (team.get('retained') if not team.get('player_retained') and not team.get('owner_retained') else None)

        if not target_data:
            return jsonify({'success': False, 'message': f'No {ret_type} retention found for {team_name}'}), 400

        push_history(state)
        released_name = target_data.get('name') if isinstance(target_data, dict) else target_data
        released_cost = target_data.get('cost', 500) if isinstance(target_data, dict) else 500

        team['budget'] += released_cost
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

        # Initialize auction queue if needed
        if not state.get('auction_players'):
            retained_names = []
            for t in state.get('teams', {}).values():
                if t.get('retained'):
                    r_name = t['retained'].get('name') if isinstance(t['retained'], dict) else t['retained']
                    retained_names.append(r_name)
            pool = [p for p in state.get('players', []) if p not in retained_names]
            state['auction_players'] = pool
            if pool and not state.get('current_player'):
                state['current_player'] = pool[0]

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
def api_auction_bid():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Auctioneer PIN required'}), 403
        data = request.json or {}
        bid = int(data.get('bid', 0))
        team = data.get('team')

        state = load_auction_state()
        state['current_bid'] = bid
        if team:
            state['bidding_team'] = team
        state['state_version'] = state.get('state_version', 1) + 1
        save_auction_state(state)
        return jsonify({'success': True, 'bid': bid, 'team': team})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/auction/sell', methods=['POST'])
def api_auction_sell():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Auctioneer PIN required'}), 403
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

        # Exact Validation from criAuctionAntigravity lines 241-257
        current_player_count = len(team.get("players", [])) + (1 if team.get("player_retained") else 0) + (1 if team.get("owner_retained") else 0) + (1 if team.get("retained") and not team.get("player_retained") and not team.get("owner_retained") else 0)
        min_required = int(state.get("max_players", 10))
        min_bid = int(state.get("min_bid", 50))

        if current_player_count < min_required:
            remaining_needed = min_required - current_player_count - 1
            budget_after_purchase = team["budget"] - price
            estimated_cost = max(0, remaining_needed) * min_bid
            if remaining_needed > 0 and budget_after_purchase < estimated_cost:
                return jsonify({
                    'success': False,
                    'message': f"Cannot afford! {team_name} needs {remaining_needed} more players to reach minimum requirement ({min_required}). Budget after purchase would be Rs.{budget_after_purchase}, but you must reserve at least Rs.{estimated_cost}."
                }), 400

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

        if cur_p in state.get('auction_players', []):
            state['auction_players'].remove(cur_p)

        if state.get('auction_players'):
            state['current_player'] = state['auction_players'][0]
        else:
            state['current_player'] = None

        state['last_action'] = {
            'type': 'SOLD',
            'player': cur_p,
            'team': team_name,
            'amount': price,
            'timestamp': int(datetime.now().timestamp() * 1000)
        }
        state['current_bid'] = state.get('min_bid', 50)
        state['bidding_team'] = None
        state['state_version'] = state.get('state_version', 1) + 1

        save_auction_state(state)
        return jsonify({'success': True, 'player': cur_p, 'team': team_name, 'price': price})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/auction/unsold', methods=['POST'])
def api_auction_unsold():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Auctioneer PIN required'}), 403
        data = request.json or {}
        is_permanent = data.get('is_permanent', False)

        state = load_auction_state()
        cur_p = state.get('current_player')
        if not cur_p:
            return jsonify({'success': False, 'message': 'No player on auction'}), 400

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

        if state.get('auction_players'):
            state['current_player'] = state['auction_players'][0]
        else:
            state['current_player'] = None

        state['current_bid'] = state.get('min_bid', 50)
        state['bidding_team'] = None
        state['last_action'] = {
            'type': 'UNSOLD',
            'player': cur_p,
            'is_permanent': is_permanent,
            'timestamp': int(datetime.now().timestamp() * 1000)
        }
        state['state_version'] = state.get('state_version', 1) + 1

        save_auction_state(state)
        return jsonify({'success': True, 'player': cur_p, 'is_permanent': is_permanent})
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
        save_auction_state(state)
        return jsonify({'success': True, 'message': 'Undo successful'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/auction/next', methods=['POST'])
def api_auction_next():
    try:
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Auctioneer PIN required'}), 403
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
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Auctioneer PIN required'}), 403
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
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Auctioneer PIN required'}), 403
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
        if not check_auctioneer_pin(request):
            return jsonify({'success': False, 'message': 'Unauthorized: Valid Auctioneer PIN required'}), 403
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
        "auction_started": False,
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
