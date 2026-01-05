// Game Screen JavaScript

let gameSessionId = null;
let gameBoard = null;

// Hamburger Menu Functions
function toggleMenu() {
    const menuPanel = document.getElementById('menuPanel');
    const menuOverlay = document.getElementById('menuOverlay');
    
    menuPanel.classList.toggle('active');
    menuOverlay.classList.toggle('active');
}

// Menu Actions
function restartGame() {
    if (confirm('Are you sure you want to restart the game? All progress will be lost.')) {
        fetch('/api/game/restart', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Reload the game
                location.reload();
            } else {
                alert('Failed to restart game: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error restarting game:', error);
            alert('Error restarting game');
        });
    }
    toggleMenu();
}

function saveGame() {
    fetch('/api/game/save', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Game saved successfully!');
        } else {
            alert('Failed to save game: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('Error saving game:', error);
        alert('Error saving game');
    });
    toggleMenu();
}

function exitGame() {
    if (confirm('Are you sure you want to exit? Unsaved progress will be lost.')) {
        window.location.href = '/';
    }
    toggleMenu();
}

// Initialize game when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Initialize game session
    fetch(`/api/game/init/${levelIndex}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                gameSessionId = data.session_id;
                console.log('Game initialized:', gameSessionId);
                
                // Hide loading message
                const loadingDiv = document.querySelector('.game-loading');
                if (loadingDiv) {
                    loadingDiv.style.display = 'none';
                }
                
                // Initialize game board rendering
                initializeGameBoard();
                
                // Polling disabled for now - game state only updates on user actions
                // Can be re-enabled later for AI turns or multiplayer
                // startGameStatePolling();
            } else {
                alert('Failed to initialize game: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error initializing game:', error);
            alert('Error initializing game');
        });
});

// Clean up on page unload
window.addEventListener('beforeunload', () => {
    stopGameStatePolling();
});

function initializeGameBoard() {
    // Create game board container
    const gameBoardContainer = document.getElementById('gameBoard');
    gameBoardContainer.innerHTML = '<div id="hexGridContainer" style="width: 100%; height: 100%;"></div>';
    
    // Initialize game board renderer
    // hexSize: radius of each hex (default 30)
    // spacingMultiplier: adjust spacing between neighbors (1.0 = default, >1.0 = more space, <1.0 = less space)
    gameBoard = new GameBoard('hexGridContainer', 30, 1.0);
    
    // Set up hex click handler
    gameBoard.onHexClick = (hex) => {
        console.log('Hex clicked:', hex);
        // TODO: Handle hex selection and actions
    };
    
    // Load game state and render
    loadGameState();
}

function loadGameState() {
    fetch('/api/game/state')
        .then(response => response.json())
        .then(data => {
            if (data.success && data.hexes) {
                gameBoard.setHexes(data.hexes);
                // Set current player color for selection filtering
                if (data.current_color) {
                    gameBoard.setCurrentPlayerColor(data.current_color);
                }
            } else {
                console.error('Failed to load game state:', data);
            }
        })
        .catch(error => {
            console.error('Error loading game state:', error);
        });
}

// Periodically update game state (polling)
let gameStateInterval = null;

function startGameStatePolling() {
    // Update every 500ms
    gameStateInterval = setInterval(() => {
        loadGameState();
    }, 500);
}

function stopGameStatePolling() {
    if (gameStateInterval) {
        clearInterval(gameStateInterval);
        gameStateInterval = null;
    }
}

// Close menu when clicking outside
document.addEventListener('DOMContentLoaded', function() {
    const menuOverlay = document.getElementById('menuOverlay');
    const menuPanel = document.getElementById('menuPanel');
    const hamburgerBtn = document.getElementById('hamburgerBtn');
    
    // Close menu when clicking on overlay
    if (menuOverlay) {
        menuOverlay.addEventListener('click', function(e) {
            // Only close if clicking directly on overlay, not on menu panel
            if (e.target === menuOverlay) {
                toggleMenu();
            }
        });
    }
    
    // Close menu when clicking outside menu panel and hamburger button
    document.addEventListener('click', function(e) {
        if (menuPanel && menuPanel.classList.contains('active')) {
            // Check if click is outside both menu panel and hamburger button
            const clickedOutsideMenu = !menuPanel.contains(e.target);
            const clickedOutsideHamburger = !hamburgerBtn.contains(e.target);
            
            if (clickedOutsideMenu && clickedOutsideHamburger) {
                // Don't close if clicking on build menu
                const buildMenu = document.getElementById('buildMenu');
                if (buildMenu && buildMenu.contains(e.target)) {
                    return;
                }
                toggleMenu();
            }
        }
    });
    
    // Prevent clicks inside menu panel from closing the menu
    if (menuPanel) {
        menuPanel.addEventListener('click', function(e) {
            e.stopPropagation();
        });
    }
});

// Build Menu Functions
function showBuildMenu(hex) {
    const buildMenu = document.getElementById('buildMenu');
    const actionsBar = document.getElementById('actionsBar');
    if (!buildMenu || !actionsBar) return;
    
    // Populate menu with pieces and costs
    populateBuildMenu(hex);
    
    // Show actions bar
    actionsBar.style.display = 'flex';
}

function closeBuildMenu() {
    const actionsBar = document.getElementById('actionsBar');
    if (actionsBar) {
        actionsBar.style.display = 'none';
    }
    if (gameBoard) {
        gameBoard.selectedHexForBuild = null;
    }
}

// Action button functions
function undoAction() {
    console.log('Undo action');
    // TODO: Implement undo functionality
}

function endTurn() {
    console.log('End turn');
    // TODO: Implement end turn functionality
}

function populateBuildMenu(hex) {
    // Define piece costs (base costs - farm cost varies by province)
    const pieceCosts = {
        'farm0': 12,  // Base cost, will increase with more farms
        'farm1': 12,
        'farm2': 12,
        'tower': 15,
        'strong_tower': 35,
        'peasant': 10,
        'spearman': 20,
        'baron': 30,
        'knight': 40
    };
    
    // Clear existing items
    const buildMenu = document.getElementById('buildMenu');
    if (!buildMenu) return;
    
    buildMenu.innerHTML = '';
    
    // Create all build items in order: Farms, Towers, Units
    const items = [
        { type: 'farm0', name: 'Farm', cost: pieceCosts['farm0'] },
        { type: 'tower', name: 'Tower', cost: pieceCosts['tower'] },
        { type: 'strong_tower', name: 'Strong Tower', cost: pieceCosts['strong_tower'] },
        { type: 'peasant', name: 'Peasant', cost: pieceCosts['peasant'] },
        { type: 'spearman', name: 'Spearman', cost: pieceCosts['spearman'] },
        { type: 'baron', name: 'Baron', cost: pieceCosts['baron'] },
        { type: 'knight', name: 'Knight', cost: pieceCosts['knight'] }
    ];
    
    items.forEach(itemData => {
        const buildItem = createBuildItemInline(itemData.type, itemData.name, itemData.cost);
        buildMenu.appendChild(buildItem);
    });
}

function createBuildItemInline(pieceType, displayName, cost) {
    const item = document.createElement('div');
    item.className = 'build-item-inline';
    item.setAttribute('data-name', displayName);
    item.onclick = () => handleBuildPiece(pieceType);
    
    const icon = document.createElement('div');
    icon.className = 'build-item-icon';
    
    const img = document.createElement('img');
    const imageName = getPieceImage(pieceType);
    if (imageName) {
        img.src = `/static/assets/original_game_assets/atlas/${imageName}`;
        img.alt = displayName;
    } else {
        // Fallback if image not found
        icon.textContent = '?';
        icon.style.color = 'white';
        icon.style.fontSize = '1.5em';
    }
    icon.appendChild(img);
    
    const costEl = document.createElement('div');
    costEl.className = 'build-item-cost';
    costEl.textContent = cost;
    
    item.appendChild(icon);
    item.appendChild(costEl);
    
    return item;
}

function handleBuildPiece(pieceType) {
    if (!gameBoard || !gameBoard.selectedHexForBuild) {
        console.warn('No hex selected for building');
        return;
    }
    
    const hex = gameBoard.selectedHexForBuild;
    console.log('Building', pieceType, 'on hex', hex);
    
    // TODO: Send build command to backend
    // For now, just close the menu
    closeBuildMenu();
}

// Province Status Functions
function updateProvinceStatus(hex) {
    if (!hex || hex.coordinate1 === undefined || hex.coordinate2 === undefined) {
        hideProvinceStatus();
        return;
    }
    
    fetch(`/api/game/province/${hex.coordinate1}/${hex.coordinate2}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const statusBar = document.getElementById('statusBar');
                const statusFunds = document.getElementById('statusFunds');
                const statusProfit = document.getElementById('statusProfit');
                const statusCityName = document.getElementById('statusCityName');
                
                if (statusBar && statusFunds && statusProfit && statusCityName) {
                    // Update funds
                    statusFunds.textContent = data.money || 0;
                    
                    // Update profit (income - consumption)
                    const profit = data.profit || 0;
                    statusProfit.textContent = profit >= 0 ? `+${profit}` : `${profit}`;
                    statusProfit.className = 'status-value ' + (profit >= 0 ? 'positive' : 'negative');
                    
                    // Update city name (if available)
                    if (data.city_name) {
                        statusCityName.textContent = data.city_name;
                        statusCityName.style.display = 'block';
                    } else {
                        statusCityName.style.display = 'none';
                    }
                    
                    // Status bar is always visible, just update content
                }
            } else {
                hideProvinceStatus();
            }
        })
        .catch(error => {
            console.error('Error loading province status:', error);
            hideProvinceStatus();
        });
}

function hideProvinceStatus() {
    const statusBar = document.getElementById('statusBar');
    const actionsBar = document.getElementById('actionsBar');
    const statusFunds = document.getElementById('statusFunds');
    const statusProfit = document.getElementById('statusProfit');
    const statusCityName = document.getElementById('statusCityName');
    
    // Clear status bar values (but keep it visible)
    if (statusFunds) statusFunds.textContent = '0';
    if (statusProfit) {
        statusProfit.textContent = '0';
        statusProfit.className = 'status-value';
    }
    if (statusCityName) {
        statusCityName.textContent = '';
        statusCityName.style.display = 'none';
    }
    
    // Hide actions bar
    if (actionsBar) {
        actionsBar.style.display = 'none';
    }
}
