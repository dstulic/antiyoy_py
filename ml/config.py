"""Default hyperparameters and configuration for ML training."""

from dataclasses import dataclass, field
from typing import List, Optional

from core.enums import Difficulty

# Max hex count across all 156 campaign levels. Verified by test_action_space_constant.
MAX_CAMPAIGN_HEXES: int = 384


@dataclass
class TrainConfig:
    # Environment
    level_indices: List[int] = field(default_factory=lambda: [0, 1])
    opponent_difficulty: Optional[Difficulty] = None
    noop_opponents: bool = False  # passive opponents (curriculum rung 0)
    # Fraction(s) of opponent income withheld. One value = constant handicap;
    # several = mixed-difficulty training, with each parallel env pinned to one
    # value (stratified) so every rollout batch spans the whole spread.
    opponent_income_tax: List[float] = field(default_factory=lambda: [0.0])
    max_turns: int = 200
    action_space_hexes: int = MAX_CAMPAIGN_HEXES

    # Reward shaping (self-relative territory + economy deltas)
    territory_weight: float = 0.5
    opponent_weight: float = 0.0
    income_weight: float = 0.004
    truncation_penalty: float = -1.0
    invalid_action_penalty: float = 0.0
    time_cost: float = 0.0  # constant per-step cost; discourages action churn

    # Curriculum / early stopping
    resume_path: Optional[str] = None
    early_stop: bool = False
    win_rate_threshold: float = 0.6
    early_stop_patience: int = 3

    # Algorithm
    algorithm: str = "MaskablePPO"  # MaskablePPO | MaskableA2C
    total_timesteps: int = 1_000_000
    learning_rate: float = 3e-4
    n_steps: int = 2048
    batch_size: int = 256
    n_epochs: int = 5
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_range: float = 0.2
    ent_coef: float = 0.01
    vf_coef: float = 0.5

    # Model identity (key into ml/model_registry.yaml)
    model_details: str = "first_approach"

    # Infrastructure
    n_envs: int = 8
    seed: int = 42
    log_dir: str = "ml_logs"
    model_dir: str = "ml_models"
    eval_freq: int = 50_000
    eval_episodes: int = 5
    save_freq: int = 500_000
    tensorboard_log: str = "ml_tb_logs"
    device_override: Optional[str] = None
    no_eval: bool = False

    # Evaluation limits (separate from training)
    eval_max_turns: int = 200
    eval_max_steps: int = 5_000
    n_eval_envs: int = 5
