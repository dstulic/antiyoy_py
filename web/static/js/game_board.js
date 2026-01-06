// Game Board Rendering

class GameBoard {
    constructor(containerId, hexSize = 30, spacingMultiplier = 1.0) {
        this.container = document.getElementById(containerId);
        this.hexSize = hexSize;
        this.spacingMultiplier = spacingMultiplier; // Adjust spacing between hexes (1.0 = default)
        this.canvas = null;
        this.ctx = null;
        this.hexes = [];
        this.offsetX = 0;
        this.offsetY = 0;
        this.scale = 1.0;
        this.selectedHex = null;
        this.pieceImages = {}; // Cache for piece images
        this.currentPlayerColor = null; // Current player's color (for selection filtering)
        this.selectedHexForBuild = null; // Hex selected for building menu
        
        // Placement mode state
        this.placementMode = false;
        this.placementPieceType = null;
        this.placementProvinceHex = null;
        this.validPlacementHexes = []; // Array of {coordinate1, coordinate2}
        
        // Movement mode state
        this.movementMode = false;
        this.selectedUnitHex = null; // Hex with unit selected for movement
        this.validMovementHexes = []; // Array of {coordinate1, coordinate2}
        
        // Pan and zoom state
        this.isPanning = false;
        this.panStartX = 0;
        this.panStartY = 0;
        this.panStartOffsetX = 0;
        this.panStartOffsetY = 0;
        this.minScale = 0.3;
        this.maxScale = 3.0;
        
        this.init();
        this.preloadPieceImages();
    }
    
    preloadPieceImages() {
        const pieces = ['peasant', 'spearman', 'baron', 'knight', 'tower', 'strong_tower', 'city', 
                       'farm', 'farm0', 'farm1', 'farm2', 'grave', 'palm', 'pine'];
        
        let loadedCount = 0;
        const totalImages = pieces.length;
        
        pieces.forEach(piece => {
            // Normalize piece name to lowercase for consistent lookup
            const normalizedPiece = piece.toLowerCase();
            const imageName = getPieceImage(normalizedPiece);
            if (imageName) {
                const img = new Image();
                // When image loads, trigger a re-render if we have hexes to display
                img.onload = () => {
                    loadedCount++;
                    // Re-render when images finish loading (if we have hexes to display)
                    if (this.hexes.length > 0) {
                        this.render();
                    }
                };
                img.onerror = () => {
                    console.warn(`Failed to load image: ${imageName} for piece: ${normalizedPiece}`);
                    loadedCount++;
                };
                img.src = `/static/assets/original_game_assets/atlas/${imageName}`;
                // Store with normalized (lowercase) key for consistent lookup
                this.pieceImages[normalizedPiece] = img;
            } else {
                // If no image name, count it as "loaded" (nothing to load)
                console.warn(`No image mapping found for piece: ${normalizedPiece}`);
                loadedCount++;
            }
        });
    }
    
    init() {
        // Create canvas
        this.canvas = document.createElement('canvas');
        this.canvas.style.width = '100%';
        this.canvas.style.height = '100%';
        this.canvas.style.display = 'block';
        this.container.appendChild(this.canvas);
        
        this.ctx = this.canvas.getContext('2d');
        
        // Set canvas size
        this.resize();
        
        // Handle window resize
        window.addEventListener('resize', () => this.resize());
        
        // Handle mouse events
        this.canvas.addEventListener('click', (e) => this.handleClick(e));
        this.canvas.addEventListener('mousemove', (e) => this.handleMouseMove(e));
        this.canvas.addEventListener('wheel', (e) => this.handleWheel(e));
        this.canvas.addEventListener('mousedown', (e) => this.handleMouseDown(e));
        this.canvas.addEventListener('mouseup', (e) => this.handleMouseUp(e));
        this.canvas.addEventListener('mouseleave', (e) => this.handleMouseLeave(e));
        
        // Prevent context menu on middle mouse button
        this.canvas.addEventListener('contextmenu', (e) => {
            if (e.button === 1) {
                e.preventDefault();
            }
        });
    }
    
    resize() {
        const rect = this.container.getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = rect.height;
        this.render();
    }
    
    setHexes(hexes) {
        this.hexes = hexes;
        this.centerView();
        this.render();
    }
    
    setCurrentPlayerColor(color) {
        this.currentPlayerColor = color;
    }
    
