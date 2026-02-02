// Campaign Selector JavaScript

function selectLevel(levelIndex) {
    // Always start a fresh game when selecting a level from campaign
    // (so that re-selecting the same level restarts it instead of resuming)
    fetch(`/api/game/init/${levelIndex}`, { credentials: 'include' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                window.location.href = `/game/${levelIndex}`;
            } else {
                alert(data.error || 'Failed to start game');
            }
        })
        .catch(error => {
            console.error('Error starting game:', error);
            alert('Failed to start game');
        });
}

// Add click handlers for level cards
document.addEventListener('DOMContentLoaded', function() {
    const levelCards = document.querySelectorAll('.level-card');
    
    levelCards.forEach(card => {
        card.addEventListener('click', function() {
            const levelIndex = parseInt(this.getAttribute('data-level'));
            selectLevel(levelIndex);
        });
    });
});
