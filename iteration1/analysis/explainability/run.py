#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import (
    DEFAULT_PCA_SCORES_INPUT_CSV,
    DEFAULT_PHASE6_INPUT_CSV,
    ensure_directory,
    write_csv,
    write_json,
)
from postprocess_common import (
    align_projection_to_labels,
    align_rows_and_labels,
    find_candidate_result,
    join_image_paths,
    load_candidate_labels,
    load_dataset_rows,
    maybe_export_contact_sheets,
    maybe_import_scipy_stats,
    maybe_import_sklearn_inspection,
    plot_heatmap,
    plot_scatter_by_cluster,
    summarize_cluster_counts,
    top_n_labels,
)

DEFAULT_ANALYSIS_ROOT = "iteration1/output/analysis"
DEFAULT_OUTPUT_DIR = "iteration1/output/analysis/explainability"
DEFAULT_SELECTION_SUMMARY_JSON = "iteration1/output/analysis/selection/summary.json"
DEFAULT_PCA_PROJECTION_CSV = "iteration1/output/analysis/pca/pca_projection_2d.csv"


def resolve_candidate_id(
    candidate_id: str | None,
    selection_summary_json: Path,
) -> str:
    if candidate_id:
        return candidate_id
    if not selection_summary_json.exists():
        raise RuntimeError(
            "No --candidate-id was provided and the selection summary file does not exist: "
            f"{selection_summary_json}"
        )
    with selection_summary_json.open("r", encoding="utf-8") as handle:
        summary = json.load(handle)
    selected = summary.get("recommended_final_candidate_id")
    if not selected:
        raise RuntimeError(f"No recommended_final_candidate_id found in {selection_summary_json}")
    return str(selected)


def cluster_summary_rows(labels: np.ndarray) -> list[dict[str, Any]]:
    return summarize_cluster_counts(labels)


def build_profile_rows(
    feature_columns: list[str],
    feature_matrix: np.ndarray,
    labels: np.ndarray,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], np.ndarray]:
    cluster_labels = top_n_labels(labels)
    total_rows = int(labels.shape[0])
    global_mean = np.mean(feature_matrix, axis=0)
    global_std = np.std(feature_matrix, axis=0, ddof=0)
    global_std[global_std == 0] = 1.0

    mean_rows: list[dict[str, Any]] = []
    median_rows: list[dict[str, Any]] = []
    standardized_rows: list[dict[str, Any]] = []
    standardized_matrix = []

    for cluster_label in cluster_labels:
        mask = labels == cluster_label
        cluster_values = feature_matrix[mask, :]
        fraction = float(np.sum(mask) / total_rows)
        cluster_mean = np.mean(cluster_values, axis=0)
        cluster_median = np.median(cluster_values, axis=0)
        standardized = (cluster_median - global_mean) / global_std
        standardized_matrix.append(standardized)

        mean_row = {
            "cluster_label": cluster_label,
            "count": int(np.sum(mask)),
            "fraction": fraction,
        }
        median_row = dict(mean_row)
        standardized_row = dict(mean_row)
        for feature_index, feature_name in enumerate(feature_columns):
            mean_row[feature_name] = float(cluster_mean[feature_index])
            median_row[feature_name] = float(cluster_median[feature_index])
            standardized_row[feature_name] = float(standardized[feature_index])
        mean_rows.append(mean_row)
        median_rows.append(median_row)
        standardized_rows.append(standardized_row)

    return mean_rows, median_rows, standardized_rows, np.vstack(standardized_matrix)


