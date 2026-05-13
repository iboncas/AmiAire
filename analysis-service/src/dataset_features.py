import math

import cv2
import numpy as np

STANDARDIZED_ROI_SIZE = (1000, 1000)
SEGMENTATION_METHOD = "classical_cv_grayscale_background_clahe_sauvola_regionprops"
ORIENTATION_BINS = 18

IMAGE_METADATA_FIELDS = [
    "image_id",
    "sensor_id",
    "capture_datetime",
    "collection_datetime",
    "latitude",
    "longitude",
    "image_path",
    "manual_qc_flag",
    "device_type",
    "sensor_exposure_time",
    "paper_type",
    "camera_type",
    "magnification",
    "weather_context",
    "official_station_id",
]

ROI_GRID_METADATA_FIELDS = [
    "roi_grid_label",
    "roi_grid_score",
    "roi_grid_confidence",
    "roi_grid_needs_review",
]

ROI_GRID_FEATURE_FIELDS = [
    "roi_grid_inner_margin_ratio",
    "roi_grid_inner_dark_ratio",
    "roi_grid_horizontal_line_count",
    "roi_grid_vertical_line_count",
    "roi_grid_horizontal_coverage",
    "roi_grid_vertical_coverage",
    "roi_grid_row_peak_count",
    "roi_grid_col_peak_count",
    "roi_grid_spacing_regularity",
]

SUMMARY_FAMILY_MAP = {
    "area_px": "area",
    "solidity": "solidity",
    "aspect_ratio": "aspect_ratio",
    "feret_diameter_max_px": "feret",
    "equivalent_diameter_px": "equivalent_diameter",
    "eccentricity": "eccentricity",
    "circularity": "circularity",
    "mean_intensity": "mean_intensity",
}

SUMMARY_SUFFIXES = ("median", "iqr", "p25", "p75", "p90", "mean", "std")

CORE_IMAGE_FEATURE_SET = [
    "num_particles",
    "area_percentage",
    "particle_density",
    "mean_pixel_intensity",
    "std_pixel_intensity",
    "orientation_entropy",
    "circular_variance",
    "area_median",
    "area_iqr",
    "area_p90",
    "solidity_median",
    "solidity_iqr",
    "aspect_ratio_median",
    "aspect_ratio_iqr",
    "feret_median",
    "feret_p90",
    "equivalent_diameter_median",
    "equivalent_diameter_p90",
    "circularity_median",
    "mean_intensity_median",
]

EXTENDED_IMAGE_FEATURE_SET = CORE_IMAGE_FEATURE_SET + [
    f"{feature}_{suffix}"
    for feature in SUMMARY_FAMILY_MAP.values()
    for suffix in SUMMARY_SUFFIXES
    if f"{feature}_{suffix}" not in CORE_IMAGE_FEATURE_SET
]

PHASE6_DEFAULT_FEATURE_SET = [
    "num_particles",
    "area_percentage",
    "particle_density",
    "mean_pixel_intensity",
    "std_pixel_intensity",
    "orientation_entropy",
    "circular_variance",
    "area_median",
    "area_iqr",
    "area_p90",
    "solidity_median",
    "solidity_iqr",
    "solidity_p90",
    "aspect_ratio_median",
    "aspect_ratio_iqr",
    "aspect_ratio_p90",
    "feret_median",
    "feret_iqr",
    "feret_p90",
    "equivalent_diameter_median",
    "equivalent_diameter_iqr",
    "equivalent_diameter_p90",
    "eccentricity_median",
    "eccentricity_iqr",
    "eccentricity_p90",
    "circularity_median",
    "circularity_iqr",
    "circularity_p90",
    "mean_intensity_median",
    "mean_intensity_iqr",
    "mean_intensity_p90",
]


