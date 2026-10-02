// ==================== REAL-TIME CRICKET AUCTION ENGINE ====================
// Supports both Host Operator Console and Mobile Viewers Live Stream

let auctionState = null;
let currentBidAmount = 0;
let currentBiddingTeam = null;
let pollTimer = null;
let isAuctioneerActing = false;
let lastActionTimestamp = 0;

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
  return sessionStorage.getItem('kpl_auction_pin') || sessionStorage.getItem('spl_auction_pin') || '';
}

function setAuctioneerPin(pin) {
  sessionStorage.setItem('kpl_auction_pin', pin);
  sessionStorage.setItem('spl_auction_pin', pin);
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
let broadcastTimeout = null;
function broadcastBid(amount, team) {
  if (window.IS_VIEWER_MODE) return;
  const pin = getAuctioneerPin();
  if (!pin) return;

  clearTimeout(broadcastTimeout);
  broadcastTimeout = setTimeout(async () => {
    try {
      await fetch('/api/auction/bid', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': pin },
        body: JSON.stringify({ bid: amount, team: team, pin: pin })
      });
    } catch(e) {}
  }, 100);
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

  playChimeSound();
  currentBidAmount = Math.max(50, currentBidAmount + activeIncrement);
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
async function drawNextPlayer() {
  closeSoldModal();
  if (!requirePinAuth(drawNextPlayer)) return;

  try {
    const pin = getAuctioneerPin();
    const res = await fetch('/api/auction/next', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Auction-PIN': pin },
      body: JSON.stringify({ pin: pin })
    });
    const data = await res.json();
    if (data.success) {
      playChimeSound();
      currentBidAmount = data.base_price || 50;
      currentBiddingTeam = null;
      showToast(`🎯 Drawn: ${data.player} (Base: ₹${currentBidAmount})`, 'success');
      fetchState();
    } else {
      showToast(data.message || 'No more players available in current round.', 'warning');
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

// --- CLOSE CELEBRATION MODAL ---
// --- SOLD MODAL HELPERS ---
window._soldDismissTimer = null;
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

function handleSoldModalBackdrop(e) {
  if (e.target === document.getElementById('soldModal') || e.target.classList.contains('sold-modal-overlay')) {
    closeSoldModal();
  }
}

async function drawNextFromModal() {
  closeSoldModal();
  await drawNextPlayer();
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

  // Look up detailed player information
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

  // Auto-dismiss celebration after 5 seconds so nobody is stuck!
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
      tagEl.textContent = `Leading: ${currentBiddingTeam}`;
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
    const res = await fetch('/api/auction/state');
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
  pollTimer = setInterval(fetchState, 1000);
}

function renderAuctionState(state) {
  if (!state) return;
  auctionState = state;
  // Auto-close celebration modal if active player advances or draw occurred
  if (state.last_action && (state.last_action.type === 'DRAW' || state.current_player !== window._lastSoldPlayer)) {
    if (document.getElementById('soldModal')?.style.display === 'flex') {
      closeSoldModal();
    }
  }

  // Populate Remaining Player Picker Dropdown
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

  // Waiting screen for spectators
  const notStartedScreen = document.getElementById('auctionNotStartedScreen');
  const activeCard = document.getElementById('activePlayerCard') || document.getElementById('activePlayerPodium');
  const emptyState = document.getElementById('noActivePlayerState') || document.getElementById('emptyPodiumMsg');

  const isViewer = window.IS_VIEWER_MODE || !document.getElementById('auctioneerControls');

  if (!state.auction_started && isViewer) {
    if (notStartedScreen) notStartedScreen.style.display = 'block';
    if (activeCard) activeCard.style.display = 'none';
    if (emptyState) emptyState.style.display = 'none';
    renderTeams(state.teams);
    return;
  } else {
    if (notStartedScreen) notStartedScreen.style.display = 'none';
  }

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
    const p = state.player_details || {};
    if (nameEl) nameEl.textContent = state.current_player;
    if (idTag) idTag.textContent = 'ID: #' + (state.player_serials?.[state.current_player] || '--');

    const roleName = p.role || 'All-Rounder';
    if (roleBadge) {
      roleBadge.textContent = roleName;
      roleBadge.className = 'role-badge ' + getRoleBadgeClass(roleName);
    }

    if (battingEl) battingEl.textContent = p.batting_style || 'Right Hand Bat';
    if (bowlingEl) bowlingEl.textContent = p.bowling_style || 'Right Arm Medium';
    if (villageEl) villageEl.textContent = p.village || 'Saidapur';
    if (basePriceEl) basePriceEl.textContent = '₹' + (p.base_price || state.min_bid || 50);

    if (photoEl) {
      photoEl.src = p.photo_url || '/static/images/avatar_allrounder.svg';
    }

    if (soldBtn) { soldBtn.disabled = false; soldBtn.style.opacity = '1'; soldBtn.style.cursor = 'pointer'; }
    unsoldBtns.forEach(btn => { btn.disabled = false; btn.style.opacity = '1'; btn.style.cursor = 'pointer'; });
    if (nextDrawBtn) nextDrawBtn.style.boxShadow = 'none';

    const curBid = state.current_bid || p.base_price || state.min_bid || 50;
    const curTeam = state.bidding_team || state.current_bid_team || null;

    if (isViewer) {
      // Spectator live sync: update odometer directly from server state
      const odo = document.getElementById('bidOdometer');
      if (odo) odo.textContent = '₹' + curBid.toLocaleString('en-IN');
      const leadTag = document.getElementById('leadingTeamTag');
      if (leadTag) {
        if (curTeam) {
          leadTag.textContent = `🎯 Leading: ${curTeam}`;
          leadTag.style.background = 'rgba(245, 158, 11, 0.25)';
          leadTag.style.color = '#fbbf24';
          leadTag.style.borderColor = 'rgba(245, 158, 11, 0.5)';
        } else {
          leadTag.textContent = 'No Bids Yet';
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
  } else {
    // Podium is empty / waiting for next draw
    if (nameEl) nameEl.innerHTML = '<span style="color:#f59e0b">Ready for Next Draw</span>';
    if (idTag) idTag.textContent = 'ID: #--';
    if (photoEl) photoEl.src = '/static/images/avatar_allrounder.svg';
    if (roleBadge) {
      roleBadge.textContent = 'Podium Ready';
      roleBadge.className = 'role-badge badge-allrounder';
    }
    if (battingEl) battingEl.textContent = '--';
    if (bowlingEl) bowlingEl.textContent = '--';
    if (villageEl) villageEl.textContent = '--';
    if (basePriceEl) basePriceEl.textContent = '₹--';

    const odo = document.getElementById('bidOdometer');
    if (odo) odo.textContent = '₹0';
    const leadTag = document.getElementById('leadingTeamTag');
    if (leadTag) leadTag.textContent = 'Click "Next Draw" to bring a player';

    if (soldBtn) { soldBtn.disabled = true; soldBtn.style.opacity = '0.35'; soldBtn.style.cursor = 'not-allowed'; }
    unsoldBtns.forEach(btn => { btn.disabled = true; btn.style.opacity = '0.35'; btn.style.cursor = 'not-allowed'; });
    if (nextDrawBtn) nextDrawBtn.style.boxShadow = '0 0 15px rgba(245, 158, 11, 0.8)';
    document.body.dataset.activePlayer = '';
    currentBidAmount = 0;
  }

  // Celebration trigger for spectators
  if (isViewer && state.last_action && state.last_action.timestamp > lastActionTimestamp) {
    lastActionTimestamp = state.last_action.timestamp;
    const act = state.last_action;
    if (act.type === 'SOLD') {
      playGavelSound();
      playFanfareSound();
      triggerCelebrationModal(act.player, act.team, act.amount);
    } else if (act.type === 'UNSOLD') {
      playBuzzerSound();
    } else if (act.type === 'UNDO') {
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

  renderTeams(state.teams);
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

  // Update team select dropdown if empty
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

  // Update sidebar purse cards
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
        retChips += `<div style="margin-top:0.35rem; background:rgba(245,158,11,0.15); border:1px solid rgba(245,158,11,0.35); border-radius:4px; padding:0.2rem 0.45rem; font-size:0.75rem; color:#fef08a; display:flex; justify-content:space-between; align-items:center;">
          <span>⭐ <strong>${rName}</strong></span>
          <span style="color:var(--primary-gold); font-weight:700;">₹${rCost}</span>
        </div>`;
      }
      if (oRet) {
        const oName = (typeof oRet === 'object') ? oRet.name : oRet;
        const oCost = (typeof oRet === 'object') ? (oRet.cost || 100) : 100;
        retChips += `<div style="margin-top:0.25rem; background:rgba(59,130,246,0.15); border:1px solid rgba(59,130,246,0.35); border-radius:4px; padding:0.2rem 0.45rem; font-size:0.75rem; color:#93c5fd; display:flex; justify-content:space-between; align-items:center;">
          <span>👑 <strong>${oName}</strong></span>
          <span style="color:#93c5fd; font-weight:700;">₹${oCost}</span>
        </div>`;
      }

      html += `
        <div class="team-card-auction" id="teamCard_${idx}" data-team="${tName}">
          <div class="team-card-header">
            <span class="team-card-name">${tName}</span>
            <span class="team-squad-count">${squadCount} Players</span>
          </div>
          <div class="team-progress-bg" style="background: rgba(255,255,255,0.08); height: 6px; border-radius: 9999px; overflow: hidden; margin: 0.4rem 0;">
            <div class="team-progress-bar" style="width: ${pct}%; background: linear-gradient(90deg, #10b981, #059669); height: 100%;"></div>
          </div>
          <div class="team-financials" style="display: flex; justify-content: space-between; font-size: 0.85rem;">
            <span class="team-rem-budget" style="color: #34d399; font-weight: 800;">Purse: ₹${purse.toLocaleString('en-IN')}</span>
            <span class="team-spent-budget" style="color: #94a3b8;">Spent: ₹${(tData.spent || 0).toLocaleString('en-IN')}</span>
          </div>
          ${retChips}
        </div>
      `;
      idx++;
    }
    container.innerHTML = html;

    const retBadge = document.getElementById('retainedCountBadge');
    if (retBadge) retBadge.textContent = totalRet;
  }
}

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

// --- EXPORT TO WINDOW (CRITICAL FOR BUTTON CLICKS) ---
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
