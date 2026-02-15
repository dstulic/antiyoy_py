/**
 * Replay page: single file for board rendering and replay logic.
 * Fetches replay data once (initial_state + final_state); all navigation is local.
 */

function isUnitPiece(piece) {
    const p = piece && String(piece).toLowerCase();
    return p === 'peasant' || p === 'spearman' || p === 'baron' || p === 'knight';
}

// --- ReplayBoard: read-only hex board (pan/zoom only) ---

class ReplayBoard {
    constructor(containerId, hexSize = 30, spacingMultiplier = 1.0) {
        this.container = document.getElementById(containerId);
        this.hexSize = hexSize;
        this.spacingMultiplier = spacingMultiplier;
        this.canvas = null;
        this.ctx = null;
        this.hexes = [];
        this.offsetX = 0;
        this.offsetY = 0;
        this.scale = 1.0;
        this.minScale = 0.3;
        this.maxScale = 3.0;
        this.isPanning = false;
        this.panStartX = 0;
        this.panStartY = 0;
        this.panStartOffsetX = 0;
        this.panStartOffsetY = 0;
        this.leftPanPointerDown = false;
        this.leftPanStartX = 0;
        this.leftPanStartY = 0;
        this.leftPanStartOffsetX = 0;
        this.leftPanStartOffsetY = 0;
        this.leftButtonPan = false;
        this.ignoreNextClick = false;
        this.PAN_THRESHOLD_PX = 5;
        this.pieceImages = {};
        this.defenseIndicatorImage = null;

        this.init();
        this.preloadPieceImages();
        this.preloadDefenseIndicatorImage();
        if (this.canvas && this.ctx) {
            this.animationSystem = initAnimationSystem(this.canvas, this.ctx);
        }
    }

    preloadPieceImages() {
        const pieces = ['peasant', 'spearman', 'baron', 'knight', 'tower', 'strong_tower', 'city',
            'farm', 'farm0', 'farm1', 'farm2', 'grave', 'palm', 'pine'];
        pieces.forEach(piece => {
            const normalizedPiece = piece.toLowerCase();
            const imageName = getPieceImage(normalizedPiece);
            if (imageName) {
                const img = new Image();
                img.onload = () => { if (this.hexes.length > 0) this.render(); };
                img.onerror = () => {};
                img.src = `/static/assets/original_game_assets/atlas/${imageName}`;
                this.pieceImages[normalizedPiece] = img;
            }
        });
    }

    preloadDefenseIndicatorImage() {
        this.defenseIndicatorImage = new Image();
        this.defenseIndicatorImage.onload = () => { if (this.hexes.length > 0) this.render(); };
        this.defenseIndicatorImage.src = '/static/assets/original_game_assets/atlas/defense_indicator.png';
    }

    init() {
        this.canvas = document.createElement('canvas');
        this.canvas.style.width = '100%';
        this.canvas.style.height = '100%';
        this.canvas.style.display = 'block';
        this.container.appendChild(this.canvas);
        this.ctx = this.canvas.getContext('2d');
        this.animationSystem = initAnimationSystem(this.canvas, this.ctx);
        this.resize();
        window.addEventListener('resize', () => this.resize());
        this.canvas.addEventListener('click', (e) => this.handleClick(e));
        this.canvas.addEventListener('mousemove', (e) => this.handleMouseMove(e));
        this.canvas.addEventListener('wheel', (e) => this.handleWheel(e));
        this.canvas.addEventListener('mousedown', (e) => this.handleMouseDown(e));
        this.canvas.addEventListener('mouseup', (e) => this.handleMouseUp(e));
        this.canvas.addEventListener('mouseleave', (e) => this.handleMouseLeave(e));
        this.canvas.addEventListener('contextmenu', (e) => { if (e.button === 1) e.preventDefault(); });
    }

    resize() {
        const rect = this.container.getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = rect.height;
        this.render();
    }

    setHexes(hexes) {
        const firstLoad = this.hexes.length === 0;
        this.hexes = hexes;
        if (firstLoad) this.centerView();
        if (!this._animationLoopRunning) this.render();
    }

