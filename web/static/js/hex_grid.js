// Hex Grid Rendering Utilities

/**
 * Convert axial hex coordinates to pixel coordinates
 * @param {number} q - coordinate1 (axial q)
 * @param {number} r - coordinate2 (axial r)
 * @param {number} hexSize - Size of hex (radius)
 * @returns {{x: number, y: number}} Pixel coordinates
 */
function hexToPixel(q, r, hexSize) {
    const sqrt3 = Math.sqrt(3);
    // For pointy-top hexagons, spacing accounts for hex width
    // Horizontal spacing: sqrt(3) * size
    // Vertical spacing: 1.5 * size
    const x = hexSize * sqrt3 * (q + r / 2);
    const y = hexSize * 1.5 * r;
    return { x, y };
}

/**
 * Convert pixel coordinates to hex coordinates (approximate)
 * @param {number} x - Pixel x
 * @param {number} y - Pixel y
 * @param {number} hexSize - Size of hex (radius)
 * @returns {{q: number, r: number}} Hex coordinates
 */
function pixelToHex(x, y, hexSize) {
    const sqrt3 = Math.sqrt(3);
    const q = (sqrt3 / 3 * x - 1 / 3 * y) / hexSize;
    const r = (2 / 3 * y) / hexSize;
    return hexRound(q, r);
}

/**
 * Round fractional hex coordinates to nearest hex
 */
function hexRound(q, r) {
    let s = -q - r;
    let rq = Math.round(q);
    let rr = Math.round(r);
    let rs = Math.round(s);
    
    const qDiff = Math.abs(rq - q);
    const rDiff = Math.abs(rr - r);
    const sDiff = Math.abs(rs - s);
    
    if (qDiff > rDiff && qDiff > sDiff) {
        rq = -rr - rs;
    } else if (rDiff > sDiff) {
        rr = -rq - rs;
    }
    
    return { q: rq, r: rr };
}

/**
 * Get color name for hex rendering
 */
function getColorName(colorValue) {
    const colorMap = {
        'gray': 'gray',
        'green': 'green',
        'red': 'red',
        'blue': 'blue',
        'yellow': 'yellow',
        'cyan': 'cyan',
        'white': 'white',
        'orange': 'orange',
        'purple': 'purple',
        'rose': 'rose',
        'mint': 'mint',
        'ice': 'ice'
    };
    return colorMap[colorValue.toLowerCase()] || 'gray';
}

/**
 * Get piece image filename
 */
function getPieceImage(pieceType) {
    if (!pieceType) return null;
    
    const pieceMap = {
        'peasant': 'peasant.png',
        'spearman': 'spearman.png',
        'baron': 'baron.png',
        'knight': 'knight.png',
        'tower': 'tower.png',
        'strong_tower': 'strong_tower.png',
        'city': 'city.png',
        'farm0': 'farm0.png',
        'farm1': 'farm1.png',
        'farm2': 'farm2.png',
        'grave': 'grave.png',
        'palm': 'palm.png',
        'pine': 'pine.png'
    };
    
    return pieceMap[pieceType.toLowerCase()] || null;
}
