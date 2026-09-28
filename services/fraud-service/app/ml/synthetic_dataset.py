"""Sprint 13 & 14 — Synthetic Dataset Generator & Model Evaluation.

Generates representative, explicitly labeled synthetic datasets covering normal
SSI operations and attack vectors per Master Implementation Plan Section 14.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix, roc_auc_score


def generate_synthetic_ssi_dataset(
    n_samples: int = 1000,
    fraud_ratio: float = 0.30,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generates an explicitly labeled synthetic dataset of SSI authentication/presentation events.
    Matches Master Implementation Plan Section 14 specifications.
    """
    rng = np.random.default_rng(seed)
    n_fraud = int(n_samples * fraud_ratio)
    n_legit = n_samples - n_fraud

    # 1. Legitimate user transactions (70%)
    legit_failed = rng.choice([0, 1], size=n_legit, p=[0.92, 0.08])
    legit_hours = rng.choice(range(7, 23), size=n_legit)  # Daytime/evening UTC
    legit_unusual_hour = np.zeros(n_legit, dtype=int)
    legit_distance = rng.uniform(0.0, 5.0, size=n_legit)
    legit_time_delta = rng.uniform(300.0, 7200.0, size=n_legit)
    legit_freq = rng.choice([1, 2, 3], size=n_legit, p=[0.75, 0.20, 0.05])
    legit_device_match = np.ones(n_legit, dtype=int)
    legit_tor = np.zeros(n_legit, dtype=int)
    legit_labels = np.zeros(n_legit, dtype=int)
    legit_types = ["NORMAL"] * n_legit

    # 2. Fraudulent & anomalous attack transactions (30%)
    fraud_failed = []
    fraud_hours = []
    fraud_unusual_hour = []
    fraud_distance = []
    fraud_time_delta = []
    fraud_freq = []
    fraud_device_match = []
    fraud_tor = []
    fraud_types = []

    for _ in range(n_fraud):
        attack_type = rng.choice([
            "BRUTE_FORCE",
            "IMPOSSIBLE_TRAVEL",
            "PRESENTATION_BURST",
            "TOR_PROXY_EXFILTRATION",
            "OFF_HOURS_ZERO_DAY",
        ])
        fraud_types.append(attack_type)

        if attack_type == "BRUTE_FORCE":
            fraud_failed.append(int(rng.integers(5, 14)))
            fraud_hours.append(int(rng.integers(0, 24)))
            fraud_unusual_hour.append(int(rng.choice([0, 1])))
            fraud_distance.append(float(rng.uniform(0.0, 50.0)))
            fraud_time_delta.append(float(rng.uniform(5.0, 30.0)))
            fraud_freq.append(int(rng.integers(4, 12)))
            fraud_device_match.append(int(rng.choice([0, 1])))
            fraud_tor.append(0)

        elif attack_type == "IMPOSSIBLE_TRAVEL":
            fraud_failed.append(int(rng.choice([0, 1, 2])))
            fraud_hours.append(int(rng.integers(0, 24)))
            fraud_unusual_hour.append(0)
            fraud_distance.append(float(rng.uniform(1800.0, 9500.0)))  # Continent jump
            fraud_time_delta.append(float(rng.uniform(30.0, 300.0)))   # < 5 min
            fraud_freq.append(int(rng.choice([1, 2])))
            fraud_device_match.append(0)
            fraud_tor.append(0)

        elif attack_type == "PRESENTATION_BURST":
            fraud_failed.append(0)
            fraud_hours.append(int(rng.integers(8, 20)))
            fraud_unusual_hour.append(0)
            fraud_distance.append(float(rng.uniform(0.0, 10.0)))
            fraud_time_delta.append(float(rng.uniform(1.0, 15.0)))
            fraud_freq.append(int(rng.integers(18, 50)))  # Burst presentation flood
            fraud_device_match.append(1)
            fraud_tor.append(0)

        elif attack_type == "TOR_PROXY_EXFILTRATION":
            fraud_failed.append(int(rng.choice([1, 2, 3])))
            fraud_hours.append(int(rng.integers(0, 24)))
            fraud_unusual_hour.append(int(rng.choice([0, 1])))
            fraud_distance.append(float(rng.uniform(500.0, 4000.0)))
            fraud_time_delta.append(float(rng.uniform(60.0, 600.0)))
            fraud_freq.append(int(rng.integers(3, 10)))
            fraud_device_match.append(0)
            fraud_tor.append(1)

        else:  # OFF_HOURS_ZERO_DAY
            fraud_failed.append(int(rng.choice([0, 1])))
            fraud_hours.append(int(rng.integers(1, 5)))  # 01:00 - 05:00 UTC
            fraud_unusual_hour.append(1)
            fraud_distance.append(float(rng.uniform(350.0, 1200.0)))
            fraud_time_delta.append(float(rng.uniform(120.0, 1800.0)))
            fraud_freq.append(int(rng.choice([1, 2, 4])))
            fraud_device_match.append(0)
            fraud_tor.append(int(rng.choice([0, 1])))

    fraud_labels = np.ones(n_fraud, dtype=int)

    df = pd.DataFrame({
        "failed_attempts": np.concatenate([legit_failed, fraud_failed]),
        "hour_of_day": np.concatenate([legit_hours, fraud_hours]),
        "is_unusual_hour": np.concatenate([legit_unusual_hour, fraud_unusual_hour]),
        "geo_distance_km": np.concatenate([legit_distance, fraud_distance]),
        "time_since_last_action_sec": np.concatenate([legit_time_delta, fraud_time_delta]),
        "presentation_frequency_10m": np.concatenate([legit_freq, fraud_freq]),
        "device_fingerprint_match": np.concatenate([legit_device_match, fraud_device_match]),
        "is_tor_or_proxy": np.concatenate([legit_tor, fraud_tor]),
        "attack_type": legit_types + fraud_types,
        "is_fraudulent": np.concatenate([legit_labels, fraud_labels]),
    })

    # Shuffle rows deterministically
    return df.sample(frac=1.0, random_state=seed).reset_index(drop=True)


def calculate_evaluation_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_probs: np.ndarray) -> Dict[str, Any]:
    """Computes academic metrics per Section 14: accuracy, precision, recall, F1, ROC-AUC, confusion matrix."""
    cm = confusion_matrix(y_true, y_pred)
    # cm layout: [[TN, FP], [FN, TP]]
    tn, fp, fn, tp = int(cm[0, 0]), int(cm[0, 1]), int(cm[1, 0]), int(cm[1, 1])

    acc = float(accuracy_score(y_true, y_pred))
    prec = float(precision_score(y_true, y_pred, zero_division=0))
    rec = float(recall_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))
    roc_auc = float(roc_auc_score(y_true, y_probs))

    return {
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1_score": round(f1, 4),
        "roc_auc": round(roc_auc, 4),
        "confusion_matrix": {
            "true_positives": tp,
            "true_negatives": tn,
            "false_positives": fp,
            "false_negatives": fn,
        },
        "sample_count": len(y_true),
    }
