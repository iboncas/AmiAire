import math

import cv2
import numpy as np

STANDARDIZED_GRID_SIZE = (1000, 1000)
DEFAULT_INNER_MARGIN_RATIO = 0.08
DEFAULT_BORDER_EXCLUSION_RATIO = 0.02
DEFAULT_DARK_THRESHOLD = 180
MIN_LINE_LENGTH_RATIO = 0.15
MAX_LINE_THICKNESS_RATIO = 0.018
MIN_PEAK_DISTANCE_RATIO = 0.06


def _clip_margin(length: int, ratio: float) -> int:
    if length <= 0:
        return 0
    return max(1, min(length // 4, int(round(length * ratio))))


def _moving_average(values: np.ndarray, window: int) -> np.ndarray:
    if values.size == 0:
        return values
    safe_window = max(1, min(values.size, int(window)))
    kernel = np.ones(safe_window, dtype=np.float64) / float(safe_window)
    return np.convolve(values.astype(np.float64), kernel, mode="same")


def _extract_inner_roi(roi_bgr: np.ndarray, margin_ratio: float) -> tuple[np.ndarray, dict[str, int]]:
    standardized = cv2.resize(roi_bgr, STANDARDIZED_GRID_SIZE, interpolation=cv2.INTER_CUBIC)
    height, width = standardized.shape[:2]
    margin_y = _clip_margin(height, margin_ratio)
    margin_x = _clip_margin(width, margin_ratio)
    inner = standardized[margin_y : height - margin_y, margin_x : width - margin_x]
    bounds = {
        "x0": margin_x,
        "y0": margin_y,
        "x1": width - margin_x,
        "y1": height - margin_y,
    }
    return inner, bounds


def _build_dark_mask(gray_image: np.ndarray) -> np.ndarray:
    blurred = cv2.GaussianBlur(gray_image, (5, 5), 0)
    _, otsu_mask = cv2.threshold(
        blurred,
        0,
        255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
    )
    _, fixed_mask = cv2.threshold(
        blurred,
        DEFAULT_DARK_THRESHOLD,
        255,
        cv2.THRESH_BINARY_INV,
    )
    dark_mask = cv2.bitwise_and(otsu_mask, fixed_mask)
    clean_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    return cv2.morphologyEx(dark_mask, cv2.MORPH_OPEN, clean_kernel, iterations=1)


def _find_line_segments(
    opened_mask: np.ndarray,
    orientation: str,
    border_exclusion_px: int,
) -> list[dict[str, float]]:
    num_labels, _, stats, centroids = cv2.connectedComponentsWithStats(opened_mask, connectivity=8)
    height, width = opened_mask.shape[:2]
    min_length = (width if orientation == "horizontal" else height) * MIN_LINE_LENGTH_RATIO
    max_thickness = max(2.0, (height if orientation == "horizontal" else width) * MAX_LINE_THICKNESS_RATIO)

    segments: list[dict[str, float]] = []
    for index in range(1, num_labels):
        x, y, component_width, component_height, area = stats[index]
        centroid_x, centroid_y = centroids[index]
        length = component_width if orientation == "horizontal" else component_height
        thickness = component_height if orientation == "horizontal" else component_width
        orthogonal_start = y if orientation == "horizontal" else x
        orthogonal_end = y + component_height if orientation == "horizontal" else x + component_width
        orthogonal_limit = height if orientation == "horizontal" else width

        if length < min_length or thickness > max_thickness or area <= 0:
            continue
        if orthogonal_start <= border_exclusion_px or orthogonal_end >= orthogonal_limit - border_exclusion_px:
            continue

        segments.append(
            {
                "x": float(x),
                "y": float(y),
                "width": float(component_width),
                "height": float(component_height),
                "area": float(area),
                "length": float(length),
                "thickness": float(thickness),
                "position": float(centroid_y if orientation == "horizontal" else centroid_x),
            }
        )

    segments.sort(key=lambda item: item["position"])
    return segments


def _count_profile_peaks(profile: np.ndarray, min_distance: int, threshold: float) -> int:
    if profile.size < 3:
        return 0
    peaks = []
    last_peak = -10**9
    for index in range(1, profile.size - 1):
        current = float(profile[index])
        if current < threshold:
            continue
        if current < float(profile[index - 1]) or current < float(profile[index + 1]):
            continue
        if index - last_peak < min_distance:
            if peaks and current > float(profile[peaks[-1]]):
                peaks[-1] = index
                last_peak = index
            continue
        peaks.append(index)
        last_peak = index
    return len(peaks)


def _spacing_regularity(positions: list[float]) -> float:
    if len(positions) < 3:
        return 0.0
    diffs = np.diff(np.asarray(positions, dtype=np.float64))
    mean_gap = float(np.mean(diffs))
    if mean_gap <= 0.0:
        return 0.0
    coeff_var = float(np.std(diffs) / mean_gap)
    return float(max(0.0, 1.0 - coeff_var))


def classify_roi_grid(
    roi_bgr: np.ndarray,
    margin_ratio: float = DEFAULT_INNER_MARGIN_RATIO,
) -> dict[str, float | int | str | bool]:
    if roi_bgr is None or not isinstance(roi_bgr, np.ndarray) or roi_bgr.size == 0:
        return {
            "roi_grid_label": "unknown",
            "roi_grid_score": 0.0,
            "roi_grid_confidence": 0.0,
            "roi_grid_needs_review": True,
            "roi_grid_inner_margin_ratio": float(margin_ratio),
            "roi_grid_inner_dark_ratio": None,
            "roi_grid_horizontal_line_count": None,
            "roi_grid_vertical_line_count": None,
            "roi_grid_horizontal_coverage": None,
            "roi_grid_vertical_coverage": None,
            "roi_grid_row_peak_count": None,
            "roi_grid_col_peak_count": None,
            "roi_grid_spacing_regularity": None,
        }

    inner_bgr, _bounds = _extract_inner_roi(roi_bgr, margin_ratio)
    inner_gray = cv2.cvtColor(inner_bgr, cv2.COLOR_BGR2GRAY)
    dark_mask = _build_dark_mask(inner_gray)
    inner_height, inner_width = dark_mask.shape[:2]

    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(15, inner_width // 18), 1))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(15, inner_height // 18)))
    horizontal_open = cv2.morphologyEx(dark_mask, cv2.MORPH_OPEN, horizontal_kernel, iterations=1)
    vertical_open = cv2.morphologyEx(dark_mask, cv2.MORPH_OPEN, vertical_kernel, iterations=1)

    border_exclusion_px = max(2, int(round(min(inner_width, inner_height) * DEFAULT_BORDER_EXCLUSION_RATIO)))
    horizontal_segments = _find_line_segments(horizontal_open, "horizontal", border_exclusion_px)
    vertical_segments = _find_line_segments(vertical_open, "vertical", border_exclusion_px)

    inner_dark_ratio = float(np.count_nonzero(dark_mask)) / float(inner_height * inner_width)
    horizontal_coverage = (
        float(sum(segment["length"] for segment in horizontal_segments)) / float(inner_width * max(1, len(horizontal_segments)))
        if horizontal_segments
        else 0.0
    )
    vertical_coverage = (
        float(sum(segment["length"] for segment in vertical_segments)) / float(inner_height * max(1, len(vertical_segments)))
        if vertical_segments
        else 0.0
    )

    row_profile = _moving_average(np.mean(dark_mask > 0, axis=1), max(5, inner_height // 60))
    col_profile = _moving_average(np.mean(dark_mask > 0, axis=0), max(5, inner_width // 60))
    min_peak_distance_y = max(10, int(round(inner_height * MIN_PEAK_DISTANCE_RATIO)))
    min_peak_distance_x = max(10, int(round(inner_width * MIN_PEAK_DISTANCE_RATIO)))
    row_peak_threshold = float(max(0.01, np.mean(row_profile) + np.std(row_profile)))
    col_peak_threshold = float(max(0.01, np.mean(col_profile) + np.std(col_profile)))
    row_peak_count = _count_profile_peaks(row_profile, min_peak_distance_y, row_peak_threshold)
    col_peak_count = _count_profile_peaks(col_profile, min_peak_distance_x, col_peak_threshold)

    spacing_regularity = max(
        _spacing_regularity([segment["position"] for segment in horizontal_segments]),
        _spacing_regularity([segment["position"] for segment in vertical_segments]),
    )

    line_score = min(1.0, (len(horizontal_segments) + len(vertical_segments)) / 8.0)
    peak_score = min(1.0, (row_peak_count + col_peak_count) / 8.0)
    structure_score = min(1.0, math.sqrt(max(0.0, horizontal_coverage * vertical_coverage)))
    grid_score = float(
        (0.40 * line_score)
        + (0.20 * peak_score)
        + (0.20 * spacing_regularity)
        + (0.15 * structure_score)
        + (0.05 * min(1.0, inner_dark_ratio / 0.08))
    )

    clear_grid = (
        len(horizontal_segments) >= 2
        and len(vertical_segments) >= 2
        and spacing_regularity >= 0.35
        and (row_peak_count >= 2 or col_peak_count >= 2)
    )
    clear_no_grid = (
        len(horizontal_segments) == 0
        and len(vertical_segments) == 0
        and row_peak_count <= 1
        and col_peak_count <= 1
        and inner_dark_ratio <= 0.015
    )

    if clear_grid or grid_score >= 0.62:
        label = "grid"
    elif clear_no_grid or grid_score <= 0.22:
        label = "no_grid"
    else:
        label = "uncertain"

    confidence = float(min(1.0, abs(grid_score - 0.42) / 0.42))
    needs_review = label == "uncertain" or confidence < 0.45

    return {
        "roi_grid_label": label,
        "roi_grid_score": grid_score,
        "roi_grid_confidence": confidence,
        "roi_grid_needs_review": bool(needs_review),
        "roi_grid_inner_margin_ratio": float(margin_ratio),
        "roi_grid_inner_dark_ratio": float(inner_dark_ratio),
        "roi_grid_horizontal_line_count": int(len(horizontal_segments)),
        "roi_grid_vertical_line_count": int(len(vertical_segments)),
        "roi_grid_horizontal_coverage": float(horizontal_coverage),
        "roi_grid_vertical_coverage": float(vertical_coverage),
        "roi_grid_row_peak_count": int(row_peak_count),
        "roi_grid_col_peak_count": int(col_peak_count),
        "roi_grid_spacing_regularity": float(spacing_regularity),
    }
