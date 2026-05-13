from __future__ import annotations

import csv
import math
from functools import lru_cache
from pathlib import Path
from typing import Any


REFERENCE_FEATURE_COLUMNS = [
    "area_iqr",
    "area_median",
    "aspect_ratio_iqr",
    "aspect_ratio_median",
    "aspect_ratio_p90",
    "circular_variance",
    "circularity_iqr",
    "circularity_median",
    "eccentricity_iqr",
    "eccentricity_p90",
    "feret_iqr",
    "feret_p90",
    "mean_intensity_iqr",
    "mean_intensity_median",
    "num_particles",
    "orientation_entropy",
    "solidity_iqr",
    "solidity_median",
]

REFERENCE_MEANS = {
    "area_iqr": 5.125388198757764,
    "area_median": 3.1364518633540373,
    "aspect_ratio_iqr": 1.6221534981715564,
    "aspect_ratio_median": 1.1994690358827673,
    "aspect_ratio_p90": 2.422480442878371,
    "circular_variance": 0.5561294030363724,
    "circularity_iqr": 0.7474104443312359,
    "circularity_median": 0.39679511485048713,
    "eccentricity_iqr": 0.8135553888777802,
    "eccentricity_p90": 0.9885018065695288,
    "feret_iqr": 2.1077497925905555,
    "feret_p90": 5.080794829256514,
    "mean_intensity_iqr": 20.193423703590536,
    "mean_intensity_median": 198.06670793983506,
    "num_particles": 496.2509697439876,
    "orientation_entropy": 2.4727370643906514,
    "solidity_iqr": 0.016955063129178747,
    "solidity_median": 0.9985627923635724,
}

REFERENCE_STDS = {
    "area_iqr": 6.252988403934275,
    "area_median": 3.4465915723547753,
    "aspect_ratio_iqr": 0.5853239356480204,
    "aspect_ratio_median": 0.6728583550854693,
    "aspect_ratio_p90": 0.42465447664069056,
    "circular_variance": 0.15928781126293878,
    "circularity_iqr": 0.41895191070251303,
    "circularity_median": 0.47661803322027163,
    "eccentricity_iqr": 0.2502971212464762,
    "eccentricity_p90": 0.05787810595752964,
    "feret_iqr": 1.285196108115477,
    "feret_p90": 2.508662323126464,
    "mean_intensity_iqr": 11.68446640740085,
    "mean_intensity_median": 11.615553844212268,
    "num_particles": 1034.0774668170714,
    "orientation_entropy": 0.5956790080732651,
    "solidity_iqr": 0.0413432228744446,
    "solidity_median": 0.010284307506014927,
}

CATEGORY_WEIGHTS: dict[str, dict[str, float]] = {
    "combustion_related": {
        "num_particles": 1.15,
        "area_median": -1.05,
        "feret_p90": -0.85,
        "circularity_median": 0.95,
        "aspect_ratio_median": -0.80,
        "eccentricity_p90": -0.70,
        "mean_intensity_median": 0.40,
    },
    "mechanical_non_combustion_particulate": {
        "area_median": 1.05,
        "feret_p90": 0.95,
        "solidity_median": 0.85,
        "num_particles": -0.30,
        "solidity_iqr": 0.80,
        "aspect_ratio_iqr": 0.65,
        "circularity_median": -0.70,
        "mean_intensity_iqr": 0.45,
        "feret_iqr": 0.55,
    },
    "biological": {
        "area_iqr": 0.85,
        "mean_intensity_iqr": 0.90,
        "circularity_iqr": 0.70,
        "orientation_entropy": 0.55,
        "aspect_ratio_iqr": 0.45,
        "circular_variance": 0.40,
    },
    "fibrous_synthetic_materials": {
        "aspect_ratio_median": 1.20,
        "aspect_ratio_p90": 1.15,
        "eccentricity_p90": 1.00,
        "feret_p90": 0.90,
        "circularity_median": -1.00,
        "solidity_median": -0.45,
        "eccentricity_iqr": 0.60,
    },
    "industrial": {
        "solidity_iqr": 0.85,
        "eccentricity_iqr": 0.80,
        "feret_iqr": 0.80,
        "mean_intensity_iqr": 0.70,
        "orientation_entropy": 0.55,
        "aspect_ratio_iqr": 0.40,
    },
    "mixed_unknown": {
        "orientation_entropy": 0.95,
        "circular_variance": 0.90,
        "area_iqr": 0.80,
        "circularity_iqr": 0.80,
        "mean_intensity_iqr": 0.70,
        "solidity_iqr": 0.55,
    },
}

