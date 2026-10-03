// ==================== REAL-TIME CRICKET AUCTION ENGINE ====================
// Supports both Host Operator Console and Mobile Viewers Live Stream

let auctionState = null;
let currentBidAmount = 0;
let currentBiddingTeam = null;
let pollTimer = null;
let isAuctioneerActing = false;
let lastActionTimestamp = 0;
let poolActiveFilter = 'all';

// --- TOAST NOTIFICATIONS (NO BLOCKING POPUPS) ---
function showToast(message, type = 'info') {
  let toastContainer = document.getElementById('toastContainer');
  if (!toastContainer) {
    toastContainer = document.createElement('div');
    toastContainer.id = 'toastContainer';
    toastContainer.style.cssText = 'position:fixed; top:20px; right:20px; z-index:999999; display:flex; flex-direction:column; gap:10px; max-width:380px; pointer-events:none;';
    document.body.appendChild(toastContainer);
  }
  const toast = document.createElement('div');
  const bg = type === 'error' ? 'linear-gradient(135deg, #ef4444, #b91c1c)' :
             (type === 'success' ? 'linear-gradient(135deg, #10b981, #059669)' :
             (type === 'warning' ? 'linear-gradient(135deg, #f59e0b, #d97706)' : 'linear-gradient(135deg, #38bdf8, #0284c7)'));
  toast.style.cssText = `background:${bg}; color:#fff; padding:12px 18px; border-radius:10px; font-weight:800; font-size:0.92rem; box-shadow:0 10px 30px rgba(0,0,0,0.5); display:flex; align-items:center; justify-content:space-between; pointer-events:auto; transition:all 0.3s ease; border: 1px solid rgba(255,255,255,0.2);`;
  toast.innerHTML = `<span>${message}</span><button onclick="this.parentElement.remove()" style="background:none;border:none;color:#fff;font-size:1.3rem;cursor:pointer;margin-left:12px;line-height:1;">&times;</button>`;
  toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(-10px)';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// --- PIN HELPERS ---
function getAuctioneerPin() {
  return sessionStorage.getItem('kpl_auction_pin') || sessionStorage.getItem('spl_auction_pin') || localStorage.getItem('kpl_auction_pin') || '2026';
}

function setAuctioneerPin(pin) {
  sessionStorage.setItem('kpl_auction_pin', pin);
  sessionStorage.setItem('spl_auction_pin', pin);
  localStorage.setItem('kpl_auction_pin', pin);
}

function requirePinAuth(callback) {
  const pin = getAuctioneerPin();
  if (pin) {
    return true;
  }
  window._pendingAction = callback;
  openPinModal();
  return false;
}

// --- PIN MODAL FUNCTIONS ---
function openPinModal() {
  const modal = document.getElementById('pinModal') || document.getElementById('hostPinModal');
  const input = document.getElementById('inputHostPin') || document.getElementById('inputAuctionPin');
  const err = document.getElementById('pinErrorMsg');
  if (err) err.style.display = 'none';
  if (input) { input.value = ''; }
  if (modal) {
    modal.style.display = 'flex';
    setTimeout(() => { if (input) input.focus(); }, 100);
  }
}

function closePinModal() {
  const modal = document.getElementById('pinModal') || document.getElementById('hostPinModal');
  if (modal) modal.style.display = 'none';
  window._pendingAction = null;
}

async function verifyHostPin() {
  const input = document.getElementById('inputHostPin') || document.getElementById('inputAuctionPin');
  const err = document.getElementById('pinErrorMsg');
  const pin = input ? input.value.trim() : '';

  if (!pin) {
    if (err) { err.textContent = 'Please enter the Organizer PIN.'; err.style.display = 'block'; }
    return;
  }

  try {
    const res = await fetch('/api/auction/verify-pin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin: pin })
    });
    const data = await res.json();
    if (data.success || data.valid) {
      setAuctioneerPin(pin);
      applyAuctioneerMode(true);
      closePinModal();
      showToast('Organizer Authenticated! Host Controls Active.', 'success');
      if (typeof window._pendingAction === 'function') {
        const action = window._pendingAction;
        window._pendingAction = null;
        try { action(); } catch(e) { console.error('Pending action error:', e); }
      }
    } else {
      if (err) { err.textContent = data.message || 'Incorrect Organizer PIN.'; err.style.display = 'block'; }
    }
  } catch (e) {
    if (err) { err.textContent = 'Verification error: ' + e.message; err.style.display = 'block'; }
  }
}

function lockAuctioneer() {
  sessionStorage.removeItem('kpl_auction_pin');
  sessionStorage.removeItem('spl_auction_pin');
  applyAuctioneerMode(false);
  showToast('Admin locked.', 'info');
}

function applyAuctioneerMode(isHost) {
  const authBox = document.getElementById('auctioneerAuthBox');
  const hostDeck = document.getElementById('auctioneerControls') || document.getElementById('auctioneerControlDeck');

  if (hostDeck) {
    hostDeck.style.display = isHost ? 'block' : 'none';
  }

  if (authBox) {
    if (isHost) {
      authBox.innerHTML = `
        <span style="color: #34d399; font-size: 0.85rem; font-weight: 800; display: inline-flex; align-items: center; gap: 0.35rem; background: rgba(16,185,129,0.15); padding: 0.3rem 0.65rem; border-radius: 6px; border: 1px solid rgba(16,185,129,0.3);">
          <span>🔓</span> Host Active
        </span>
        <button type="button" onclick="lockAuctioneer()" class="btn btn-secondary" style="font-size: 0.75rem; padding: 0.25rem 0.5rem; margin-left: 0.35rem;">Lock</button>
      `;
    } else {
      authBox.innerHTML = `
        <button type="button" id="btnUnlockAuctioneer" onclick="openPinModal()" class="btn btn-secondary" style="font-size: 0.8rem; padding: 0.3rem 0.65rem; border-color: rgba(245, 158, 11, 0.5); color: #f59e0b; display: flex; align-items: center; gap: 0.35rem;">
          <span>🔒</span> Host Controls
        </button>
      `;
    }
  }
}

async function checkSavedPin() {
  const saved = getAuctioneerPin();
  if (!saved) {
    applyAuctioneerMode(false);
    return;
  }
  try {
    const res = await fetch('/api/auction/verify-pin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin: saved })
    });
    const data = await res.json();
    if (data.success || data.valid) {
      applyAuctioneerMode(true);
    } else {
      sessionStorage.removeItem('kpl_auction_pin');
      sessionStorage.removeItem('spl_auction_pin');
      applyAuctioneerMode(false);
    }
  } catch (e) {
    applyAuctioneerMode(false);
  }
}

// --- SYNTHESIZED SOUND EFFECTS ---
const AudioContextClass = window.AudioContext || window.webkitAudioContext;
let audioCtx = null;

function getAudioContext() {
  if (!audioCtx && AudioContextClass) {
    try { audioCtx = new AudioContextClass(); } catch(e) {}
  }
  if (audioCtx && audioCtx.state === 'suspended') {
    audioCtx.resume();
  }
  return audioCtx;
}

function playGavelSound() {
  const ctx = getAudioContext();
  if (!ctx) return;
  [0, 0.12].forEach(delay => {
    try {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(140, ctx.currentTime + delay);
      osc.frequency.exponentialRampToValueAtTime(30, ctx.currentTime + delay + 0.08);
      gain.gain.setValueAtTime(1, ctx.currentTime + delay);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + delay + 0.08);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(ctx.currentTime + delay);
      osc.stop(ctx.currentTime + delay + 0.09);
    } catch(e) {}
  });
}

function playFanfareSound() {
  const ctx = getAudioContext();
  if (!ctx) return;
  const notes = [523.25, 659.25, 783.99, 1046.50];
  notes.forEach((freq, idx) => {
    try {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(freq, ctx.currentTime + idx * 0.1);
      gain.gain.setValueAtTime(0.3, ctx.currentTime + idx * 0.1);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + idx * 0.1 + 0.4);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(ctx.currentTime + idx * 0.1);
      osc.stop(ctx.currentTime + idx * 0.1 + 0.45);
    } catch(e) {}
  });
}

function playBuzzerSound() {
  const ctx = getAudioContext();
  if (!ctx) return;
  try {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(120, ctx.currentTime);
    osc.frequency.linearRampToValueAtTime(80, ctx.currentTime + 0.4);
    gain.gain.setValueAtTime(0.4, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.4);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.4);
  } catch(e) {}
}

function playChimeSound() {
  const ctx = getAudioContext();
  if (!ctx) return;
  try {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.2);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.2);
  } catch(e) {}
}

// --- REAL-TIME BID BROADCAST ---
function broadcastBid(amount, team) {
  if (window.IS_VIEWER_MODE) return;
  const pin = getAuctioneerPin();
  fetch('/api/auction/bid', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': pin },
    body: JSON.stringify({ bid: amount, team: team, pin: pin })
  }).then(r => r.json()).then(data => {
    if (!data.success) {
      showToast(data.message || 'Bid rejected', 'error');
      fetchState();
    }
  }).catch(e => console.warn('Broadcast error:', e));
}