    centerView() {
        if (this.hexes.length === 0) return;
        const effectiveHexSize = this.hexSize * this.spacingMultiplier;
        let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
        for (const hex of this.hexes) {
            const pos = hexToPixel(hex.coordinate1, hex.coordinate2, effectiveHexSize);
            minX = Math.min(minX, pos.x); maxX = Math.max(maxX, pos.x);
            minY = Math.min(minY, pos.y); maxY = Math.max(maxY, pos.y);
        }
        const centerX = (minX + maxX) / 2, centerY = (minY + maxY) / 2;
        this.offsetX = this.canvas.width / 2 - centerX * this.scale;
        this.offsetY = this.canvas.height / 2 - centerY * this.scale;
    }

    render() {
        if (!this.ctx) return;
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        if (this.animationSystem && !this._animationLoopRunning) this.animationSystem.update();
        for (const hex of this.hexes) this.drawHex(hex);
        if (this.animationSystem) this.animationSystem.render(this);
    }

    drawHex(hex) {
        const worldHexSize = this.hexSize * this.spacingMultiplier;
        const pos = hexToPixel(hex.coordinate1, hex.coordinate2, worldHexSize);
        const x = (pos.x * this.scale) + this.offsetX;
        const y = (pos.y * this.scale) + this.offsetY;
        const effectiveSize = this.hexSize * this.scale;
        if (x < -effectiveSize || x > this.canvas.width + effectiveSize ||
            y < -effectiveSize || y > this.canvas.height + effectiveSize) return;
        this.drawHexShape(x, y, hex.color);
        if (hex.piece) {
            const opacity = (hex.piece && isUnitPiece(hex.piece) && hex.is_ready === false) ? 0.5 : 1.0;
            this.drawPiece(x, y, hex.piece, opacity);
        }
    }

    drawHexShape(x, y, color) {
        const ctx = this.ctx, radius = this.hexSize * this.scale;
        ctx.save();
        ctx.beginPath();
        for (let i = 0; i < 6; i++) {
            const angle = (Math.PI / 3 * i) - (Math.PI / 2);
            const hx = x + radius * Math.cos(angle), hy = y + radius * Math.sin(angle);
            if (i === 0) ctx.moveTo(hx, hy); else ctx.lineTo(hx, hy);
        }
        ctx.closePath();
        const colorName = getColorName(color);
        ctx.fillStyle = this.getColorHex(colorName);
        ctx.fill();
        ctx.strokeStyle = '#333';
        ctx.lineWidth = 1;
        ctx.stroke();
        ctx.restore();
    }

    getColorHex(colorName) {
        const colors = { 'gray': '#808080', 'green': '#4CAF50', 'red': '#F44336', 'blue': '#2196F3', 'yellow': '#FFEB3B', 'cyan': '#00BCD4', 'aqua': '#00FFFF', 'white': '#FFFFFF', 'orange': '#FF9800', 'purple': '#9C27B0', 'rose': '#E91E63', 'mint': '#4CAF50', 'ice': '#B3E5FC', 'brown': '#8D6E63', 'lavender': '#B39DDB', 'brass': '#CD7F32', 'algae': '#64B5F6', 'orchid': '#BA68C8', 'whiskey': '#D2691E' };
        return colors[colorName] || '#808080';
    }

    drawPiece(x, y, pieceType, opacity = 1.0) {
        const normalizedPieceType = pieceType ? pieceType.toLowerCase() : null;
        if (!normalizedPieceType) return;
        const img = this.pieceImages[normalizedPieceType];
        if (!img || !img.complete || !img.naturalHeight) return;
        const size = this.hexSize * this.scale * 1.1;
        this.ctx.save();
        this.ctx.globalAlpha = opacity;
        this.ctx.drawImage(img, x - size / 2, y - size / 2, size, size);
        this.ctx.restore();
    }

    handleWheel(e) {
        e.preventDefault();
        const rect = this.canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left, mouseY = e.clientY - rect.top;
        const worldX = (mouseX - this.offsetX) / this.scale, worldY = (mouseY - this.offsetY) / this.scale;
        const zoomDelta = e.deltaY > 0 ? 0.9 : 1.1;
        const newScale = Math.max(this.minScale, Math.min(this.maxScale, this.scale * zoomDelta));
        if (newScale === this.scale) return;
        this.offsetX = mouseX - worldX * newScale;
        this.offsetY = mouseY - worldY * newScale;
        this.scale = newScale;
        this.render();
    }

