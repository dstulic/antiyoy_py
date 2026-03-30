"""Default hyperparameters and configuration for ML training."""

from dataclasses import dataclass, field
from typing import List, Optional

from core.enums import Difficulty


@dataclass
class TrainConfig:
    # Environment
    level_indices: List[int] = field(default_factory=lambda: [0, 1])
    opponent_difficulty: Optional[Difficulty] = None
    max_turns: int = 500
    shaping_weight: float = 0.1

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
    n_envs: int = 4
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
    eval_max_turns: int = 50
    eval_max_steps: int = 5_000
    n_eval_envs: int = 5
