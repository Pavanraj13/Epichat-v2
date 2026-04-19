from __future__ import annotations

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

# ── Lazy globals — loaded only on first inference call ────────────────────────
# This keeps FastAPI startup RAM under 512MB on Render's free tier.
# PyTorch + MNE together ~400MB; loading them at import time crashes the instance.
_torch = None
_mne = None
_model = None
_device = None
_MODEL_READY = False


def _ensure_loaded():
    """Import torch/MNE and load the model on first call only."""
    global _torch, _mne, _model, _device, _MODEL_READY

    if _MODEL_READY:
        return True

    # ── Import heavy deps lazily ──────────────────────────────────────────────
    try:
        import torch as _t
        _torch = _t
    except ImportError:
        return False

    try:
        import mne as _m
        _m.set_log_level("ERROR")
        _mne = _m
    except ImportError:
        return False

    # ── Import model class ────────────────────────────────────────────────────
    from models.epichat_model import EpiChatModel

    _device = _torch.device("cpu")  # Free tier has no GPU
    model_path = Path(__file__).resolve().parent.parent.parent / "model_weights" / "epichat_realistic.pt"

    try:
        if model_path.exists():
            m = EpiChatModel()
            checkpoint = _torch.load(model_path, map_location=_device)
            m.load_state_dict(checkpoint["model_state_dict"])
            m.to(_device)
            m.eval()
            _model = m
            _MODEL_READY = True
    except Exception as e:
        print(f"[EpiChat] Model load failed: {e}")
        return False

    return _MODEL_READY

UPLOAD_DIR = Path("/app/backend/data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _softmax_seizure_prob(logits) -> float:
    probs = _torch.nn.functional.softmax(logits, dim=1)
    return float(probs[0, 1].item())


def _label_from_risk(max_prob: float) -> Tuple[str, float]:
    """
    Map seizure prob (0..1) to UX labels + confidence%.
    Confidence is the max seizure probability in percent.
    """
    conf = round(max_prob * 100.0, 2)
    # Keep thresholds aligned with existing model sensitivity (0.05) but add a mid-zone.
    if max_prob >= 0.20:
        return "Ictal", conf
    if max_prob >= 0.05:
        return "Pre-ictal", conf
    return "Normal", conf


def _estimate_seizure_channels(epoch: np.ndarray, top_k: int = 3) -> List[int]:
    """
    epoch: [18, 2400]. We estimate 'hot' channels via RMS energy.
    Returns channel indices (0-based) sorted by descending energy.
    """
    rms = np.sqrt(np.mean(np.square(epoch), axis=1))  # [18]
    if not np.isfinite(rms).all():
        rms = np.nan_to_num(rms, nan=0.0, posinf=0.0, neginf=0.0)
    idxs = np.argsort(-rms)[:top_k].astype(int).tolist()
    return idxs


def analyze_edf_to_summary(file_path: Path) -> Dict[str, Any]:
    """
    Runs EDF -> preprocess -> per-epoch inference.
    Returns:
      - risk_score_series: list[float] (0..100 per epoch)
      - max_prob: float (0..1)
      - label: Normal/Pre-ictal/Ictal
      - confidence: float (0..100)
      - seizure_channels: list[int]
    """
    # Lazy-load torch, MNE and model on first call
    if not _ensure_loaded():
        raise RuntimeError("Model or dependencies failed to load.")

    from scripts.preprocess import EPOCH_SAMP, N_CHANNELS, TARGET_SFREQ, map_channels, zero_pad_to_18

    raw = _mne.io.read_raw_edf(str(file_path), preload=True, verbose=False)

    raw_mapped = map_channels(raw.copy(), dataset="chbmit")
    if raw_mapped is None:
        raw_mapped = map_channels(raw.copy(), dataset="tusz")
    if raw_mapped is None:
        raise ValueError("File does not have the required EEG channels to process.")

    raw = raw_mapped
    available_channels = list(raw.ch_names)

    if abs(raw.info["sfreq"] - TARGET_SFREQ) > 0.5:
        raw.resample(TARGET_SFREQ, npad="auto")

    data = raw.get_data()
    data = zero_pad_to_18(data, available_channels)  # [18, N]

    n_samples = data.shape[1]
    n_epochs = n_samples // EPOCH_SAMP
    if n_epochs == 0:
        raise ValueError(f"File is too short. Need at least 12 seconds, found {n_samples / TARGET_SFREQ:.1f}s.")

    data = data[:, : n_epochs * EPOCH_SAMP]
    epochs = data.reshape(n_epochs, N_CHANNELS, EPOCH_SAMP)  # [E, 18, 2400]

    risk_series: List[float] = []
    max_prob = 0.0
    max_epoch_idx = 0

    with _torch.no_grad():
        for i in range(n_epochs):
            epoch_data = epochs[i].astype(np.float32)
            x = _torch.tensor(epoch_data, dtype=_torch.float32).unsqueeze(0).to(_device)
            logits = _model(x)
            p = _softmax_seizure_prob(logits)
            max_prob = max(max_prob, p)
            if p == max_prob:
                max_epoch_idx = i
            risk_series.append(round(p * 100.0, 2))

    label, confidence = _label_from_risk(max_prob)
    seizure_channels = _estimate_seizure_channels(epochs[max_epoch_idx], top_k=4) if label != "Normal" else []

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