def compute_feature_discrimination(
    feature_columns: list[str],
    feature_matrix: np.ndarray,
    labels: np.ndarray,
) -> list[dict[str, Any]]:
    stats = maybe_import_scipy_stats()
    cluster_labels = top_n_labels(labels)
    rows = []
    global_means = np.mean(feature_matrix, axis=0)

    for feature_index, feature_name in enumerate(feature_columns):
        grouped_values = [feature_matrix[labels == cluster_label, feature_index] for cluster_label in cluster_labels]
        group_sizes = [int(values.shape[0]) for values in grouped_values]
        cluster_means = [float(np.mean(values)) for values in grouped_values]
        cluster_medians = [float(np.median(values)) for values in grouped_values]

        total_values = np.concatenate(grouped_values)
        if stats is not None and not np.allclose(total_values, total_values[0]):
            kw_statistic, kw_p_value = stats.kruskal(*grouped_values)
            kw_statistic = float(kw_statistic)
            kw_p_value = float(kw_p_value)
        else:
            kw_statistic = None
            kw_p_value = None

        ss_total = float(np.sum((total_values - np.mean(total_values)) ** 2))
        ss_between = float(
            sum(
                group_size * (cluster_mean - global_means[feature_index]) ** 2
                for group_size, cluster_mean in zip(group_sizes, cluster_means)
            )
        )
        eta_squared = ss_between / ss_total if ss_total > 0 else 0.0

        rows.append(
            {
                "feature": feature_name,
                "eta_squared": eta_squared,
                "kruskal_wallis_statistic": kw_statistic,
                "kruskal_wallis_p_value": kw_p_value,
                "cluster_mean_range": float(max(cluster_means) - min(cluster_means)),
                "cluster_median_range": float(max(cluster_medians) - min(cluster_medians)),
            }
        )

    if stats is not None:
        from postprocess_common import benjamini_hochberg

        adjusted = benjamini_hochberg([row["kruskal_wallis_p_value"] for row in rows])
        for row, adjusted_p in zip(rows, adjusted):
            row["kruskal_wallis_p_value_bh"] = adjusted_p
    else:
        for row in rows:
            row["kruskal_wallis_p_value_bh"] = None

    rows.sort(key=lambda item: (item["eta_squared"], item["kruskal_wallis_statistic"] or 0.0), reverse=True)
    return rows


def summarize_signature_terms(
    standardized_lookup: dict[str, float],
    positive_terms: list[tuple[str, str, float]],
    negative_terms: list[tuple[str, str, float]],
) -> list[str]:
    phrases = []
    for feature_name, phrase, threshold in positive_terms:
        if standardized_lookup.get(feature_name, 0.0) >= threshold:
            phrases.append(phrase)
    for feature_name, phrase, threshold in negative_terms:
        if standardized_lookup.get(feature_name, 0.0) <= -threshold:
            phrases.append(phrase)
    return phrases


def build_cluster_descriptions(
    standardized_profile_rows: list[dict[str, Any]],
    feature_columns: list[str],
) -> list[dict[str, Any]]:
    rows = []
    for row in standardized_profile_rows:
        cluster_label = int(row["cluster_label"])
        standardized_lookup = {feature_name: float(row[feature_name]) for feature_name in feature_columns}
        ordered_positive = sorted(
            [(feature_name, standardized_lookup[feature_name]) for feature_name in feature_columns],
            key=lambda item: item[1],
            reverse=True,
        )
        ordered_negative = sorted(
            [(feature_name, standardized_lookup[feature_name]) for feature_name in feature_columns],
            key=lambda item: item[1],
        )

        morphology_phrases = summarize_signature_terms(
            standardized_lookup,
            positive_terms=[
                ("area_median", "larger particle bodies", 0.8),
                ("feret_p90", "long upper-tail particle extent", 0.8),
                ("aspect_ratio_median", "elongated particle shapes", 0.8),
                ("aspect_ratio_p90", "very elongated tail cases", 0.8),
                ("circularity_median", "round compact particles", 0.8),
                ("circularity_iqr", "heterogeneous circularity", 0.6),
                ("solidity_iqr", "heterogeneous solidity", 0.6),
                ("orientation_entropy", "high orientation dispersion", 0.8),
                ("circular_variance", "broad directional spread", 0.8),
                ("mean_pixel_intensity", "brighter overall deposits", 0.8),
                ("mean_intensity_iqr", "heterogeneous particle intensity", 0.6),
                ("num_particles", "higher particle counts", 0.8),
            ],
            negative_terms=[
                ("area_median", "smaller particle bodies", 0.8),
                ("feret_p90", "shorter upper-tail particle extent", 0.8),
                ("aspect_ratio_median", "more compact non-elongated shapes", 0.8),
                ("circularity_median", "less circular particles", 0.8),
                ("orientation_entropy", "more aligned orientations", 0.8),
                ("mean_pixel_intensity", "darker overall deposits", 0.8),
                ("num_particles", "lower particle counts", 0.8),
            ],
        )
        if not morphology_phrases:
            morphology_phrases = ["mixed morphology without one dominant extreme"]

        top_positive_signature = "; ".join(
            f"{feature_name} (z={value:+.2f})" for feature_name, value in ordered_positive[:4]
        )
        top_negative_signature = "; ".join(
            f"{feature_name} (z={value:+.2f})" for feature_name, value in ordered_negative[:4]
        )
        morphology_summary = ", ".join(dict.fromkeys(morphology_phrases))

        rows.append(
            {
                "cluster_label": cluster_label,
                "count": int(row["count"]),
                "fraction": float(row["fraction"]),
                "morphology_summary": morphology_summary,
                "top_positive_signature": top_positive_signature,
                "top_negative_signature": top_negative_signature,
            }
        )
    return rows


