#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import (
    DEFAULT_PHASE6_INPUT_CSV,
    DEFAULT_PCA_OUTPUT_DIR,
    align_feature_space_datasets,
    ensure_directory,
    import_pyplot,
    load_phase6_dataset,
    sample_feature_spaces,
    write_csv,
    write_json,
)


def require_sklearn_pca() -> Any:
    try:
        from sklearn.decomposition import PCA
    except ImportError as error:
        raise SystemExit(
            "scikit-learn is required for phase 7. "
            "Install it with `pip install -r requirements.txt`."
        ) from error
    return PCA


def run_pca(
    features: np.ndarray,
    feature_columns: list[str],
    variance_threshold: float,
    loading_components: int,
    loading_features: int,
) -> dict[str, Any]:
    pca_model = require_sklearn_pca()()
    full_scores = pca_model.fit_transform(features)
    explained_variance_ratio = pca_model.explained_variance_ratio_
    cumulative_variance_ratio = np.cumsum(explained_variance_ratio)
    retained_components = int(np.searchsorted(cumulative_variance_ratio, variance_threshold, side="left") + 1)
    retained_components = max(1, retained_components)

    retained_scores = full_scores[:, :retained_components]
    projection_2d = np.zeros((features.shape[0], 2), dtype=np.float64)
    projection_2d[:, 0] = full_scores[:, 0]
    if full_scores.shape[1] > 1:
        projection_2d[:, 1] = full_scores[:, 1]

    loadings = pca_model.components_.T * np.sqrt(pca_model.explained_variance_)
    top_loading_summary: dict[str, dict[str, list[dict[str, float]]]] = {}
    for component_index in range(min(loading_components, loadings.shape[1])):
        component_name = f"PC{component_index + 1}"
        component_loadings = loadings[:, component_index]
        ordered_indices = np.argsort(np.abs(component_loadings))[::-1][:loading_features]
        top_loading_summary[component_name] = {
            "top_absolute_loadings": [
                {
                    "feature": feature_columns[index],
                    "loading": float(component_loadings[index]),
                }
                for index in ordered_indices
            ]
        }

    return {
        "retained_scores": retained_scores,
        "projection_2d": projection_2d,
        "explained_variance_ratio": explained_variance_ratio,
        "cumulative_variance_ratio": cumulative_variance_ratio,
        "retained_components": retained_components,
        "variance_threshold": variance_threshold,
        "loadings": loadings,
        "top_loading_summary": top_loading_summary,
    }


def save_pca_outputs(
    output_dir: Path,
    metadata_rows: list[dict[str, Any]],
    feature_columns: list[str],
    pca_results: dict[str, Any],
) -> dict[str, str]:
    retained_scores = pca_results["retained_scores"]
    projection_2d = pca_results["projection_2d"]
    explained_variance_ratio = pca_results["explained_variance_ratio"]
    cumulative_variance_ratio = pca_results["cumulative_variance_ratio"]
    loadings = pca_results["loadings"]

    variance_rows = []
    for component_index, variance_ratio in enumerate(explained_variance_ratio, start=1):
        variance_rows.append(
            {
                "component": f"PC{component_index}",
                "explained_variance_ratio": float(variance_ratio),
                "cumulative_variance_ratio": float(cumulative_variance_ratio[component_index - 1]),
            }
        )
    write_csv(
        output_dir / "pca_variance.csv",
        variance_rows,
        ["component", "explained_variance_ratio", "cumulative_variance_ratio"],
    )

    score_rows = []
    for row_index, metadata in enumerate(metadata_rows):
        row = dict(metadata)
        for component_index in range(retained_scores.shape[1]):
            row[f"PC{component_index + 1}"] = float(retained_scores[row_index, component_index])
        score_rows.append(row)
    write_csv(
        output_dir / "pca_scores_retained.csv",
        score_rows,
        list(metadata_rows[0].keys()) + [f"PC{index + 1}" for index in range(retained_scores.shape[1])],
    )

    projection_rows = []
    for row_index, metadata in enumerate(metadata_rows):
        row = dict(metadata)
        row["PC1"] = float(projection_2d[row_index, 0])
        row["PC2"] = float(projection_2d[row_index, 1])
        projection_rows.append(row)
    write_csv(
        output_dir / "pca_projection_2d.csv",
        projection_rows,
        list(metadata_rows[0].keys()) + ["PC1", "PC2"],
    )

    loading_rows = []
    for feature_index, feature_name in enumerate(feature_columns):
        row = {"feature": feature_name}
        for component_index in range(loadings.shape[1]):
            row[f"PC{component_index + 1}"] = float(loadings[feature_index, component_index])
        loading_rows.append(row)
    write_csv(
        output_dir / "pca_loadings.csv",
        loading_rows,
        ["feature"] + [f"PC{index + 1}" for index in range(loadings.shape[1])],
    )

    report = {
        "input_feature_count": len(feature_columns),
        "variance_threshold": pca_results["variance_threshold"],
        "retained_components_for_variance_threshold": pca_results["retained_components"],
        "explained_variance_ratio": [float(value) for value in explained_variance_ratio.tolist()],
        "cumulative_variance_ratio": [float(value) for value in cumulative_variance_ratio.tolist()],
        "top_loading_summary": pca_results["top_loading_summary"],
    }
    write_json(output_dir / "pca_report.json", report)

    return {
        "pca_variance_csv": str(output_dir / "pca_variance.csv"),
        "pca_scores_csv": str(output_dir / "pca_scores_retained.csv"),
        "pca_projection_csv": str(output_dir / "pca_projection_2d.csv"),
        "pca_loadings_csv": str(output_dir / "pca_loadings.csv"),
        "pca_report_json": str(output_dir / "pca_report.json"),
    }


