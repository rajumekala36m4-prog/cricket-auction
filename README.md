# 🏏 Kunsi Premier League (KPL 2026) — Live Cricket Auction Suite

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/framework-Flask%203.x-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/license-MIT-purple.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-Production%20Ready-brightgreen.svg)]()

A complete, real-time, responsive **Cricket Auction & Tournament Management Web Application** designed for local, regional, and corporate cricket tournaments (IPL-style auction mechanism).

---

## 🌟 Key Features

1. **🎙️ Host Auctioneer Control Console (`/admin`)**
   - 1-Tap Player Draw with category and village filtering.
   - Dynamic quick-bid cards for instant incremental bidding (+50, +100, +200, +500).
   - Instant **UNDO** button to rollback accidental sales or bids.
   - Round 1 $\to$ Round 2 automatic transition for unsold players.
   - Master Organizer PIN protection (`2026`).

2. **📱 Franchise Owner Bidding Portal (`/owner`)**
   - Individual secure team passcodes (`DR26`, `KW26`, `SS26`, `TT26`, `HB26`).
   - 1-Tap live bidding button with real-time budget and squad counters.
   - **Anti-Self-Bidding Guard**: Prevents teams from bidding against themselves.
   - **Squad Reserve Budget Formula**: Automatically ensures teams reserve enough purse to fill minimum required squad slots at base price.

3. **📺 Public Live Spectator Stream (`/view`)**
   - Real-time animated auction block showing player photo, role, base price, and current bid.
   - Live Last-Sold Ticker with team badge and sale price.
   - Complete live squad rosters and remaining budget meters for all franchises.
   - Full mobile responsiveness (portrait & landscape optimized).

4. **📝 Player Registration & Verification Portal (`/register`)**
   - Public player signup with batting style, bowling style, role, village, and mobile number.
   - HD Photo upload with base64 thumbnail rendering and lightbox view.
   - UPI fee payment submission with UTR number and payment receipt screenshot.
   - Toggleable Free vs Paid registration mode from Admin settings.

5. **📊 Professional Excel Accounting & Reporting**
   - **Full Tournament Financial Sheet** (`/api/export-excel`): Complete mathematical breakdown of squad lists, purse spent, remaining purse, and player purchase prices.
   - **Approved Players Roster** (`/api/export-approved-players-excel`): Official 4-column formatted roster (`ID`, `Player Name`, `Role`, `Mobile Number`).

6. **🔒 Tournament Integrity & Crash Resilience**
   - Atomic disk persistence (`auction_state.json`, `registrations.json`, `tournament_config.json`).
   - Zero state loss across server restarts or unexpected crashes.
   - Integrated full-vault backup & restore system.

---

## 🚀 Quick Start (Local Setup)

### 1. Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/kpl-cricket-auction.git
cd kpl-cricket-auction
```

### 2. Create Virtual Environment & Install Dependencies
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Run the Application
```bash
python auction_web_suite.py
```
Open your browser at: **`http://localhost:5000`**

---

## 🌐 Public URLs & Navigation

| Screen / Portal | URL | Description / Credentials |
| :--- | :--- | :--- |
| **Home / Landing Page** | `/` | Tournament hub & portal navigation |
| **Live Spectator Stream** | `/view` | Public live auction feed (No PIN required) |
| **Player Registration** | `/register` | Public registration with photo & UPI UTR |
| **Franchise Owner Portal** | `/owner` | Team passcodes: `DR26`, `KW26`, `SS26`, `TT26`, `HB26` |
| **Organizer / Host Console** | `/admin` | Organizer PIN: `2026` |
| **Team Rosters & Budgets** | `/teams` | Live squad standings |

---

## ☁️ Deployment Guide

### Deploying to Render.com
1. Fork or push this repository to your GitHub account.
2. In Render Dashboard, click **New +** $\to$ **Web Service**.
3. Connect your GitHub repository.
4. Render will automatically detect `render.yaml` or you can configure:
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn auction_web_suite:app`
5. Click **Deploy Web Service**!

### Deploying to Railway / Heroku
The included `Procfile` is pre-configured:
```text
web: gunicorn auction_web_suite:app
```

---

## 📋 Default Tournament Configuration

- **Organizer PIN:** `2026`
- **Default Purse:** `₹5,000`
- **Minimum Bid Increment:** `₹100`
- **Star Player Retention:** `₹500`
- **Owner Retention:** `₹100`
- **Initial Teams:**
  - `Deccan Royals` (Passcode: `DR26`)
  - `Kunsi Warriors` (Passcode: `KW26`)
  - `Saidapur Super Kings` (Passcode: `SS26`)
  - `Telangana Titans` (Passcode: `TT26`)
  - `Hyderabad Blasters` (Passcode: `HB26`)

---

## 🛡️ License
Released under the [MIT License](LICENSE).
