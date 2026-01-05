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

// Handle escape key to cancel placement mode
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && gameBoard && gameBoard.placementMode) {
        gameBoard.cancelPlacementMode();
        closeBuildMenu();
    }
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
    return fetch('/api/game/state')
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
            return data;
        })
        .catch(error => {
            console.error('Error loading game state:', error);
            throw error;
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
    if (!buildMenu) return;
    
    // Populate menu with pieces and costs
    populateBuildMenu(hex);
    
    // Show build menu (actions bar is always visible now)
    buildMenu.style.display = 'flex';
}

function closeBuildMenu() {
    const buildMenu = document.getElementById('buildMenu');
    if (buildMenu) {
        buildMenu.style.display = 'none';
    }
    if (gameBoard) {
        gameBoard.selectedHexForBuild = null;
        // Cancel placement mode if active
        if (gameBoard.placementMode) {
            gameBoard.cancelPlacementMode();
        }
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
    // Clear existing items
    const buildMenu = document.getElementById('buildMenu');
    if (!buildMenu) return;
    
    buildMenu.innerHTML = '';
    
    // Fetch province data to get current money
    fetch(`/api/game/province/${hex.coordinate1}/${hex.coordinate2}`)
        .then(response => response.json())
        .then(data => {
            if (!data.success) {
                console.error('Failed to fetch province data for build menu');
                return;
            }
            
            const provinceMoney = data.money || 0;
            const pieceCosts = data.piece_costs || {};
            
            // Create all build items in order: Farms, Towers, Units
            const items = [
                { type: 'farm', name: 'Farm', cost: pieceCosts['farm'] || 0 },
                { type: 'tower', name: 'Tower', cost: pieceCosts['tower'] || 0 },
                { type: 'strong_tower', name: 'Strong Tower', cost: pieceCosts['strong_tower'] || 0 },
                { type: 'peasant', name: 'Peasant', cost: pieceCosts['peasant'] || 0 },
                { type: 'spearman', name: 'Spearman', cost: pieceCosts['spearman'] || 0 },
                { type: 'baron', name: 'Baron', cost: pieceCosts['baron'] || 0 },
                { type: 'knight', name: 'Knight', cost: pieceCosts['knight'] || 0 }
            ];
            
            items.forEach(itemData => {
                const canAfford = provinceMoney >= itemData.cost;
                const buildItem = createBuildItemInline(itemData.type, itemData.name, itemData.cost, canAfford);
                buildMenu.appendChild(buildItem);
            });
        })
        .catch(error => {
            console.error('Error fetching province data for build menu:', error);
            // Don't show items if we can't fetch province data
        });
}

function createBuildItemInline(pieceType, displayName, cost, canAfford = true) {
    const item = document.createElement('div');
    item.className = 'build-item-inline';
    if (!canAfford) {
        item.classList.add('unaffordable');
    }
    item.setAttribute('data-name', displayName);
    
    // Only allow clicking if affordable
    if (canAfford) {
        item.onclick = () => handleBuildPiece(pieceType);
    } else {
        item.onclick = () => {
            // Show feedback that item is unaffordable
            console.log(`Cannot afford ${displayName} (cost: ${cost})`);
        };
        item.style.cursor = 'not-allowed';
    }
    
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
    if (!canAfford) {
        costEl.classList.add('unaffordable-cost');
    }
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
    console.log('Entering placement mode for', pieceType, 'from province hex', hex);
    
    // Enter placement mode: fetch valid placement hexes
    fetch('/api/game/valid-placement', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            province_coordinate1: hex.coordinate1,
            province_coordinate2: hex.coordinate2,
            piece_type: pieceType
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Check if there are any valid hexes
            if (!data.valid_hexes || data.valid_hexes.length === 0) {
                // Generate appropriate error message based on piece type
                let errorMsg = 'No valid locations to place ' + pieceType + '.';
                if (pieceType === 'farm') {
                    errorMsg += ' Farms must be adjacent to a city or another farm.';
                } else if (pieceType === 'tower') {
                    errorMsg += ' Towers can only be built on empty hexes within the province.';
                } else if (pieceType === 'strong_tower') {
                    errorMsg += ' Strong towers can only be built on existing towers.';
                } else if (['peasant', 'spearman', 'baron', 'knight'].includes(pieceType)) {
                    errorMsg += ' Units can only be built on empty hexes or trees.';
                }
                alert(errorMsg);
                return;
            }
            // Enter placement mode with valid hexes
            gameBoard.setPlacementMode(pieceType, hex, data.valid_hexes);
            console.log('Placement mode active. Valid hexes:', data.valid_hexes.length);
        } else {
            console.error('Failed to get valid placement hexes:', data.error);
            alert('Cannot place ' + pieceType + ': ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error fetching valid placement hexes:', error);
        alert('Error: ' + error.message);
    });
}

function handlePlacementBuild(hex, pieceType) {
    console.log('Building', pieceType, 'on hex', hex);
    
    // Get province hex for units (needed when building on gray hexes)
    const provinceHex = gameBoard && gameBoard.placementProvinceHex;
    
    // Send build command to backend
    const buildData = {
        coordinate1: hex.coordinate1,
        coordinate2: hex.coordinate2,
        piece_type: pieceType
    };
    
    // Include province coordinates for units (allows building on gray hexes)
    if (provinceHex) {
        buildData.province_coordinate1 = provinceHex.coordinate1;
        buildData.province_coordinate2 = provinceHex.coordinate2;
    }
    
    fetch('/api/game/build', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(buildData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('Build successful:', data.message);
            // Store province hex before reloading (since placement mode will be cancelled)
            const provinceHexToUpdate = provinceHex || (gameBoard && gameBoard.selectedHexForBuild);
            
            // Cancel placement mode (remove outlines) but keep selectedHexForBuild
            if (gameBoard) {
                gameBoard.cancelPlacementMode();
                // Ensure selectedHexForBuild is still set to the province hex
                if (provinceHexToUpdate && !gameBoard.selectedHexForBuild) {
                    gameBoard.selectedHexForBuild = provinceHexToUpdate;
                }
            }
            
            // Reload game state to show the new piece, then update province status and rebuild menu
            loadGameState().then(() => {
                // Update province status to show new money amount
                if (provinceHexToUpdate) {
                    updateProvinceStatus(provinceHexToUpdate);
                    // Re-populate build menu with updated costs (money changed)
                    // Find the hex in the updated game state
                    const updatedHex = gameBoard.hexes.find(h => 
                        h.coordinate1 === provinceHexToUpdate.coordinate1 && 
                        h.coordinate2 === provinceHexToUpdate.coordinate2
                    );
                    if (updatedHex) {
                        gameBoard.selectedHexForBuild = updatedHex;
                        showBuildMenu(updatedHex);
                    }
                }
            }).catch(error => {
                console.error('Error reloading game state:', error);
            });
        } else {
            console.error('Build failed:', data.error);
            alert('Build failed: ' + data.error);
            // Cancel placement mode on error
            if (gameBoard) {
                gameBoard.cancelPlacementMode();
            }
        }
    })
    .catch(error => {
        console.error('Error building piece:', error);
        alert('Error building piece: ' + error.message);
        // Cancel placement mode on error
        if (gameBoard) {
            gameBoard.cancelPlacementMode();
        }
    });
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
    
    // Actions bar is always visible now, so we don't hide it
}
