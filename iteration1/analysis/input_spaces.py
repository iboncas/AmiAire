from __future__ import annotations

from pathlib import Path
from typing import Any

from common import (
    DEFAULT_FEATURE_SPACES,
    align_feature_space_datasets,
    load_pca_scores_dataset,
    load_phase6_dataset,
    sample_feature_spaces,
)


def validate_feature_spaces(feature_spaces: list[str]) -> None:
    if not feature_spaces:
        raise RuntimeError("At least one feature space must be requested")
    unknown_spaces = sorted(set(feature_spaces) - set(DEFAULT_FEATURE_SPACES))
    if unknown_spaces:
        raise RuntimeError(f"Unsupported feature spaces requested: {', '.join(unknown_spaces)}")


def validate_row_count_for_clustering(row_count: int) -> None:
    if row_count < 3:
        raise RuntimeError("At least 3 rows are required to run clustering")


def validate_k_values(row_count: int, k_values: list[int]) -> None:
    if row_count <= max(k_values):
        raise RuntimeError(
            "The dataset is too small for the requested k range. "
            "Use more rows or lower the maximum k value."
        )


def load_requested_feature_spaces(
    selected_input_csv: Path,
    pca_input_csv: Path | None,
    feature_spaces: list[str],
    sample_size: int,
    random_seed: int,
) -> dict[str, Any]:
    validate_feature_spaces(feature_spaces)

    datasets: dict[str, dict[str, Any]] = {}
    loaded_paths: dict[str, str] = {}
    row_counts_by_space: dict[str, int] = {}

    if "selected_features" in feature_spaces:
        selected_dataset = load_phase6_dataset(selected_input_csv)
        datasets["selected_features"] = selected_dataset
        loaded_paths["selected_features"] = str(selected_input_csv)
        row_counts_by_space["selected_features"] = len(selected_dataset["metadata_rows"])

    if "pca_scores" in feature_spaces:
        if pca_input_csv is None:
            raise RuntimeError(
                "The pca_scores feature space was requested, but no --pca-input-csv path was provided."
            )
        pca_dataset = load_pca_scores_dataset(pca_input_csv)
        datasets["pca_scores"] = pca_dataset
        loaded_paths["pca_scores"] = str(pca_input_csv)
        row_counts_by_space["pca_scores"] = len(pca_dataset["metadata_rows"])

    metadata_rows, feature_space_map, feature_columns_by_space = align_feature_space_datasets(datasets)
    metadata_rows, feature_space_map, sampled_indices = sample_feature_spaces(
        metadata_rows,
        feature_space_map,
        sample_size=sample_size,
        random_seed=random_seed,
    )

    return {
        "metadata_rows": metadata_rows,
        "feature_space_map": feature_space_map,
        "feature_columns_by_space": feature_columns_by_space,
        "loaded_paths": loaded_paths,
        "row_counts_by_space": row_counts_by_space,
        "aligned_row_count": len(metadata_rows),
        "sampled_indices": sampled_indices if sample_size > 0 else None,
    }