// --- ACTIVE INCREMENT & 1-TAP QUICK TEAM BIDDING ---
let activeIncrement = 50;

function setActiveIncrement(amt) {
  activeIncrement = amt;
  document.querySelectorAll('.inc-pill-btn').forEach(btn => {
    const a = parseInt(btn.dataset.amt);
    if (a === amt) {
      btn.style.background = '#38bdf8';
      btn.style.color = '#0b1120';
      btn.style.border = 'none';
    } else {
      btn.style.background = 'rgba(255,255,255,0.08)';
      btn.style.color = '#fff';
      btn.style.border = '1px solid rgba(255,255,255,0.15)';
    }
  });
}

function quickBidTeam(teamName) {
  if (!requirePinAuth(() => quickBidTeam(teamName))) return;

  if (!auctionState || !auctionState.current_player) {
    showToast('Click "Next Draw" to bring a player to the block first!', 'warning');
    return;
  }

  const p = (auctionState.all_player_details && auctionState.all_player_details[auctionState.current_player]) || auctionState.player_details || {};
  const basePrice = Math.max(100, Number(p.base_price || auctionState.min_bid || 100));

  playChimeSound();
  // First bid rule: if no team is leading or currentBidAmount is 0, start at base price (e.g. 100)
  if (!currentBiddingTeam || currentBidAmount === 0) {
    currentBidAmount = basePrice;
  } else {
    currentBidAmount = currentBidAmount + (activeIncrement || 50);
  }
  currentBiddingTeam = teamName;

  const teamSelect = document.getElementById('biddingTeamSelect') || document.getElementById('bidTeamSelect');
  if (teamSelect) teamSelect.value = teamName;

  updateBidDisplay();
  broadcastBid(currentBidAmount, currentBiddingTeam);
  showToast(`${teamName} bids ₹${currentBidAmount}`, 'info');
  renderQuickTeamGrid();
}

function renderQuickTeamGrid() {
  const grid = document.getElementById('quickTeamGrid');
  if (!grid || !auctionState || !auctionState.teams) return;
  grid.innerHTML = '';
  const teams = auctionState.teams;
  const maxPurse = auctionState.default_purse || auctionState.total_purse || 6000;

  Object.entries(teams).forEach(([name, data]) => {
    const purse = (data.budget !== undefined) ? data.budget : ((data.purse !== undefined) ? data.purse : maxPurse);
    const pct = Math.max(0, Math.min(100, Math.round((purse / maxPurse) * 100)));
    const count = (data.players || []).length + (data.player_retained ? 1 : 0) + (data.owner_retained ? 1 : 0) + (data.retained && !data.player_retained && !data.owner_retained ? 1 : 0);
    const isLeading = (currentBiddingTeam === name);

    const card = document.createElement('div');
    card.className = 'team-quick-bid-card';
    card.dataset.team = name;
    card.onclick = () => quickBidTeam(name);
    card.style.cssText = `
      background: ${isLeading ? 'linear-gradient(145deg, rgba(16,185,129,0.25), rgba(15,23,42,0.95))' : 'rgba(11,17,32,0.85)'};
      border: ${isLeading ? '2px solid #10b981' : '1.5px solid rgba(255,255,255,0.12)'};
      border-radius: 12px;
      padding: 0.5rem 0.55rem;
      cursor: pointer;
      transition: all 0.15s ease;
      box-shadow: ${isLeading ? '0 0 18px rgba(16,185,129,0.35)' : 'none'};
      user-select: none;
      touch-action: manipulation;
      min-width: 0;
      box-sizing: border-box;
      overflow: hidden;
    `;
    card.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.25rem; min-width:0; gap:0.25rem; width:100%;">
        <strong style="font-size:0.8rem; font-weight:800; color:${isLeading ? '#34d399' : '#fff'}; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; min-width:0; flex:1;" title="${name}">${name}</strong>
        <span style="font-size:0.65rem; font-weight:800; background:rgba(255,255,255,0.1); padding:0.08rem 0.32rem; border-radius:9999px; color:#94a3b8; flex-shrink:0; white-space:nowrap;">${count}P</span>
      </div>
      <div style="width:100%; height:3.5px; background:rgba(255,255,255,0.08); border-radius:99px; overflow:hidden; margin-bottom:0.3rem;">
        <div style="height:100%; width:${pct}%; background:linear-gradient(90deg,#10b981,#34d399); border-radius:99px;"></div>
      </div>
      <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.75rem; min-width:0; gap:0.2rem; width:100%;">
        <span style="font-weight:900; color:#10b981; font-size:0.78rem; white-space:nowrap; flex-shrink:0;">₹${purse}</span>
        <span style="background:${isLeading ? '#10b981' : 'rgba(56,189,248,0.15)'}; color:${isLeading ? '#000' : '#38bdf8'}; font-weight:800; padding:0.1rem 0.35rem; border-radius:6px; font-size:0.65rem; white-space:nowrap; flex-shrink:0;">
          ${isLeading ? '🎯 LEADING' : '+ Tap to Bid'}
        </span>
      </div>
    `;
    grid.appendChild(card);
  });
}

// --- BID ADJUSTER (+50, +100, +200, +500, -50) ---
function adjustCurrentBid(delta) {
  if (!requirePinAuth(() => adjustCurrentBid(delta))) return;

  if (!auctionState || !auctionState.current_player) {
    showToast('Click "Next Draw" to bring a player to the auction block first!', 'warning');
    return;
  }

  const teamSelect = document.getElementById('biddingTeamSelect') || document.getElementById('bidTeamSelect');
  const selectedTeam = (teamSelect && teamSelect.value) ? teamSelect.value : currentBiddingTeam;

  if (delta > 0 && !selectedTeam) {
    showToast('Please select a bidding team from the dropdown first.', 'warning');
    if (teamSelect) teamSelect.focus();
    return;
  }

  playChimeSound();
  currentBidAmount = Math.max(0, currentBidAmount + delta);
  currentBiddingTeam = selectedTeam;
  updateBidDisplay();
  broadcastBid(currentBidAmount, currentBiddingTeam);
}

function stepBid(delta) {
  adjustCurrentBid(delta);
}

// --- ASSIGN LEADING BIDDER ---
function assignLeadingBidder() {
  if (!requirePinAuth(assignLeadingBidder)) return;

  const teamSelect = document.getElementById('biddingTeamSelect') || document.getElementById('bidTeamSelect');
  const team = teamSelect ? teamSelect.value : '';
  if (!team) {
    showToast('Please select a team from the dropdown.', 'warning');
    return;
  }
  currentBiddingTeam = team;
  updateBidDisplay();
  broadcastBid(currentBidAmount, currentBiddingTeam);
  showToast(`Leading bidder set to ${team}`, 'info');
}

// --- DRAW NEXT PLAYER ---
async function drawNextPlayer(force = false) {
  closeSoldModal();
  closeUnsoldModal();
  if (!requirePinAuth(() => drawNextPlayer(force))) return;

  if (!force && auctionState && auctionState.current_player) {
    const pName = auctionState.current_player;
    const ok = confirm(`⚠️ "${pName}" is currently active on the auction block!\n\nDo you want to SKIP and draw a new player without selling or marking unsold?`);
    if (!ok) return;
    force = true;
  }

  try {
    const pin = getAuctioneerPin();
    const res = await fetch('/api/auction/next', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': pin },
      body: JSON.stringify({ pin: pin, force: force })
    });
    const data = await res.json();
    if (data.success) {
      playChimeSound();
      currentBidAmount = data.base_price || 50;
      currentBiddingTeam = null;
      if (data.auto_round2) {
        showToast(`🔥 Round 2 (Unsold Pool) Commenced! Drawn: ${data.player}`, 'success');
      } else {
        showToast(`🎯 Drawn: ${data.player} (Base: ₹${currentBidAmount})`, 'success');
      }
      fetchState();
    } else if (data.needs_confirmation) {
      const ok = confirm(`⚠️ ${data.message}\n\nDo you wish to skip anyway?`);
      if (ok) {
        drawNextPlayer(true);
      }
    } else {
      showToast(data.message || 'No more players available in tournament.', 'warning');
    }
  } catch (e) {
    showToast('Error drawing player: ' + e.message, 'error');
  }
}

// --- CONFIRM SOLD PLAYER ---
async function confirmSellPlayer() {
  if (!requirePinAuth(confirmSellPlayer)) return;

  if (!auctionState || !auctionState.current_player) {
    showToast('No player is currently on the auction block!', 'warning');
    return;
  }

  const teamSelect = document.getElementById('biddingTeamSelect') || document.getElementById('bidTeamSelect');
  const team = (teamSelect && teamSelect.value) ? teamSelect.value : currentBiddingTeam;

  if (!team) {
    showToast('Please select the winning team before clicking SOLD!', 'warning');
    if (teamSelect) teamSelect.focus();
    return;
  }

  if (currentBidAmount <= 0) {
    showToast('Current bid amount must be greater than 0.', 'warning');
    return;
  }

  if (!confirm(`Confirm sale of ${auctionState.current_player} to ${team} for ₹${currentBidAmount}?`)) {
    return;
  }

  isAuctioneerActing = true;
  playGavelSound();
  playFanfareSound();
  triggerCelebrationModal(auctionState.current_player, team, currentBidAmount);

  try {
    const pin = getAuctioneerPin();
    const res = await fetch('/api/auction/sell', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': pin },
      body: JSON.stringify({
        team: team,
        price: currentBidAmount,
        pin: pin
      })
    });
    const data = await res.json();
    if (!data.success) {
      showToast(data.message || 'Error executing sale.', 'error');
    } else {
      showToast(`🎉 Sold ${auctionState.current_player} to ${team} for ₹${currentBidAmount}!`, 'success');
      setTimeout(fetchState, 1000);
    }
  } catch (e) {
    showToast('Error executing sale: ' + e.message, 'error');
  } finally {
    setTimeout(() => { isAuctioneerActing = false; }, 2000);
  }
}

// --- MARK UNSOLD (ROUND 2 OR PERMANENT) ---
async function markUnsold(isPermanent) {
  if (!requirePinAuth(() => markUnsold(isPermanent))) return;

  if (!auctionState || !auctionState.current_player) {
    showToast('No player is currently on the auction block!', 'warning');
    return;
  }

  const player = auctionState.current_player;
  const promptText = isPermanent
    ? `⚠️ Confirm PERMANENT UNSOLD for ${player}? This player will NOT return in Round 2.`
    : `Mark ${player} as UNSOLD? (This player will return in Round 2)`;

  if (!confirm(promptText)) return;

  playBuzzerSound();
  isAuctioneerActing = true;
  try {
    const pin = getAuctioneerPin();
    const res = await fetch('/api/auction/unsold', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': pin },
      body: JSON.stringify({ is_permanent: !!isPermanent, pin: pin })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Marked ${player} as unsold.`, 'info');
      setTimeout(fetchState, 500);
    } else {
      showToast(data.message || 'Error marking player unsold.', 'error');
    }
  } catch (e) {
    showToast('Error marking unsold: ' + e.message, 'error');
  } finally {
    isAuctioneerActing = false;
  }
}

