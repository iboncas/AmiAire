#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import DEFAULT_PHASE6_INPUT_CSV, ensure_directory, write_csv, write_json
from postprocess_common import (
    benjamini_hochberg,
    capture_date_parts,
    find_candidate_result,
    load_candidate_labels,
    load_dataset_rows,
    maybe_import_scipy_stats,
    maybe_import_sklearn_inspection,
    parse_float,
    plot_heatmap,
)

DEFAULT_ANALYSIS_ROOT = "iteration1/output/analysis"
DEFAULT_OUTPUT_DIR = "iteration1/output/analysis/context"
DEFAULT_SELECTION_SUMMARY_JSON = "iteration1/output/analysis/selection/summary.json"
PREFERRED_NUMERIC_CONTEXT_COLUMNS = [
    "latitude",
    "longitude",
    "official_station_distance_km",
    "record_pm10",
    "record_pm25",
    "official_pm10",
    "official_pm25",
    "record_pm25_to_pm10_ratio",
    "official_pm25_to_pm10_ratio",
    "official_pm10_minus_record_pm10",
    "official_pm25_minus_record_pm25",
    "abs_pm10_gap",
    "abs_pm25_gap",
    "official_pm_total",
    "record_pm_total",
    "capture_year",
    "capture_month",
    "capture_dayofyear",
    "capture_weekday",
]
PREFERRED_CATEGORICAL_CONTEXT_COLUMNS = [
    "official_station_id",
    "capture_season",
    "station_distance_band",
    "official_pm25_band",
    "official_pm10_band",
]


def resolve_candidate_id(candidate_id: str | None, selection_summary_json: Path) -> str:
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


def safe_ratio(numerator: str | None, denominator: str | None) -> float | None:
    numerator_value = parse_float(numerator)
    denominator_value = parse_float(denominator)
    if numerator_value is None or denominator_value in (None, 0.0):
        return None
    return numerator_value / denominator_value