    centerView() {
        if (this.hexes.length === 0) return;
        
        // Calculate bounds using effective hex size
        const effectiveHexSize = this.hexSize * this.spacingMultiplier;
        let minX = Infinity, maxX = -Infinity;
        let minY = Infinity, maxY = -Infinity;
        
        for (const hex of this.hexes) {
            const pos = hexToPixel(hex.coordinate1, hex.coordinate2, effectiveHexSize);
            minX = Math.min(minX, pos.x);
            maxX = Math.max(maxX, pos.x);
            minY = Math.min(minY, pos.y);
            maxY = Math.max(maxY, pos.y);
        }
        
        // Center the view (account for zoom scale)
        const centerX = (minX + maxX) / 2;
        const centerY = (minY + maxY) / 2;
        
        this.offsetX = this.canvas.width / 2 - centerX * this.scale;
        this.offsetY = this.canvas.height / 2 - centerY * this.scale;
    }
    
    render() {
        if (!this.ctx) return;
        
        // Clear canvas
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Draw hexes
        for (const hex of this.hexes) {
            this.drawHex(hex);
        }
    }
    
    drawHex(hex) {
        // Calculate position in world space (without zoom)
        const worldHexSize = this.hexSize * this.spacingMultiplier;
        const pos = hexToPixel(hex.coordinate1, hex.coordinate2, worldHexSize);
        
        // Apply zoom scale to position, then add offset
        const x = (pos.x * this.scale) + this.offsetX;
        const y = (pos.y * this.scale) + this.offsetY;
        
        // Skip if outside viewport (account for zoom)
        const effectiveSize = this.hexSize * this.scale;
        if (x < -effectiveSize || x > this.canvas.width + effectiveSize ||
            y < -effectiveSize || y > this.canvas.height + effectiveSize) {
            return;
        }
        
        // Draw hex background (color)
        this.drawHexShape(x, y, hex.color);
        
        // Draw piece if present
        if (hex.piece) {
            this.drawPiece(x, y, hex.piece);
        }
        
        // Gray out units that have moved (not ready) - draw after piece
        if (hex.piece && isUnitPiece(hex.piece) && hex.is_ready === false) {
            this.drawGrayedOutUnit(x, y);
        }
        
        // Draw selection border if selected
        if (this.selectedHex && 
            this.selectedHex.coordinate1 === hex.coordinate1 &&
            this.selectedHex.coordinate2 === hex.coordinate2) {
            this.drawSelectionBorder(x, y);
        }
        
        // Draw placement outline if in placement mode and hex is valid
        if (this.placementMode && this.isValidPlacementHex(hex)) {
            this.drawPlacementOutline(x, y);
        }
        
        // Draw movement outline if in movement mode and hex is valid
        if (this.movementMode && this.isValidMovementHex(hex)) {
            this.drawMovementOutline(x, y);
        }
    }
    
    drawHexShape(x, y, color) {
        const ctx = this.ctx;
        const radius = this.hexSize * this.scale;
        
        ctx.save();
        
        // Draw hexagon (pointy-top orientation)
        // Start at top point (angle -π/2) for pointy-top hex
        ctx.beginPath();
        for (let i = 0; i < 6; i++) {
            // Offset by -π/2 to start at top (pointy-top hex)
            const angle = (Math.PI / 3 * i) - (Math.PI / 2);
            const hx = x + radius * Math.cos(angle);
            const hy = y + radius * Math.sin(angle);
            if (i === 0) {
                ctx.moveTo(hx, hy);
            } else {
                ctx.lineTo(hx, hy);
            }
        }
        ctx.closePath();
        
        // Fill with color
        const colorName = getColorName(color);
        ctx.fillStyle = this.getColorHex(colorName);
        ctx.fill();
        
        // Draw border
        ctx.strokeStyle = '#333';
        ctx.lineWidth = 1;
        ctx.stroke();
        
        ctx.restore();
    }
    
    getColorHex(colorName) {
        const colors = {
            'gray': '#808080',
            'green': '#4CAF50',
            'red': '#F44336',
            'blue': '#2196F3',
            'yellow': '#FFEB3B',
            'cyan': '#00BCD4',
            'aqua': '#00FFFF',
            'white': '#FFFFFF',
            'orange': '#FF9800',
            'purple': '#9C27B0',
            'rose': '#E91E63',
            'mint': '#4CAF50',
            'ice': '#B3E5FC',
            'brown': '#8D6E63',
            'lavender': '#B39DDB',
            'brass': '#CD7F32',
            'algae': '#64B5F6',
            'orchid': '#BA68C8',
            'whiskey': '#D2691E'
        };
        return colors[colorName] || '#808080';
    }
    