// --- UNDO LAST ACTION ---
async function undoLastAction() {
  if (!requirePinAuth(undoLastAction)) return;

  if (!confirm('Undo the last auction action? This will restore the player and team purse.')) return;

  try {
    const pin = getAuctioneerPin();
    const res = await fetch('/api/auction/undo', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': pin },
      body: JSON.stringify({ pin: pin })
    });
    const data = await res.json();
    if (data.success) {
      playChimeSound();
      showToast('Last auction action undone successfully!', 'success');
      fetchState();
    } else {
      showToast(data.message || 'Nothing to undo.', 'warning');
    }
  } catch (e) {
    showToast('Error undoing action: ' + e.message, 'error');
  }
}

// --- START ROUND 2 ---
async function startRound2() {
  if (!requirePinAuth(startRound2)) return;

  if (!confirm('Start Round 2 for all previously unsold players?')) return;

  try {
    const pin = getAuctioneerPin();
    const res = await fetch('/api/auction/round2', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': pin },
      body: JSON.stringify({ pin: pin })
    });
    const data = await res.json();
    if (data.success) {
      showToast('Round 2 started successfully!', 'success');
      fetchState();
    } else {
      showToast(data.message || 'Error starting Round 2.', 'error');
    }
  } catch (e) {
    showToast('Error: ' + e.message, 'error');
  }
}

// --- SOLD & UNSOLD MODAL HELPERS ---
window._soldDismissTimer = null;
window._unsoldDismissTimer = null;
window._lastSoldPlayer = null;

function closeSoldModal() {
  if (window._soldDismissTimer) {
    clearTimeout(window._soldDismissTimer);
    window._soldDismissTimer = null;
  }
  const modal = document.getElementById('soldModal') || document.getElementById('soldModalOverlay');
  if (modal) {
    modal.classList.remove('active');
    modal.style.display = 'none';
  }
}

function closeUnsoldModal() {
  if (window._unsoldDismissTimer) {
    clearTimeout(window._unsoldDismissTimer);
    window._unsoldDismissTimer = null;
  }
  const modal = document.getElementById('unsoldModal');
  if (modal) {
    modal.classList.remove('active');
    modal.style.display = 'none';
  }
}

function handleSoldModalBackdrop(e) {
  if (e.target === document.getElementById('soldModal') || e.target.classList.contains('sold-modal-overlay')) {
    closeSoldModal();
  }
}

function handleUnsoldModalBackdrop(e) {
  if (e.target === document.getElementById('unsoldModal') || e.target.classList.contains('sold-modal-overlay')) {
    closeUnsoldModal();
  }
}

async function drawNextFromModal() {
  closeSoldModal();
  closeUnsoldModal();
  await drawNextPlayer();
}

async function drawNextFromUnsoldModal() {
  closeUnsoldModal();
  closeSoldModal();
  await drawNextPlayer();
}

function triggerUnsoldModal(player, isPermanent) {
  closeSoldModal();
  const modal = document.getElementById('unsoldModal');
  if (!modal) return;
  const nameEl = document.getElementById('unsoldPlayerName');
  const bannerEl = document.getElementById('unsoldModalBanner');
  const subEl = document.getElementById('unsoldModalSubtitle');
  const photoEl = document.getElementById('unsoldPlayerPhoto');
  const roleBadge = document.getElementById('unsoldPlayerRoleBadge');

  if (nameEl) nameEl.textContent = player || '-';
  if (bannerEl) {
    bannerEl.textContent = isPermanent ? '⛔ PERMANENTLY UNSOLD ⛔' : '❌ UNSOLD (ROUND 2) ❌';
  }
  if (subEl) {
    subEl.textContent = isPermanent ? 
      'No bids were placed. This player is permanently excluded from the tournament.' :
      'No bids were placed. This player has been queued for Round 2 (Unsold Pool).';
  }

  const playerInfo = (auctionState?.all_player_details && auctionState.all_player_details[player]) ||
                     (auctionState?.player_details?.name === player ? auctionState.player_details : null);

  const roleName = playerInfo?.role || 'All-Rounder';
  if (roleBadge) {
    roleBadge.textContent = roleName;
    roleBadge.className = 'role-badge ' + getRoleBadgeClass(roleName);
  }

  if (photoEl) {
    let photoSrc = playerInfo?.photo_url;
    if (!photoSrc) {
      const r = (roleName).toLowerCase();
      if (r.includes('keep')) photoSrc = '/static/images/avatar_keeper.svg';
      else if (r.includes('bowl')) photoSrc = '/static/images/avatar_bowler.svg';
      else if (r.includes('bat')) photoSrc = '/static/images/avatar_batsman.svg';
      else photoSrc = '/static/images/avatar_allrounder.svg';
    }
    photoEl.src = photoSrc;
  }

  modal.style.display = 'flex';
  modal.classList.add('active');

  if (window._unsoldDismissTimer) clearTimeout(window._unsoldDismissTimer);
  window._unsoldDismissTimer = setTimeout(() => {
    closeUnsoldModal();
  }, 4500);
}

// --- PICK SPECIFIC PLAYER FROM LIST ---
async function chooseSelectedPlayer(val) {
  if (!requirePinAuth(() => chooseSelectedPlayer(val))) return;

  const select = document.getElementById('selectPlayerDropdown');
  const player = val || (select ? select.value : '');

  if (!player) {
    showToast('Please select a player from the dropdown first.', 'warning');
    return;
  }

  closeSoldModal();
  try {
    const pin = getAuctioneerPin();
    const res = await fetch('/api/auction/select-player', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': pin },
      body: JSON.stringify({ player: player, pin: pin })
    });
    const data = await res.json();
    if (data.success) {
      playChimeSound();
      currentBidAmount = data.base_price || 50;
      currentBiddingTeam = null;
      showToast(`🎯 Drawn: ${data.player} (Base: ₹${currentBidAmount})`, 'success');
      await fetchState();
    } else {
      showToast(data.message || 'Error selecting player', 'error');
    }
  } catch (e) {
    showToast('Error selecting player: ' + e.message, 'error');
  }
}

