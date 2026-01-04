// Campaign Selector JavaScript

function selectLevel(levelIndex) {
    // Allow selection of any available level (no restrictions)
    // Navigate to game screen
    window.location.href = `/game/${levelIndex}`;
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
