vkBridge.send('VKWebAppInit');

const params = new URLSearchParams(window.location.search);
const VK_ID = parseInt(params.get('vk_user_id'));

if (!VK_ID) {
    document.getElementById('vk-auth-overlay').style.display = 'flex';
} else {
    document.getElementById('vk-auth-overlay').style.display = 'none';
}

const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');
canvas.width = window.innerWidth;
canvas.height = window.innerHeight;

const HEX_SIZE = 40;

const BIOME_COLORS = { "forest": "#228B22", "highland": "#9ACD32", "mountain": "#808080", "steppe": "#EDC9AF", "swamp": "#556B2F", "city": "#FFD700" };
const BIOME_NAMES = { "forest": "Лес", "highland": "Холмы", "mountain": "Горы", "steppe": "Степь", "swamp": "Болото", "city": "Город" };
const RES_EMOJI = {"wood": "🪵", "stone": "🪨", "iron": "⚙️", "fiber": "🌿", "hide": "🦇", "food": "🍖"};

let currentPlayer = { q: 0, r: 0, energy: 100, inventory: {}, coins: 0 };
let currentMapCells = [];
let currentOtherPlayers = [];
let selectedHex = null;
let recipesData = {};
let activeTHTab = 1;
let activeMarketTab = 1;
let currentCombatTarget = "";

function hex_distance(q1, r1, q2, r2) {
    return (Math.abs(q1 - q2) + Math.abs(q1 + r1 - q2 - r2) + Math.abs(r1 - r2)) / 2;
}

function hexToPixel(q, r) {
    const x = HEX_SIZE * (1.5 * q);
    const y = HEX_SIZE * (Math.sqrt(3)/2 * q + Math.sqrt(3) * r);
    return { x: x + canvas.width / 2, y: y + canvas.height / 2 };
}

function pixelToHex(x, y) {
    const rect = canvas.getBoundingClientRect();
    x = x - rect.left - canvas.width / 2;
    y = y - rect.top - canvas.height / 2;
    const q = (2/3 * x) / HEX_SIZE;
    const r = (-1/3 * x + Math.sqrt(3)/3 * y) / HEX_SIZE;
    let s = -q - r;
    let rq = Math.round(q), rr = Math.round(r), rs = Math.round(s);
    const q_diff = Math.abs(rq - q), r_diff = Math.abs(rr - r), s_diff = Math.abs(rs - s);
    if (q_diff > r_diff && q_diff > s_diff) { rq = -rr - rs; } 
    else if (r_diff > s_diff) { rr = -rq - rs; }
    return { q: rq, r: rr };
}

function drawHex(x, y, color, hasRoad=false) {
    ctx.beginPath();
    for (let i = 0; i < 6; i++) {
        const angle = Math.PI / 180 * (60 * i);
        ctx.lineTo(x + HEX_SIZE * Math.cos(angle), y + HEX_SIZE * Math.sin(angle));
    }
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
    ctx.strokeStyle = "rgba(0,0,0, 0.4)";
    ctx.stroke();

    if (hasRoad) {
        ctx.beginPath();
        ctx.arc(x, y, HEX_SIZE * 0.4, 0, 2 * Math.PI);
        ctx.fillStyle = "rgba(139, 69, 19, 0.6)";
        ctx.fill();
    }
}

async function loadMap(force=false) {
    if (!VK_ID) return;
    if (await checkCombatState()) return;
    
    let url = `/api/map?vk_id=${VK_ID}`;
    const response = await fetch(url);
    const data = await response.json();
    
    currentMapCells = data.cells;
    currentPlayer = data.player;
    currentOtherPlayers = data.other_players || [];

    document.getElementById('energy-stat').innerText = `⚡ ${currentPlayer.energy}/100`;
    document.getElementById('coins-stat').innerText = `🪙 ${currentPlayer.inventory.coins || 0}`;
    document.getElementById('essence-stat').innerText = `🔮 ${currentPlayer.inventory.essence || 0}`;
    document.getElementById('inv-wood').innerText = `🪵 ${currentPlayer.inventory.wood}`;
    document.getElementById('inv-stone').innerText = `🪨 ${currentPlayer.inventory.stone}`;
    document.getElementById('inv-iron').innerText = `⚙️ ${currentPlayer.inventory.iron}`;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    currentMapCells.forEach(cell => {
        const pos = hexToPixel(cell.q - currentPlayer.q, cell.r - currentPlayer.r);
        drawHex(pos.x, pos.y, BIOME_COLORS[cell.biome] || "#000", cell.has_road);
    });
    
    currentOtherPlayers.forEach(p => {
        const pos = hexToPixel(p.q - currentPlayer.q, p.r - currentPlayer.r);
        ctx.beginPath(); ctx.arc(pos.x, pos.y, 8, 0, 2 * Math.PI);
        ctx.fillStyle = "#2196F3"; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = "white"; ctx.stroke();
    });

    const playerPixel = hexToPixel(0, 0);
    ctx.beginPath(); ctx.arc(playerPixel.x, playerPixel.y, 12, 0, 2 * Math.PI);
    ctx.fillStyle = "#e53935"; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = "white"; ctx.stroke();
}