    handleMouseDown(e) {
        if (e.button === 0) {
            this.leftPanPointerDown = true;
            const rect = this.canvas.getBoundingClientRect();
            this.leftPanStartX = e.clientX - rect.left;
            this.leftPanStartY = e.clientY - rect.top;
            this.leftPanStartOffsetX = this.offsetX;
            this.leftPanStartOffsetY = this.offsetY;
            return;
        }
        if (e.button === 1) {
            e.preventDefault();
            this.isPanning = true;
            const rect = this.canvas.getBoundingClientRect();
            this.panStartX = e.clientX - rect.left;
            this.panStartY = e.clientY - rect.top;
            this.panStartOffsetX = this.offsetX;
            this.panStartOffsetY = this.offsetY;
            this.canvas.style.cursor = 'grabbing';
        }
    }

    handleMouseUp(e) {
        if (e.button === 0) {
            if (this.leftButtonPan) this.ignoreNextClick = true;
            this.isPanning = false;
            this.leftButtonPan = false;
            this.leftPanPointerDown = false;
            this.canvas.style.cursor = 'default';
            return;
        }
        if (e.button === 1) {
            const rect = this.canvas.getBoundingClientRect();
            const endX = e.clientX - rect.left, endY = e.clientY - rect.top;
            const dx = endX - this.panStartX, dy = endY - this.panStartY;
            if (Math.sqrt(dx * dx + dy * dy) < this.PAN_THRESHOLD_PX) {
                this.centerView();
                this.render();
            }
            this.isPanning = false;
            this.canvas.style.cursor = 'default';
        }
    }

    handleMouseLeave() {
        if (this.leftPanPointerDown || this.leftButtonPan) this.ignoreNextClick = true;
        this.isPanning = false;
        this.leftButtonPan = false;
        this.leftPanPointerDown = false;
        this.canvas.style.cursor = 'default';
        this.render();
    }

    handleMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left, mouseY = e.clientY - rect.top;
        if (!this.isPanning && this.leftPanPointerDown && (e.buttons & 1)) {
            const dx = mouseX - this.leftPanStartX, dy = mouseY - this.leftPanStartY;
            if (Math.sqrt(dx * dx + dy * dy) >= this.PAN_THRESHOLD_PX) {
                this.isPanning = true;
                this.leftButtonPan = true;
                this.panStartX = this.leftPanStartX;
                this.panStartY = this.leftPanStartY;
                this.panStartOffsetX = this.leftPanStartOffsetX;
                this.panStartOffsetY = this.leftPanStartOffsetY;
                this.canvas.style.cursor = 'grabbing';
            }
        }
        if (this.isPanning) {
            this.offsetX = this.panStartOffsetX + (mouseX - this.panStartX);
            this.offsetY = this.panStartOffsetY + (mouseY - this.panStartY);
            this.render();
        }
    }

    handleClick() {}
}

// --- Replay page logic: event-based, single fetch ---
//
// We keep three states: beginning state, current state, end state.
// - beginningState: initial game state (fixed).
// - endState: final game state (fixed).
// - currentState: the one we display; equals beginning + events[0..eventIndex-1] applied.
// - events: list of event encodings from the replay file (e.g. "um 1 2 3 4 1", "pa 0 0 tower -1").
// - eventIndex: number of events applied to get currentState (0 = at beginning).
//
// |< : set current state to beginning state (eventIndex = 0).
// >| : set current state to end state (eventIndex = events.length).
// >> : apply events[eventIndex] to current state, then eventIndex++.
// << : eventIndex--, then set current state = beginning + events[0..eventIndex-1] applied.