    drawPiece(x, y, pieceType) {
        // Normalize piece type to lowercase for consistent lookup
        const normalizedPieceType = pieceType ? pieceType.toLowerCase() : null;
        if (!normalizedPieceType) return;
        
        const img = this.pieceImages[normalizedPieceType];
        if (!img) {
            console.warn(`Piece image not found for: ${normalizedPieceType} (original: ${pieceType})`);
            return;
        }
        
        // Only draw if image is loaded
        if (img.complete && img.naturalHeight !== 0) {
            const size = this.hexSize * this.scale;
            this.ctx.drawImage(
                img,
                x - size / 2,
                y - size / 2,
                size,
                size
            );
        }
    }
    
    drawSelectionBorder(x, y) {
        const ctx = this.ctx;
        const radius = this.hexSize * this.scale;
        
        ctx.save();
        ctx.strokeStyle = '#FFFF00';
        ctx.lineWidth = 3;
        
        ctx.beginPath();
        for (let i = 0; i < 6; i++) {
            // Offset by -π/2 to match hex drawing (pointy-top)
            const angle = (Math.PI / 3 * i) - (Math.PI / 2);
            const hx = x + radius * Math.cos(angle);
            const hy = y + radius * Math.sin(angle);
            if (i === 0) {
                ctx.moveTo(hx, hy);
            } else {
                ctx.lineTo(hx, hy);
            }
        }
        ctx.closePath();
        ctx.stroke();
        
        ctx.restore();
    }
    
