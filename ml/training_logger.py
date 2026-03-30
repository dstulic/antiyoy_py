"""Training session logger with resource monitoring and energy estimation.

Appends one JSON object per session to ``training_sessions.jsonl`` in the
project root.  Optionally uses CodeCarbon for energy/CO2 estimation and
always collects CPU/RAM (and NVIDIA GPU when available) via psutil/pynvml.
"""

import json
import platform
import shutil
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = PROJECT_ROOT / "ml" / "model_registry.yaml"
LOG_PATH = PROJECT_ROOT / "training_sessions.json"
FINAL_MODELS_DIR = PROJECT_ROOT / "final_models"


# ---------------------------------------------------------------------------
# Model registry helpers
# ---------------------------------------------------------------------------

def load_model_details(model_name: str) -> Dict[str, str]:
    """Load a model entry from the YAML registry."""
    if not REGISTRY_PATH.exists():
        return {"name": model_name, "description": "(no registry file found)"}
    with open(REGISTRY_PATH) as f:
        registry = yaml.safe_load(f) or {}
    entry = registry.get("models", {}).get(model_name)
    if entry is None:
        return {"name": model_name, "description": f"('{model_name}' not in registry)"}
    return entry


# ---------------------------------------------------------------------------
# Hardware detection
# ---------------------------------------------------------------------------

def _get_hardware_info() -> Dict[str, Any]:
    cpu_model = platform.processor() or "unknown"
    if platform.system() == "Darwin":
        cpu_model = _get_mac_chip_name() or cpu_model
    info: Dict[str, Any] = {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "architecture": platform.machine(),
        "cpu_model": cpu_model,
        "cpu_count_physical": psutil.cpu_count(logical=False),
        "cpu_count_logical": psutil.cpu_count(logical=True),
        "ram_total_gb": round(psutil.virtual_memory().total / (1024 ** 3), 2),
    }
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        info["gpu_model"] = pynvml.nvmlDeviceGetName(handle)
        if isinstance(info["gpu_model"], bytes):
            info["gpu_model"] = info["gpu_model"].decode()
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        info["gpu_memory_gb"] = round(mem.total / (1024 ** 3), 2)
        pynvml.nvmlShutdown()
    except Exception:
        info["gpu_model"] = None
        info["gpu_memory_gb"] = None
    return info


# ---------------------------------------------------------------------------
# Background resource sampler
# ---------------------------------------------------------------------------

class ResourceMonitor:
    """Periodically samples CPU / RAM / GPU in a daemon thread."""

    def __init__(self, interval: float = 5.0):
        self.interval = interval
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.cpu_samples: List[float] = []
        self.ram_samples: List[float] = []
        self.gpu_util_samples: List[float] = []
        self.gpu_power_samples: List[float] = []
        self._gpu_handle: Any = None
        self._has_nvidia = False

    def start(self) -> None:
        try:
            import pynvml
            pynvml.nvmlInit()
            self._gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self._has_nvidia = True
        except Exception:
            pass
        psutil.cpu_percent(interval=None)  # prime the counter
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            self.cpu_samples.append(psutil.cpu_percent(interval=None))
            self.ram_samples.append(psutil.virtual_memory().used / (1024 ** 2))
            if self._has_nvidia and self._gpu_handle:
                try:
                    import pynvml
                    util = pynvml.nvmlDeviceGetUtilizationRates(self._gpu_handle)
                    power = pynvml.nvmlDeviceGetPowerUsage(self._gpu_handle) / 1000.0
                    self.gpu_util_samples.append(util.gpu)
                    self.gpu_power_samples.append(power)
                except Exception:
                    pass

    def stop(self) -> Dict[str, Any]:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        if self._has_nvidia:
            try:
                import pynvml
                pynvml.nvmlShutdown()
            except Exception:
                pass

        def _avg(lst: List[float]) -> Optional[float]:
            return round(sum(lst) / len(lst), 2) if lst else None

        def _peak(lst: List[float]) -> Optional[float]:
            return round(max(lst), 2) if lst else None

        return {
            "cpu_avg_percent": _avg(self.cpu_samples),
            "cpu_peak_percent": _peak(self.cpu_samples),
            "ram_avg_mb": _avg(self.ram_samples),
            "ram_peak_mb": _peak(self.ram_samples),
            "gpu_avg_util_percent": _avg(self.gpu_util_samples),
            "gpu_peak_util_percent": _peak(self.gpu_util_samples),
            "gpu_avg_power_w": _avg(self.gpu_power_samples),
            "gpu_peak_power_w": _peak(self.gpu_power_samples),
            "samples_collected": len(self.cpu_samples),
        }


# ---------------------------------------------------------------------------
# Main logger
# ---------------------------------------------------------------------------