function triggerCelebrationModal(player, team, price) {
  window._lastSoldPlayer = player;
  const modal = document.getElementById('soldModal') || document.getElementById('soldModalOverlay');
  const nameEl = document.getElementById('soldPlayerName');
  const teamEl = document.getElementById('soldTeamName');
  const priceEl = document.getElementById('soldFinalPrice');
  const photoEl = document.getElementById('soldPlayerPhoto');
  const roleBadge = document.getElementById('soldPlayerRoleBadge');

  if (nameEl) nameEl.textContent = player || '-';
  if (teamEl) teamEl.textContent = team || '-';
  if (priceEl) priceEl.textContent = '₹' + (price || 0).toLocaleString('en-IN');

  const playerInfo = (auctionState?.all_player_details && auctionState.all_player_details[player]) ||
                     (auctionState?.player_details?.name === player ? auctionState.player_details : null);

  const roleName = playerInfo?.role || 'All-Rounder';
  if (roleBadge) {
    roleBadge.textContent = roleName;
    roleBadge.className = 'role-badge ' + getRoleBadgeClass(roleName);
  }

  if (photoEl) {
    let photoSrc = playerInfo?.photo_url;
    if (!photoSrc) {
      const r = (roleName).toLowerCase();
      if (r.includes('keep')) photoSrc = '/static/images/avatar_keeper.svg';
      else if (r.includes('bowl')) photoSrc = '/static/images/avatar_bowler.svg';
      else if (r.includes('bat')) photoSrc = '/static/images/avatar_batsman.svg';
      else photoSrc = '/static/images/avatar_allrounder.svg';
    }
    photoEl.src = photoSrc;
  }

  if (modal) {
    modal.style.display = 'flex';
    modal.classList.add('active');
  }

  if (window._soldDismissTimer) clearTimeout(window._soldDismissTimer);
  window._soldDismissTimer = setTimeout(() => {
    closeSoldModal();
  }, 5000);
}

// --- UPDATE BID DISPLAY ---
function updateBidDisplay() {
  const odometerEl = document.getElementById('bidOdometer') || document.getElementById('currentBidDisplay');
  const tagEl = document.getElementById('leadingTeamTag') || document.getElementById('biddingTeamBanner');

  if (odometerEl) {
    odometerEl.textContent = '₹' + currentBidAmount.toLocaleString('en-IN');
  }

  if (tagEl) {
    if (currentBiddingTeam) {
      tagEl.textContent = `🎯 Leading: ${currentBiddingTeam}`;
      tagEl.style.background = 'rgba(245, 158, 11, 0.25)';
      tagEl.style.color = '#fbbf24';
      tagEl.style.borderColor = 'rgba(245, 158, 11, 0.5)';
    } else {
      tagEl.textContent = 'No Bids Yet';
      tagEl.style.background = 'rgba(255, 255, 255, 0.08)';
      tagEl.style.color = '#94a3b8';
      tagEl.style.borderColor = 'rgba(255, 255, 255, 0.15)';
    }
  }

  const teamSelect = document.getElementById('biddingTeamSelect') || document.getElementById('bidTeamSelect');
  if (teamSelect && currentBiddingTeam && teamSelect.value !== currentBiddingTeam) {
    teamSelect.value = currentBiddingTeam;
  }
}

// --- FETCH & RENDER STATE ---
async function fetchState() {
  if (isAuctioneerActing) return;
  try {
    const res = await fetch('/api/auction/state?_t=' + Date.now(), { cache: 'no-store' });
    if (!res.ok) return;
    const data = await res.json();
    renderAuctionState(data);
  } catch (e) {
    console.error('Error fetching state:', e);
  }
}

function startStatePolling() {
  fetchState();
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(fetchState, 400);
}