    drawPlacementOutline(x, y) {
        const ctx = this.ctx;
        const radius = this.hexSize * this.scale;
        
        ctx.save();
        ctx.strokeStyle = '#00FF00'; // Green color for valid placement
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 5]); // Dashed line
        
        ctx.beginPath();
        for (let i = 0; i < 6; i++) {
            // Offset by -π/2 to match hex drawing (pointy-top)
            const angle = (Math.PI / 3 * i) - (Math.PI / 2);
            const hx = x + radius * Math.cos(angle);
            const hy = y + radius * Math.sin(angle);
            if (i === 0) {
                ctx.moveTo(hx, hy);
            } else {
                ctx.lineTo(hx, hy);
            }
        }
        ctx.closePath();
        ctx.stroke();
        ctx.restore();
    }
    
    isValidPlacementHex(hex) {
        if (!this.placementMode || this.validPlacementHexes.length === 0) {
            return false;
        }
        return this.validPlacementHexes.some(
            vh => vh.coordinate1 === hex.coordinate1 && vh.coordinate2 === hex.coordinate2
        );
    }
    
    setPlacementMode(pieceType, provinceHex, validHexes) {
        this.placementMode = true;
        this.placementPieceType = pieceType;
        this.placementProvinceHex = provinceHex;
        this.validPlacementHexes = validHexes || [];
        this.render();
    }
    
    cancelPlacementMode() {
        this.placementMode = false;
        this.placementPieceType = null;
        this.placementProvinceHex = null;
        this.validPlacementHexes = [];
        this.render();
    }
    
    drawMovementOutline(x, y) {
        const ctx = this.ctx;
        const radius = this.hexSize * this.scale;
        
        ctx.save();
        ctx.strokeStyle = '#FFFF00'; // Yellow color for valid movement
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 5]); // Dashed line
        
        ctx.beginPath();
        for (let i = 0; i < 6; i++) {
            // Offset by -π/2 to match hex drawing (pointy-top)
            const angle = (Math.PI / 3 * i) - (Math.PI / 2);
            const hx = x + radius * Math.cos(angle);
            const hy = y + radius * Math.sin(angle);
            if (i === 0) {
                ctx.moveTo(hx, hy);
            } else {
                ctx.lineTo(hx, hy);
            }
        }
        ctx.closePath();
        ctx.stroke();
        ctx.restore();
    }
    
    drawGrayedOutUnit(x, y) {
        const ctx = this.ctx;
        const radius = this.hexSize * this.scale;
        
        ctx.save();
        // Draw a semi-transparent overlay to gray out the unit
        ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
        ctx.beginPath();
        ctx.arc(x, y, radius * 0.8, 0, 2 * Math.PI);
        ctx.fill();
        ctx.restore();
    }
    
    isValidMovementHex(hex) {
        if (!this.movementMode || this.validMovementHexes.length === 0) {
            return false;
        }
        return this.validMovementHexes.some(
            vh => vh.coordinate1 === hex.coordinate1 && vh.coordinate2 === hex.coordinate2
        );
    }
    
    setMovementMode(unitHex, validHexes) {
        this.movementMode = true;
        this.selectedUnitHex = unitHex;
        this.validMovementHexes = validHexes || [];
        this.render();
    }
    
    cancelMovementMode() {
        this.movementMode = false;
        this.selectedUnitHex = null;
        this.validMovementHexes = [];
        this.render();
    }
    
    handleMouseMove(e) {
        if (this.isPanning) {
            // Pan the map
            const rect = this.canvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;
            
            const deltaX = mouseX - this.panStartX;
            const deltaY = mouseY - this.panStartY;
            
            this.offsetX = this.panStartOffsetX + deltaX;
            this.offsetY = this.panStartOffsetY + deltaY;
            
            this.render();
        }
    }
    
    handleWheel(e) {
        e.preventDefault();
        
        const rect = this.canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        
        // Get mouse position in world coordinates (before zoom)
        const worldX = (mouseX - this.offsetX) / this.scale;
        const worldY = (mouseY - this.offsetY) / this.scale;
        
        // Calculate zoom delta
        const zoomDelta = e.deltaY > 0 ? 0.9 : 1.1;
        const newScale = Math.max(this.minScale, Math.min(this.maxScale, this.scale * zoomDelta));
        
        if (newScale === this.scale) return; // Hit zoom limit
        
        // Calculate new offset to keep mouse position fixed in world space
        this.offsetX = mouseX - worldX * newScale;
        this.offsetY = mouseY - worldY * newScale;
        
        this.scale = newScale;
        this.render();
    }
    
    handleMouseDown(e) {
        // Middle mouse button (button 1) for panning
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
        if (e.button === 1) {
            this.isPanning = false;
            this.canvas.style.cursor = 'default';
        }
    }
    
    handleMouseLeave(e) {
        // Stop panning if mouse leaves canvas
        this.isPanning = false;
        this.canvas.style.cursor = 'default';
    }
    
    handleClick(e) {
        // Middle mouse button click to recenter
        if (e.button === 1) {
            e.preventDefault();
            const rect = this.canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            // Convert click position to world coordinates
            const worldX = (x - this.offsetX) / this.scale;
            const worldY = (y - this.offsetY) / this.scale;
            
            // Recenter view on this position
            this.offsetX = this.canvas.width / 2 - worldX * this.scale;
            this.offsetY = this.canvas.height / 2 - worldY * this.scale;
            
            this.render();
            return;
        }
        
        // Left click for hex selection (existing behavior)
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        // Convert to hex coordinates (account for offset and zoom)
        const worldX = (x - this.offsetX) / this.scale;
        const worldY = (y - this.offsetY) / this.scale;
        const effectiveHexSize = this.hexSize * this.spacingMultiplier;
        const hexCoords = pixelToHex(worldX, worldY, effectiveHexSize);
        
        // Find hex
        const hex = this.hexes.find(h => 
            h.coordinate1 === hexCoords.q && 
            h.coordinate2 === hexCoords.r
        );
        
        // Check if we're in movement mode
        if (this.movementMode) {
            if (hex && this.isValidMovementHex(hex)) {
                // Valid movement hex selected - move the unit
                handleUnitMove(this.selectedUnitHex, hex);
                this.cancelMovementMode();
            } else {
                // Invalid hex or empty space - cancel movement mode
                this.cancelMovementMode();
            }
            return;
        }
        
        // Check if we're in placement mode
        if (this.placementMode) {
            if (hex && this.isValidPlacementHex(hex)) {
                // Valid placement hex selected - build the piece
                handlePlacementBuild(hex, this.placementPieceType);
                this.cancelPlacementMode();
            } else {
                // Invalid hex or empty space - cancel placement mode
                this.cancelPlacementMode();
                closeBuildMenu();
                hideProvinceStatus();
            }
            return;
        }
        
        // Normal selection mode
        if (hex) {
            // Only select hexes owned by the current player
            // If currentPlayerColor is not set, allow selection (for backwards compatibility)
            if (this.currentPlayerColor && hex.color !== this.currentPlayerColor) {
                // Clicked on non-player-owned tile - hide status and actions
                closeBuildMenu();
                hideProvinceStatus();
                return;
            }
            
            // Cancel placement mode if selecting a different hex
            if (this.placementMode) {
                this.cancelPlacementMode();
            }
            
            // Check if hex has a unit that can move
            if (hex.piece && isUnitPiece(hex.piece) && hex.is_ready !== false) {
                // Unit selected - enter movement mode
                handleUnitSelection(hex);
                return;
            }
            
            this.selectedHex = hex;
            this.selectedHexForBuild = hex;
            this.render();
            console.log('Selected hex:', hex);
            
            // Update status bar with province information
            updateProvinceStatus(hex);
            
            // Show build menu for user-owned tiles
            showBuildMenu(hex);
            
            // Emit event or call callback
            if (this.onHexClick) {
                this.onHexClick(hex);
            }
        } else {
            // Clicked on empty space - hide status and actions
            closeBuildMenu();
            hideProvinceStatus();
        }
    }
}