class TrainingLogger:
    """Wraps one training run: start → stop → append to JSONL + archive model."""

    def __init__(self, cfg: Any, device: str):
        self.cfg = cfg
        self.device = device
        self.model_info = load_model_details(cfg.model_details)
        self._monitor = ResourceMonitor()
        self._tracker: Any = None
        self._start_time: Optional[float] = None
        self._start_dt: Optional[datetime] = None

    def start(self) -> None:
        self._start_time = time.monotonic()
        self._start_dt = datetime.now(timezone.utc)
        self._monitor.start()

        # CodeCarbon on macOS tries `sudo powermetrics` which prompts for a
        # password — skip it there and use our own TDP-based estimate instead.
        if platform.system() == "Darwin":
            print("  (macOS detected — using TDP-based energy estimate)")
            return

        try:
            import logging
            logging.getLogger("codecarbon").setLevel(logging.ERROR)

            from codecarbon import EmissionsTracker
            self._tracker = EmissionsTracker(
                project_name="antiyoy",
                log_level="error",
                save_to_file=False,
                allow_multiple_runs=True,
                measure_power_secs=30,
            )
            self._tracker.start()
        except ImportError:
            print("  (codecarbon not installed — using TDP-based energy estimate)")
        except Exception as e:
            print(f"  (codecarbon failed to start: {e} — using TDP-based energy estimate)")

    # ------------------------------------------------------------------
    def stop(self, completed: bool, timesteps_completed: int) -> Optional[str]:
        """Stop tracking, write log, archive best model.

        Returns the archived model path (relative to project root), or None.
        """
        duration = time.monotonic() - self._start_time if self._start_time else 0

        energy_kwh: Optional[float] = None
        co2_kg: Optional[float] = None
        energy_source: Optional[str] = None
        if self._tracker:
            try:
                emissions = self._tracker.stop()
                energy_kwh = round(self._tracker._total_energy.kWh, 6)
                co2_kg = round(emissions, 6) if emissions else None
                energy_source = "codecarbon"
            except Exception:
                pass

        resource_stats = self._monitor.stop()

        if energy_kwh is None and resource_stats.get("cpu_avg_percent") is not None:
            energy_kwh, energy_source = _estimate_energy_from_tdp(
                duration, resource_stats,
            )
        hardware = _get_hardware_info()
        final_model_path = self._archive_best_model()

        diff_label = (self.cfg.opponent_difficulty.value
                      if self.cfg.opponent_difficulty else "campaign")

        entry: Dict[str, Any] = {
            "timestamp": self._start_dt.isoformat() if self._start_dt else None,
            "model_details": self.cfg.model_details,
            "model_description": self.model_info.get("description", "").strip(),
            "algorithm": self.cfg.algorithm,
            "hyperparameters": {
                "learning_rate": self.cfg.learning_rate,
                "n_steps": self.cfg.n_steps,
                "batch_size": self.cfg.batch_size,
                "n_epochs": self.cfg.n_epochs,
                "gamma": self.cfg.gamma,
                "gae_lambda": self.cfg.gae_lambda,
                "clip_range": self.cfg.clip_range,
                "ent_coef": self.cfg.ent_coef,
                "vf_coef": self.cfg.vf_coef,
                "shaping_weight": self.cfg.shaping_weight,
            },
            "levels": self.cfg.level_indices,
            "difficulty": diff_label,
            "n_envs": self.cfg.n_envs,
            "device": self.device,
            "hardware": hardware,
            "duration_seconds": round(duration, 2),
            "resources": resource_stats,
            "energy_kwh": energy_kwh,
            "energy_source": energy_source,
            "co2_kg": co2_kg,
            "completed": completed,
            "total_timesteps_target": self.cfg.total_timesteps,
            "timesteps_completed": timesteps_completed,
            "final_model_path": final_model_path,
        }

        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        sessions = []
        if LOG_PATH.exists():
            try:
                sessions = json.loads(LOG_PATH.read_text())
            except (json.JSONDecodeError, ValueError):
                pass
        sessions.append(entry)
        LOG_PATH.write_text(json.dumps(sessions, indent=2, default=str) + "\n")

        self._print_summary(entry)
        return final_model_path

    # ------------------------------------------------------------------
    def _archive_best_model(self) -> Optional[str]:
        """Copy the best eval model to final_models/ with a unique name."""
        best_src = Path(self.cfg.model_dir) / "best" / "best_model.zip"
        if not best_src.exists():
            return None

        FINAL_MODELS_DIR.mkdir(parents=True, exist_ok=True)
        ts = (self._start_dt.strftime("%Y%m%d_%H%M%S")
              if self._start_dt else "unknown")
        dest_name = f"{self.cfg.model_details}_{ts}.zip"
        dest = FINAL_MODELS_DIR / dest_name

        counter = 1
        while dest.exists():
            dest_name = f"{self.cfg.model_details}_{ts}_{counter}.zip"
            dest = FINAL_MODELS_DIR / dest_name
            counter += 1

        shutil.copy2(best_src, dest)
        return str(dest.relative_to(PROJECT_ROOT))

    # ------------------------------------------------------------------
    @staticmethod
    def _print_summary(entry: Dict[str, Any]) -> None:
        secs = entry["duration_seconds"]
        h, rem = divmod(int(secs), 3600)
        m, s = divmod(rem, 60)
        dur_str = (f"{h}h {m:02d}m {s:02d}s" if h
                   else f"{m}m {s:02d}s" if m
                   else f"{s}s")

        status = "COMPLETED" if entry["completed"] else "INTERRUPTED"
        ts_done = f"{entry['timesteps_completed']:,}"
        ts_target = f"{entry['total_timesteps_target']:,}"

        res = entry.get("resources", {})
        cpu_line = _fmt_avg_peak(res.get("cpu_avg_percent"),
                                 res.get("cpu_peak_percent"), "%")
        ram_line = _fmt_avg_peak(res.get("ram_avg_mb"),
                                 res.get("ram_peak_mb"), " MB")
        gpu_line = _fmt_avg_peak(res.get("gpu_avg_util_percent"),
                                 res.get("gpu_peak_util_percent"), "%")
        gpu_pwr = _fmt_avg_peak(res.get("gpu_avg_power_w"),
                                res.get("gpu_peak_power_w"), " W")

        lines = [
            "",
            "=" * 56,
            "  Training Session Summary",
            "=" * 56,
            f"  Model details:   {entry['model_details']}",
            f"  Algorithm:       {entry['algorithm']}",
            f"  Status:          {status} ({ts_done} / {ts_target} timesteps)",
            f"  Duration:        {dur_str}",
            "",
            f"  CPU avg/peak:    {cpu_line}",
            f"  RAM avg/peak:    {ram_line}",
            f"  GPU util:        {gpu_line}",
            f"  GPU power:       {gpu_pwr}",
        ]

        if entry.get("energy_kwh") is not None:
            lines.append("")
            src = entry.get("energy_source", "")
            lines.append(f"  Energy:          {entry['energy_kwh']:.4f} kWh  ({src})")
            if entry.get("co2_kg") is not None:
                lines.append(f"  CO2:             {entry['co2_kg']:.4f} kg")

        if entry.get("final_model_path"):
            lines.append("")
            lines.append(f"  Archived model:  {entry['final_model_path']}")

        lines += [
            "",
            f"  Log:             {LOG_PATH.relative_to(PROJECT_ROOT)}",
            "=" * 56,
        ]
        print("\n".join(lines), flush=True)