CATEGORY_LABELS: dict[str, str] = {
    "combustion_related": "Relacionada con combustion",
    "mechanical_non_combustion_particulate": "Particulado mecanico no ligado a combustion",
    "biological": "Origen biologico",
    "fibrous_synthetic_materials": "Materiales sinteticos fibrosos",
    "industrial": "Origen industrial",
    "mixed_unknown": "Mixto o desconocido",
}

METADATA_COLUMNS = {
    "image_id",
    "sensor_id",
    "capture_datetime",
    "collection_datetime",
    "latitude",
    "longitude",
    "image_path",
    "roi_detected",
    "roi_width_px",
    "roi_height_px",
    "segmentation_method",
    "analysis_success",
    "segmentation_success",
    "manual_qc_flag",
    "device_type",
    "sensor_exposure_time",
    "paper_type",
    "camera_type",
    "magnification",
    "weather_context",
    "official_station_id",
    "failure_reason",
    "record_pm10",
    "record_pm25",
    "record_pollution_level",
    "official_station_name",
    "official_station_distance_km",
    "official_pm10",
    "official_pm25",
    "official_fetched_at",
    "capture_month",
    "capture_season",
    "capture_month_sin",
    "capture_month_cos",
    "season_winter",
    "season_spring",
    "season_summer",
    "season_autumn",
    "total",
    "transit",
    "park",
    "gas_station",
    "parking",
    "industrial",
    "major_road_proxy",
    "place_diversity_entropy",
    "green_vs_traffic_ratio_500m",
    "dominant_place_category",
    "zero_particle_flag",
    "blur_score_laplacian",
    "roi_b_mean",
    "roi_b_std",
    "roi_g_mean",
    "roi_g_std",
    "roi_r_mean",
    "roi_r_std",
    "roi_h_mean",
    "roi_h_std",
    "roi_s_mean",
    "roi_s_std",
    "roi_v_mean",
    "roi_v_std",
    "roi_grid_label",
    "roi_grid_score",
    "roi_grid_confidence",
    "roi_grid_needs_review",
    "roi_grid_inner_margin_ratio",
    "roi_grid_inner_dark_ratio",
    "roi_grid_horizontal_line_count",
    "roi_grid_vertical_line_count",
    "roi_grid_horizontal_coverage",
    "roi_grid_vertical_coverage",
    "roi_grid_row_peak_count",
    "roi_grid_col_peak_count",
    "roi_grid_spacing_regularity",
}

MODEL_NOTE = (
    "Este modelo probabilístico es una estimación basada en fórmulas de compatibilidad taxonómica. "
    "Su resultado es orientativo y no constituye una confirmación calibrada de la fuente real del contaminante."
)


def resolve_reference_dataset_path() -> Path | None:
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "iteration2" / "output" / "dataset" / "image_features_enriched.csv"
        if candidate.exists():
            return candidate
    return None