(function() {
    const params = new URLSearchParams(window.location.search);
    const replayPath = params.get('path');

    let board = null;
    let beginningState = null;
    let endState = null;
    /** List of event encodings from replay file (e.g. "um 1 2 3 4 1"). */
    let events = [];
    /** Mutable current state (what we display). */
    let currentState = null;
    /** Number of events applied to get currentState. 0 = at beginning. */
    let eventIndex = 0;

    const loadingEl = document.getElementById('replayLoading');
    const turnCounterEl = document.getElementById('replayTurnCounter');
    const statusTableBody = document.getElementById('replayStatusTableBody');
    const statusOverlay = document.getElementById('replayStatusOverlay');
    const statusToggle = document.getElementById('replayStatusToggle');

    function hideLoading() {
        if (loadingEl) loadingEl.style.display = 'none';
    }

    function showLoading(msg) {
        if (loadingEl) {
            loadingEl.textContent = msg || 'Loading...';
            loadingEl.style.display = 'flex';
        }
    }

    function updateTurnCounter(state) {
        const turn = state && (state.turn_index != null) ? state.turn_index : 0;
        const lap = state && (state.lap != null) ? state.lap : 0;
        turnCounterEl.textContent = lap > 0 ? `Turn: ${turn} (Lap ${lap})` : `Turn: ${turn}`;
    }

    function formatType(type) {
        if (!type) return '—';
        const t = String(type).toLowerCase();
        if (t === 'human') return 'human';
        if (t === 'balancer') return 'balancer';
        if (['easy', 'average', 'hard', 'expert'].includes(t)) return t;
        return type;
    }

    function updateStatusTable(state) {
        statusTableBody.innerHTML = '';
        if (!state || !state.entity_stats || !state.entity_stats.length) {
            const row = statusTableBody.insertRow();
            row.innerHTML = '<td colspan="4">No entities</td>';
            return;
        }
        for (const e of state.entity_stats) {
            const row = statusTableBody.insertRow();
            row.innerHTML = `
                <td>${formatType(e.type)}</td>
                <td>${e.hex_pct != null ? e.hex_pct : '—'}</td>
                <td>${e.money != null ? e.money : '—'}</td>
                <td>${e.income != null ? e.income : '—'}</td>
            `;
        }
    }

    function displayState(state) {
        if (!state || !state.hexes) return;
        board.setHexes(state.hexes);
        updateTurnCounter(state);
        updateStatusTable(state);
    }

    function updateButtonStates() {
        const btnBegin = document.getElementById('btnBegin');
        const btnBack = document.getElementById('btnBack');
        const btnFwd = document.getElementById('btnFwd');
        const btnEnd = document.getElementById('btnEnd');
        const atBeginning = eventIndex <= 0;
        const atEnd = eventIndex >= events.length;
        if (btnBegin) btnBegin.disabled = atBeginning;
        if (btnBack) btnBack.disabled = atBeginning;
        if (btnFwd) btnFwd.disabled = atEnd;
        if (btnEnd) btnEnd.disabled = atEnd;
    }

    /** Deep-clone state (hexes and top-level fields) for mutating. */
    function cloneState(state) {
        if (!state) return null;
        const hexes = (state.hexes || []).map(h => ({ ...h }));
        return {
            hexes,
            entities: state.entities ? state.entities.map(e => ({ ...e })) : [],
            entity_stats: state.entity_stats ? state.entity_stats.map(e => ({ ...e })) : [],
            turn_index: state.turn_index != null ? state.turn_index : 0,
            lap: state.lap != null ? state.lap : 0,
        };
    }

    function findHex(state, c1, c2) {
        if (!state || !state.hexes) return null;
        return state.hexes.find(h => h.coordinate1 === c1 && h.coordinate2 === c2) || null;
    }

    /** Apply a single encoded event to state (mutates state.hexes, state.turn_index, state.lap). */
    function applyEvent(state, enc) {
        if (!state || !enc || typeof enc !== 'string') return;
        const parts = enc.trim().split(/\s+/);
        if (parts.length < 1) return;
        const key = parts[0];
        const p = parts.slice(1);

        if (key === 'um' && p.length >= 4) {
            const c1 = parseInt(p[0], 10); const c2 = parseInt(p[1], 10);
            const c3 = parseInt(p[2], 10); const c4 = parseInt(p[3], 10);
            const start = findHex(state, c1, c2);
            const finish = findHex(state, c3, c4);
            if (start && finish && start.piece) {
                finish.piece = start.piece;
                finish.unit_id = start.unit_id != null ? start.unit_id : -1;
                finish.is_ready = start.is_ready;
                start.piece = null;
                start.unit_id = null;
                if (p.length >= 5 && p[4] === '1') finish.color = start.color;
            }
        } else if (key === 'pa' && p.length >= 3) {
            const c1 = parseInt(p[0], 10); const c2 = parseInt(p[1], 10);
            const piece = p[2];
            const unitId = p.length > 3 ? parseInt(p[3], 10) : -1;
            const hex = findHex(state, c1, c2);
            if (hex) {
                hex.piece = piece;
                if (unitId !== -1) hex.unit_id = unitId;
            }
        } else if (key === 'pd' && p.length >= 2) {
            const c1 = parseInt(p[0], 10); const c2 = parseInt(p[1], 10);
            const hex = findHex(state, c1, c2);
            if (hex) { hex.piece = null; hex.unit_id = null; }
        } else if (key === 'te' && p.length >= 2) {
            const n = state.entities && state.entities.length ? state.entities.length : 1;
            state.turn_index = ((state.turn_index != null ? state.turn_index : 0) + 1) % n;
            if (state.turn_index === 0) state.lap = (state.lap || 0) + 1;
        } else if (key === 'hcc' && p.length >= 3) {
            const c1 = parseInt(p[0], 10); const c2 = parseInt(p[1], 10);
            const hex = findHex(state, c1, c2);
            if (hex) hex.color = p[2];
        } else if (key === 'pb' && p.length >= 3) {
            const c1 = parseInt(p[0], 10); const c2 = parseInt(p[1], 10);
            const hex = findHex(state, c1, c2);
            if (hex) hex.piece = p[2];
        }
    }

    function goToBeginning() {
        currentState = cloneState(beginningState);
        eventIndex = 0;
        displayState(currentState);
        updateButtonStates();
    }

    function goOneEventBack() {
        if (eventIndex <= 0) return;
        eventIndex--;
        currentState = cloneState(beginningState);
        for (let i = 0; i < eventIndex; i++) applyEvent(currentState, events[i]);
        displayState(currentState);
        updateButtonStates();
    }

    function goOneEventForward() {
        if (eventIndex >= events.length) return;
        applyEvent(currentState, events[eventIndex]);
        eventIndex++;
        displayState(currentState);
        updateButtonStates();
    }

    function goToEnd() {
        currentState = cloneState(endState);
        eventIndex = events.length;
        displayState(currentState);
        updateButtonStates();
    }

    function initBoard() {
        const container = document.getElementById('replayBoard');
        if (!container) return;
        board = new ReplayBoard('replayBoard', 30, 1.0);
    }

    function initStatusToggle() {
        if (!statusToggle || !statusOverlay) return;
        statusToggle.addEventListener('click', function() {
            statusOverlay.classList.toggle('collapsed');
            statusToggle.textContent = statusOverlay.classList.contains('collapsed') ? '▶' : '◀';
        });
    }

    function initControls() {
        const btnBegin = document.getElementById('btnBegin');
        const btnBack = document.getElementById('btnBack');
        const btnFwd = document.getElementById('btnFwd');
        const btnEnd = document.getElementById('btnEnd');
        if (btnBegin) btnBegin.addEventListener('click', goToBeginning);
        if (btnBack) btnBack.addEventListener('click', goOneEventBack);
        if (btnFwd) btnFwd.addEventListener('click', goOneEventForward);
        if (btnEnd) btnEnd.addEventListener('click', goToEnd);
    }

    function run() {
        if (!replayPath) {
            showLoading('No replay selected. Go back to the main menu and choose a replay.');
            return;
        }

        initBoard();
        initStatusToggle();
        initControls();

        showLoading('Loading replay...');
        fetch('/api/replay/content?path=' + encodeURIComponent(replayPath))
            .then(r => r.json())
            .then(data => {
                if (!data.success) {
                    showLoading(data.error || 'Invalid replay.');
                    return;
                }
                const initial = data.initial_state || null;
                const final = data.final_state || null;
                const eventList = Array.isArray(data.events) ? data.events : [];
                if (!final) {
                    showLoading('Invalid replay: no state data.');
                    return;
                }
                beginningState = initial || final;
                endState = final;
                events = eventList;
                eventIndex = events.length;
                currentState = cloneState(endState);
                hideLoading();
                displayState(currentState);
                updateButtonStates();
            })
            .catch(err => {
                console.error(err);
                showLoading('Error loading replay.');
            });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', run);
    } else {
        run();
    }
})();