def plot_pca_outputs(output_dir: Path, pca_results: dict[str, Any]) -> dict[str, str]:
    plt = import_pyplot()
    if plt is None:
        return {}

    plot_paths: dict[str, str] = {}
    explained_variance_ratio = pca_results["explained_variance_ratio"]
    cumulative_variance_ratio = pca_results["cumulative_variance_ratio"]
    projection_2d = pca_results["projection_2d"]
    retained_components = pca_results["retained_components"]
    variance_threshold = pca_results["variance_threshold"]

    scree_path = output_dir / "pca_scree_plot.png"
    component_axis = np.arange(1, explained_variance_ratio.shape[0] + 1)
    figure, axis_left = plt.subplots(figsize=(9, 5))
    axis_left.bar(component_axis, explained_variance_ratio, color="#52796f", alpha=0.8)
    axis_left.set_xlabel("Principal component")
    axis_left.set_ylabel("Explained variance ratio")
    axis_left.axvline(retained_components, color="#d62828", linestyle="--", linewidth=1.5)

    axis_right = axis_left.twinx()
    axis_right.plot(component_axis, cumulative_variance_ratio, color="#1d3557", marker="o", linewidth=2)
    axis_right.axhline(variance_threshold, color="#ff7f11", linestyle=":", linewidth=1.5)
    axis_right.set_ylabel("Cumulative explained variance")
    figure.tight_layout()
    figure.savefig(scree_path, dpi=180, bbox_inches="tight")
    plt.close(figure)
    plot_paths["pca_scree_plot"] = str(scree_path)

    projection_path = output_dir / "pca_projection_2d.png"
    figure, axis = plt.subplots(figsize=(6, 6))
    axis.scatter(projection_2d[:, 0], projection_2d[:, 1], s=12, alpha=0.7, color="#264653")
    axis.set_xlabel("PC1")
    axis.set_ylabel("PC2")
    axis.set_title("2D PCA projection")
    figure.tight_layout()
    figure.savefig(projection_path, dpi=180, bbox_inches="tight")
    plt.close(figure)
    plot_paths["pca_projection_plot"] = str(projection_path)
    return plot_paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run PCA on the reduced feature matrix."
    )
    parser.add_argument("--input-csv", default=DEFAULT_PHASE6_INPUT_CSV, help="Path to image_features_final.csv")
    parser.add_argument("--output-dir", default=DEFAULT_PCA_OUTPUT_DIR, help="Directory where PCA outputs will be written")
    parser.add_argument(
        "--sample-size",
        type=int,
        default=0,
        help="Optional random sample size for a pilot run; 0 keeps all rows",
    )
    parser.add_argument("--random-seed", type=int, default=7, help="Base random seed used for sampling")
    parser.add_argument(
        "--variance-threshold",
        type=float,
        default=0.85,
        help="Minimum cumulative explained variance required for retained PCA components",
    )
    parser.add_argument(
        "--top-loading-components",
        type=int,
        default=5,
        help="Number of principal components to summarize in the PCA report",
    )
    parser.add_argument(
        "--top-loading-features",
        type=int,
        default=10,
        help="Number of features to keep per component in the PCA loading summary",
    )
    args = parser.parse_args()

    if args.variance_threshold <= 0 or args.variance_threshold > 1:
        raise RuntimeError("--variance-threshold must be in the interval (0, 1]")

    input_csv = Path(args.input_csv).resolve()
    output_dir = Path(args.output_dir).resolve()
    ensure_directory(output_dir)

    dataset = load_phase6_dataset(input_csv)
    metadata_rows, feature_space_map, feature_columns_by_space = align_feature_space_datasets(
        {"selected_features": dataset}
    )
    metadata_rows, feature_space_map, sampled_indices = sample_feature_spaces(
        metadata_rows,
        feature_space_map,
        sample_size=args.sample_size,
        random_seed=args.random_seed,
    )
    feature_columns = feature_columns_by_space["selected_features"]
    feature_matrix = feature_space_map["selected_features"]

    if feature_matrix.shape[0] < 3:
        raise RuntimeError("At least 3 rows are required to run PCA")

    pca_results = run_pca(
        feature_matrix,
        feature_columns,
        variance_threshold=args.variance_threshold,
        loading_components=args.top_loading_components,
        loading_features=args.top_loading_features,
    )
    output_files = save_pca_outputs(output_dir, metadata_rows, feature_columns, pca_results)
    plot_files = plot_pca_outputs(output_dir, pca_results)

    summary = {
        "input_csv": str(input_csv),
        "output_dir": str(output_dir),
        "rows_loaded": len(dataset["metadata_rows"]),
        "rows_used": len(metadata_rows),
        "sample_size_argument": args.sample_size,
        "sampled_indices": sampled_indices if args.sample_size > 0 else None,
        "feature_count": len(feature_columns),
        "variance_threshold": args.variance_threshold,
        "retained_components": pca_results["retained_components"],
        "files": {**output_files, **plot_files},
    }
    write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
