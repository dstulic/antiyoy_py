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
    // Generate default save name: YY_MM_DD_HH_MM
    const now = new Date();
    const year = now.getFullYear().toString().slice(-2);
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const defaultName = `${year}_${month}_${day}_${hours}_${minutes}`;
    
    // Show save dialog
    const saveName = prompt('Enter save name:', defaultName);
    if (saveName === null) {
        // User cancelled
        toggleMenu();
        return;
    }
    
    if (!saveName.trim()) {
        alert('Save name cannot be empty');
        toggleMenu();
        return;
    }
    
    fetch('/api/game/save', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            save_name: saveName.trim()
        })
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

function toggleSounds() {
    if (!gameBoard || !gameBoard.animationSystem) {
        return;
    }
    
    const currentState = gameBoard.animationSystem.soundsEnabled;
    const newState = !currentState;
    gameBoard.animationSystem.setSoundsEnabled(newState);
    
    // Update UI
    const soundToggleBtn = document.getElementById('soundToggleBtn');
    const soundToggleText = document.getElementById('soundToggleText');
    const menuIcon = soundToggleBtn.querySelector('.menu-icon');
    
    if (newState) {
        menuIcon.textContent = '🔊';
        soundToggleText.textContent = 'Disable Sounds';
    } else {
        menuIcon.textContent = '🔇';
        soundToggleText.textContent = 'Enable Sounds';
    }
    
    toggleMenu();
}

// Update sound toggle UI on page load
function updateSoundToggleUI() {
    if (!gameBoard || !gameBoard.animationSystem) {
        return;
    }
    
    const soundToggleBtn = document.getElementById('soundToggleBtn');
    const soundToggleText = document.getElementById('soundToggleText');
    if (!soundToggleBtn || !soundToggleText) {
        return;
    }
    
    const menuIcon = soundToggleBtn.querySelector('.menu-icon');
    const soundsEnabled = gameBoard.animationSystem.soundsEnabled;
    
    if (soundsEnabled) {
        menuIcon.textContent = '🔊';
        soundToggleText.textContent = 'Disable Sounds';
    } else {
        menuIcon.textContent = '🔇';
        soundToggleText.textContent = 'Enable Sounds';
    }
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
                
                // Load initial game state and auto-select city hex
                loadGameState().then(() => {
                    autoSelectCityHex();
                });
                
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

// Handle escape key to cancel placement mode or movement mode
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        if (gameBoard && gameBoard.placementMode) {
            gameBoard.cancelPlacementMode();
            closeBuildMenu();
        } else if (gameBoard && gameBoard.movementMode) {
            gameBoard.cancelMovementMode();
        }
    }
});

// Helper function to check if a piece is a unit
function isUnitPiece(piece) {
    return piece === 'peasant' || piece === 'spearman' || piece === 'baron' || piece === 'knight';
}

// Handle unit selection - enter movement mode
function handleUnitSelection(hex) {
    if (!gameBoard || !hex) {
        return;
    }
    
    // Update selected hex to the unit's hex so province status shows the correct province
    gameBoard.selectedHex = hex;
    gameBoard.selectedHexForBuild = hex;
    
    // Update province status to show the province that owns this unit
    updateProvinceStatus(hex);
    
    // Fetch valid movement hexes
    fetch('/api/game/valid-movement', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            coordinate1: hex.coordinate1,
            coordinate2: hex.coordinate2
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Enter movement mode with valid hexes
            gameBoard.setMovementMode(hex, data.valid_hexes);
            console.log('Movement mode active. Valid hexes:', data.valid_hexes.length);
        } else {
            console.error('Failed to get valid movement hexes:', data.error);
            alert('Failed to get valid movement hexes: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('Error fetching valid movement hexes:', error);
        alert('Error fetching valid movement hexes');
    });
}