async function checkCombatState() {
    const res = await fetch(`/api/combat/state?vk_id=${VK_ID}`);
    const data = await res.json();
    if (data.in_combat) {
        renderCombat(data.state);
        return true;
    }
    document.getElementById('combat-screen').style.display = 'none';
    return false;
}

function renderCombat(state) {
    document.getElementById('combat-screen').style.display = 'flex';
    
    const alliesContainer = document.getElementById('combat-allies');
    alliesContainer.innerHTML = '';
    state.allies.forEach(a => {
        const activeClass = state.turn_order[state.current_turn_index] === a.key ? 'active' : '';
        const hpPercent = (a.hp / a.max_hp) * 100;
        alliesContainer.innerHTML += `
            <div class="fighter-card ${activeClass}">
                <strong>${a.name}</strong> (AP: ${a.ap})
                <div class="fighter-hp-bar"><div class="fighter-hp-fill" style="width: ${hpPercent}%"></div></div>
                <div style="font-size:12px; margin-top:3px;">HP: ${a.hp}/${a.max_hp} | Energy: ${a.energy}</div>
            </div>
        `;
    });

    const enemiesContainer = document.getElementById('combat-enemies');
    enemiesContainer.innerHTML = '';
    let anyTargetable = false;
    
    state.enemies.forEach(e => {
        if (e.hp <= 0) return;
        const activeClass = state.turn_order[state.current_turn_index] === e.key ? 'active' : '';
        const targetClass = currentCombatTarget === e.key ? 'targetable' : '';
        if (!currentCombatTarget) {
            currentCombatTarget = e.key; 
        }
        
        const hpPercent = (e.hp / e.max_hp) * 100;
        enemiesContainer.innerHTML += `
            <div class="fighter-card ${activeClass} ${targetClass}" onclick="currentCombatTarget='${e.key}'; checkCombatState();">
                <strong>${e.name}</strong>
                <div class="fighter-hp-bar"><div class="fighter-hp-fill" style="width: ${hpPercent}%"></div></div>
                <div style="font-size:12px; margin-top:3px;">HP: ${e.hp}/${e.max_hp}</div>
            </div>
        `;
        anyTargetable = true;
    });
    
    if (!anyTargetable) currentCombatTarget = "";

    const logBox = document.getElementById('combat-log-container');
    logBox.innerHTML = '';
    state.action_log.forEach(log => {
        logBox.innerHTML += `<div>&gt; ${log}</div>`;
    });
    logBox.scrollTop = logBox.scrollHeight;

    const actionsContainer = document.getElementById('combat-actions');
    actionsContainer.innerHTML = '';
    
    const activeKey = state.turn_order[state.current_turn_index];
    const isPlayerTurn = state.allies.some(a => a.key === activeKey);
    
    if (isPlayerTurn) {
        actionsContainer.innerHTML = `
            <button class="modal-btn" style="background:#e53935; width:auto; flex-grow:1; margin:0;" onclick="sendCombatAction('attack')">Атака (2 AP)</button>
            <button class="modal-btn" style="background:#555; width:auto; flex-grow:1; margin:0;" onclick="sendCombatAction('skip')">Пропуск</button>
        `;
    } else {
        actionsContainer.innerHTML = `<p style="text-align:center; width:100%; color:#aaa; font-weight:bold;">Ожидание хода противника...</p>`;
    }
}

