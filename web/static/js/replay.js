/**
 * Replay page: diff-based hex state management.
 *
 * Backend sends:
 *   initial_state  – full hex list + turn/lap/entity_stats at step 0
 *   step_diffs[]   – per-step: hex_changes (only modified hexes), animation, turn/lap/entity_stats
 *
 * The frontend maintains a running hexMap that is patched forward/backward
 * via hex_changes diffs.  Reverse diffs are computed on-the-fly so backward
 * navigation is instant.
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

    drawPiece(x, y, pieceType, opacity = 1.0, scaleFactor = 1.0) {
        const normalizedPieceType = pieceType ? pieceType.toLowerCase() : null;
        if (!normalizedPieceType) return;
        const img = this.pieceImages[normalizedPieceType];
        if (!img || !img.complete || !img.naturalHeight) return;
        const size = this.hexSize * this.scale * 1.1 * (scaleFactor || 1);
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

// --- Replay page logic: diff-based, single fetch ---

(function() {
    const params = new URLSearchParams(window.location.search);
    const replayPath = params.get('path');

    let board = null;

    /** Full initial state from backend. */
    let initialState = null;
    /** Array of { hex_changes, animation, turn_index, lap, entity_stats }. */
    let stepDiffs = [];
    /**
     * Running hex state: Map<"c1,c2", hexObj>.
     * Patched forward/backward as the user navigates.
     */
    let hexMap = new Map();
    /**
     * Reverse patches for undo: reversePatches[i] = array of old hex objects
     * that were overwritten when step_diffs[i] was applied.
     */
    let reversePatches = {};
    /**
     * Current position.  0 = initial state; N = state after step_diffs[0..N-1].
     * Range: [0, stepDiffs.length].
     */
    let currentStep = 0;

    const loadingEl = document.getElementById('replayLoading');
    const turnCounterEl = document.getElementById('replayTurnCounter');
    const statusTableBody = document.getElementById('replayStatusTableBody');
    const statusOverlay = document.getElementById('replayStatusOverlay');
    const statusToggle = document.getElementById('replayStatusToggle');

    function hideLoading() { if (loadingEl) loadingEl.style.display = 'none'; }
    function showLoading(msg) {
        if (loadingEl) { loadingEl.textContent = msg || 'Loading...'; loadingEl.style.display = 'flex'; }
    }

    // --- hex map helpers ---

    function hexKey(c1, c2) { return c1 + ',' + c2; }

    function buildHexMap(hexes) {
        const m = new Map();
        for (const h of hexes) m.set(hexKey(h.coordinate1, h.coordinate2), h);
        return m;
    }

    /** Apply step_diffs[stepIdx] forward. Stores reverse patch for undo. */
    function applyForward(stepIdx) {
        const diff = stepDiffs[stepIdx];
        if (!diff) return;
        const reverse = [];
        for (const ch of diff.hex_changes) {
            const k = hexKey(ch.coordinate1, ch.coordinate2);
            const old = hexMap.get(k);
            reverse.push(old ? Object.assign({}, old) : null);
            hexMap.set(k, ch);
        }
        reversePatches[stepIdx] = reverse;
    }

    /** Undo step_diffs[stepIdx] using the stored reverse patch. */
    function applyBackward(stepIdx) {
        const diff = stepDiffs[stepIdx];
        const reverse = reversePatches[stepIdx];
        if (!diff || !reverse) return;
        for (let i = 0; i < diff.hex_changes.length; i++) {
            const ch = diff.hex_changes[i];
            const k = hexKey(ch.coordinate1, ch.coordinate2);
            if (reverse[i]) hexMap.set(k, reverse[i]);
        }
        delete reversePatches[stepIdx];
    }

    // --- metadata for current position ---

    function currentMeta() {
        if (currentStep === 0) {
            return {
                turn_index: initialState.turn_index || 0,
                lap: initialState.lap || 0,
                entity_stats: initialState.entity_stats || [],
            };
        }
        const d = stepDiffs[currentStep - 1];
        return {
            turn_index: d.turn_index || 0,
            lap: d.lap || 0,
            entity_stats: d.entity_stats || [],
        };
    }

    // --- display ---

    function formatType(type) {
        if (!type) return '—';
        const t = String(type).toLowerCase();
        if (t === 'human') return 'human';
        if (t === 'balancer') return 'balancer';
        if (['easy', 'average', 'hard', 'expert'].includes(t)) return t;
        return type;
    }

    function getCurrentPlayerColor(turnIndex) {
        const entities = initialState && initialState.entities;
        if (!entities || !entities.length) return null;
        return entities[turnIndex % entities.length].color;
    }

    function updateStatusTable(entityStats, turnIndex) {
        statusTableBody.innerHTML = '';
        if (!entityStats || !entityStats.length) {
            const row = statusTableBody.insertRow();
            row.innerHTML = '<td colspan="4">No entities</td>';
            return;
        }
        const activeColor = getCurrentPlayerColor(turnIndex);
        for (const e of entityStats) {
            const row = statusTableBody.insertRow();
            const marker = (e.color === activeColor) ? '▸' : '\u2002';
            row.innerHTML = `
                <td>${marker} ${formatType(e.type)}</td>
                <td>${e.hex_pct != null ? e.hex_pct : '—'}</td>
                <td>${e.money != null ? e.money : '—'}</td>
                <td>${e.income != null ? e.income : '—'}</td>
            `;
        }
    }

    function displayCurrentState() {
        const hexes = Array.from(hexMap.values());
        board.setHexes(hexes);
        const meta = currentMeta();
        const turn = meta.turn_index, lap = meta.lap;
        turnCounterEl.textContent = `Turn: ${lap}-${turn}`;
        updateStatusTable(meta.entity_stats, meta.turn_index);
        board.render();
    }

    function updateButtonStates() {
        const btnBegin = document.getElementById('btnBegin');
        const btnBack = document.getElementById('btnBack');
        const btnFwd = document.getElementById('btnFwd');
        const btnEnd = document.getElementById('btnEnd');
        const atStart = currentStep <= 0;
        const atEnd = currentStep >= stepDiffs.length;
        if (btnBegin) btnBegin.disabled = atStart;
        if (btnBack) btnBack.disabled = atStart;
        if (btnFwd) btnFwd.disabled = atEnd;
        if (btnEnd) btnEnd.disabled = atEnd;
    }

    // --- animation ---

    function hexToPixelCoords(c1, c2) {
        const effectiveHexSize = board.hexSize * board.spacingMultiplier;
        const pos = typeof hexToPixel === 'function'
            ? hexToPixel(c1, c2, effectiveHexSize)
            : { x: 0, y: 0 };
        return { x: pos.x * board.scale + board.offsetX, y: pos.y * board.scale + board.offsetY };
    }

    function runAnimation(animation, onComplete) {
        if (!animation || !board || !board.animationSystem) {
            if (onComplete) onComplete();
            return;
        }
        const sys = board.animationSystem;
        function tick() {
            sys.update();
            if (board && typeof board.render === 'function') board.render();
            const inProgress = sys.animations.some(a =>
                (a.type === 'unit_move' || a.type === 'piece_build') && !a.completed);
            if (!inProgress) {
                sys.clearCompletedAnimations();
                if (onComplete) onComplete();
                return;
            }
            requestAnimationFrame(tick);
        }
        if (animation.type === 'unit_move') {
            const src = animation.source || {};
            const tgt = animation.target || {};
            const startPx = hexToPixelCoords(src.coordinate1, src.coordinate2);
            const endPx = hexToPixelCoords(tgt.coordinate1, tgt.coordinate2);
            sys.addUnitMoveAnimation(
                startPx.x, startPx.y, endPx.x, endPx.y,
                animation.piece_type || 'peasant',
                { coordinate1: src.coordinate1, coordinate2: src.coordinate2 },
                { coordinate1: tgt.coordinate1, coordinate2: tgt.coordinate2 },
                true, false
            );
            requestAnimationFrame(tick);
        } else if (animation.type === 'piece_build') {
            const tgt = animation.target || {};
            const px = hexToPixelCoords(tgt.coordinate1, tgt.coordinate2);
            sys.addPieceBuildAnimation(px.x, px.y, (animation.piece_type || 'peasant').toLowerCase(), true);
            requestAnimationFrame(tick);
        } else {
            if (onComplete) onComplete();
        }
    }

    // --- navigation ---

    function goToBeginning() {
        hexMap = buildHexMap(initialState.hexes);
        reversePatches = {};
        currentStep = 0;
        displayCurrentState();
        updateButtonStates();
    }

    function goOneStepBack() {
        if (currentStep <= 0) return;
        currentStep--;
        applyBackward(currentStep);
        displayCurrentState();
        updateButtonStates();
    }

    function goOneStepForward() {
        if (currentStep >= stepDiffs.length) return;
        const idx = currentStep;
        const diff = stepDiffs[idx];
        runAnimation(diff.animation, function() {
            applyForward(idx);
            currentStep = idx + 1;
            displayCurrentState();
            updateButtonStates();
        });
    }

    function goToEnd() {
        while (currentStep < stepDiffs.length) {
            applyForward(currentStep);
            currentStep++;
        }
        displayCurrentState();
        updateButtonStates();
    }

    // --- init ---

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
        if (btnBack) btnBack.addEventListener('click', goOneStepBack);
        if (btnFwd) btnFwd.addEventListener('click', goOneStepForward);
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
                initialState = data.initial_state;
                stepDiffs = Array.isArray(data.step_diffs) ? data.step_diffs : [];
                if (!initialState || !initialState.hexes || !initialState.hexes.length) {
                    showLoading('Invalid replay: no initial state.');
                    return;
                }

                // Build hex map from initial state, then fast-forward to end
                hexMap = buildHexMap(initialState.hexes);
                for (let i = 0; i < stepDiffs.length; i++) applyForward(i);
                currentStep = stepDiffs.length;

                hideLoading();
                displayCurrentState();
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