function renderAuctionState(state) {
  if (!state) return;
  auctionState = state;

  if (state.last_action && state.last_action.type === 'DRAW') {
    closeSoldModal();
    closeUnsoldModal();
  }

  // Populate Remaining Player Picker Dropdown for Host
  const pickerDropdown = document.getElementById('selectPlayerDropdown');
  if (pickerDropdown && state.auction_players) {
    const currentVal = pickerDropdown.value;
    pickerDropdown.innerHTML = '<option value="">-- Choose Player to Bring to Auction --</option>' +
      state.auction_players.map(pName => {
        const pRole = (state.all_player_details && state.all_player_details[pName]?.role) || '';
        const pSerial = state.player_serials?.[pName] ? `(#${state.player_serials[pName]}) ` : '';
        const roleLabel = pRole ? ` [${pRole}]` : '';
        return `<option value="${pName}">${pSerial}${pName}${roleLabel}</option>`;
      }).join('');
    if (currentVal) pickerDropdown.value = currentVal;
  }

  // Connection tag
  const poolTag = document.getElementById('poolStatusTag');
  if (poolTag) {
    const rem = state.auction_players?.length || 0;
    const unsold = state.unsold_players?.length || 0;
    poolTag.textContent = `Remaining: ${rem} | Unsold: ${unsold}`;
    poolTag.style.background = 'rgba(16, 185, 129, 0.15)';
    poolTag.style.color = '#34d399';
    poolTag.style.borderColor = 'rgba(16, 185, 129, 0.4)';
  }

  // Round tag
  const roundTag = document.getElementById('currentRoundTag');
  if (roundTag) {
    roundTag.textContent = `Round ${state.current_round || 1}`;
  }

  // Host toggle
  const hostToggle = document.getElementById('btnHostAuctionToggle');
  if (hostToggle) {
    if (state.auction_started) {
      hostToggle.className = 'btn btn-secondary';
      hostToggle.textContent = '⏸️ Pause Auction';
    } else {
      hostToggle.className = 'btn btn-success';
      hostToggle.textContent = '🚀 Start Live Auction';
    }
  }

  // Always display Active Stage for spectators and host
  const notStartedScreen = document.getElementById('auctionNotStartedScreen');
  if (notStartedScreen) notStartedScreen.style.display = 'none';

  const activeCard = document.getElementById('activePlayerCard') || document.getElementById('activePlayerPodium');
  if (activeCard) activeCard.style.display = 'block';

  const isViewer = window.IS_VIEWER_MODE || !document.getElementById('auctioneerControls');

  // Active Player Data
  const nameEl = document.getElementById('playerName') || document.getElementById('podiumPlayerName');
  const photoEl = document.getElementById('playerPhoto') || document.getElementById('podiumPlayerPhoto');
  const idTag = document.getElementById('playerIdTag') || document.getElementById('podiumPlayerSerial');
  const roleBadge = document.getElementById('playerRoleBadge') || document.getElementById('podiumPlayerRole');
  const battingEl = document.getElementById('playerBatting') || document.getElementById('podiumMetaBatting');
  const bowlingEl = document.getElementById('playerBowling') || document.getElementById('podiumMetaBowling');
  const villageEl = document.getElementById('playerVillage');
  const basePriceEl = document.getElementById('playerBasePrice');
  const soldBtn = document.querySelector('.btn-sold');
  const unsoldBtns = document.querySelectorAll('.btn-unsold, .btn-perm-unsold');
  const nextDrawBtn = document.querySelector('.btn-next-draw');

  if (state.current_player) {
    if (activeCard) activeCard.style.display = 'block';

    const p = state.player_details || {};
    if (nameEl) nameEl.textContent = state.current_player;
    if (idTag) idTag.textContent = 'ID: #' + (state.player_serials?.[state.current_player] || p.serial_no || '--');

    const roleName = p.role || 'All-Rounder';
    if (roleBadge) {
      roleBadge.textContent = roleName;
      roleBadge.className = 'role-badge ' + getRoleBadgeClass(roleName);
    }

    if (battingEl) battingEl.textContent = p.batting_style || 'Right Hand Bat';
    if (bowlingEl) bowlingEl.textContent = p.bowling_style || 'Right Arm Medium';
    if (villageEl) villageEl.textContent = p.village || 'Saidapur';
    const computedBase = Math.max(100, Number(p.base_price || state.min_bid || 100));
    if (basePriceEl) basePriceEl.textContent = '₹' + computedBase;

    if (photoEl) {
      photoEl.onerror = function() { this.onerror = null; this.src = '/static/images/avatar_allrounder.svg'; };
      photoEl.src = p.photo_url || '/static/images/avatar_allrounder.svg';
    }

    if (soldBtn) { soldBtn.disabled = false; soldBtn.style.opacity = '1'; soldBtn.style.cursor = 'pointer'; }
    unsoldBtns.forEach(btn => { btn.disabled = false; btn.style.opacity = '1'; btn.style.cursor = 'pointer'; });
    if (nextDrawBtn) nextDrawBtn.style.boxShadow = 'none';

    const baseVal = computedBase;
    const curBid = (state.current_bid !== undefined && state.current_bid !== null) ? state.current_bid : 0;
    const curTeam = state.bidding_team || state.current_bid_team || null;

    if (isViewer) {
      const odo = document.getElementById('bidOdometer');
      if (odo) odo.textContent = '₹' + curBid.toLocaleString('en-IN');
      const leadTag = document.getElementById('leadingTeamTag');
      if (leadTag) {
        if (curTeam && curBid > 0) {
          leadTag.textContent = `🎯 Leading: ${curTeam}`;
          leadTag.style.background = 'rgba(245, 158, 11, 0.25)';
          leadTag.style.color = '#fbbf24';
          leadTag.style.borderColor = 'rgba(245, 158, 11, 0.5)';
        } else {
          leadTag.textContent = `No Bids Yet • Base: ₹${baseVal}`;
          leadTag.style.background = 'rgba(255, 255, 255, 0.08)';
          leadTag.style.color = '#94a3b8';
          leadTag.style.borderColor = 'rgba(255, 255, 255, 0.15)';
        }
      }
    } else {
      if (currentBidAmount === 0 || document.body.dataset.activePlayer !== state.current_player) {
        currentBidAmount = curBid;
        currentBiddingTeam = curTeam;
        document.body.dataset.activePlayer = state.current_player;
        updateBidDisplay();
      }
    }

    // Spectator Live Countdown Timer Update
    const vTimerBox = document.getElementById('viewerTimerBox');
    const vTimerClock = document.getElementById('viewerTimerClock');
    const vTimerBar = document.getElementById('viewerTimerBar');
    const vTimerStatus = document.getElementById('viewerTimerStatusText');
    const vTimerPulse = document.getElementById('viewerTimerPulse');

    if (state.timer_enabled && state.timer_end) {
      if (vTimerBox) vTimerBox.style.display = 'block';
      const nowMs = Date.now();
      const remainingSec = Math.max(0, Math.round((state.timer_end - nowMs) / 1000));
      const totalDur = state.timer_duration || 120;
      const pct = Math.min(100, Math.max(0, (remainingSec / totalDur) * 100));

      const m = Math.floor(remainingSec / 60);
      const s = remainingSec % 60;
      const formattedTime = `${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}`;

      if (vTimerClock) vTimerClock.textContent = formattedTime;
      if (vTimerBar) vTimerBar.style.width = `${pct}%`;

      if (remainingSec === 0) {
        if (vTimerClock) {
          vTimerClock.style.color = '#ef4444';
          vTimerClock.classList.add('timer-pulse-red');
        }
        if (vTimerBar) vTimerBar.style.background = '#ef4444';
        if (vTimerPulse) vTimerPulse.style.background = '#ef4444';
        if (vTimerStatus) vTimerStatus.textContent = '⏱️ Bidding Closed! Resolving winner...';
      } else if (remainingSec <= 10) {
        if (vTimerClock) {
          vTimerClock.style.color = '#ef4444';
          vTimerClock.classList.add('timer-pulse-red');
        }
        if (vTimerBar) vTimerBar.style.background = '#ef4444';
        if (vTimerPulse) vTimerPulse.style.background = '#ef4444';
        if (vTimerStatus) vTimerStatus.textContent = '⚠️ Final Call! Bidding closing...';
      } else if (remainingSec <= 30) {
        if (vTimerClock) {
          vTimerClock.style.color = '#fbbf24';
          vTimerClock.classList.remove('timer-pulse-red');
        }
        if (vTimerBar) vTimerBar.style.background = 'linear-gradient(90deg, #f59e0b, #ef4444)';
        if (vTimerPulse) vTimerPulse.style.background = '#f59e0b';
        if (vTimerStatus) vTimerStatus.textContent = '⏱️ Auto-awards on 00:00';
      } else {
        if (vTimerClock) {
          vTimerClock.style.color = '#fbbf24';
          vTimerClock.classList.remove('timer-pulse-red');
        }
        if (vTimerBar) vTimerBar.style.background = 'linear-gradient(90deg, #10b981, #34d399)';
        if (vTimerPulse) vTimerPulse.style.background = '#10b981';
        if (vTimerStatus) vTimerStatus.textContent = '⏱️ Auto-awards on 00:00';
      }
    } else {
      if (vTimerBox) vTimerBox.style.display = 'none';
    }
  } else {
    const vTimerBox = document.getElementById('viewerTimerBox');
    if (vTimerBox) vTimerBox.style.display = 'none';
    // Empty block state (Waiting for next draw)
    if (activeCard) activeCard.style.display = 'block';
    const lastUnsold = state.last_action && state.last_action.type === 'UNSOLD' ? state.last_action.player : null;
    if (nameEl) {
      nameEl.innerHTML = lastUnsold ? 
        `<span style="color:#f87171">❌ ${lastUnsold} (UNSOLD)</span>` : 
        `<span style="color:#f59e0b">⏳ Ready for Next Draw</span>`;
    }
    if (idTag) idTag.textContent = 'ID: #--';
    if (photoEl) photoEl.src = '/static/images/avatar_allrounder.svg';
    if (roleBadge) {
      roleBadge.textContent = lastUnsold ? 'Marked Unsold' : 'Podium Ready';
      roleBadge.className = lastUnsold ? 'role-badge badge-bowler' : 'role-badge badge-allrounder';
    }
    if (battingEl) battingEl.textContent = '--';
    if (bowlingEl) bowlingEl.textContent = '--';
    if (villageEl) villageEl.textContent = '--';
    if (basePriceEl) basePriceEl.textContent = '₹--';

    const odo = document.getElementById('bidOdometer');
    if (odo) odo.textContent = '₹0';
    const leadTag = document.getElementById('leadingTeamTag');
    if (leadTag) {
      leadTag.textContent = lastUnsold ? `Moved to Unsold Pool • Ready for Next Draw` : `Waiting for Auctioneer Draw`;
      leadTag.style.background = lastUnsold ? 'rgba(239, 68, 68, 0.18)' : 'rgba(255, 255, 255, 0.08)';
      leadTag.style.color = lastUnsold ? '#f87171' : '#94a3b8';
      leadTag.style.borderColor = lastUnsold ? 'rgba(239, 68, 68, 0.4)' : 'rgba(255, 255, 255, 0.15)';
    }

    if (soldBtn) { soldBtn.disabled = true; soldBtn.style.opacity = '0.35'; soldBtn.style.cursor = 'not-allowed'; }
    unsoldBtns.forEach(btn => { btn.disabled = true; btn.style.opacity = '0.35'; btn.style.cursor = 'not-allowed'; });
    if (nextDrawBtn) nextDrawBtn.style.boxShadow = '0 0 15px rgba(245, 158, 11, 0.8)';
    document.body.dataset.activePlayer = '';
    currentBidAmount = 0;
  }

  // Celebration and announcement triggers for spectators
  if (isViewer && state.last_action && state.last_action.timestamp > lastActionTimestamp) {
    lastActionTimestamp = state.last_action.timestamp;
    const act = state.last_action;
    if (act.type === 'SOLD') {
      closeUnsoldModal();
      playGavelSound();
      playFanfareSound();
      triggerCelebrationModal(act.player, act.team, act.amount);
    } else if (act.type === 'UNSOLD') {
      closeSoldModal();
      playBuzzerSound();
      showToast(`❌ ${act.player} marked ${act.is_permanent ? 'Permanently Unsold' : 'UNSOLD (Queued for Round 2)'}`, 'warning');
      triggerUnsoldModal(act.player, act.is_permanent);
    } else if (act.type === 'UNDO') {
      closeSoldModal();
      closeUnsoldModal();
      playChimeSound();
      showToast('↩️ Last action undone by Auctioneer', 'info');
    } else if (act.type === 'DRAW') {
      closeSoldModal();
      closeUnsoldModal();
      playChimeSound();
    }
  }

  // Show Round 2 button if round 1 finished
  const r2Btn = document.getElementById('btnStartRound2');
  if (r2Btn) {
    const hasUnsold = (state.unsold_players?.length || 0) > 0;
    const round1Finished = (!state.auction_players || state.auction_players.length === 0) && !state.current_player;
    r2Btn.style.display = (hasUnsold && round1Finished) ? 'inline-block' : 'none';
  }

  // Last Sold Player Live Ticker Display (Viewer & Host)
  const lastSoldName = document.getElementById('lastSoldTickerName');
  const lastSoldTeam = document.getElementById('lastSoldTickerTeam');
  const lastSoldPrice = document.getElementById('lastSoldTickerPrice');

  if (state.last_sold_player && state.last_sold_player.name) {
    if (lastSoldName) lastSoldName.textContent = state.last_sold_player.name;
    if (lastSoldTeam) lastSoldTeam.textContent = state.last_sold_player.team;
    if (lastSoldPrice) lastSoldPrice.textContent = '₹' + Number(state.last_sold_player.price || 0).toLocaleString('en-IN');
  } else {
    // Scan teams for the most recent purchase if any
    let mostRecent = null;
    if (state.teams) {
      Object.entries(state.teams).forEach(([tName, tData]) => {
        (tData.players || []).forEach(p => {
          if (!mostRecent || (p.round && p.round >= (mostRecent.round || 1))) {
            mostRecent = { name: p.name, team: tName, price: p.cost, round: p.round };
          }
        });
      });
    }
    if (mostRecent) {
      if (lastSoldName) lastSoldName.textContent = mostRecent.name;
      if (lastSoldTeam) lastSoldTeam.textContent = mostRecent.team;
      if (lastSoldPrice) lastSoldPrice.textContent = '₹' + Number(mostRecent.price || 0).toLocaleString('en-IN');
    } else {
      if (lastSoldName) lastSoldName.textContent = 'Waiting for first sale...';
      if (lastSoldTeam) lastSoldTeam.textContent = '-';
      if (lastSoldPrice) lastSoldPrice.textContent = '₹0';
    }
  }

  renderTeams(state.teams);
  renderRemainingPool();
  renderActivityFeed();
}

function getRoleBadgeClass(role) {
  const r = (role || '').toLowerCase();
  if (r.includes('bat') && !r.includes('keep')) return 'badge-batsman';
  if (r.includes('bowl')) return 'badge-bowler';
  if (r.includes('keep')) return 'badge-keeper';
  return 'badge-allrounder';
}