def _safe_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _scalarize_context_value(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def build_image_metadata_record(
    metadata=None,
    roi_shape=None,
    roi_detected=False,
    analysis_success=False,
    segmentation_success=None,
    failure_reason=None,
    roi_grid_metadata=None,
):
    metadata = metadata or {}
    roi_height = int(roi_shape[0]) if roi_shape else None
    roi_width = int(roi_shape[1]) if roi_shape else None

    record = {field: metadata.get(field) for field in IMAGE_METADATA_FIELDS}
    record["latitude"] = _safe_float(record.get("latitude"))
    record["longitude"] = _safe_float(record.get("longitude"))
    record["roi_detected"] = bool(roi_detected)
    record["roi_width_px"] = roi_width
    record["roi_height_px"] = roi_height
    record["segmentation_method"] = SEGMENTATION_METHOD
    record["analysis_success"] = bool(analysis_success)
    if segmentation_success is None:
        record["segmentation_success"] = bool(analysis_success and roi_detected)
    else:
        record["segmentation_success"] = bool(segmentation_success)
    record["failure_reason"] = failure_reason or ""

    if not record.get("manual_qc_flag"):
        record["manual_qc_flag"] = "pending"

    for field in ROI_GRID_METADATA_FIELDS:
        record[field] = None
    if roi_grid_metadata:
        for field in ROI_GRID_METADATA_FIELDS:
            if field in roi_grid_metadata:
                record[field] = roi_grid_metadata.get(field)

    return record


def compute_blur_score(gray_image):
    laplacian = cv2.Laplacian(gray_image, cv2.CV_64F)
    return float(laplacian.var())


def build_particle_records(filtered_regions, intensity_image, image_id=None):
    particle_records = []

    for index, region in enumerate(filtered_regions, start=1):
        perimeter = float(region.perimeter or 0.0)
        area = float(region.area)
        major_axis_length = float(region.major_axis_length or 0.0)
        minor_axis_length = float(region.minor_axis_length or 0.0)
        aspect_ratio = major_axis_length / minor_axis_length if minor_axis_length > 0 else major_axis_length

        coords = region.coords
        intensities = intensity_image[coords[:, 0], coords[:, 1]].astype(np.float32) if coords.size else np.array([], dtype=np.float32)
        centroid_y, centroid_x = region.centroid
        raw_circularity = (4.0 * math.pi * area / (perimeter ** 2)) if perimeter > 0 else 0.0
        # Region-perimeter estimates on tiny particles can overshoot the theoretical range.
        circularity = min(max(raw_circularity, 0.0), 1.0)

        record = {
            "image_id": image_id,
            "particle_id": f"{image_id}_p{index:05d}" if image_id else f"particle_{index:05d}",
            "area_px": area,
            "perimeter_px": perimeter,
            "equivalent_diameter_px": float(getattr(region, "equivalent_diameter_area", 0.0) or 0.0),
            "major_axis_length_px": major_axis_length,
            "minor_axis_length_px": minor_axis_length,
            "aspect_ratio": float(aspect_ratio),
            "solidity": float(region.solidity or 0.0),
            "eccentricity": float(region.eccentricity or 0.0),
            "feret_diameter_max_px": float(getattr(region, "feret_diameter_max", 0.0) or 0.0),
            "orientation_rad": float(region.orientation or 0.0),
            "circularity": float(circularity),
            "mean_intensity": float(np.mean(intensities)) if intensities.size else 0.0,
            "std_intensity": float(np.std(intensities)) if intensities.size else 0.0,
            "min_intensity": float(np.min(intensities)) if intensities.size else 0.0,
            "max_intensity": float(np.max(intensities)) if intensities.size else 0.0,
            "centroid_x": float(centroid_x),
            "centroid_y": float(centroid_y),
        }
        particle_records.append(record)

    return particle_records


def _summarize_feature(values):
    if not values:
        return {suffix: None for suffix in SUMMARY_SUFFIXES}

    array = np.asarray(values, dtype=np.float64)
    p25, median, p75, p90 = np.percentile(array, [25, 50, 75, 90])
    return {
        "median": float(median),
        "iqr": float(p75 - p25),
        "p25": float(p25),
        "p75": float(p75),
        "p90": float(p90),
        "mean": float(np.mean(array)),
        "std": float(np.std(array)),
    }


def _compute_orientation_metrics(orientations):
    if not orientations:
        return {
            "orientation_entropy": None,
            "circular_variance": None,
        }

    angles = np.asarray(orientations, dtype=np.float64)
    hist, _ = np.histogram(angles, bins=ORIENTATION_BINS, range=(-math.pi / 2.0, math.pi / 2.0))
    probabilities = hist[hist > 0] / hist.sum()
    orientation_entropy = float(-np.sum(probabilities * np.log2(probabilities))) if probabilities.size else None

    mean_resultant_length = float(np.abs(np.mean(np.exp(1j * 2.0 * angles))))
    circular_variance = float(1.0 - mean_resultant_length)

    return {
        "orientation_entropy": orientation_entropy,
        "circular_variance": circular_variance,
    }


def build_empty_image_feature_record(image_metadata, contextual_data=None):
    contextual_data = contextual_data or {}
    record = dict(image_metadata)
    record.update({
        "roi_area_px": None,
        "num_particles": None,
        "area_percentage": None,
        "particle_density": None,
        "mean_pixel_intensity": None,
        "std_pixel_intensity": None,
        "zero_particle_flag": None,
        "blur_score_laplacian": None,
        "orientation_entropy": None,
        "circular_variance": None,
    })

    for feature_prefix in SUMMARY_FAMILY_MAP.values():
        for suffix in SUMMARY_SUFFIXES:
            record[f"{feature_prefix}_{suffix}"] = None

    for field in ROI_GRID_FEATURE_FIELDS:
        record[field] = None

    for key, value in contextual_data.items():
        record[key] = _scalarize_context_value(value)

    return record


def build_image_feature_record(
    image_metadata,
    particle_records,
    standardized_gray,
    contextual_data=None,
    roi_grid_features=None,
):
    contextual_data = contextual_data or {}
    roi_grid_features = roi_grid_features or {}
    roi_height, roi_width = standardized_gray.shape[:2]
    roi_area_px = roi_height * roi_width
    total_particle_area = float(sum(record["area_px"] for record in particle_records))
    num_particles = len(particle_records)

    feature_record = dict(image_metadata)
    feature_record.update({
        "roi_area_px": int(roi_area_px),
        "num_particles": int(num_particles),
        "area_percentage": float((total_particle_area / roi_area_px) * 100.0) if roi_area_px else 0.0,
        "particle_density": float(num_particles / roi_area_px) if roi_area_px else 0.0,
        "mean_pixel_intensity": float(np.mean(standardized_gray)),
        "std_pixel_intensity": float(np.std(standardized_gray)),
        "zero_particle_flag": bool(num_particles == 0),
        "blur_score_laplacian": compute_blur_score(standardized_gray),
    })

    orientation_metrics = _compute_orientation_metrics([
        record["orientation_rad"]
        for record in particle_records
        if record.get("orientation_rad") is not None
    ])
    feature_record.update(orientation_metrics)

    for particle_column, feature_prefix in SUMMARY_FAMILY_MAP.items():
        summaries = _summarize_feature([
            record[particle_column]
            for record in particle_records
            if record.get(particle_column) is not None
        ])
        for suffix, value in summaries.items():
            feature_record[f"{feature_prefix}_{suffix}"] = value

    for key, value in contextual_data.items():
        feature_record[key] = _scalarize_context_value(value)

    for field in ROI_GRID_FEATURE_FIELDS:
        feature_record[field] = roi_grid_features.get(field)

    return feature_record


def get_feature_set_catalog():
    return {
        "core": CORE_IMAGE_FEATURE_SET,
        "extended": EXTENDED_IMAGE_FEATURE_SET,
        "phase6_default": PHASE6_DEFAULT_FEATURE_SET,
    }