async function sendCombatAction(actionName) {
    const res = await fetch('/api/combat/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vk_id: VK_ID, action: actionName, target_key: currentCombatTarget })
    });
    const data = await res.json();
    if (!res.ok) {
        alert(data.detail);
        return;
    }
    if (data.status === "won" || data.status === "dead") {
        alert(data.log[data.log.length - 1]);
        currentCombatTarget = "";
        loadMap();
    } else {
        checkCombatState();
    }
}

async function postAction(url, body) {
    const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });
    const data = await res.json();
    if (res.ok) {
        if (data.status === "warning_trigger") {
            triggerWarning(data.risk_zone, data.message);
            return false;
        }
        if (data.status === "combat") {
            closeModals();
            await checkCombatState();
            return true;
        }
        if (data.message) {
            document.querySelectorAll('.action-msg').forEach(el => el.innerText = data.message);
        }
        loadMap();
        return true;
    } else {
        document.querySelectorAll('.action-msg').forEach(el => el.innerText = "❌ " + data.detail);
        return false;
    }
}

function triggerWarning(zone, msg) {
    closeModals();
    document.getElementById('warning-title').innerText = `Предупреждение: ${zone.toUpperCase()} ЗОНА`;
    document.getElementById('warning-text').innerText = msg;
    document.getElementById('warning-modal').style.display = 'block';
    
    document.getElementById('btn-warning-force').onclick = async () => {
        const body = { vk_id: VK_ID, target_q: selectedHex.q, target_r: selectedHex.r, force: true };
        const res = await fetch('/api/move', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        if (res.ok) {
            closeModals();
            loadMap();
        } else {
            const data = await res.json();
            alert(data.detail);
        }
    };
}

canvas.addEventListener('click', (e) => {
    if (!VK_ID) return;
    if(document.getElementById('combat-screen').style.display === 'flex') return;
    
    const clickedHex = pixelToHex(e.clientX, e.clientY);
    const absQ = currentPlayer.q + clickedHex.q;
    const absR = currentPlayer.r + clickedHex.r;
    const cellData = currentMapCells.find(c => c.q === absQ && c.r === absR);
    if (!cellData) return;
    selectedHex = { q: absQ, r: absR, cell_id: cellData.id };
    
    document.getElementById('modal-title').innerText = `Клетка: ${BIOME_NAMES[cellData.biome]} [${cellData.risk_zone.toUpperCase()}]`;
    document.querySelectorAll('.action-msg').forEach(el => el.innerText = '');
    
    const dist = hex_distance(absQ, absR, currentPlayer.q, currentPlayer.r);
    document.getElementById('btn-move').style.display = dist === 1 ? 'block' : 'none';
    document.getElementById('btn-explore').style.display = (dist === 0 && cellData.biome !== 'city') ? 'block' : 'none';
    document.getElementById('btn-enter-city').style.display = (dist === 0 && cellData.biome === 'city') ? 'block' : 'none';
    document.getElementById('action-modal').style.display = 'block';
});

document.getElementById('btn-move').addEventListener('click', () => {
    postAction('/api/move', { vk_id: VK_ID, target_q: selectedHex.q, target_r: selectedHex.r });
    closeModals();
});

document.getElementById('btn-explore').addEventListener('click', () => {
    postAction('/api/explore', { vk_id: VK_ID });
});

document.getElementById('btn-enter-city').addEventListener('click', () => {
    closeModals();
    document.getElementById('city-modal').style.display = 'block';
});

function closeModals() {
    document.querySelectorAll('.modal').forEach(m => m.style.display = 'none');
}

async function openTownHall() {
    document.getElementById('city-modal').style.display = 'none';
    document.getElementById('townhall-modal').style.display = 'block';
    await loadTownHall();
}

function closeTownHall() {
    document.getElementById('townhall-modal').style.display = 'none';
    document.getElementById('city-modal').style.display = 'block';
}

function switchTHTab(idx) {
    activeTHTab = idx;
    document.querySelectorAll('#townhall-modal .tab-btn').forEach((b, i) => b.classList.toggle('active', i + 1 === idx));
    document.querySelectorAll('#townhall-modal .pane').forEach((p, i) => p.classList.toggle('active', i + 1 === idx));
}

async function loadTownHall() {
    const res = await fetch(`/api/city/townhall?vk_id=${VK_ID}`);
    const data = await res.json();
    if (!res.ok) return;

    document.getElementById('th-title').innerText = `Ратуша: ${data.city_name} (Налог: ${data.tax_rate}%)`;
    document.getElementById('th-cit-status').innerText = `Ваш статус: ${data.citizenship}`;
    document.getElementById('th-elec-timer').innerText = `Выборы завершатся через: ${data.elections.ends_in} мин.`;

    let cHTML = "";
    data.elections.candidates.forEach(c => {
        cHTML += `
            <div class="item-card">
                <div class="item-info">Игрок #${c.id}</div> 
                <div>${c.votes} 🗳️ <button style="background:#4caf50; color:white; border:none; border-radius:4px; padding:5px; cursor:pointer;" onclick="voteElec(${c.id})" ${!data.elections.can_vote ? 'disabled' : ''}>Голосовать</button></div>
            </div>
        `;
    });
    document.getElementById('th-cands').innerHTML = cHTML;

    document.getElementById('th-mayor-panel').style.display = data.perms.is_mayor ? 'block' : 'none';
    document.getElementById('th-contract-panel').style.display = data.perms.is_mayor ? 'block' : 'none';

    let lHTML = "";
    data.laws.forEach(l => {
        lHTML += `
            <div class="item-card" style="flex-direction:column; align-items:flex-start;">
                <strong>Законопроект: ${l.new_tax}%</strong>
                <div style="font-size:12px; color:#aaa; margin-bottom:5px;">За: ${l.for} | Против: ${l.against}</div>
                ${data.perms.is_council ? `<div style="display:flex; gap:5px; width:100%;"><button style="flex:1; background:#4caf50; color:white; border:none; padding:5px;" onclick="voteLaw(${l.id}, 'yes')">За</button><button style="flex:1; background:#f44336; color:white; border:none; padding:5px;" onclick="voteLaw(${l.id}, 'no')">Против</button></div>` : ''}
            </div>
        `;
    });
    document.getElementById('th-laws').innerHTML = lHTML || "<p style='font-size:12px; color:#aaa;'>Нет активных законопроектов.</p>";
}

async function nominate() {
    if (await postAction('/api/city/election/nominate', { vk_id: VK_ID, obj_id: 0 })) {
        loadTownHall();
    }
}

async function voteElec(candId) {
    if (await postAction('/api/city/election/vote', { vk_id: VK_ID, obj_id: candId })) {
        loadTownHall();
    }
}

async function proposeLaw() {
    const taxRate = parseInt(document.getElementById('th-new-tax').value) || 0;
    if (await postAction('/api/city/law/propose', { vk_id: VK_ID, tax_rate: taxRate })) {
        loadTownHall();
    }
}

async function openMarket() {
    document.getElementById('city-modal').style.display = 'none';
    document.getElementById('market-modal').style.display = 'block';
    await loadMarket();
}

function closeMarket() {
    document.getElementById('market-modal').style.display = 'none';
    document.getElementById('city-modal').style.display = 'block';
}

function switchMarketTab(idx) {
    activeMarketTab = idx;
    document.querySelectorAll('#market-modal .tab-btn').forEach((b, i) => b.classList.toggle('active', i + 1 === idx));
    document.querySelectorAll('#market-modal .pane').forEach((p, i) => p.classList.toggle('active', i + 1 === idx));
    loadMarket();
}

async function loadMarket() {
    const orderType = activeMarketTab === 1 ? "sell" : "buy";
    if (activeMarketTab === 1 || activeMarketTab === 2) {
        const res = await fetch(`/api/market/list?vk_id=${VK_ID}&order_type=${orderType}`);
        const data = await res.json();
        const list = document.getElementById('market-buy-list');
        list.innerHTML = '';
        data.orders.forEach(o => {
            list.innerHTML += `
                <div class="item-card">
                    <div><strong>${o.item_id} x${o.amount}</strong><br>Цена: ${o.price} 🪙</div>
                    <button class="tab-btn" onclick="fulfillOrder(${o.id}, ${o.amount})">Выкупить</button>
                </div>
            `;
        });
    } else if (activeMarketTab === 3) {
        const res = await fetch(`/api/market/my_orders?vk_id=${VK_ID}`);
        const orders = await res.json();
        const list = document.getElementById('market-my-list');
        list.innerHTML = '';
        orders.forEach(o => {
            list.innerHTML += `
                <div class="item-card">
                    <div><strong>${o.item_id} x${o.amount}</strong> [${o.order_type.toUpperCase()}]<br>Цена: ${o.price} 🪙</div>
                    <button class="tab-btn btn-close" onclick="cancelOrder(${o.id})">Отмена</button>
                </div>
            `;
        });
    } else if (activeMarketTab === 4) {
        const res = await fetch(`/api/market/inbox?vk_id=${VK_ID}`);
        const inbox = await res.json();
        const list = document.getElementById('market-inbox-list');
        list.innerHTML = '';
        inbox.forEach(i => {
            let desc = i.item_id ? `${i.item_id} x${i.amount}` : `${i.coins} 🪙`;
            list.innerHTML += `
                <div class="item-card">
                    <div><strong>${desc}</strong><br>Причина: ${i.reason}</div>
                    <button class="tab-btn" onclick="claimInbox(${i.id})">Забрать</button>
                </div>
            `;
        });
    }
}

async function createMarketOrder() {
    const type = document.getElementById('market-order-type').value;
    const itemId = document.getElementById('market-item-id').value;
    const amount = parseInt(document.getElementById('market-amount').value) || 0;
    const price = parseInt(document.getElementById('market-price').value) || 0;
    
    if (await postAction('/api/market/create', { vk_id: VK_ID, order_type: type, item_id: itemId, amount: amount, price_per_unit: price })) {
        loadMarket();
    }
}

async function fulfillOrder(orderId, maxAmt) {
    const amt = parseInt(prompt(`Какое количество выкупить (макс: ${maxAmt})?`)) || 0;
    if (amt > 0) {
        if (await postAction('/api/market/fulfill', { vk_id: VK_ID, order_id: orderId, amount: amt })) {
            loadMarket();
        }
    }
}

async function cancelOrder(orderId) {
    if (await postAction('/api/market/cancel', { vk_id: VK_ID, order_id: orderId })) {
        loadMarket();
    }
}

async function claimInbox(claimId) {
    if (await postAction('/api/market/claim', { vk_id: VK_ID, claim_id: claimId })) {
        loadMarket();
    }
}

function openGacha() {
    document.getElementById('city-modal').style.display = 'none';
    document.getElementById('gacha-modal').style.display = 'block';
}

function closeGacha() {
    document.getElementById('gacha-modal').style.display = 'none';
    document.getElementById('city-modal').style.display = 'block';
}

window.rollGacha = async function(rollsCount) {
    const res = await fetch('/api/gacha/roll', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vk_id: VK_ID, rolls_count: rollsCount })
    });
    const data = await res.json();
    if (!res.ok) {
        alert(data.detail);
        return;
    }
    
    const container = document.getElementById('gacha-display');
    container.innerHTML = `<h4>Результаты:</h4>`;
    data.results.forEach(r => {
        container.innerHTML += `<div>• ${r.msg}</div>`;
    });
    loadMap();
};