def parse_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    lowered = str(value).strip().lower()
    if lowered in {"true", "false", "pending"}:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def load_rows(dataset_path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with dataset_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        headers = reader.fieldnames or []
    return rows, headers


def numeric_feature_columns(rows: list[dict[str, str]], headers: list[str]) -> list[str]:
    columns: list[str] = []
    for header in headers:
        if header in METADATA_COLUMNS:
            continue
        values = [parse_float(row.get(header)) for row in rows]
        if any(value is not None for value in values):
            columns.append(header)
    return columns


def compute_stats(
    rows: list[dict[str, str]], feature_columns: list[str]
) -> tuple[dict[str, float], dict[str, float]]:
    means: dict[str, float] = {}
    stds: dict[str, float] = {}
    for column in feature_columns:
        values = [parse_float(row.get(column)) for row in rows]
        clean_values = [value for value in values if value is not None]
        if not clean_values:
            means[column] = 0.0
            stds[column] = 1.0
            continue
        mean = sum(clean_values) / len(clean_values)
        variance = sum((value - mean) ** 2 for value in clean_values) / len(clean_values)
        std = math.sqrt(variance) or 1.0
        means[column] = mean
        stds[column] = std
    return means, stds


def standardize_profile(
    profile: dict[str, float], means: dict[str, float], stds: dict[str, float]
) -> dict[str, float]:
    return {
        column: (value - means.get(column, 0.0)) / stds.get(column, 1.0)
        for column, value in profile.items()
    }


def score_profile(standardized_profile: dict[str, float]) -> dict[str, dict[str, Any]]:
    scored: dict[str, dict[str, Any]] = {}
    for category, weights in CATEGORY_WEIGHTS.items():
        contributions = []
        score = 0.0
        for feature_name, weight in weights.items():
            if feature_name not in standardized_profile:
                continue
            z_value = standardized_profile[feature_name]
            contribution = z_value * weight
            score += contribution
            contributions.append({
                "feature": feature_name,
                "z": z_value,
                "weight": weight,
                "contribution": contribution,
            })
        contributions.sort(key=lambda item: abs(item["contribution"]), reverse=True)
        scored[category] = {"score": score, "contributions": contributions}
    return scored


def softmax_percentages(
    scores: dict[str, dict[str, Any]], temperature: float = 1.5
) -> dict[str, float]:
    clean_temperature = temperature if temperature > 0 else 1.0
    raw_scores = {
        category: float(data["score"]) / clean_temperature
        for category, data in scores.items()
    }
    max_score = max(raw_scores.values())
    exp_scores = {
        category: math.exp(score - max_score)
        for category, score in raw_scores.items()
    }
    total = sum(exp_scores.values()) or 1.0
    return {category: value * 100.0 / total for category, value in exp_scores.items()}


class FeatureProfileScorer:
    def __init__(self, reference_dataset_path: Path | None = None) -> None:
        resolved_path = reference_dataset_path or resolve_reference_dataset_path()
        self.reference_dataset_path = resolved_path

        if resolved_path and resolved_path.exists():
            self.rows, self.headers = load_rows(resolved_path)
            self.feature_columns = numeric_feature_columns(self.rows, self.headers)
            self.means, self.stds = compute_stats(self.rows, self.feature_columns)
            return

        self.rows = []
        self.headers = list(REFERENCE_FEATURE_COLUMNS)
        self.feature_columns = list(REFERENCE_FEATURE_COLUMNS)
        self.means = dict(REFERENCE_MEANS)
        self.stds = dict(REFERENCE_STDS)

    def score_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        numeric_profile = {
            column: value
            for column, value in (
                (key, parse_float(raw_value))
                for key, raw_value in profile.items()
            )
            if value is not None
        }
        if not numeric_profile:
            return {
                "status": "error",
                "message": "No numeric features could be extracted for the taxonomy model.",
                "note": MODEL_NOTE,
            }

        standardized_profile = standardize_profile(
            numeric_profile,
            self.means,
            self.stds,
        )
        raw_scores = score_profile(standardized_profile)
        percentages = softmax_percentages(raw_scores)
        ranked = sorted(
            (
                {
                    "category": category,
                    "label": CATEGORY_LABELS.get(category, category),
                    "score": raw_scores[category]["score"],
                    "percentage": percentages[category],
                    "evidence": raw_scores[category]["contributions"][:4],
                }
                for category in raw_scores
            ),
            key=lambda item: item["percentage"],
            reverse=True,
        )

        return {
            "status": "ok",
            "top_category": ranked[0]["category"] if ranked else "",
            "top_category_label": ranked[0]["label"] if ranked else "",
            "ranked_categories": ranked,
            "feature_count": len(numeric_profile),
            "used_formula_features": sorted(
                {
                    feature
                    for weights in CATEGORY_WEIGHTS.values()
                    for feature in weights
                    if feature in numeric_profile
                }
            ),
            "note": MODEL_NOTE,
            "is_definitive_truth": False,
        }


@lru_cache(maxsize=1)
def get_default_feature_profile_scorer() -> FeatureProfileScorer:
    return FeatureProfileScorer()


def score_feature_profile(profile: dict[str, Any]) -> dict[str, Any]:
    return get_default_feature_profile_scorer().score_profile(profile)