def compute_pairwise_feature_differences(
    standardized_profile_rows: list[dict[str, Any]],
    feature_columns: list[str],
    top_n: int,
) -> list[dict[str, Any]]:
    lookup = {int(row["cluster_label"]): row for row in standardized_profile_rows}
    rows = []
    for left_label, right_label in combinations(sorted(lookup), 2):
        left_row = lookup[left_label]
        right_row = lookup[right_label]
        differences = []
        for feature_name in feature_columns:
            delta = float(left_row[feature_name]) - float(right_row[feature_name])
            differences.append((feature_name, delta))
        differences.sort(key=lambda item: abs(item[1]), reverse=True)
        for rank_index, (feature_name, delta) in enumerate(differences[:top_n], start=1):
            higher_cluster = left_label if delta > 0 else right_label
            rows.append(
                {
                    "cluster_a": left_label,
                    "cluster_b": right_label,
                    "rank": rank_index,
                    "feature": feature_name,
                    "standardized_median_delta": delta,
                    "higher_cluster": higher_cluster,
                }
            )
    return rows


def compute_pca_cluster_positions(points: np.ndarray, labels: np.ndarray) -> list[dict[str, Any]]:
    rows = []
    for cluster_label in top_n_labels(labels):
        mask = labels == cluster_label
        cluster_points = points[mask, :]
        centroid = np.mean(cluster_points, axis=0)
        distances = np.linalg.norm(cluster_points - centroid, axis=1)
        rows.append(
            {
                "cluster_label": cluster_label,
                "count": int(np.sum(mask)),
                "pc1_mean": float(np.mean(cluster_points[:, 0])),
                "pc2_mean": float(np.mean(cluster_points[:, 1])),
                "pc1_std": float(np.std(cluster_points[:, 0], ddof=0)),
                "pc2_std": float(np.std(cluster_points[:, 1], ddof=0)),
                "mean_distance_to_pca_centroid": float(np.mean(distances)),
                "p90_distance_to_pca_centroid": float(np.percentile(distances, 90)),
            }
        )
    return rows


def compute_silhouette_outputs(
    aligned_rows: list[dict[str, str]],
    features: np.ndarray,
    labels: np.ndarray,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], np.ndarray | None]:
    try:
        from sklearn.metrics import silhouette_samples
    except ImportError:
        return [], [], None

    non_noise_mask = labels != -1
    effective_labels = labels[non_noise_mask]
    if len(set(effective_labels.tolist())) < 2:
        return [], [], None

    effective_features = features[non_noise_mask, :]
    silhouette_values = silhouette_samples(effective_features, effective_labels)
    silhouette_rows = []
    summary_rows = []
    effective_rows = [row for row, keep in zip(aligned_rows, non_noise_mask.tolist()) if keep]
    for metadata_row, cluster_label, silhouette_value in zip(effective_rows, effective_labels.tolist(), silhouette_values.tolist()):
        silhouette_rows.append(
            {
                "image_id": metadata_row["image_id"],
                "cluster_label": int(cluster_label),
                "silhouette_value": float(silhouette_value),
            }
        )

    for cluster_label in top_n_labels(effective_labels):
        cluster_values = silhouette_values[effective_labels == cluster_label]
        summary_rows.append(
            {
                "cluster_label": cluster_label,
                "count": int(cluster_values.shape[0]),
                "mean_silhouette": float(np.mean(cluster_values)),
                "median_silhouette": float(np.median(cluster_values)),
                "std_silhouette": float(np.std(cluster_values, ddof=0)),
                "min_silhouette": float(np.min(cluster_values)),
                "p10_silhouette": float(np.percentile(cluster_values, 10)),
                "p90_silhouette": float(np.percentile(cluster_values, 90)),
            }
        )

    return silhouette_rows, summary_rows, silhouette_values


