// Animation and Sound System

class AnimationSystem {
    constructor(canvas, ctx) {
        this.canvas = canvas;
        this.ctx = ctx;
        this.animations = [];
        this.soundsEnabled = false; // Disabled by default
    }
    
    // Enable/disable sounds
    setSoundsEnabled(enabled) {
        this.soundsEnabled = enabled;
        // Store in localStorage
        localStorage.setItem('antiyoy_sounds_enabled', enabled ? 'true' : 'false');
    }
    
    // Load sound preference from localStorage
    loadSoundPreference() {
        const saved = localStorage.getItem('antiyoy_sounds_enabled');
        if (saved !== null) {
            this.soundsEnabled = saved === 'true';
        }
    }
    
    // Play sound using Web Audio API
    playSound(soundName) {
        if (!this.soundsEnabled) {
            return;
        }
        
        try {
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            
            let oscillator = audioContext.createOscillator();
            let gainNode = audioContext.createGain();
            
            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);
            
            // Different sounds for different actions
            if (soundName === 'ding') {
                // Ding sound - high frequency, short duration
                oscillator.frequency.value = 800;
                oscillator.type = 'sine';
                gainNode.gain.setValueAtTime(0.1, audioContext.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.1);
                oscillator.start(audioContext.currentTime);
                oscillator.stop(audioContext.currentTime + 0.1);
            } else if (soundName === 'swoosh') {
                // Swoosh sound - frequency sweep
                oscillator.frequency.setValueAtTime(200, audioContext.currentTime);
                oscillator.frequency.exponentialRampToValueAtTime(100, audioContext.currentTime + 0.2);
                oscillator.type = 'sawtooth';
                gainNode.gain.setValueAtTime(0.1, audioContext.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.2);
                oscillator.start(audioContext.currentTime);
                oscillator.stop(audioContext.currentTime + 0.2);
            } else if (soundName === 'clang') {
                // Clang sound - metallic, multiple frequencies
                const frequencies = [300, 400, 500];
                frequencies.forEach((freq, index) => {
                    const osc = audioContext.createOscillator();
                    const gain = audioContext.createGain();
                    osc.connect(gain);
                    gain.connect(audioContext.destination);
                    osc.frequency.value = freq;
                    osc.type = 'square';
                    gain.gain.setValueAtTime(0.05, audioContext.currentTime + index * 0.05);
                    gain.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);
                    osc.start(audioContext.currentTime + index * 0.05);
                    osc.stop(audioContext.currentTime + 0.3);
                });
            }
        } catch (err) {
            // Ignore errors (e.g., user hasn't interacted with page yet, or Web Audio not supported)
            console.log('Sound generation failed:', err);
        }
    }
    
    // Add money emoji animation
    addMoneyAnimation(x, y, isVisible = true) {
        if (!isVisible) {
            return; // Don't animate if not visible (fog of war)
        }
        
        const animation = {
            type: 'money',
            x: x,
            y: y,
            startY: y,
            startTime: Date.now(),
            duration: 1000, // 1 second
            emoji: '💰',
            fontSize: 20,
            opacity: 1.0
        };
        
        this.animations.push(animation);
        
        // Play ding sound
        this.playSound('ding');
    }
    
    // Add unit movement animation
    addUnitMoveAnimation(startX, startY, endX, endY, pieceType, startHexCoord, endHexCoord, isVisible = true, isCombat = false) {
        if (!isVisible) {
            return; // Don't animate if not visible (fog of war)
        }
        
        // Calculate distance for constant speed animation
        const dx = endX - startX;
        const dy = endY - startY;
        const distance = Math.sqrt(dx * dx + dy * dy);
        
        // Constant speed: pixels per millisecond
        // Adjust this value to make animations faster or slower
        const speed = 0.8; // pixels per millisecond (800 pixels per second)
        
        // Calculate duration based on distance
        const duration = Math.max(150, Math.ceil(distance / speed)); // Minimum 150ms for very short moves
        
        const animation = {
            type: 'unit_move',
            startX: startX,
            startY: startY,
            endX: endX,
            endY: endY,
            currentX: startX,
            currentY: startY,
            startTime: Date.now(),
            duration: duration, // Duration based on distance for constant speed
            pieceType: pieceType,
            opacity: 1.0,
            startHexCoord: startHexCoord, // {coordinate1, coordinate2} to hide unit at start
            endHexCoord: endHexCoord // {coordinate1, coordinate2} for reference
        };
        
        this.animations.push(animation);
        
        // Play appropriate sound
        if (isCombat) {
            this.playSound('clang');
        } else {
            this.playSound('swoosh');
        }
    }
    
    // Check if a hex is currently being animated (so we can hide the unit at that position)
    isHexBeingAnimated(hexCoord) {
        for (const anim of this.animations) {
            if (anim.type === 'unit_move' && anim.startHexCoord) {
                // Check if this is the start hex (unit should be hidden here)
                if (anim.startHexCoord.coordinate1 === hexCoord.coordinate1 &&
                    anim.startHexCoord.coordinate2 === hexCoord.coordinate2) {
                    return true;
                }
                // Also check if animation is completed and at end position (hide unit there too until reload)
                if (anim.completed && anim.endHexCoord) {
                    if (anim.endHexCoord.coordinate1 === hexCoord.coordinate1 &&
                        anim.endHexCoord.coordinate2 === hexCoord.coordinate2) {
                        return true;
                    }
                }
            }
        }
        return false;
    }
    
    // Update animations
    update() {
        const now = Date.now();
        
        for (let i = this.animations.length - 1; i >= 0; i--) {
            const anim = this.animations[i];
            const elapsed = now - anim.startTime;
            const progress = Math.min(elapsed / anim.duration, 1.0);
            
            if (anim.type === 'money') {
                if (progress >= 1.0) {
                    // Animation complete, remove it
                    this.animations.splice(i, 1);
                    continue;
                }
                // Money emoji floats up and fades out
                anim.y = anim.startY - (progress * 50); // Move up 50 pixels
                anim.opacity = 1.0 - progress; // Fade out
            } else if (anim.type === 'unit_move') {
                if (progress >= 1.0) {
                    // Animation complete - keep it visible at end position until reload completes
                    anim.currentX = anim.endX;
                    anim.currentY = anim.endY;
                    anim.completed = true;
                    // Don't remove it yet - wait for reload to complete
                    continue;
                }
                // Unit moves from start to end position
                const easeProgress = this.easeInOutQuad(progress);
                anim.currentX = anim.startX + (anim.endX - anim.startX) * easeProgress;
                anim.currentY = anim.startY + (anim.endY - anim.startY) * easeProgress;
            }
        }
    }
    
    // Remove completed unit move animations (called after state reload)
    clearCompletedAnimations() {
        for (let i = this.animations.length - 1; i >= 0; i--) {
            const anim = this.animations[i];
            if (anim.type === 'unit_move' && anim.completed) {
                this.animations.splice(i, 1);
            }
        }
    }
    
    // Easing function for smooth animation
    easeInOutQuad(t) {
        return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
    }
    
    // Render animations
    render(gameBoard) {
        for (const anim of this.animations) {
            this.ctx.save();
            
            if (anim.type === 'money') {
                // Draw money emoji
                this.ctx.globalAlpha = anim.opacity;
                this.ctx.font = `${anim.fontSize}px Arial`;
                this.ctx.textAlign = 'center';
                this.ctx.textBaseline = 'middle';
                this.ctx.fillText(anim.emoji, anim.x, anim.y);
            } else if (anim.type === 'unit_move') {
                // Draw unit at current animation position
                this.ctx.globalAlpha = anim.opacity;
                gameBoard.drawPiece(anim.currentX, anim.currentY, anim.pieceType, anim.opacity);
            }
            
            this.ctx.restore();
        }
    }
    
    // Clear all animations
    clear() {
        this.animations = [];
    }
}

// Global animation system instance
let animationSystem = null;

// Initialize animation system
function initAnimationSystem(canvas, ctx) {
    animationSystem = new AnimationSystem(canvas, ctx);
    animationSystem.loadSoundPreference();
    return animationSystem;
}

// Check if action is visible (not covered by fog of war)
function isActionVisible(hex, currentPlayerColor, gameState) {
    // If fog of war is disabled, all actions are visible
    if (!gameState || !gameState.fog_of_war_enabled) {
        return true;
    }
    
    // Check if hex is visible to current player
    // This is a simplified check - in practice, you'd check the fog of war manager
    // For now, assume all hexes are visible if they're in the game state
    return true;
}