function renderTeams(teams) {
  renderQuickTeamGrid();
  const container = document.getElementById('teamsPurseList') || document.getElementById('teamsSidebarList');
  const select = document.getElementById('biddingTeamSelect') || document.getElementById('bidTeamSelect');

  if (!teams) return;

  if (select && select.options.length <= 1) {
    const prev = select.value;
    select.innerHTML = '<option value="">-- Choose Team --</option>';
    Object.keys(teams).forEach(tName => {
      const opt = document.createElement('option');
      opt.value = tName;
      opt.textContent = tName;
      select.appendChild(opt);
    });
    if (prev) select.value = prev;
  }

  if (container) {
    let html = '';
    let idx = 1;
    let totalRet = 0;
    for (const [tName, tData] of Object.entries(teams)) {
      const pRet = tData.player_retained || (tData.retained && tData.retained.type !== 'Owner' ? tData.retained : null);
      const oRet = tData.owner_retained || (tData.retained && tData.retained.type === 'Owner' ? tData.retained : null);
      const retCount = (pRet ? 1 : 0) + (oRet ? 1 : 0);
      totalRet += retCount;

      const squadCount = (tData.players ? tData.players.length : 0) + retCount;
      const purse = (tData.budget !== undefined) ? tData.budget : (tData.purse || 0);
      const totalPurse = tData.total_purse || 6000;
      const pct = Math.max(5, Math.min(100, Math.round((purse / totalPurse) * 100)));

      let retChips = '';
      if (pRet) {
        const rName = (typeof pRet === 'object') ? pRet.name : pRet;
        const rCost = (typeof pRet === 'object') ? (pRet.cost || 500) : 500;
        retChips += `<div style="margin-top:0.35rem; background:rgba(245,158,11,0.15); border:1px solid rgba(245,158,11,0.35); border-radius:6px; padding:0.2rem 0.45rem; font-size:0.75rem; color:#fef08a; display:flex; justify-content:space-between; align-items:center;">
          <span>⭐ <strong>${rName}</strong></span>
          <span style="color:var(--primary-gold); font-weight:700;">₹${rCost}</span>
        </div>`;
      }
      if (oRet) {
        const oName = (typeof oRet === 'object') ? oRet.name : oRet;
        const oCost = (typeof oRet === 'object') ? (oRet.cost || 100) : 100;
        retChips += `<div style="margin-top:0.25rem; background:rgba(59,130,246,0.15); border:1px solid rgba(59,130,246,0.35); border-radius:6px; padding:0.2rem 0.45rem; font-size:0.75rem; color:#93c5fd; display:flex; justify-content:space-between; align-items:center;">
          <span>👑 <strong>${oName}</strong></span>
          <span style="color:#93c5fd; font-weight:700;">₹${oCost}</span>
        </div>`;
      }

      html += `
        <div class="team-card-auction" id="teamCard_${idx}" data-team="${tName}">
          <div class="team-card-header">
            <span class="team-card-name">${tName}</span>
            <span class="team-squad-count">${squadCount} / 10 Players</span>
          </div>
          <div class="team-progress-bg" style="background: rgba(255,255,255,0.08); height: 6px; border-radius: 9999px; overflow: hidden; margin: 0.4rem 0;">
            <div class="team-progress-bar" style="width: ${pct}%; background: linear-gradient(90deg, #10b981, #059669); height: 100%;"></div>
          </div>
          <div class="team-financials" style="display: flex; justify-content: space-between; font-size: 0.85rem;">
            <span class="team-rem-budget" style="color: #34d399; font-weight: 800;">Purse: ₹${purse.toLocaleString('en-IN')}</span>
            <span class="team-spent-budget" style="color: #94a3b8;">Spent: ₹${(tData.spent || 0).toLocaleString('en-IN')}</span>
          </div>
          ${retChips}
          <div style="margin-top: 0.5rem; text-align: right;">
            <button type="button" class="btn-view-squad" onclick="openTeamSquadModal('${tName}')">
              <span>👁️</span> View Full Squad &rarr;
            </button>
          </div>
        </div>
      `;
      idx++;
    }
    container.innerHTML = html;

    const retBadge = document.getElementById('retainedCountBadge');
    if (retBadge) retBadge.textContent = totalRet;

    const teamsCountBadge = document.getElementById('teamsCountBadge');
    if (teamsCountBadge) teamsCountBadge.textContent = `${Object.keys(teams).length} Teams`;
  }
}

// --- TEAM SQUAD DETAILS MODAL ---
function openTeamSquadModal(teamName) {
  const modal = document.getElementById('teamSquadModal');
  const teamTitle = document.getElementById('squadModalTeamName');
  const finSummary = document.getElementById('squadModalFinSummary');
  const body = document.getElementById('squadModalBody');

  if (!modal || !body || !auctionState || !auctionState.teams) return;

  const team = auctionState.teams[teamName];
  if (!team) {
    showToast('Team details not found', 'warning');
    return;
  }

  const allDetails = auctionState.all_player_details || {};
  const purse = team.budget !== undefined ? team.budget : (team.purse || 0);
  const spent = team.spent || 0;
  const pRet = team.player_retained || (team.retained && team.retained.type !== 'Owner' ? team.retained : null);
  const oRet = team.owner_retained || (team.retained && team.retained.type === 'Owner' ? team.retained : null);
  const players = team.players || [];
  const totalCount = players.length + (pRet ? 1 : 0) + (oRet ? 1 : 0);

  if (teamTitle) teamTitle.textContent = `🏆 ${teamName} Squad`;
  if (finSummary) finSummary.innerHTML = `Remaining Purse: <strong style="color:#34d399">₹${purse.toLocaleString('en-IN')}</strong> | Spent: <strong style="color:#fbbf24">₹${spent.toLocaleString('en-IN')}</strong> | Squad: <strong>${totalCount} / 10 Players</strong>`;

  let html = '';

  // 1. Retained Players Section
  if (pRet || oRet) {
    html += `<div style="margin-bottom: 1rem;"><h4 style="font-size: 0.95rem; font-weight: 800; color: #fbbf24; margin-bottom: 0.4rem; text-transform: uppercase;">⭐ Retained Franchise Players</h4><div style="display:flex; flex-direction:column; gap:0.4rem;">`;
    if (pRet) {
      const pName = typeof pRet === 'object' ? pRet.name : pRet;
      const pCost = typeof pRet === 'object' ? (pRet.cost || 500) : 500;
      const pInfo = allDetails[pName] || {};
      html += `
        <div style="background: rgba(245,158,11,0.12); border: 1px solid rgba(245,158,11,0.35); border-radius: 10px; padding: 0.6rem 0.8rem; display: flex; justify-content: space-between; align-items: center;">
          <div style="display:flex; align-items:center; gap:0.6rem;">
            <img src="${pInfo.photo_url || '/static/images/avatar_allrounder.svg'}" style="width:36px; height:36px; border-radius:50%; object-fit:cover; border:1.5px solid #f59e0b;">
            <div>
              <div style="font-weight:800; color:#fff; font-size:0.92rem;">${pName}</div>
              <span class="role-badge ${getRoleBadgeClass(pInfo.role)}" style="font-size:0.7rem; padding:0.1rem 0.4rem;">${pInfo.role || 'Player'}</span>
            </div>
          </div>
          <div style="text-align:right;">
            <span style="font-size:0.72rem; color:#fef08a; display:block;">Player Retained</span>
            <strong style="color:#fbbf24; font-size:0.95rem;">₹${pCost}</strong>
          </div>
        </div>
      `;
    }
    if (oRet) {
      const oName = typeof oRet === 'object' ? oRet.name : oRet;
      const oCost = typeof oRet === 'object' ? (oRet.cost || 100) : 100;
      const oInfo = allDetails[oName] || {};
      html += `
        <div style="background: rgba(59,130,246,0.12); border: 1px solid rgba(59,130,246,0.35); border-radius: 10px; padding: 0.6rem 0.8rem; display: flex; justify-content: space-between; align-items: center;">
          <div style="display:flex; align-items:center; gap:0.6rem;">
            <img src="${oInfo.photo_url || '/static/images/avatar_allrounder.svg'}" style="width:36px; height:36px; border-radius:50%; object-fit:cover; border:1.5px solid #3b82f6;">
            <div>
              <div style="font-weight:800; color:#fff; font-size:0.92rem;">${oName}</div>
              <span class="role-badge badge-allrounder" style="font-size:0.7rem; padding:0.1rem 0.4rem; background:#3b82f6;">Team Owner</span>
            </div>
          </div>
          <div style="text-align:right;">
            <span style="font-size:0.72rem; color:#93c5fd; display:block;">Owner Retained</span>
            <strong style="color:#93c5fd; font-size:0.95rem;">₹${oCost}</strong>
          </div>
        </div>
      `;
    }
    html += `</div></div>`;
  }

  // 2. Auction Purchased Players
  html += `<div><h4 style="font-size: 0.95rem; font-weight: 800; color: #34d399; margin-bottom: 0.4rem; text-transform: uppercase;">🔨 Auction Purchased Players (${players.length})</h4>`;
  if (!players || players.length === 0) {
    html += `<div style="background: rgba(15,23,42,0.6); border: 1px dashed rgba(255,255,255,0.15); border-radius: 10px; padding: 1.5rem; text-align: center; color: #94a3b8; font-size: 0.85rem;">No auction players purchased by this team yet.</div>`;
  } else {
    html += `<div style="display:flex; flex-direction:column; gap:0.45rem;">`;
    players.forEach((p, idx) => {
      const pName = p.name;
      const pCost = p.cost || 0;
      const pRound = p.round || 1;
      const pInfo = allDetails[pName] || {};
      const roleStr = pInfo.role || 'Player';
      const pSerial = auctionState.player_serials?.[pName] ? `#${auctionState.player_serials[pName]}` : `#${idx + 1}`;
      const village = pInfo.village || 'Saidapur';

      html += `
        <div style="background: rgba(15,23,42,0.7); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 0.55rem 0.75rem; display: flex; justify-content: space-between; align-items: center; transition: all 0.15s ease;">
          <div style="display:flex; align-items:center; gap:0.65rem;">
            <img src="${pInfo.photo_url || '/static/images/avatar_allrounder.svg'}" style="width:38px; height:38px; border-radius:50%; object-fit:cover; border:1.5px solid #10b981; background:#000;">
            <div>
              <div style="display:flex; align-items:center; gap:0.35rem;">
                <span style="font-size:0.72rem; color:#94a3b8; font-weight:700;">${pSerial}</span>
                <strong style="color:#fff; font-size:0.92rem;">${pName}</strong>
              </div>
              <div style="display:flex; align-items:center; gap:0.35rem; margin-top:0.15rem;">
                <span class="role-badge ${getRoleBadgeClass(roleStr)}" style="font-size:0.68rem; padding:0.08rem 0.35rem;">${roleStr}</span>
                <span style="font-size:0.72rem; color:#94a3b8;">📍 ${village}</span>
              </div>
            </div>
          </div>
          <div style="text-align:right;">
            <span style="font-size:0.7rem; background:rgba(56,189,248,0.15); color:#38bdf8; font-weight:800; padding:0.1rem 0.35rem; border-radius:4px; display:inline-block; margin-bottom:0.15rem;">Round ${pRound}</span>
            <div style="font-weight:900; color:#34d399; font-size:1.05rem;">₹${pCost.toLocaleString('en-IN')}</div>
          </div>
        </div>
      `;
    });
    html += `</div>`;
  }
  html += `</div>`;

  body.innerHTML = html;
  modal.style.display = 'flex';
}

