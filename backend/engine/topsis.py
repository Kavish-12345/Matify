"""TOPSIS (Technique for Order of Preference by Similarity to Ideal Solution)."""
from __future__ import annotations

import numpy as np


def topsis(matrix: np.ndarray, weights: np.ndarray, benefit: np.ndarray) -> np.ndarray:
    """
    matrix  : (n_alternatives, n_criteria) raw values
    weights : (n_criteria,) non-negative; normalised to sum 1 here
    benefit : (n_criteria,) True = higher is better, False = lower is better
    Returns closeness scores in [0, 1] (higher = better).

    Steps: vector-normalise each column, apply weights, find ideal best/worst,
    distance to each, score = d_worst / (d_best + d_worst).
    Known limitation: adding/removing alternatives can change the order of
    others (rank reversal).
    """
    X = np.asarray(matrix, dtype=float)
    w = np.asarray(weights, dtype=float)
    if w.sum() <= 0:
        raise ValueError("At least one TOPSIS weight must be positive")
    w = w / w.sum()

    norm = np.sqrt((X ** 2).sum(axis=0))
    norm[norm == 0] = 1.0
    V = X / norm * w

    best = np.where(benefit, V.max(axis=0), V.min(axis=0))
    worst = np.where(benefit, V.min(axis=0), V.max(axis=0))
    d_best = np.sqrt(((V - best) ** 2).sum(axis=1))
    d_worst = np.sqrt(((V - worst) ** 2).sum(axis=1))
    denom = d_best + d_worst
    return np.where(denom > 0, d_worst / np.where(denom > 0, denom, 1), 1.0)