// Handle unit movement
function handleUnitMove(startHex, finishHex) {
    if (!gameBoard || !startHex || !finishHex) {
        return;
    }
    
    // Send move request to backend
    fetch('/api/game/move-unit', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            start_coordinate1: startHex.coordinate1,
            start_coordinate2: startHex.coordinate2,
            finish_coordinate1: finishHex.coordinate1,
            finish_coordinate2: finishHex.coordinate2
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('Unit moved successfully');
            
            // Check if this was a combat move (enemy unit killed or building destroyed)
            const isCombat = data.combat || false;
            
            // Get hex positions for animation
            const startPos = hexToPixel(startHex.coordinate1, startHex.coordinate2, gameBoard.hexSize * gameBoard.spacingMultiplier);
            const endPos = hexToPixel(finishHex.coordinate1, finishHex.coordinate2, gameBoard.hexSize * gameBoard.spacingMultiplier);
            
            // Apply transform to get screen coordinates
            const startX = (startPos.x * gameBoard.scale) + gameBoard.offsetX;
            const startY = (startPos.y * gameBoard.scale) + gameBoard.offsetY;
            const endX = (endPos.x * gameBoard.scale) + gameBoard.offsetX;
            const endY = (endPos.y * gameBoard.scale) + gameBoard.offsetY;
            
            // Check if action is visible (not covered by fog of war)
            const isVisible = isActionVisible(finishHex, gameBoard.currentPlayerColor, data);
            
            // Add unit movement animation
            if (gameBoard.animationSystem && isVisible) {
                gameBoard.animationSystem.addUnitMoveAnimation(
                    startX, startY, endX, endY, 
                    startHex.piece, 
                    {coordinate1: startHex.coordinate1, coordinate2: startHex.coordinate2},
                    {coordinate1: finishHex.coordinate1, coordinate2: finishHex.coordinate2},
                    isVisible, isCombat
                );
                // Start animation loop if not already running
                gameBoard.startAnimationLoop();
            }
            
            // Calculate animation duration for the delay
            const dx = endX - startX;
            const dy = endY - startY;
            const distance = Math.sqrt(dx * dx + dy * dy);
            const speed = 0.8; // pixels per millisecond (must match animation speed)
            const animationDuration = Math.max(150, Math.ceil(distance / speed));
            
            // Reload game state to reflect changes (with delay to allow animation to play)
            setTimeout(() => {
                loadGameState().then(() => {
                    // Cancel movement mode
                    gameBoard.cancelMovementMode();
                    
                    // Update province status if we have a selected province hex
                    // The move might have captured a gray hex, changing the province income
                    if (gameBoard && (gameBoard.selectedHex || gameBoard.selectedHexForBuild)) {
                        const selectedHex = gameBoard.selectedHex || gameBoard.selectedHexForBuild;
                        // Find the updated hex in the new game state
                        const updatedHex = gameBoard.hexes.find(h => 
                            h.coordinate1 === selectedHex.coordinate1 && 
                            h.coordinate2 === selectedHex.coordinate2
                        );
                        if (updatedHex) {
                            // Update the selected hex reference
                            gameBoard.selectedHex = updatedHex;
                            gameBoard.selectedHexForBuild = updatedHex;
                            // Update province status to reflect new income/consumption
                            updateProvinceStatus(updatedHex);
                        }
                    }
                });
            }, animationDuration); // Wait for animation to complete
        } else {
            console.error('Failed to move unit:', data.error);
            alert('Failed to move unit: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('Error moving unit:', error);
        alert('Error moving unit');
    });
}

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
    loadGameState().then(() => {
        // Update sound toggle UI after game board is initialized
        updateSoundToggleUI();
    });
}