def build_borderline_examples(
    aligned_rows: list[dict[str, str]],
    labels: np.ndarray,
    silhouette_rows: list[dict[str, Any]],
    top_n: int,
) -> list[dict[str, Any]]:
    silhouette_lookup = {row["image_id"]: row for row in silhouette_rows}
    grouped_rows: dict[int, list[dict[str, Any]]] = {}
    for metadata_row in aligned_rows:
        image_id = metadata_row["image_id"]
        if image_id not in silhouette_lookup:
            continue
        cluster_label = int(silhouette_lookup[image_id]["cluster_label"])
        grouped_rows.setdefault(cluster_label, []).append(
            {
                "cluster_label": cluster_label,
                "image_id": image_id,
                "sensor_id": metadata_row.get("sensor_id", ""),
                "capture_datetime": metadata_row.get("capture_datetime", ""),
                "collection_datetime": metadata_row.get("collection_datetime", ""),
                "official_station_id": metadata_row.get("official_station_id", ""),
                "official_station_name": metadata_row.get("official_station_name", ""),
                "silhouette_value": float(silhouette_lookup[image_id]["silhouette_value"]),
            }
        )

    rows = []
    for cluster_label, cluster_rows in sorted(grouped_rows.items()):
        ordered = sorted(cluster_rows, key=lambda item: item["silhouette_value"])
        for rank_index, row in enumerate(ordered[:top_n], start=1):
            row["rank_within_cluster"] = rank_index
            rows.append(row)
    return rows


def plot_silhouette_profile(
    output_path: Path,
    labels: np.ndarray,
    silhouette_values: np.ndarray | None,
) -> str | None:
    if silhouette_values is None:
        return None
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    cluster_labels = top_n_labels(labels[labels != -1])
    figure, axis = plt.subplots(figsize=(8, max(4, len(cluster_labels) * 1.1)))
    y_lower = 10
    for cluster_label in cluster_labels:
        cluster_silhouettes = np.sort(silhouette_values[labels[labels != -1] == cluster_label])
        size = cluster_silhouettes.shape[0]
        y_upper = y_lower + size
        axis.fill_betweenx(
            np.arange(y_lower, y_upper),
            0,
            cluster_silhouettes,
            alpha=0.75,
            label=f"cluster {cluster_label}",
        )
        axis.text(-0.05, y_lower + 0.5 * size, str(cluster_label))
        y_lower = y_upper + 10
    axis.axvline(float(np.mean(silhouette_values)), color="#d62828", linestyle="--", linewidth=1.5)
    axis.set_xlabel("Silhouette value")
    axis.set_ylabel("Cluster")
    axis.set_title("Silhouette profile by cluster")
    axis.set_yticks([])
    figure.tight_layout()
    figure.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(figure)
    return str(output_path)


