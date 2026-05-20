from __future__ import annotations

import json
import math
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any, Callable

import numpy as np

from common import import_pyplot, write_csv


def require_sklearn_metrics() -> dict[str, Any]:
    from sklearn.metrics import (
        adjusted_rand_score,
        calinski_harabasz_score,
        davies_bouldin_score,
        silhouette_score,
    )

    return {
        "adjusted_rand_score": adjusted_rand_score,
        "calinski_harabasz_score": calinski_harabasz_score,
        "davies_bouldin_score": davies_bouldin_score,
        "silhouette_score": silhouette_score,
    }


def import_hdbscan() -> Any | None:
    try:
        import hdbscan
    except ImportError:
        return None
    return hdbscan


def normalize_labels(labels: np.ndarray) -> np.ndarray:
    labels = np.asarray(labels, dtype=int)
    normalized = np.full(labels.shape, -1, dtype=int)
    unique_non_noise = sorted({int(label) for label in labels.tolist() if int(label) >= 0})
    for normalized_label, original_label in enumerate(unique_non_noise, start=1):
        normalized[labels == original_label] = normalized_label
    return normalized


def build_cluster_distribution(labels: np.ndarray) -> list[dict[str, Any]]:
    values, counts = np.unique(labels, return_counts=True)
    distribution = []
    for value, count in sorted(zip(values.tolist(), counts.tolist()), key=lambda item: (item[0] == -1, item[0])):
        distribution.append({"label": int(value), "count": int(count)})
    return distribution


def build_candidate_id(candidate: dict[str, Any]) -> str:
    parts = [candidate["feature_space"], candidate["method"]]
    if candidate.get("k") is not None:
        parts.append(f"k-{candidate['k']}")
    if candidate.get("covariance_type"):
        parts.append(f"covariance-{candidate['covariance_type']}")
    if candidate.get("min_cluster_size") is not None:
        parts.append(f"mcs-{candidate['min_cluster_size']}")
    if candidate.get("min_samples") is not None:
        parts.append(f"ms-{candidate['min_samples']}")
    return "__".join(parts)


def compute_internal_metrics(features: np.ndarray, labels: np.ndarray, metrics_lib: dict[str, Any]) -> dict[str, Any]:
    labels = np.asarray(labels, dtype=int)
    total_rows = labels.shape[0]
    non_noise_mask = labels != -1
    non_noise_labels = labels[non_noise_mask]
    unique_non_noise = sorted(set(non_noise_labels.tolist()))
    distribution = build_cluster_distribution(labels)
    cluster_counts = [item["count"] for item in distribution if item["label"] != -1]
    noise_points = int(np.sum(labels == -1))

    metrics = {
        "num_clusters": len(unique_non_noise),
        "noise_points": noise_points,
        "noise_fraction": float(noise_points / total_rows) if total_rows else 0.0,
        "smallest_cluster_fraction": None,
        "largest_cluster_fraction": None,
        "tiny_cluster_flag": False,
        "silhouette_score": None,
        "calinski_harabasz_score": None,
        "davies_bouldin_score": None,
        "cluster_size_distribution": json.dumps(distribution, ensure_ascii=False),
    }

    if cluster_counts:
        metrics["smallest_cluster_fraction"] = float(min(cluster_counts) / total_rows)
        metrics["largest_cluster_fraction"] = float(max(cluster_counts) / total_rows)
        metrics["tiny_cluster_flag"] = metrics["smallest_cluster_fraction"] < 0.02

    if len(unique_non_noise) < 2 or np.sum(non_noise_mask) < 3:
        return metrics

    effective_features = features[non_noise_mask, :]
    effective_labels = labels[non_noise_mask]
    if len(set(effective_labels.tolist())) < 2:
        return metrics

    metrics["silhouette_score"] = float(metrics_lib["silhouette_score"](effective_features, effective_labels))
    metrics["calinski_harabasz_score"] = float(
        metrics_lib["calinski_harabasz_score"](effective_features, effective_labels)
    )
    metrics["davies_bouldin_score"] = float(
        metrics_lib["davies_bouldin_score"](effective_features, effective_labels)
    )
    return metrics


def compute_repeat_stability(
    features: np.ndarray,
    candidate: dict[str, Any],
    repeats: int,
    base_seed: int,
    fit_predict: Callable[..., tuple[np.ndarray, np.ndarray | None, dict[str, Any]]],
    adjusted_rand_score: Callable[[np.ndarray, np.ndarray], float],
) -> tuple[float | None, float | None]:
    if repeats <= 1:
        return None, None

    repeated_labels = []
    for repeat_index in range(repeats):
        seed = base_seed + repeat_index
        labels, _confidence, _extras = fit_predict(
            features,
            candidate,
            random_seed=seed,
            shuffle_seed=seed + 100_000,
        )
        repeated_labels.append(labels)

    ari_scores = []
    for left_index, right_index in combinations(range(len(repeated_labels)), 2):
        ari_scores.append(float(adjusted_rand_score(repeated_labels[left_index], repeated_labels[right_index])))

    return float(np.mean(ari_scores)), float(np.std(ari_scores))