function loadGameState() {
    return fetch('/api/game/state')
        .then(response => response.json())
        .then(data => {
            if (data.success && data.hexes) {
                // Update hexes first (animations will stay visible during this)
                gameBoard.setHexes(data.hexes);
                // Set current player color for selection filtering
                if (data.current_color) {
                    console.log('loadGameState: Setting current player color to:', data.current_color);
                    gameBoard.setCurrentPlayerColor(data.current_color);
                } else {
                    console.log('loadGameState: No current_color in response');
                }
                
                // Clear completed animations AFTER hexes are updated (seamless transition)
                // Use a small delay to ensure the animation loop has rendered the updated hexes
                setTimeout(() => {
                    if (gameBoard.animationSystem) {
                        gameBoard.animationSystem.clearCompletedAnimations();
                        // Stop animation loop if no more animations
                        if (gameBoard.animationSystem.animations.length === 0) {
                            gameBoard._animationLoopRunning = false;
                        }
                        // Re-render to show final state without animations
                        gameBoard.render();
                    }
                }, 50); // Small delay to ensure seamless transition
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

function autoSelectCityHex() {
    /**
     * Automatically select the city hex of the first province for the current player.
     * This shows the build menu automatically when a turn starts.
     */
    if (!gameBoard || !gameBoard.hexes) {
        console.log('autoSelectCityHex: gameBoard or hexes not available');
        return;
    }
    
    // Get current player color
    const currentColor = gameBoard.currentPlayerColor;
    if (!currentColor) {
        console.log('autoSelectCityHex: currentPlayerColor not set');
        return;
    }
    
    console.log('autoSelectCityHex: Looking for city hex with color:', currentColor);
    console.log('autoSelectCityHex: Available hexes:', gameBoard.hexes.length);
    
    // Find the first city hex of the current player's color
    let cityHex = null;
    for (const hex of gameBoard.hexes) {
        console.log('autoSelectCityHex: Checking hex:', hex.coordinate1, hex.coordinate2, 'color:', hex.color, 'piece:', hex.piece);
        if (hex.color === currentColor && hex.piece === 'city') {
            cityHex = hex;
            break;
        }
    }
    
    if (cityHex) {
        // Select the hex and show build menu
        gameBoard.selectedHex = cityHex;
        gameBoard.selectedHexForBuild = cityHex;
        
        // Show build menu and update province status
        // These functions will fetch province data and verify the hex is in a province
        console.log('autoSelectCityHex: Found city hex, showing build menu');
        showBuildMenu(cityHex);
        updateProvinceStatus(cityHex);
        gameBoard.render(); // Re-render to show selection
        console.log('Auto-selected city hex:', cityHex);
    } else {
        console.log('No city hex found for current player. Current color:', currentColor);
        // Try to find any hex owned by the current player as fallback
        for (const hex of gameBoard.hexes) {
            if (hex.color === currentColor) {
                console.log('autoSelectCityHex: Found fallback hex (not a city):', hex);
                gameBoard.selectedHex = hex;
                gameBoard.selectedHexForBuild = hex;
                showBuildMenu(hex);
                updateProvinceStatus(hex);
                gameBoard.render();
                break;
            }
        }
    }
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
    
    fetch('/api/game/undo', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('Undo successful');
            // Reload game state to reflect the undo
            loadGameState().then(() => {
                // If we had a selected hex, try to restore it
                if (gameBoard && gameBoard.selectedHexForBuild) {
                    const hex = gameBoard.selectedHexForBuild;
                    updateProvinceStatus(hex);
                    populateBuildMenu(hex);
                } else {
                    // Clear selection and menus
                    closeBuildMenu();
                    hideProvinceStatus();
                }
            });
        } else {
            console.error('Undo failed:', data.error);
            alert('Cannot undo: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('Error during undo:', error);
        alert('Error: ' + error.message);
    });
}

function endTurn() {
    console.log('End turn');
    
    fetch('/api/game/end-turn', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('Turn ended successfully');
            // Clear any selections and menus
            if (gameBoard) {
                gameBoard.selectedHexForBuild = null;
                gameBoard.cancelPlacementMode();
            }
            closeBuildMenu();
            hideProvinceStatus();
            
            // Reload game state to reflect the new turn
            loadGameState().then(() => {
                console.log('Game state reloaded after turn end');
                // Auto-select city hex for the new current player
                autoSelectCityHex();
            });
        } else {
            console.error('End turn failed:', data.error);
            alert('Cannot end turn: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('Error ending turn:', error);
        alert('Error: ' + error.message);
    });
}

function populateBuildMenu(hex) {
    // Clear existing items
    const buildMenu = document.getElementById('buildMenu');
    if (!buildMenu) {
        console.error('populateBuildMenu: buildMenu element not found');
        return;
    }
    
    buildMenu.innerHTML = '';
    
    console.log('populateBuildMenu: Fetching province data for hex:', hex.coordinate1, hex.coordinate2);
    
    // Fetch province data to get current money
    fetch(`/api/game/province/${hex.coordinate1}/${hex.coordinate2}`)
        .then(response => response.json())
        .then(data => {
            console.log('populateBuildMenu: Province data received:', data);
            if (!data.success) {
                console.error('Failed to fetch province data for build menu:', data);
                // Still show the menu even if province fetch fails (might be a gray hex)
                buildMenu.style.display = 'flex';
                return;
            }
            
            // Check if this is the current player's province
            const isCurrentPlayerProvince = data.province_color && data.current_color && 
                                            data.province_color === data.current_color;
            
            console.log('populateBuildMenu: isCurrentPlayerProvince:', isCurrentPlayerProvince, 
                       'province_color:', data.province_color, 'current_color:', data.current_color);
            
            // Only show build menu for current player's provinces
            if (!isCurrentPlayerProvince) {
                console.log('populateBuildMenu: Not current player province, hiding menu');
                buildMenu.style.display = 'none';
                return;
            }
            
            buildMenu.style.display = 'flex';
            
            const provinceMoney = data.money || 0;
            const pieceCosts = data.piece_costs || {};
            const pieceMaintenance = data.piece_maintenance || {};
            const pieceStrength = data.piece_strength || {};
            
            // Create all build items in order: Farms, Towers, Units
            const items = [
                { type: 'farm', name: 'Farm', cost: pieceCosts['farm'] || 0, maintenance: pieceMaintenance['farm'] || 0, strength: pieceStrength['farm'] },
                { type: 'tower', name: 'Tower', cost: pieceCosts['tower'] || 0, maintenance: pieceMaintenance['tower'] || 0, strength: pieceStrength['tower'] },
                { type: 'strong_tower', name: 'Strong Tower', cost: pieceCosts['strong_tower'] || 0, maintenance: pieceMaintenance['strong_tower'] || 0, strength: pieceStrength['strong_tower'] },
                { type: 'peasant', name: 'Peasant', cost: pieceCosts['peasant'] || 0, maintenance: pieceMaintenance['peasant'] || 0, strength: pieceStrength['peasant'] },
                { type: 'spearman', name: 'Spearman', cost: pieceCosts['spearman'] || 0, maintenance: pieceMaintenance['spearman'] || 0, strength: pieceStrength['spearman'] },
                { type: 'baron', name: 'Baron', cost: pieceCosts['baron'] || 0, maintenance: pieceMaintenance['baron'] || 0, strength: pieceStrength['baron'] },
                { type: 'knight', name: 'Knight', cost: pieceCosts['knight'] || 0, maintenance: pieceMaintenance['knight'] || 0, strength: pieceStrength['knight'] }
            ];
            
            items.forEach(itemData => {
                const canAfford = provinceMoney >= itemData.cost;
                const buildItem = createBuildItemInline(itemData.type, itemData.name, itemData.cost, itemData.maintenance, itemData.strength, canAfford);
                buildMenu.appendChild(buildItem);
            });
        })
        .catch(error => {
            console.error('Error fetching province data for build menu:', error);
            // Don't show items if we can't fetch province data
        });
}

function createBuildItemInline(pieceType, displayName, cost, maintenance, strength, canAfford = true) {
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
    
    // Strength on top-right (for units and towers only)
    if (strength !== null && strength !== undefined && strength > 0) {
        const strengthEl = document.createElement('div');
        strengthEl.className = 'build-item-strength';
        strengthEl.textContent = strength.toString();
        item.appendChild(strengthEl);
    }
    
    // Cost on bottom-left
    const costEl = document.createElement('div');
    costEl.className = 'build-item-cost';
    costEl.textContent = cost;
    item.appendChild(costEl);
    
    // Maintenance/income on bottom-right
    const maintenanceEl = document.createElement('div');
    maintenanceEl.className = 'build-item-maintenance';
    if (maintenance > 0) {
        // Positive value (income for farms)
        maintenanceEl.textContent = `+${maintenance}`;
        maintenanceEl.classList.add('income');
    } else if (maintenance < 0) {
        // Negative value (maintenance cost)
        maintenanceEl.textContent = maintenance.toString(); // Already negative, will show as "-2"
        maintenanceEl.classList.add('maintenance');
    } else {
        // Zero or undefined - don't show
        maintenanceEl.style.display = 'none';
    }
    item.appendChild(maintenanceEl);
    
    item.appendChild(icon);
    
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
            
            // Get hex position for animation
            const hexPos = hexToPixel(hex.coordinate1, hex.coordinate2, gameBoard.hexSize * gameBoard.spacingMultiplier);
            const screenX = (hexPos.x * gameBoard.scale) + gameBoard.offsetX;
            const screenY = (hexPos.y * gameBoard.scale) + gameBoard.offsetY;
            
            // Check if action is visible (not covered by fog of war)
            const isVisible = isActionVisible(hex, gameBoard.currentPlayerColor, data);
            
            // Add money animation for builds (units, farms, towers)
            if (gameBoard.animationSystem && (pieceType === 'peasant' || pieceType === 'spearman' || 
                pieceType === 'baron' || pieceType === 'knight' || pieceType === 'farm' || 
                pieceType === 'tower' || pieceType === 'strong_tower')) {
                gameBoard.animationSystem.addMoneyAnimation(screenX, screenY, isVisible);
                // Start animation loop if not already running
                gameBoard.startAnimationLoop();
            }
            
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
                // Check if this is the current player's province
                const isCurrentPlayerProvince = data.province_color && data.current_color && 
                                                data.province_color === data.current_color;
                
                const statusBar = document.getElementById('statusBar');
                const statusFunds = document.getElementById('statusFunds');
                const statusProfit = document.getElementById('statusProfit');
                const statusCityName = document.getElementById('statusCityName');
                
                if (statusBar && statusFunds && statusProfit && statusCityName) {
                    if (isCurrentPlayerProvince) {
                        // Show province info for current player
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
                    } else {
                        // Hide province info for enemy provinces
                        statusFunds.textContent = '?';
                        statusProfit.textContent = '?';
                        statusProfit.className = 'status-value';
                        statusCityName.style.display = 'none';
                    }
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