def build_context_rows(
    dataset_rows: list[dict[str, str]],
    labels_by_image_id: dict[str, int],
    exclude_noise: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in dataset_rows:
        image_id = row.get("image_id")
        if image_id not in labels_by_image_id:
            continue
        cluster_label = labels_by_image_id[image_id]
        if exclude_noise and cluster_label == -1:
            continue

        derived = capture_date_parts(row.get("capture_datetime"))
        enriched = dict(row)
        enriched["cluster_label"] = cluster_label
        enriched["record_pm25_to_pm10_ratio"] = safe_ratio(row.get("record_pm25"), row.get("record_pm10"))
        enriched["official_pm25_to_pm10_ratio"] = safe_ratio(row.get("official_pm25"), row.get("official_pm10"))
        enriched.update(derived)

        official_pm10 = parse_float(row.get("official_pm10"))
        official_pm25 = parse_float(row.get("official_pm25"))
        record_pm10 = parse_float(row.get("record_pm10"))
        record_pm25 = parse_float(row.get("record_pm25"))
        station_distance = parse_float(row.get("official_station_distance_km"))

        enriched["official_pm10_minus_record_pm10"] = (
            official_pm10 - record_pm10 if official_pm10 is not None and record_pm10 is not None else None
        )
        enriched["official_pm25_minus_record_pm25"] = (
            official_pm25 - record_pm25 if official_pm25 is not None and record_pm25 is not None else None
        )
        enriched["abs_pm10_gap"] = abs(enriched["official_pm10_minus_record_pm10"]) if enriched["official_pm10_minus_record_pm10"] is not None else None
        enriched["abs_pm25_gap"] = abs(enriched["official_pm25_minus_record_pm25"]) if enriched["official_pm25_minus_record_pm25"] is not None else None
        enriched["official_pm_total"] = (
            official_pm10 + official_pm25 if official_pm10 is not None and official_pm25 is not None else None
        )
        enriched["record_pm_total"] = (
            record_pm10 + record_pm25 if record_pm10 is not None and record_pm25 is not None else None
        )

        capture_month = derived.get("capture_month")
        capture_date = row.get("capture_datetime")
        if capture_date:
            try:
                from datetime import datetime

                parsed_capture = datetime.fromisoformat(capture_date)
                enriched["capture_dayofyear"] = parsed_capture.timetuple().tm_yday
                enriched["capture_weekday"] = parsed_capture.weekday()
            except ValueError:
                enriched["capture_dayofyear"] = None
                enriched["capture_weekday"] = None
        else:
            enriched["capture_dayofyear"] = None
            enriched["capture_weekday"] = None

        if station_distance is None:
            enriched["station_distance_band"] = "missing"
        elif station_distance < 1.0:
            enriched["station_distance_band"] = "under_1km"
        elif station_distance < 3.0:
            enriched["station_distance_band"] = "1_to_3km"
        elif station_distance < 10.0:
            enriched["station_distance_band"] = "3_to_10km"
        else:
            enriched["station_distance_band"] = "over_10km"

        if official_pm25 is None:
            enriched["official_pm25_band"] = "missing"
        elif official_pm25 <= 10.0:
            enriched["official_pm25_band"] = "low"
        elif official_pm25 <= 25.0:
            enriched["official_pm25_band"] = "moderate"
        else:
            enriched["official_pm25_band"] = "high"

        if official_pm10 is None:
            enriched["official_pm10_band"] = "missing"
        elif official_pm10 <= 20.0:
            enriched["official_pm10_band"] = "low"
        elif official_pm10 <= 50.0:
            enriched["official_pm10_band"] = "moderate"
        else:
            enriched["official_pm10_band"] = "high"
        rows.append(enriched)

    if not rows:
        raise RuntimeError("No overlapping context rows were found for the selected candidate")
    return rows


def detect_context_columns(context_rows: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    numeric_columns = []
    categorical_columns = []

    for column in PREFERRED_NUMERIC_CONTEXT_COLUMNS:
        values = [row.get(column) for row in context_rows]
        parsed_values = []
        for value in values:
            if isinstance(value, (int, float)):
                parsed_values.append(float(value))
            else:
                parsed = parse_float(value if isinstance(value, str) else None)
                if parsed is not None:
                    parsed_values.append(parsed)
        if len(parsed_values) >= 2 and len({round(value, 8) for value in parsed_values}) >= 2:
            numeric_columns.append(column)

    for column in PREFERRED_CATEGORICAL_CONTEXT_COLUMNS:
        values = [str(row.get(column) or "").strip() for row in context_rows]
        non_empty = [value for value in values if value]
        if len(set(non_empty)) >= 2:
            categorical_columns.append(column)

    return numeric_columns, categorical_columns


def summarize_numeric_context(
    context_rows: list[dict[str, Any]],
    cluster_labels: list[int],
    numeric_columns: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], np.ndarray]:
    stats = maybe_import_scipy_stats()
    summary_rows: list[dict[str, Any]] = []
    test_rows: list[dict[str, Any]] = []
    heatmap_matrix = []

    for variable_name in numeric_columns:
        grouped_values = []
        cluster_medians = []
        for cluster_label in cluster_labels:
            values = []
            for row in context_rows:
                if row["cluster_label"] != cluster_label:
                    continue
                raw_value = row.get(variable_name)
                if isinstance(raw_value, (int, float)):
                    values.append(float(raw_value))
                else:
                    parsed = parse_float(str(raw_value))
                    if parsed is not None:
                        values.append(parsed)
            grouped_values.append(values)
            if values:
                ordered = np.asarray(values, dtype=np.float64)
                q75, q25 = np.percentile(ordered, [75, 25])
                summary_rows.append(
                    {
                        "variable": variable_name,
                        "cluster_label": cluster_label,
                        "count": len(values),
                        "mean": float(np.mean(ordered)),
                        "median": float(np.median(ordered)),
                        "std": float(np.std(ordered, ddof=0)),
                        "iqr": float(q75 - q25),
                    }
                )
                cluster_medians.append(float(np.median(ordered)))
            else:
                summary_rows.append(
                    {
                        "variable": variable_name,
                        "cluster_label": cluster_label,
                        "count": 0,
                        "mean": None,
                        "median": None,
                        "std": None,
                        "iqr": None,
                    }
                )
                cluster_medians.append(np.nan)

        usable_groups = [np.asarray(values, dtype=np.float64) for values in grouped_values if len(values) > 0]
        pooled_values = np.concatenate(usable_groups) if usable_groups else np.empty((0,), dtype=np.float64)
        if stats is not None and len(usable_groups) >= 2 and pooled_values.size > 0 and not np.allclose(pooled_values, pooled_values[0]):
            kruskal_statistic, kruskal_p_value = stats.kruskal(*usable_groups)
            kruskal_statistic = float(kruskal_statistic)
            kruskal_p_value = float(kruskal_p_value)
            total_n = int(sum(len(values) for values in usable_groups))
            group_count = len(usable_groups)
            if total_n > group_count:
                epsilon_squared = max(0.0, float((kruskal_statistic - group_count + 1) / (total_n - group_count)))
            else:
                epsilon_squared = None
        else:
            kruskal_statistic = None
            kruskal_p_value = None
            epsilon_squared = None

        test_rows.append(
            {
                "variable": variable_name,
                "kruskal_wallis_statistic": kruskal_statistic,
                "kruskal_wallis_p_value": kruskal_p_value,
                "epsilon_squared": epsilon_squared,
            }
        )
        heatmap_matrix.append(cluster_medians)

    adjusted = benjamini_hochberg([row["kruskal_wallis_p_value"] for row in test_rows])
    for row, adjusted_p in zip(test_rows, adjusted):
        row["kruskal_wallis_p_value_bh"] = adjusted_p

    for row in test_rows:
        row["sort_effect"] = row["epsilon_squared"] if row["epsilon_squared"] is not None else -1.0
    test_rows.sort(key=lambda item: item["sort_effect"], reverse=True)
    for row in test_rows:
        row.pop("sort_effect", None)

    matrix = np.asarray(heatmap_matrix, dtype=np.float64).T if heatmap_matrix else np.empty((0, 0))
    return summary_rows, test_rows, matrix


def summarize_categorical_context(
    context_rows: list[dict[str, Any]],
    cluster_labels: list[int],
    categorical_columns: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    stats = maybe_import_scipy_stats()
    summary_rows: list[dict[str, Any]] = []
    test_rows: list[dict[str, Any]] = []

    for variable_name in categorical_columns:
        categories = sorted({str(row.get(variable_name) or "").strip() for row in context_rows if str(row.get(variable_name) or "").strip()})
        if len(categories) < 2:
            continue
        contingency = []
        for cluster_label in cluster_labels:
            counts = []
            cluster_total = sum(
                1
                for row in context_rows
                if row["cluster_label"] == cluster_label and str(row.get(variable_name) or "").strip()
            )
            for category in categories:
                count = sum(
                    1
                    for row in context_rows
                    if row["cluster_label"] == cluster_label and str(row.get(variable_name) or "").strip() == category
                )
                counts.append(count)
                summary_rows.append(
                    {
                        "variable": variable_name,
                        "cluster_label": cluster_label,
                        "category": category,
                        "count": count,
                        "fraction_within_cluster": (count / cluster_total) if cluster_total else None,
                    }
                )
            contingency.append(counts)

        if stats is not None:
            chi2_statistic, chi2_p_value, dof, _expected = stats.chi2_contingency(contingency)
            chi2_statistic = float(chi2_statistic)
            chi2_p_value = float(chi2_p_value)
            total_n = float(np.sum(contingency))
            r_count = len(contingency)
            c_count = len(categories)
            if total_n > 0 and min(r_count - 1, c_count - 1) > 0:
                cramer_v = math.sqrt((chi2_statistic / total_n) / min(r_count - 1, c_count - 1))
            else:
                cramer_v = None
        else:
            chi2_statistic = None
            chi2_p_value = None
            dof = None
            cramer_v = None

        test_rows.append(
            {
                "variable": variable_name,
                "chi_square_statistic": chi2_statistic,
                "chi_square_p_value": chi2_p_value,
                "degrees_of_freedom": dof,
                "cramers_v": cramer_v,
                "category_count": len(categories),
            }
        )

    adjusted = benjamini_hochberg([row["chi_square_p_value"] for row in test_rows])
    for row, adjusted_p in zip(test_rows, adjusted):
        row["chi_square_p_value_bh"] = adjusted_p

    for row in test_rows:
        row["sort_effect"] = row["cramers_v"] if row["cramers_v"] is not None else -1.0
    test_rows.sort(key=lambda item: item["sort_effect"], reverse=True)
    for row in test_rows:
        row.pop("sort_effect", None)

    return summary_rows, test_rows


def plot_numeric_context_boxplots(
    output_path: Path,
    context_rows: list[dict[str, Any]],
    cluster_labels: list[int],
    top_variables: list[str],
) -> str | None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    if not top_variables:
        return None

    def draw_boxplot(axis: Any, grouped_values: list[list[float]], label_values: list[str]) -> None:
        try:
            axis.boxplot(grouped_values, tick_labels=label_values)
        except TypeError:
            axis.boxplot(grouped_values, labels=label_values)

    columns = min(2, len(top_variables))
    rows = int(math.ceil(len(top_variables) / columns))
    figure, axes = plt.subplots(rows, columns, figsize=(10, max(4, rows * 3.1)))
    axes_array = np.atleast_1d(axes).reshape(rows, columns)
    for axis in axes_array.flat:
        axis.set_visible(False)

    for plot_index, variable_name in enumerate(top_variables):
        axis = axes_array.flat[plot_index]
        axis.set_visible(True)
        grouped = []
        labels = []
        for cluster_label in cluster_labels:
            values = []
            for row in context_rows:
                if row["cluster_label"] != cluster_label:
                    continue
                raw_value = row.get(variable_name)
                if isinstance(raw_value, (int, float)):
                    values.append(float(raw_value))
                else:
                    parsed = parse_float(str(raw_value))
                    if parsed is not None:
                        values.append(parsed)
            if values:
                grouped.append(values)
                labels.append(str(cluster_label))
        if grouped:
            draw_boxplot(axis, grouped, labels)
        axis.set_title(variable_name)
        axis.set_xlabel("Cluster")
        axis.set_ylabel("Value")

    figure.suptitle("Top contextual numeric differences by cluster", y=1.02)
    figure.tight_layout()
    figure.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(figure)
    return str(output_path)


def run_context_models(
    context_rows: list[dict[str, Any]],
    numeric_columns: list[str],
    categorical_columns: list[str],
    random_seed: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    sklearn_lib = maybe_import_sklearn_inspection()
    if sklearn_lib is None:
        return [], {"status": "skipped", "reason": "scikit-learn is not available"}

    if not numeric_columns and not categorical_columns:
        return [], {"status": "skipped", "reason": "no contextual predictor columns are available"}

    dict_vectorizer_cls = sklearn_lib["DictVectorizer"]
    rf_cls = sklearn_lib["RandomForestClassifier"]
    logreg_cls = sklearn_lib["LogisticRegression"]
    cv_cls = sklearn_lib["StratifiedKFold"]
    scaler_cls = sklearn_lib["StandardScaler"]
    cross_val_score = sklearn_lib["cross_val_score"]

    numeric_medians = {}
    for column in numeric_columns:
        values = []
        for row in context_rows:
            raw_value = row.get(column)
            if isinstance(raw_value, (int, float)):
                values.append(float(raw_value))
            else:
                parsed = parse_float(str(raw_value))
                if parsed is not None:
                    values.append(parsed)
        numeric_medians[column] = float(np.median(values)) if values else 0.0

    model_inputs = []
    model_labels = []
    for row in context_rows:
        entry: dict[str, Any] = {}
        for column in numeric_columns:
            raw_value = row.get(column)
            if isinstance(raw_value, (int, float)):
                entry[column] = float(raw_value)
            else:
                parsed = parse_float(str(raw_value))
                entry[column] = parsed if parsed is not None else numeric_medians[column]
        for column in categorical_columns:
            entry[column] = str(row.get(column) or "missing")
        model_inputs.append(entry)
        model_labels.append(int(row["cluster_label"]))

    y = np.asarray(model_labels, dtype=int)
    if len(set(y.tolist())) < 2:
        return [], {"status": "skipped", "reason": "fewer than two clusters are available after preprocessing"}

    vectorizer = dict_vectorizer_cls(sparse=False)
    X = vectorizer.fit_transform(model_inputs)
    feature_names = vectorizer.get_feature_names_out()
    scaler = scaler_cls()
    X_scaled = scaler.fit_transform(X)

    cv = cv_cls(n_splits=5, shuffle=True, random_state=random_seed)
    rf_model = rf_cls(n_estimators=400, random_state=random_seed, class_weight="balanced")
    rf_scores = cross_val_score(rf_model, X, y, cv=cv, scoring="balanced_accuracy")
    rf_model.fit(X, y)

    logreg_model = logreg_cls(
        max_iter=5000,
        class_weight="balanced",
        random_state=random_seed,
    )
    logreg_scores = cross_val_score(logreg_model, X_scaled, y, cv=cv, scoring="balanced_accuracy")
    logreg_model.fit(X_scaled, y)

    abs_coefficients = np.mean(np.abs(logreg_model.coef_), axis=0)
    rows = []
    for feature_index, feature_name in enumerate(feature_names):
        rows.append(
            {
                "feature": str(feature_name),
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


def plot_context_importance(output_path: Path, rows: list[dict[str, Any]], top_n: int) -> str | None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    if not rows:
        return None

    top_rows = rows[:top_n]
    labels = [row["feature"] for row in reversed(top_rows)]
    rf_values = [row["random_forest_importance"] for row in reversed(top_rows)]
    log_values = [row["logistic_abs_mean_coefficient"] for row in reversed(top_rows)]

    figure, axes = plt.subplots(1, 2, figsize=(12, max(4, len(labels) * 0.32)))
    axes[0].barh(labels, rf_values, color="#457b9d")
    axes[0].set_title("Random forest importance")
    axes[0].set_xlabel("Importance")
    axes[1].barh(labels, log_values, color="#e76f51")
    axes[1].set_title("Logistic mean |coef|")
    axes[1].set_xlabel("Magnitude")
    figure.tight_layout()
    figure.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(figure)
    return str(output_path)


def build_categorical_enrichment(
    context_rows: list[dict[str, Any]],
    cluster_labels: list[int],
    categorical_columns: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variable_name in categorical_columns:
        categories = sorted({str(row.get(variable_name) or "").strip() for row in context_rows if str(row.get(variable_name) or "").strip()})
        if len(categories) < 2:
            continue
        contingency = np.array(
            [
                [
                    sum(
                        1
                        for row in context_rows
                        if row["cluster_label"] == cluster_label and str(row.get(variable_name) or "").strip() == category
                    )
                    for category in categories
                ]
                for cluster_label in cluster_labels
            ],
            dtype=np.float64,
        )
        total = contingency.sum()
        if total <= 0:
            continue
        expected = contingency.sum(axis=1, keepdims=True) @ contingency.sum(axis=0, keepdims=True) / total
        with np.errstate(divide="ignore", invalid="ignore"):
            residuals = np.where(expected > 0, (contingency - expected) / np.sqrt(expected), 0.0)
        for cluster_index, cluster_label in enumerate(cluster_labels):
            for category_index, category in enumerate(categories):
                rows.append(
                    {
                        "variable": variable_name,
                        "cluster_label": cluster_label,
                        "category": category,
                        "observed_count": int(contingency[cluster_index, category_index]),
                        "expected_count": float(expected[cluster_index, category_index]),
                        "pearson_residual": float(residuals[cluster_index, category_index]),
                    }
                )
    rows.sort(key=lambda item: abs(item["pearson_residual"]), reverse=True)
    return rows


def plot_categorical_enrichment_heatmap(
    output_path: Path,
    enrichment_rows: list[dict[str, Any]],
    variable_name: str,
    cluster_labels: list[int],
    top_n_categories: int,
) -> str | None:
    variable_rows = [row for row in enrichment_rows if row["variable"] == variable_name]
    if not variable_rows:
        return None

    category_scores: dict[str, float] = {}
    for row in variable_rows:
        category = row["category"]
        category_scores[category] = max(category_scores.get(category, 0.0), abs(float(row["pearson_residual"])))
    selected_categories = [category for category, _score in sorted(category_scores.items(), key=lambda item: item[1], reverse=True)[:top_n_categories]]
    matrix = np.array(
        [
            [
                next(
                    float(row["pearson_residual"])
                    for row in variable_rows
                    if row["cluster_label"] == cluster_label and row["category"] == category
                )
                for category in selected_categories
            ]
            for cluster_label in cluster_labels
        ],
        dtype=np.float64,
    )
    return plot_heatmap(
        output_path=output_path,
        matrix=matrix,
        row_labels=[f"cluster {label}" for label in cluster_labels],
        column_labels=selected_categories,
        title=f"{variable_name} enrichment residuals",
        cmap="coolwarm",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Relate the selected clustering solution to available project context variables.")
    parser.add_argument("--analysis-root", default=DEFAULT_ANALYSIS_ROOT, help="Directory containing the per-method analysis folders")
    parser.add_argument("--feature-csv", default=DEFAULT_PHASE6_INPUT_CSV, help="Path to image_features_final.csv")
    parser.add_argument("--selection-summary-json", default=DEFAULT_SELECTION_SUMMARY_JSON, help="Selection summary JSON used when --candidate-id is omitted")
    parser.add_argument("--candidate-id", default="", help="Explicit candidate id to analyze")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directory where context-analysis outputs will be written")
    parser.add_argument("--random-seed", type=int, default=7, help="Random seed for contextual predictive models")
    parser.add_argument("--exclude-noise", action="store_true", help="Exclude HDBSCAN-style noise points from the association tests")
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
    _assignment_rows, labels_by_image_id = load_candidate_labels(assignments_csv)

    dataset_rows, _headers, _feature_columns = load_dataset_rows(Path(args.feature_csv).resolve())
    context_rows = build_context_rows(dataset_rows, labels_by_image_id, exclude_noise=args.exclude_noise)
    cluster_labels = sorted({int(row["cluster_label"]) for row in context_rows})
    numeric_columns, categorical_columns = detect_context_columns(context_rows)

    numeric_summary_rows, numeric_test_rows, numeric_heatmap = summarize_numeric_context(
        context_rows=context_rows,
        cluster_labels=cluster_labels,
        numeric_columns=numeric_columns,
    )
    categorical_summary_rows, categorical_test_rows = summarize_categorical_context(
        context_rows=context_rows,
        cluster_labels=cluster_labels,
        categorical_columns=categorical_columns,
    )
    categorical_enrichment_rows = build_categorical_enrichment(
        context_rows=context_rows,
        cluster_labels=cluster_labels,
        categorical_columns=categorical_columns,
    )

    plot_files = {}
    if numeric_columns and numeric_heatmap.size > 0:
        heatmap_path = plot_heatmap(
            output_path=output_dir / "numeric_context_heatmap.png",
            matrix=numeric_heatmap,
            row_labels=[f"cluster {label}" for label in cluster_labels],
            column_labels=numeric_columns,
            title="Numeric contextual medians by cluster",
            cmap="cividis",
        )
        if heatmap_path:
            plot_files["numeric_context_heatmap"] = heatmap_path

    top_numeric_variables = [row["variable"] for row in numeric_test_rows[:4]]
    boxplot_path = plot_numeric_context_boxplots(
        output_path=output_dir / "numeric_context_boxplots.png",
        context_rows=context_rows,
        cluster_labels=cluster_labels,
        top_variables=top_numeric_variables,
    )
    if boxplot_path:
        plot_files["numeric_context_boxplots"] = boxplot_path

    context_model_rows, context_model_summary = run_context_models(
        context_rows=context_rows,
        numeric_columns=numeric_columns,
        categorical_columns=categorical_columns,
        random_seed=args.random_seed,
    )
    context_importance_plot = plot_context_importance(
        output_path=output_dir / "context_model_feature_importance.png",
        rows=context_model_rows,
        top_n=12,
    )
    if context_importance_plot:
        plot_files["context_model_feature_importance"] = context_importance_plot
    for variable_name, filename, top_n in [
        ("official_station_id", "official_station_enrichment_heatmap.png", 12),
        ("capture_season", "capture_season_enrichment_heatmap.png", 8),
    ]:
        enrichment_plot = plot_categorical_enrichment_heatmap(
            output_path=output_dir / filename,
            enrichment_rows=categorical_enrichment_rows,
            variable_name=variable_name,
            cluster_labels=cluster_labels,
            top_n_categories=top_n,
        )
        if enrichment_plot:
            plot_files[variable_name + "_enrichment_heatmap"] = enrichment_plot

    if numeric_summary_rows:
        write_csv(output_dir / "numeric_context_summary.csv", numeric_summary_rows, list(numeric_summary_rows[0].keys()))
    if numeric_test_rows:
        write_csv(output_dir / "numeric_context_tests.csv", numeric_test_rows, list(numeric_test_rows[0].keys()))
    if categorical_summary_rows:
        write_csv(output_dir / "categorical_context_summary.csv", categorical_summary_rows, list(categorical_summary_rows[0].keys()))
    if categorical_test_rows:
        write_csv(output_dir / "categorical_context_tests.csv", categorical_test_rows, list(categorical_test_rows[0].keys()))
    if categorical_enrichment_rows:
        write_csv(output_dir / "categorical_context_enrichment.csv", categorical_enrichment_rows, list(categorical_enrichment_rows[0].keys()))
    if context_model_rows:
        write_csv(output_dir / "context_model_feature_importance.csv", context_model_rows, list(context_model_rows[0].keys()))

    summary = {
        "analysis_root": str(analysis_root),
        "output_dir": str(output_dir),
        "candidate_id": selected_candidate_id,
        "candidate_result": {
            "method": candidate_result["method"],
            "feature_space": candidate_result["feature_space"],
            "k": candidate_result.get("k"),
        },
        "assignments_csv": str(assignments_csv),
        "rows_used": len(context_rows),
        "cluster_labels": cluster_labels,
        "numeric_context_columns": numeric_columns,
        "categorical_context_columns": categorical_columns,
        "top_numeric_associations": numeric_test_rows[:5],
        "top_categorical_associations": categorical_test_rows[:5],
        "context_model_summary": context_model_summary,
        "plot_files": plot_files,
        "notes": [
            "The contextual association step measures association and enrichment, not direct chemical proof.",
            "This implementation prioritizes project-native station and capture-time variables before any external API enrichment.",
        ],
    }
    write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
