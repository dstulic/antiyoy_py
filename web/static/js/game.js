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

// Close menu when clicking overlay
document.addEventListener('DOMContentLoaded', function() {
    const menuOverlay = document.getElementById('menuOverlay');
    if (menuOverlay) {
        menuOverlay.addEventListener('click', toggleMenu);
    }
});
