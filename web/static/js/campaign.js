// Campaign Selector JavaScript

const AI_OPTIONS = [
    { value: 'human', label: 'Human' },
    { value: 'easy', label: 'Easy' },
    { value: 'average', label: 'Average' },
    { value: 'hard', label: 'Hard' },
    { value: 'expert', label: 'Expert' },
    { value: 'balancer', label: 'Balancer' },
    { value: 'ml', label: 'ML Model' },
];

let currentSelectorLevelIndex = null;

function openAiSelector(levelIndex, defaultDifficulty) {
    currentSelectorLevelIndex = levelIndex;
    const modal = document.getElementById('aiSelectorModal');
    const titleEl = document.getElementById('aiSelectorTitle');
    const rowsEl = document.getElementById('aiSelectorRows');
    titleEl.textContent = `Level ${levelIndex} – Select AI`;

    fetch(`/api/campaign/level/${levelIndex}/entities`, { credentials: 'include' })
        .then(response => response.json())
        .then(data => {
            if (!data.success) {
                alert(data.error || 'Failed to load level');
                return;
            }
            const entities = data.entities || [];
            const defaultDiff = data.default_difficulty || defaultDifficulty || 'average';
            rowsEl.innerHTML = '';
            entities.forEach((entity, i) => {
                const isHuman = entity.type === 'human';
                const row = document.createElement('div');
                row.className = 'ai-selector-row';
                row.dataset.index = String(i);
                const label = document.createElement('label');
                label.textContent = `Player ${i + 1} (${entity.color})`;
                const select = document.createElement('select');
                select.dataset.index = String(i);
                AI_OPTIONS.forEach(opt => {
                    const option = document.createElement('option');
                    option.value = opt.value;
                    option.textContent = opt.label;
                    if (isHuman) {
                        if (opt.value === 'human') option.selected = true;
                    } else {
                        if (opt.value === defaultDiff) option.selected = true;
                    }
                    select.appendChild(option);
                });
                if (isHuman) {
                    select.disabled = true;
                }
                row.appendChild(label);
                row.appendChild(select);
                rowsEl.appendChild(row);
            });
            modal.style.display = 'flex';
        })
        .catch(err => {
            console.error(err);
            alert('Failed to load level');
        });
}

function closeAiSelector() {
    document.getElementById('aiSelectorModal').style.display = 'none';
    currentSelectorLevelIndex = null;
}

function startGameFromSelector() {
    if (currentSelectorLevelIndex === null) return;
    const rows = document.querySelectorAll('#aiSelectorRows .ai-selector-row');
    const difficulties = [];
    rows.forEach(row => {
        const select = row.querySelector('select');
        difficulties.push(select ? select.value : 'average');
    });

    const startBtn = document.getElementById('aiSelectorStartBtn');
    startBtn.disabled = true;

    fetch('/api/game/init', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            level_index: currentSelectorLevelIndex,
            difficulties: difficulties.length ? difficulties : undefined,
        }),
    })
        .then(response => response.json())
        .then(data => {
            startBtn.disabled = false;
            if (data.success) {
                const levelIndex = currentSelectorLevelIndex;
                closeAiSelector();
                window.location.href = `/game/${levelIndex}`;
            } else {
                alert(data.error || 'Failed to start game');
            }
        })
        .catch(err => {
            console.error(err);
            startBtn.disabled = false;
            alert('Failed to start game');
        });
}

function selectLevel(levelIndex, defaultDifficulty) {
    openAiSelector(levelIndex, defaultDifficulty);
}

document.addEventListener('DOMContentLoaded', function () {
    const levelCards = document.querySelectorAll('.level-card');
    levelCards.forEach(card => {
        card.addEventListener('click', function () {
            const levelIndex = parseInt(this.getAttribute('data-level'), 10);
            const defaultDifficulty = this.getAttribute('data-difficulty') || 'average';
            selectLevel(levelIndex, defaultDifficulty);
        });
    });
});
