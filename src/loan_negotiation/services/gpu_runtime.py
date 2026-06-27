from __future__ import annotations

import os
import shutil
import subprocess


def nvidia_smi_available() -> bool:
    return shutil.which("nvidia-smi") is not None


def gpu_visible() -> bool:
    """Best-effort check that an NVIDIA GPU is visible to this process."""
    if not nvidia_smi_available():
        return False
    try:
        result = subprocess.run(
            ["nvidia-smi", "-L"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and "GPU" in (result.stdout or "")


def resolve_ollama_num_gpu(explicit: int | None = None) -> int | None:
    """
    How many model layers to offload to GPU for Ollama (`options.num_gpu`).

    Explicit OLLAMA_NUM_GPU wins (use -1 for Ollama auto, 999 to force max).
    Otherwise leave unset and let Ollama decide.
    """
    if explicit is not None:
        return explicit
    raw = os.environ.get("OLLAMA_NUM_GPU")
    if raw is not None and raw.strip() != "":
        return int(raw)
    return None