def compute_bootstrap_stability(
    features: np.ndarray,
    reference_labels: np.ndarray,
    candidate: dict[str, Any],
    repeats: int,
    sample_fraction: float,
    base_seed: int,
    fit_predict: Callable[..., tuple[np.ndarray, np.ndarray | None, dict[str, Any]]],
    adjusted_rand_score: Callable[[np.ndarray, np.ndarray], float],
) -> tuple[float | None, float | None]:
    if repeats <= 0 or sample_fraction <= 0 or sample_fraction >= 1:
        return None, None

    n_rows = features.shape[0]
    sample_size = max(2, int(round(n_rows * sample_fraction)))
    rng = np.random.default_rng(base_seed + 200_000)

    bootstrap_scores = []
    for repeat_index in range(repeats):
        subset_indices = np.sort(rng.choice(n_rows, size=sample_size, replace=False))
        subset_features = features[subset_indices, :]
        subset_labels, _confidence, _extras = fit_predict(
            subset_features,
            candidate,
            random_seed=base_seed + repeat_index,
            shuffle_seed=base_seed + repeat_index + 300_000,
        )
        bootstrap_scores.append(float(adjusted_rand_score(reference_labels[subset_indices], subset_labels)))

    return float(np.mean(bootstrap_scores)), float(np.std(bootstrap_scores))


def build_assignments_rows(
    metadata_rows: list[dict[str, Any]],
    labels: np.ndarray,
    confidence: np.ndarray | None,
    candidate_id: str,
    feature_space: str,
    method: str,
    method_variant: str,
) -> list[dict[str, Any]]:
    rows = []
    for index, metadata in enumerate(metadata_rows):
        row = dict(metadata)
        row["candidate_id"] = candidate_id
        row["feature_space"] = feature_space
        row["method"] = method
        row["method_variant"] = method_variant
        row["cluster_label"] = int(labels[index])
        row["noise_flag"] = bool(labels[index] == -1)
        if confidence is not None and math.isfinite(float(confidence[index])):
            row["membership_strength"] = float(confidence[index])
        else:
            row["membership_strength"] = None
        rows.append(row)
    return rows


def write_assignments_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    write_csv(path, rows, fieldnames)


def summarize_benchmark_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    valid_results = [result for result in results if result.get("num_clusters", 0) >= 2]

    def rank_by(metric: str, reverse: bool) -> list[dict[str, Any]]:
        filtered = [result for result in valid_results if result.get(metric) is not None]
        return sorted(filtered, key=lambda item: item[metric], reverse=reverse)[:10]

    return {
        "top_by_silhouette": rank_by("silhouette_score", reverse=True),
        "top_by_calinski_harabasz": rank_by("calinski_harabasz_score", reverse=True),
        "top_by_davies_bouldin": rank_by("davies_bouldin_score", reverse=False),
        "top_by_repeat_stability": rank_by("repeat_mean_ari", reverse=True),
        "top_by_bootstrap_stability": rank_by("bootstrap_mean_ari", reverse=True),
    }


def trim_ranked_results(ranked_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    trimmed = []
    for result in ranked_results:
        trimmed.append(
            {
                "candidate_id": result["candidate_id"],
                "feature_space": result["feature_space"],
                "method": result["method"],
                "method_variant": result.get("method_variant") or "",
                "k": result.get("k"),
                "silhouette_score": result.get("silhouette_score"),
                "calinski_harabasz_score": result.get("calinski_harabasz_score"),
                "davies_bouldin_score": result.get("davies_bouldin_score"),
                "repeat_mean_ari": result.get("repeat_mean_ari"),
                "bootstrap_mean_ari": result.get("bootstrap_mean_ari"),
                "num_clusters": result.get("num_clusters"),
                "smallest_cluster_fraction": result.get("smallest_cluster_fraction"),
                "noise_fraction": result.get("noise_fraction"),
            }
        )
    return trimmed


def plot_metric_by_k(
    output_path: Path,
    results: list[dict[str, Any]],
    metric_name: str,
    title: str,
    label_builder: Callable[[dict[str, Any]], str],
) -> str | None:
    plt = import_pyplot()
    if plt is None:
        return None

    grouped: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for result in results:
        k_value = result.get("k")
        metric_value = result.get(metric_name)
        if k_value is None or metric_value is None:
            continue
        grouped[label_builder(result)].append((int(k_value), float(metric_value)))

    if not grouped:
        return None

    figure, axis = plt.subplots(figsize=(8, 5))
    for label, values in sorted(grouped.items()):
        ordered_values = sorted(values, key=lambda item: item[0])
        axis.plot(
            [value[0] for value in ordered_values],
            [value[1] for value in ordered_values],
            marker="o",
            linewidth=2,
            label=label,
        )

    axis.set_xlabel("k")
    axis.set_ylabel(metric_name.replace("_", " ").title())
    axis.set_title(title)
    axis.grid(alpha=0.25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(figure)
    return str(output_path)