async function openForge() {
    document.getElementById('city-modal').style.display = 'none';
    document.getElementById('forge-modal').style.display = 'block';
    
    const res = await fetch('/api/recipes');
    const data = await res.json();
    const list = document.getElementById('forge-recipes-list');
    list.innerHTML = '';
    
    for (const category in data) {
        list.innerHTML += `<h4 style="color:#aaa; margin: 10px 0 5px;">${category.toUpperCase()}</h4>`;
        for (const [itemId, recipe] of Object.entries(data[category])) {
            let costHtml = '';
            for (const [resName, amt] of Object.entries(recipe.cost)) {
                costHtml += `${RES_EMOJI[resName]||resName}:${amt} `;
            }
            list.innerHTML += `
                <div class="item-card">
                    <div><strong>${recipe.name}</strong><br><span style="font-size:11px;">Цена: ${costHtml}</span></div>
                    <button class="tab-btn" style="background:#ffd700; border:none; color:black; font-weight:bold; flex-grow:0; padding: 5px 15px;" onclick="craftItem('${itemId}')">Создать</button>
                </div>
            `;
        }
    }
}

function closeForge() {
    document.getElementById('forge-modal').style.display = 'none';
    document.getElementById('city-modal').style.display = 'block';
}

async function craftItem(itemId) {
    if (await postAction('/api/craft', { vk_id: VK_ID, item_id: itemId })) {
        document.getElementById('action-msg-forge').innerText = `Предмет успешно создан!`;
    }
}

if (VK_ID) {
    loadMap();
}