# ---------------------------------------------------------------------------
# TDP-based energy fallback (used when CodeCarbon is unavailable)
# ---------------------------------------------------------------------------

# Conservative whole-package TDP values in watts.  When the exact chip is
# unknown we fall back to a reasonable default for the platform.
_TDP_DEFAULTS_W: Dict[str, float] = {
    "apple_m1":     20,
    "apple_m1_pro": 30,
    "apple_m1_max": 60,
    "apple_m2":     22,
    "apple_m2_pro": 35,
    "apple_m2_max": 75,
    "apple_m3":     25,
    "apple_m3_pro": 40,
    "apple_m3_max": 80,
    "apple_m4":     25,
    "apple_m4_pro": 45,
    "apple_m4_max": 85,
    "darwin_default": 30,     # conservative Apple Silicon fallback
    "linux_default":  65,     # typical desktop CPU package
}


def _get_mac_chip_name() -> str:
    """Use sysctl to get the actual chip name on macOS (e.g. 'Apple M4 Pro')."""
    import subprocess
    try:
        result = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip().lower()
    except Exception:
        return ""


def _guess_tdp_watts() -> float:
    """Best-effort TDP guess from chip name."""
    if platform.system() == "Darwin":
        chip = _get_mac_chip_name()  # e.g. "apple m4 pro"
        # Match longest key first so "m4_pro" beats "m4"
        for key in sorted(_TDP_DEFAULTS_W, key=len, reverse=True):
            if key.startswith("apple_"):
                pattern = key.replace("apple_", "").replace("_", " ")
                if pattern in chip:
                    return _TDP_DEFAULTS_W[key]
        return _TDP_DEFAULTS_W["darwin_default"]
    return _TDP_DEFAULTS_W["linux_default"]


def _estimate_energy_from_tdp(
    duration_secs: float,
    resource_stats: Dict[str, Any],
) -> tuple:
    """Return (energy_kwh, source_label) using TDP * utilisation * time."""
    tdp = _guess_tdp_watts()
    cpu_frac = (resource_stats.get("cpu_avg_percent") or 0) / 100.0

    # GPU power from pynvml is already in watts — use it directly if present.
    gpu_avg_w = resource_stats.get("gpu_avg_power_w") or 0.0

    hours = duration_secs / 3600.0
    energy_kwh = round((tdp * cpu_frac + gpu_avg_w) * hours / 1000.0, 6)
    return energy_kwh, f"tdp_estimate ({tdp}W)"


def _fmt_avg_peak(avg: Optional[float], peak: Optional[float],
                  unit: str) -> str:
    if avg is None:
        return "N/A"
    peak_str = f" / {peak:.1f}{unit}" if peak is not None else ""
    return f"{avg:.1f}{unit}{peak_str}"
