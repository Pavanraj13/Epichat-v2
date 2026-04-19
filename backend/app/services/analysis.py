from __future__ import annotations

import gc
import os
import shutil
import warnings
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import sys

# Ensure repo root is on sys.path (for importing scripts/)
sys.path.append(str(Path(__file__).resolve().parents[3]))

warnings.filterwarnings("ignore", category=RuntimeWarning)
os.environ.setdefault("MNE_LOGGING_LEVEL", "ERROR")
# Tell MNE not to use numba JIT — saves ~50MB RAM on free tier
os.environ.setdefault("MNE_USE_NUMBA", "false")

# ── Lazy globals — loaded only on first inference call ────────────────────────
# FastAPI starts at ~150MB. torch+MNE together ~350MB. GC between steps keeps
# peak usage under Render's 512MB free-tier limit.
_torch = None
_mne = None
_model = None
_device = None
_MODEL_READY = False


def _ensure_loaded() -> bool:
    """Import torch/MNE and load the model on first call only."""
    global _torch, _mne, _model, _device, _MODEL_READY

    if _MODEL_READY:
        return True

    try:
        import torch as _t
        # Limit CPU thread pool — each extra thread costs ~2MB stack
        _t.set_num_threads(1)
        _t.set_num_interop_threads(1)
        _torch = _t
    except ImportError:
        return False

    gc.collect()  # clean up before loading MNE

    try:
        import mne as _m
        _m.set_log_level("ERROR")
        _mne = _m
    except ImportError:
        return False

    gc.collect()

    from models.epichat_model import EpiChatModel

    _device = _torch.device("cpu")
    model_path = Path(__file__).resolve().parent.parent.parent / "model_weights" / "epichat_realistic.pt"

    try:
        if model_path.exists():
            m = EpiChatModel()
            checkpoint = _torch.load(model_path, map_location=_device, weights_only=True)
            m.load_state_dict(checkpoint["model_state_dict"])
            m.to(_device)
            m.eval()
            _model = m
            del checkpoint  # free checkpoint dict immediately
            gc.collect()
            _MODEL_READY = True
    except Exception as e:
        print(f"[EpiChat] Model load failed: {e}")
        return False

    return _MODEL_READY


# Use a relative path so it works both locally and in Docker
UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _softmax_seizure_prob(logits) -> float:
    probs = _torch.nn.functional.softmax(logits, dim=1)
    return float(probs[0, 1].item())


def _label_from_risk(max_prob: float) -> Tuple[str, float]:
    conf = round(max_prob * 100.0, 2)
    if max_prob >= 0.20:
        return "Ictal", conf
    if max_prob >= 0.05:
        return "Pre-ictal", conf
    return "Normal", conf


def _estimate_seizure_channels(epoch: np.ndarray, top_k: int = 3) -> List[int]:
    rms = np.sqrt(np.mean(np.square(epoch), axis=1))
    if not np.isfinite(rms).all():
        rms = np.nan_to_num(rms, nan=0.0, posinf=0.0, neginf=0.0)
    return np.argsort(-rms)[:top_k].astype(int).tolist()


def analyze_edf_to_summary(file_path: Path) -> Dict[str, Any]:
    """
    Runs EDF -> preprocess -> per-epoch inference.
    Memory-optimised for Render's 512MB free tier:
      - Lazy loads torch/MNE only when needed
      - Deletes large intermediate objects and calls gc.collect() aggressively
    """
    if not _ensure_loaded():
        raise RuntimeError("Model or dependencies failed to load.")

    from scripts.preprocess import EPOCH_SAMP, N_CHANNELS, TARGET_SFREQ, map_channels, zero_pad_to_18

    # ── 1. Load EDF ───────────────────────────────────────────────────────────
    raw = _mne.io.read_raw_edf(str(file_path), preload=True, verbose=False)
    raw_mapped = map_channels(raw.copy(), dataset="chbmit")
    if raw_mapped is None:
        raw_mapped = map_channels(raw.copy(), dataset="tusz")
    if raw_mapped is None:
        del raw
        gc.collect()
        raise ValueError("File does not have the required EEG channels to process.")

    del raw  # free original raw immediately
    raw = raw_mapped
    available_channels = list(raw.ch_names)

    if abs(raw.info["sfreq"] - TARGET_SFREQ) > 0.5:
        raw.resample(TARGET_SFREQ, npad="auto")

    # ── 2. Extract numpy data and free MNE object ──────────────────────────────
    data = raw.get_data()
    del raw  # ← free MNE object before torch inference
    gc.collect()

    data = zero_pad_to_18(data, available_channels)  # [18, N]
    n_samples = data.shape[1]
    n_epochs = n_samples // EPOCH_SAMP
    if n_epochs == 0:
        raise ValueError(f"File too short. Need ≥12 s, got {n_samples / TARGET_SFREQ:.1f}s.")

    data = data[:, : n_epochs * EPOCH_SAMP]
    epochs = data.reshape(n_epochs, N_CHANNELS, EPOCH_SAMP)  # [E,18,2400]
    del data
    gc.collect()

    # ── 3. Inference (epoch by epoch — minimal peak memory) ──────────────────
    risk_series: List[float] = []
    max_prob = 0.0
    max_epoch_idx = 0

    with _torch.no_grad():
        for i in range(n_epochs):
            epoch_np = epochs[i].astype(np.float32)
            x = _torch.tensor(epoch_np, dtype=_torch.float32).unsqueeze(0)
            logits = _model(x)
            p = _softmax_seizure_prob(logits)
            del x, logits, epoch_np  # free each tensor immediately
            if p > max_prob:
                max_prob = p
                max_epoch_idx = i
            risk_series.append(round(p * 100.0, 2))

    label, confidence = _label_from_risk(max_prob)
    seizure_channels = (
        _estimate_seizure_channels(epochs[max_epoch_idx], top_k=4)
        if label != "Normal" else []
    )
    del epochs
    gc.collect()

    return {
        "risk_score_series": risk_series,
        "max_prob": max_prob,
        "result_label": label,
        "confidence": confidence,
        "seizure_channels": seizure_channels,
    }


def save_upload_file(upload_file, filename: str) -> Path:
    path = UPLOAD_DIR / filename
    with open(path, "wb") as buffer:
        shutil.copyfileobj(upload_file, buffer)
    return path