function closeTeamSquadModal() {
  const modal = document.getElementById('teamSquadModal');
  if (modal) modal.style.display = 'none';
}
window.openTeamSquadModal = openTeamSquadModal;
window.closeTeamSquadModal = closeTeamSquadModal;

// --- REMAINING PLAYER POOL RENDERING & FILTERING ---
function setPoolFilter(filterType, btnEl) {
  poolActiveFilter = filterType;
  document.querySelectorAll('.pool-pill-btn').forEach(btn => btn.classList.remove('active'));
  if (btnEl) btnEl.classList.add('active');
  renderRemainingPool();
}
window.setPoolFilter = setPoolFilter;

function filterRemainingPool() {
  renderRemainingPool();
}
window.filterRemainingPool = filterRemainingPool;

function renderRemainingPool() {
  const container = document.getElementById('poolGridContainer');
  if (!container || !auctionState) return;

  const pool = auctionState.auction_players || [];
  const allDetails = auctionState.all_player_details || {};
  const searchVal = (document.getElementById('poolSearchInput')?.value || '').toLowerCase().trim();

  let countAll = 0;
  let countBat = 0;
  let countBowl = 0;
  let countAR = 0;
  let countWK = 0;

  // Compute counts
  pool.forEach(pName => {
    countAll++;
    const pInfo = allDetails[pName] || {};
    const r = (pInfo.role || '').toLowerCase();
    if (r.includes('keep')) countWK++;
    else if (r.includes('bowl')) countBowl++;
    else if (r.includes('bat')) countBat++;
    else countAR++;
  });

  const elCountAll = document.getElementById('pillCountAll');
  const elCountBat = document.getElementById('pillCountBat');
  const elCountBowl = document.getElementById('pillCountBowl');
  const elCountAR = document.getElementById('pillCountAR');
  const elCountWK = document.getElementById('pillCountWK');
  const elHeaderCount = document.getElementById('poolHeaderCount');

  if (elCountAll) elCountAll.textContent = countAll;
  if (elCountBat) elCountBat.textContent = countBat;
  if (elCountBowl) elCountBowl.textContent = countBowl;
  if (elCountAR) elCountAR.textContent = countAR;
  if (elCountWK) elCountWK.textContent = countWK;
  if (elHeaderCount) elHeaderCount.textContent = countAll;

  // Filter pool items
  const filtered = pool.filter(pName => {
    const pInfo = allDetails[pName] || {};
    const r = (pInfo.role || '').toLowerCase();
    const v = (pInfo.village || '').toLowerCase();
    const nameLow = pName.toLowerCase();

    // Role filter
    if (poolActiveFilter === 'batsman' && (!r.includes('bat') || r.includes('keep'))) return false;
    if (poolActiveFilter === 'bowler' && !r.includes('bowl')) return false;
    if (poolActiveFilter === 'keeper' && !r.includes('keep')) return false;
    if (poolActiveFilter === 'allrounder' && (r.includes('bat') && !r.includes('round') || r.includes('bowl') && !r.includes('round') || r.includes('keep'))) return false;

    // Search filter
    if (searchVal) {
      if (!nameLow.includes(searchVal) && !v.includes(searchVal) && !r.includes(searchVal)) {
        return false;
      }
    }
    return true;
  });

  if (filtered.length === 0) {
    container.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; padding: 2rem; color: #94a3b8; font-size: 0.9rem; background: rgba(15,23,42,0.5); border-radius: 10px;">No matching remaining players in pool.</div>`;
    return;
  }

  let html = '';
  filtered.forEach(pName => {
    const pInfo = allDetails[pName] || {};
    const roleStr = pInfo.role || 'All-Rounder';
    const village = pInfo.village || 'Saidapur';
    const basePrice = Math.max(100, Number(pInfo.base_price || auctionState.min_bid || 100));
    const serial = auctionState.player_serials?.[pName] ? `#${auctionState.player_serials[pName]}` : '';

    html += `
      <div class="pool-player-item">
        <img src="${pInfo.photo_url || '/static/images/avatar_allrounder.svg'}" class="pool-player-photo" alt="${pName}">
        <div style="min-width: 0; flex: 1;">
          <div style="display:flex; align-items:center; gap:0.3rem;">
            ${serial ? `<span style="font-size:0.7rem; color:#94a3b8; font-weight:800;">${serial}</span>` : ''}
            <strong style="color:#fff; font-size:0.85rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${pName}">${pName}</strong>
          </div>
          <div style="display:flex; align-items:center; gap:0.3rem; margin-top:0.2rem;">
            <span class="role-badge ${getRoleBadgeClass(roleStr)}" style="font-size:0.65rem; padding:0.05rem 0.35rem;">${roleStr}</span>
          </div>
          <div style="display:flex; justify-content:space-between; align-items:center; margin-top:0.3rem; font-size:0.75rem;">
            <span style="color:#94a3b8;">📍 ${village}</span>
            <span style="color:#34d399; font-weight:800;">₹${basePrice}</span>
          </div>
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
}

// --- LIVE ACTIVITY FEED RENDERING ---
function renderActivityFeed() {
  const container = document.getElementById('activityFeedList');
  if (!container || !auctionState) return;

  const teams = auctionState.teams || {};
  const unsold = auctionState.unsold_players || [];
  const allDetails = auctionState.all_player_details || {};

  const events = [];

  // 1. Gather all sold events
  Object.entries(teams).forEach(([tName, tData]) => {
    (tData.players || []).forEach(p => {
      events.push({
        type: 'SOLD',
        player: p.name,
        team: tName,
        cost: p.cost,
        round: p.round || 1
      });
    });
  });

  // 2. Gather unsold events
  unsold.forEach(pName => {
    events.push({
      type: 'UNSOLD',
      player: pName
    });
  });

  if (events.length === 0) {
    container.innerHTML = `<div style="text-align: center; padding: 1.5rem; color: #94a3b8; font-size: 0.85rem; background: rgba(15,23,42,0.5); border-radius: 8px;">No auction events recorded yet. Sold & Unsold history will appear here in real time.</div>`;
    return;
  }

  // Reverse order (latest first)
  const reversed = [...events].reverse().slice(0, 15);
  let html = '';

  reversed.forEach(ev => {
    const pInfo = allDetails[ev.player] || {};
    const roleStr = pInfo.role || 'Player';

    if (ev.type === 'SOLD') {
      html += `
        <div class="activity-item">
          <div style="display:flex; align-items:center; gap:0.55rem;">
            <span style="font-size:1.1rem;">🎉</span>
            <div>
              <strong style="color:#fff;">${ev.player}</strong>
              <span class="role-badge ${getRoleBadgeClass(roleStr)}" style="font-size:0.65rem; padding:0.05rem 0.3rem; margin-left:0.3rem;">${roleStr}</span>
              <div style="font-size:0.75rem; color:#94a3b8; margin-top:0.1rem;">Sold to <strong style="color:var(--primary-gold);">${ev.team}</strong> (Round ${ev.round})</div>
            </div>
          </div>
          <div style="text-align:right;">
            <strong style="color:#34d399; font-size:0.95rem;">₹${ev.cost?.toLocaleString('en-IN')}</strong>
          </div>
        </div>
      `;
    } else {
      html += `
        <div class="activity-item unsold-act">
          <div style="display:flex; align-items:center; gap:0.55rem;">
            <span style="font-size:1.1rem;">❌</span>
            <div>
              <strong style="color:#fff;">${ev.player}</strong>
              <span class="role-badge ${getRoleBadgeClass(roleStr)}" style="font-size:0.65rem; padding:0.05rem 0.3rem; margin-left:0.3rem;">${roleStr}</span>
              <div style="font-size:0.75rem; color:#f87171; margin-top:0.1rem;">Marked Unsold (Available in Round 2)</div>
            </div>
          </div>
          <div style="text-align:right;">
            <span style="font-size:0.75rem; color:#f87171; font-weight:800;">UNSOLD</span>
          </div>
        </div>
      `;
    }
  });

  container.innerHTML = html;
}

// --- MOBILE TAB SWITCHER ---
function switchViewerTab(tabId, btnEl) {
  document.querySelectorAll('.viewer-tab-btn').forEach(b => b.classList.remove('active'));
  if (btnEl) btnEl.classList.add('active');

  const liveStage = document.getElementById('activePlayerCard');
  const teamsSec = document.getElementById('teamsSection');
  const poolSec = document.getElementById('poolSection');
  const actSec = document.getElementById('activitySection');

  if (window.innerWidth <= 768) {
    if (tabId === 'liveStageTab') {
      if (liveStage) liveStage.style.display = 'block';
      if (teamsSec) teamsSec.style.display = 'none';
      if (poolSec) poolSec.style.display = 'none';
      if (actSec) actSec.style.display = 'none';
    } else if (tabId === 'teamsTab') {
      if (liveStage) liveStage.style.display = 'none';
      if (teamsSec) teamsSec.style.display = 'block';
      if (poolSec) poolSec.style.display = 'none';
      if (actSec) actSec.style.display = 'none';
    } else if (tabId === 'poolTab') {
      if (liveStage) liveStage.style.display = 'none';
      if (teamsSec) teamsSec.style.display = 'none';
      if (poolSec) poolSec.style.display = 'block';
      if (actSec) actSec.style.display = 'none';
    } else if (tabId === 'activityTab') {
      if (liveStage) liveStage.style.display = 'none';
      if (teamsSec) teamsSec.style.display = 'none';
      if (poolSec) poolSec.style.display = 'none';
      if (actSec) actSec.style.display = 'block';
    }
  } else {
    // On desktop, keep all sections visible in their responsive grid
    if (liveStage) liveStage.style.display = 'block';
    if (teamsSec) teamsSec.style.display = 'block';
    if (poolSec) poolSec.style.display = 'block';
    if (actSec) actSec.style.display = 'block';
  }
}
window.switchViewerTab = switchViewerTab;

// --- RETAINED PLAYERS MODAL ---
function openRetainedModal() {
  const modal = document.getElementById('retainedPlayersModal');
  const body = document.getElementById('retainedModalBody');
  if (!modal || !body) return;

  fetch('/api/auction/state')
    .then(r => r.json())
    .then(data => {
      const teams = data.teams || {};
      const allDetails = data.all_player_details || {};
      let html = '';
      let totalRet = 0;

      for (const [tName, tData] of Object.entries(teams)) {
        const pRet = tData.player_retained || (tData.retained && tData.retained.type !== 'Owner' ? tData.retained : null);
        const oRet = tData.owner_retained || (tData.retained && tData.retained.type === 'Owner' ? tData.retained : null);

        let pName = pRet ? (typeof pRet === 'object' ? pRet.name : pRet) : null;
        let pCost = pRet ? (typeof pRet === 'object' ? (pRet.cost || 500) : 500) : 500;
        let oName = oRet ? (typeof oRet === 'object' ? oRet.name : oRet) : null;
        let oCost = oRet ? (typeof oRet === 'object' ? (oRet.cost || 100) : 100) : 100;

        let cardItems = '';
        if (pName) {
          totalRet++;
          const pDet = allDetails[pName] || {};
          cardItems += `
            <div style="background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.35); border-radius: 8px; padding: 0.65rem 0.85rem; margin-top: 0.5rem; display: flex; justify-content: space-between; align-items: center;">
              <div style="display:flex; align-items:center; gap:0.6rem;">
                <img src="${pDet.photo_url || '/static/images/avatar_allrounder.svg'}" style="width:34px; height:34px; border-radius:50%; object-fit:cover; border:1px solid #f59e0b;">
                <div>
                  <div style="font-weight:700; color:#fff; font-size:0.95rem;">${pName}</div>
                  <span style="font-size:0.75rem; background:#f59e0b; color:#000; font-weight:800; padding:0.1rem 0.4rem; border-radius:4px;">PLAYER RETAINED</span>
                </div>
              </div>
              <div style="text-align:right;">
                <strong style="color:var(--primary-gold); font-size:1.05rem;">₹${pCost}</strong>
              </div>
            </div>
          `;
        }
        if (oName) {
          totalRet++;
          const oDet = allDetails[oName] || {};
          cardItems += `
            <div style="background: rgba(59, 130, 246, 0.12); border: 1px solid rgba(59, 130, 246, 0.35); border-radius: 8px; padding: 0.65rem 0.85rem; margin-top: 0.5rem; display: flex; justify-content: space-between; align-items: center;">
              <div style="display:flex; align-items:center; gap:0.6rem;">
                <img src="${oDet.photo_url || '/static/images/avatar_allrounder.svg'}" style="width:34px; height:34px; border-radius:50%; object-fit:cover; border:1px solid #3b82f6;">
                <div>
                  <div style="font-weight:700; color:#fff; font-size:0.95rem;">${oName}</div>
                  <span style="font-size:0.75rem; background:#3b82f6; color:#fff; font-weight:800; padding:0.1rem 0.4rem; border-radius:4px;">OWNER RETAINED</span>
                </div>
              </div>
              <div style="text-align:right;">
                <strong style="color:#93c5fd; font-size:1.05rem;">₹${oCost}</strong>
              </div>
            </div>
          `;
        }

        html += `
          <div class="glass-card" style="margin-bottom:1rem; padding:1rem; border-left:4px solid var(--primary-gold);">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <h4 style="font-size:1.15rem; font-weight:800; color:#fff; margin:0;">${tName}</h4>
              <span style="color:#34d399; font-weight:700; font-size:0.9rem;">Purse: ₹${(tData.budget || 0).toLocaleString('en-IN')}</span>
            </div>
            ${cardItems || '<p style="color:#94a3b8; font-size:0.85rem; margin-top:0.5rem; font-style:italic;">No player or owner retained for this team.</p>'}
          </div>
        `;
      }

      body.innerHTML = html;
      const badge = document.getElementById('retainedCountBadge');
      if (badge) badge.textContent = totalRet;
      modal.style.display = 'flex';
    });
}

function closeRetainedModal() {
  const modal = document.getElementById('retainedPlayersModal');
  if (modal) modal.style.display = 'none';
}
window.openRetainedModal = openRetainedModal;
window.closeRetainedModal = closeRetainedModal;

// --- EXPORT TO WINDOW (CRITICAL FOR INLINE ONCLICK EVENTS) ---
window.drawNextPlayer = drawNextPlayer;
window.adjustCurrentBid = adjustCurrentBid;
window.stepBid = stepBid;
window.assignLeadingBidder = assignLeadingBidder;
window.confirmSellPlayer = confirmSellPlayer;
window.markUnsold = markUnsold;
window.undoLastAction = undoLastAction;
window.startRound2 = startRound2;
window.openPinModal = openPinModal;
window.closePinModal = closePinModal;
window.verifyHostPin = verifyHostPin;
window.closeSoldModal = closeSoldModal;
window.lockAuctioneer = lockAuctioneer;
window.showToast = showToast;
window.chooseSelectedPlayer = chooseSelectedPlayer;
window.drawNextFromModal = drawNextFromModal;
window.handleSoldModalBackdrop = handleSoldModalBackdrop;

// --- INITIALIZATION ---
document.addEventListener('DOMContentLoaded', () => {
  const teamSelect = document.getElementById('biddingTeamSelect') || document.getElementById('bidTeamSelect');
  if (teamSelect) {
    teamSelect.addEventListener('change', (e) => {
      currentBiddingTeam = e.target.value;
      updateBidDisplay();
      broadcastBid(currentBidAmount, currentBiddingTeam);
    });
  }

  checkSavedPin();
  startStatePolling();
});