def compute_alternative_agreement(
    selection_summary_json: Path,
    selected_candidate_id: str,
    labels_by_image_id: dict[str, int],
    analysis_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    if not selection_summary_json.exists():
        return [], None
    try:
        from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score
    except ImportError:
        return [], None

    with selection_summary_json.open("r", encoding="utf-8") as handle:
        selection_summary = json.load(handle)

    shortlist = selection_summary.get("top_shortlist") or []
    alternative = next((row for row in shortlist if row.get("candidate_id") != selected_candidate_id), None)
    if not alternative:
        return [], None

    alternative_candidate_id = str(alternative["candidate_id"])
    _rows, alternative_lookup = load_candidate_labels(
        Path(find_candidate_result(analysis_root, alternative_candidate_id)["assignments_csv"]).resolve()
    )
    overlapping_ids = sorted(set(labels_by_image_id) & set(alternative_lookup))
    if not overlapping_ids:
        return [], None

    reference_labels = [labels_by_image_id[image_id] for image_id in overlapping_ids]
    comparison_labels = [alternative_lookup[image_id] for image_id in overlapping_ids]
    agreement_rows = []
    selected_cluster_labels = sorted({labels_by_image_id[image_id] for image_id in overlapping_ids})
    alternative_cluster_labels = sorted({alternative_lookup[image_id] for image_id in overlapping_ids})
    for selected_label in selected_cluster_labels:
        selected_total = sum(1 for image_id in overlapping_ids if labels_by_image_id[image_id] == selected_label)
        for alternative_label in alternative_cluster_labels:
            overlap_count = sum(
                1
                for image_id in overlapping_ids
                if labels_by_image_id[image_id] == selected_label and alternative_lookup[image_id] == alternative_label
            )
            agreement_rows.append(
                {
                    "selected_cluster_label": selected_label,
                    "alternative_cluster_label": alternative_label,
                    "overlap_count": overlap_count,
                    "fraction_within_selected_cluster": overlap_count / selected_total if selected_total else None,
                }
            )
    summary = {
        "alternative_candidate_id": alternative_candidate_id,
        "adjusted_rand_index": float(adjusted_rand_score(reference_labels, comparison_labels)),
        "normalized_mutual_information": float(normalized_mutual_info_score(reference_labels, comparison_labels)),
        "overlap_count": len(overlapping_ids),
    }
    return agreement_rows, summary


def plot_feature_boxplots(
    output_path: Path,
    feature_columns: list[str],
    feature_matrix: np.ndarray,
    labels: np.ndarray,
    top_features: list[str],
) -> str | None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    if not top_features:
        return None

    def draw_boxplot(axis: Any, grouped_values: list[np.ndarray], label_values: list[str]) -> None:
        try:
            axis.boxplot(grouped_values, tick_labels=label_values)
        except TypeError:
            axis.boxplot(grouped_values, labels=label_values)

    feature_index_by_name = {feature_name: index for index, feature_name in enumerate(feature_columns)}
    cluster_labels = top_n_labels(labels)
    columns = min(2, len(top_features))
    rows = int(math.ceil(len(top_features) / columns))
    figure, axes = plt.subplots(rows, columns, figsize=(10, max(4, rows * 3.2)))
    axes_array = np.atleast_1d(axes).reshape(rows, columns)

    for axis in axes_array.flat:
        axis.set_visible(False)

    for plot_index, feature_name in enumerate(top_features):
        axis = axes_array.flat[plot_index]
        axis.set_visible(True)
        feature_index = feature_index_by_name[feature_name]
        grouped = [feature_matrix[labels == cluster_label, feature_index] for cluster_label in cluster_labels]
        draw_boxplot(axis, grouped, [str(label) for label in cluster_labels])
        axis.set_title(feature_name)
        axis.set_xlabel("Cluster")
        axis.set_ylabel("Feature value")

    figure.suptitle("Top discriminative feature boxplots", y=1.02)
    figure.tight_layout()
    figure.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(figure)
    return str(output_path)


def build_representative_rows(
    aligned_rows: list[dict[str, str]],
    feature_matrix: np.ndarray,
    labels: np.ndarray,
    cluster_labels: list[int],
    assignment_rows: list[dict[str, str]],
    top_n: int,
) -> list[dict[str, Any]]:
    assignment_lookup = {row["image_id"]: row for row in assignment_rows}
    representatives: list[dict[str, Any]] = []

    for cluster_label in cluster_labels:
        mask = labels == cluster_label
        cluster_matrix = feature_matrix[mask, :]
        cluster_rows = [row for row, row_mask in zip(aligned_rows, mask.tolist()) if row_mask]
        centroid = np.mean(cluster_matrix, axis=0)
        distances = np.linalg.norm(cluster_matrix - centroid, axis=1)
        order = np.argsort(distances)[:top_n]

        for rank_index, local_index in enumerate(order, start=1):
            base_row = cluster_rows[int(local_index)]
            assignment = assignment_lookup[base_row["image_id"]]
            representatives.append(
                {
                    "cluster_label": cluster_label,
                    "rank_in_cluster": rank_index,
                    "image_id": base_row["image_id"],
                    "sensor_id": base_row.get("sensor_id", ""),
                    "capture_datetime": base_row.get("capture_datetime", ""),
                    "collection_datetime": base_row.get("collection_datetime", ""),
                    "distance_to_cluster_centroid": float(distances[int(local_index)]),
                    "membership_strength": assignment.get("membership_strength", ""),
                    "official_station_id": base_row.get("official_station_id", ""),
                    "official_station_name": base_row.get("official_station_name", ""),
                    "record_pm10": base_row.get("record_pm10", ""),
                    "record_pm25": base_row.get("record_pm25", ""),
                    "official_pm10": base_row.get("official_pm10", ""),
                    "official_pm25": base_row.get("official_pm25", ""),
                }
            )
    return representatives


def run_surrogate_models(
    feature_columns: list[str],
    feature_matrix: np.ndarray,
    labels: np.ndarray,
    random_seed: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    sklearn_lib = maybe_import_sklearn_inspection()
    if sklearn_lib is None:
        return [], {"status": "skipped", "reason": "scikit-learn is not available"}

    cluster_mask = labels != -1
    clean_features = feature_matrix[cluster_mask, :]
    clean_labels = labels[cluster_mask]
    if len(set(clean_labels.tolist())) < 2:
        return [], {"status": "skipped", "reason": "fewer than two non-noise clusters are available"}

    rf_cls = sklearn_lib["RandomForestClassifier"]
    logreg_cls = sklearn_lib["LogisticRegression"]
    cv_cls = sklearn_lib["StratifiedKFold"]
    cross_val_score = sklearn_lib["cross_val_score"]

    cv = cv_cls(n_splits=5, shuffle=True, random_state=random_seed)

    rf_model = rf_cls(
        n_estimators=400,
        random_state=random_seed,
        class_weight="balanced",
    )
    rf_scores = cross_val_score(rf_model, clean_features, clean_labels, cv=cv, scoring="balanced_accuracy")
    rf_model.fit(clean_features, clean_labels)

    logreg_model = logreg_cls(
        max_iter=3000,
        class_weight="balanced",
        random_state=random_seed,
    )
    logreg_scores = cross_val_score(logreg_model, clean_features, clean_labels, cv=cv, scoring="balanced_accuracy")
    logreg_model.fit(clean_features, clean_labels)

    abs_coefficients = np.mean(np.abs(logreg_model.coef_), axis=0)
    rows = []
    for feature_index, feature_name in enumerate(feature_columns):
        rows.append(
            {
                "feature": feature_name,
                "random_forest_importance": float(rf_model.feature_importances_[feature_index]),
                "logistic_abs_mean_coefficient": float(abs_coefficients[feature_index]),
            }
        )

    rows.sort(
        key=lambda item: (
            item["random_forest_importance"],
            item["logistic_abs_mean_coefficient"],
        ),
        reverse=True,
    )
    summary = {
        "status": "completed",
        "random_forest_balanced_accuracy_mean": float(np.mean(rf_scores)),
        "random_forest_balanced_accuracy_std": float(np.std(rf_scores)),
        "logistic_balanced_accuracy_mean": float(np.mean(logreg_scores)),
        "logistic_balanced_accuracy_std": float(np.std(logreg_scores)),
    }
    return rows, summary


def plot_surrogate_importance(output_path: Path, importance_rows: list[dict[str, Any]], top_n: int) -> str | None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    if not importance_rows:
        return None

    top_rows = importance_rows[:top_n]
    features = [row["feature"] for row in reversed(top_rows)]
    rf_values = [row["random_forest_importance"] for row in reversed(top_rows)]
    logreg_values = [row["logistic_abs_mean_coefficient"] for row in reversed(top_rows)]

    figure, axes = plt.subplots(1, 2, figsize=(12, max(4, len(features) * 0.35)))
    axes[0].barh(features, rf_values, color="#52796f")
    axes[0].set_title("Random forest importance")
    axes[0].set_xlabel("Importance")
    axes[1].barh(features, logreg_values, color="#1d3557")
    axes[1].set_title("Logistic mean |coef|")
    axes[1].set_xlabel("Magnitude")
    figure.tight_layout()
    figure.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(figure)
    return str(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Phase 10 explainability outputs for a selected clustering solution.")
    parser.add_argument("--analysis-root", default=DEFAULT_ANALYSIS_ROOT, help="Directory containing the per-method analysis folders")
    parser.add_argument("--feature-csv", default=DEFAULT_PHASE6_INPUT_CSV, help="Path to image_features_final.csv")
    parser.add_argument("--pca-scores-csv", default=DEFAULT_PCA_SCORES_INPUT_CSV, help="Path to pca_scores_retained.csv")
    parser.add_argument("--pca-projection-csv", default=DEFAULT_PCA_PROJECTION_CSV, help="Path to pca_projection_2d.csv")
    parser.add_argument("--selection-summary-json", default=DEFAULT_SELECTION_SUMMARY_JSON, help="Selection summary JSON used when --candidate-id is omitted")
    parser.add_argument("--candidate-id", default="", help="Explicit candidate id to explain")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directory where explainability outputs will be written")
    parser.add_argument("--representatives-per-cluster", type=int, default=5, help="Number of nearest-to-centroid examples to keep per cluster")
    parser.add_argument("--top-features", type=int, default=10, help="Number of discriminative features to plot and summarize")
    parser.add_argument("--top-pairwise-features", type=int, default=8, help="Number of pairwise separating features to keep per cluster pair")
    parser.add_argument("--random-seed", type=int, default=7, help="Random seed for surrogate models")
    parser.add_argument(
        "--image-paths-csv",
        default="",
        help="Optional CSV with at least image_id and image_path columns for representative-image exports",
    )
    args = parser.parse_args()

    analysis_root = Path(args.analysis_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    ensure_directory(output_dir)

    selected_candidate_id = resolve_candidate_id(
        candidate_id=args.candidate_id.strip() or None,
        selection_summary_json=Path(args.selection_summary_json).resolve(),
    )
    candidate_result = find_candidate_result(analysis_root, selected_candidate_id)

    assignments_csv = Path(candidate_result["assignments_csv"]).resolve()
    assignment_rows, labels_by_image_id = load_candidate_labels(assignments_csv)

    feature_csv = Path(args.feature_csv).resolve()
    dataset_rows, _dataset_headers, feature_columns = load_dataset_rows(feature_csv)
    aligned_feature_rows, feature_matrix, labels = align_rows_and_labels(dataset_rows, feature_columns, labels_by_image_id)
    cluster_rows = cluster_summary_rows(labels)
    cluster_labels = top_n_labels(labels)

    mean_profile_rows, median_profile_rows, standardized_profile_rows, standardized_matrix = build_profile_rows(
        feature_columns=feature_columns,
        feature_matrix=feature_matrix,
        labels=labels,
    )
    discrimination_rows = compute_feature_discrimination(feature_columns, feature_matrix, labels)
    top_feature_names = [row["feature"] for row in discrimination_rows[: args.top_features]]
    cluster_description_rows = build_cluster_descriptions(standardized_profile_rows, feature_columns)
    pairwise_difference_rows = compute_pairwise_feature_differences(
        standardized_profile_rows,
        feature_columns,
        top_n=args.top_pairwise_features,
    )

    candidate_feature_csv = (
        Path(args.pca_scores_csv).resolve()
        if candidate_result["feature_space"] == "pca_scores"
        else feature_csv
    )
    candidate_rows, _candidate_headers, candidate_feature_columns = load_dataset_rows(candidate_feature_csv)
    aligned_candidate_rows, candidate_feature_matrix, candidate_labels = align_rows_and_labels(
        candidate_rows,
        candidate_feature_columns,
        labels_by_image_id,
    )
    representative_rows = build_representative_rows(
        aligned_rows=aligned_candidate_rows,
        feature_matrix=candidate_feature_matrix,
        labels=candidate_labels,
        cluster_labels=cluster_labels,
        assignment_rows=assignment_rows,
        top_n=args.representatives_per_cluster,
    )
    image_paths_csv = Path(args.image_paths_csv).resolve() if args.image_paths_csv else None
    representative_rows_with_paths = join_image_paths(representative_rows, image_paths_csv)
    silhouette_rows, silhouette_summary_rows, silhouette_values = compute_silhouette_outputs(
        aligned_candidate_rows,
        candidate_feature_matrix,
        candidate_labels,
    )
    borderline_rows = build_borderline_examples(
        aligned_rows=aligned_candidate_rows,
        labels=candidate_labels,
        silhouette_rows=silhouette_rows,
        top_n=args.representatives_per_cluster,
    )
    borderline_rows_with_paths = join_image_paths(borderline_rows, image_paths_csv)

    plot_files = {}
    heatmap_path = plot_heatmap(
        output_dir / "cluster_profile_heatmap.png",
        standardized_matrix,
        row_labels=[f"cluster {label}" for label in cluster_labels],
        column_labels=feature_columns,
        title="Cluster profile heatmap",
    )
    if heatmap_path:
        plot_files["cluster_profile_heatmap"] = heatmap_path

    pca_points, pca_labels, _pca_image_ids = align_projection_to_labels(Path(args.pca_projection_csv).resolve(), labels_by_image_id)
    cluster_pca_position_rows = compute_pca_cluster_positions(pca_points, pca_labels)
    pca_plot = plot_scatter_by_cluster(
        output_path=output_dir / "pca_colored_by_cluster.png",
        points=pca_points,
        labels=pca_labels,
        title=f"PCA projection colored by {selected_candidate_id}",
        xlabel="PC1",
        ylabel="PC2",
    )
    if pca_plot:
        plot_files["pca_colored_by_cluster"] = pca_plot

    boxplot_path = plot_feature_boxplots(
        output_path=output_dir / "top_feature_boxplots.png",
        feature_columns=feature_columns,
        feature_matrix=feature_matrix,
        labels=labels,
        top_features=top_feature_names,
    )
    if boxplot_path:
        plot_files["top_feature_boxplots"] = boxplot_path

    silhouette_plot = plot_silhouette_profile(
        output_path=output_dir / "silhouette_profile.png",
        labels=candidate_labels,
        silhouette_values=silhouette_values,
    )
    if silhouette_plot:
        plot_files["silhouette_profile"] = silhouette_plot

    surrogate_rows, surrogate_summary = run_surrogate_models(
        feature_columns=feature_columns,
        feature_matrix=feature_matrix,
        labels=labels,
        random_seed=args.random_seed,
    )
    if surrogate_rows:
        write_csv(
            output_dir / "surrogate_feature_importance.csv",
            surrogate_rows,
            list(surrogate_rows[0].keys()),
        )
        surrogate_plot = plot_surrogate_importance(
            output_path=output_dir / "surrogate_feature_importance.png",
            importance_rows=surrogate_rows,
            top_n=min(args.top_features, len(surrogate_rows)),
        )
        if surrogate_plot:
            plot_files["surrogate_feature_importance"] = surrogate_plot

    contact_sheet_paths = maybe_export_contact_sheets(
        representative_rows_with_paths,
        output_dir=output_dir,
        title_prefix="representative_examples",
    )
    if contact_sheet_paths:
        plot_files["representative_contact_sheets"] = contact_sheet_paths
    borderline_contact_sheet_paths = maybe_export_contact_sheets(
        borderline_rows_with_paths,
        output_dir=output_dir,
        title_prefix="borderline_examples",
    )
    if borderline_contact_sheet_paths:
        plot_files["borderline_contact_sheets"] = borderline_contact_sheet_paths

    agreement_rows, agreement_summary = compute_alternative_agreement(
        selection_summary_json=Path(args.selection_summary_json).resolve(),
        selected_candidate_id=selected_candidate_id,
        labels_by_image_id=labels_by_image_id,
        analysis_root=analysis_root,
    )

    write_csv(output_dir / "cluster_counts.csv", cluster_rows, list(cluster_rows[0].keys()))
    write_csv(output_dir / "cluster_profile_mean.csv", mean_profile_rows, list(mean_profile_rows[0].keys()))
    write_csv(output_dir / "cluster_profile_median.csv", median_profile_rows, list(median_profile_rows[0].keys()))
    write_csv(
        output_dir / "cluster_profile_standardized.csv",
        standardized_profile_rows,
        list(standardized_profile_rows[0].keys()),
    )
    write_csv(
        output_dir / "feature_discrimination.csv",
        discrimination_rows,
        list(discrimination_rows[0].keys()),
    )
    write_csv(
        output_dir / "cluster_descriptions.csv",
        cluster_description_rows,
        list(cluster_description_rows[0].keys()),
    )
    write_csv(
        output_dir / "pairwise_feature_differences.csv",
        pairwise_difference_rows,
        list(pairwise_difference_rows[0].keys()),
    )
    write_csv(
        output_dir / "representative_examples.csv",
        representative_rows_with_paths,
        list(representative_rows_with_paths[0].keys()),
    )
    write_csv(
        output_dir / "cluster_pca_positions.csv",
        cluster_pca_position_rows,
        list(cluster_pca_position_rows[0].keys()),
    )
    if silhouette_rows:
        write_csv(output_dir / "silhouette_samples.csv", silhouette_rows, list(silhouette_rows[0].keys()))
    if silhouette_summary_rows:
        write_csv(output_dir / "cluster_silhouette_summary.csv", silhouette_summary_rows, list(silhouette_summary_rows[0].keys()))
    if borderline_rows:
        write_csv(output_dir / "borderline_examples.csv", borderline_rows_with_paths, list(borderline_rows_with_paths[0].keys()))
    if agreement_rows:
        write_csv(output_dir / "alternative_candidate_agreement.csv", agreement_rows, list(agreement_rows[0].keys()))

    summary = {
        "analysis_root": str(analysis_root),
        "output_dir": str(output_dir),
        "candidate_id": selected_candidate_id,
        "candidate_result": {
            "method": candidate_result["method"],
            "feature_space": candidate_result["feature_space"],
            "k": candidate_result.get("k"),
            "silhouette_score": candidate_result.get("silhouette_score"),
            "bootstrap_mean_ari": candidate_result.get("bootstrap_mean_ari"),
            "repeat_mean_ari": candidate_result.get("repeat_mean_ari"),
        },
        "assignments_csv": str(assignments_csv),
        "feature_csv": str(feature_csv),
        "candidate_feature_csv": str(candidate_feature_csv),
        "rows_used": int(labels.shape[0]),
        "cluster_count": len(cluster_labels),
        "cluster_labels": cluster_labels,
        "top_discriminative_features": top_feature_names,
        "cluster_descriptions": cluster_description_rows,
        "alternative_candidate_agreement": agreement_summary,
        "surrogate_summary": surrogate_summary,
        "plot_files": plot_files,
        "notes": [
            "Cluster profiles are computed from the saved Phase 6 feature matrix, not from the discarded raw feature pool.",
            "Representative examples default to image IDs and metadata. Real image exports require an optional image-path manifest.",
        ],
    }
    write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
