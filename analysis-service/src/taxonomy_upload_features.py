from __future__ import annotations

import base64
import io
import math
import uuid
from typing import Any

import numpy as np
from PIL import Image, ImageDraw
from skimage import color, exposure, filters, measure, morphology, transform, util


STANDARDIZED_ROI_SIZE = (1000, 1000)
ORIENTATION_BINS = 18

COLOR_FEATURE_COLUMNS = [
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
    "roi_lab_l_mean",
    "roi_lab_l_std",
    "roi_lab_a_mean",
    "roi_lab_a_std",
    "roi_lab_b_mean",
    "roi_lab_b_std",
    "colorfulness",
    "particle_mask_mean_rgb_contrast",
    "particle_mask_mean_v_contrast",
]


def decode_uploaded_image(file_bytes: bytes) -> np.ndarray | None:
    try:
        image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    except Exception:
        return None
    return np.asarray(image, dtype=np.uint8)


def encode_png_b64(image_rgb: np.ndarray | None) -> str:
    if image_rgb is None:
        return ""
    clipped = np.clip(image_rgb, 0, 255).astype(np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(clipped).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def extract_roi(image_rgb: np.ndarray) -> tuple[np.ndarray, bool, np.ndarray]:
    gray = color.rgb2gray(image_rgb)
    threshold = max(float(filters.threshold_otsu(gray)), 0.55)
    mask = gray >= threshold
    mask = morphology.remove_small_objects(mask, min_size=max(64, int(mask.size * 0.005)))
    mask = morphology.remove_small_holes(mask, area_threshold=max(64, int(mask.size * 0.003)))

    labels = measure.label(mask)
    regions = measure.regionprops(labels)
    if not regions:
        return image_rgb, False, image_rgb

    h, w = gray.shape
    min_area = 0.05 * h * w
    candidates = [region for region in regions if region.area >= min_area]
    if not candidates:
        return image_rgb, False, image_rgb

    region = max(candidates, key=lambda item: item.area)
    minr, minc, maxr, maxc = region.bbox
    pad_y = int(0.02 * (maxr - minr))
    pad_x = int(0.02 * (maxc - minc))
    minr = max(0, minr - pad_y)
    minc = max(0, minc - pad_x)
    maxr = min(h, maxr + pad_y)
    maxc = min(w, maxc + pad_x)

    roi = image_rgb[minr:maxr, minc:maxc]
    preview = image_rgb.copy()
    preview_image = Image.fromarray(preview)
    draw = ImageDraw.Draw(preview_image)
    draw.rectangle((minc, minr, maxc, maxr), outline=(0, 180, 90), width=max(2, int(min(h, w) * 0.004)))
    return roi, True, np.asarray(preview_image, dtype=np.uint8)


def resize_rgb(image_rgb: np.ndarray) -> np.ndarray:
    resized = transform.resize(
        image_rgb,
        STANDARDIZED_ROI_SIZE,
        order=3,
        mode="reflect",
        preserve_range=True,
        anti_aliasing=True,
    )
    return np.clip(resized, 0, 255).astype(np.uint8)


def preprocess_gray(roi_rgb: np.ndarray) -> np.ndarray:
    gray = color.rgb2gray(roi_rgb)
    blurred = filters.gaussian(gray, sigma=10.0, preserve_range=True)
    bg_removed = gray - blurred
    bg_removed = exposure.rescale_intensity(bg_removed, out_range=(0.0, 1.0))
    p_low, p_high = np.percentile(bg_removed, [0, 20])
    if p_high <= p_low:
        rescaled = bg_removed
    else:
        rescaled = exposure.rescale_intensity(bg_removed, in_range=(p_low, p_high), out_range=(0.0, 1.0))
    clahe = exposure.equalize_adapthist(rescaled, clip_limit=0.004, nbins=12)
    return util.img_as_ubyte(clahe)


def segment_particles(gray_u8: np.ndarray) -> tuple[np.ndarray, list[Any]]:
    gray_float = gray_u8.astype(np.float64) / 255.0
    threshold = filters.threshold_sauvola(gray_float, window_size=21, k=0.18)
    binary = gray_float <= threshold

    labels = measure.label(binary)
    regions = measure.regionprops(labels, intensity_image=gray_u8)
    filtered_regions = []
    for region in regions:
        area = float(region.area)
        solidity = float(region.solidity or 0.0)
        minor_axis = float(region.minor_axis_length or 0.0)
        major_axis = float(region.major_axis_length or 0.0)
        aspect_ratio = major_axis / minor_axis if minor_axis > 0 else major_axis
        feret = float(getattr(region, "feret_diameter_max", 0.0) or 0.0)
        if not (0.0 <= area <= 300.0):
            continue
        if not (0.3 <= solidity <= 1.0):
            continue
        if not (0.0 <= aspect_ratio <= 4.0):
            continue
        if not (0.0 <= feret <= 50.0):
            continue
        filtered_regions.append(region)

    mask = np.zeros_like(gray_u8, dtype=bool)
    for region in filtered_regions:
        coords = region.coords
        mask[coords[:, 0], coords[:, 1]] = True
    return mask, filtered_regions


def summarize(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {suffix: None for suffix in ("median", "iqr", "p25", "p75", "p90", "mean", "std")}
    array = np.asarray(values, dtype=np.float64)
    p25, med, p75, p90 = np.percentile(array, [25, 50, 75, 90])
    return {
        "median": float(med),
        "iqr": float(p75 - p25),
        "p25": float(p25),
        "p75": float(p75),
        "p90": float(p90),
        "mean": float(np.mean(array)),
        "std": float(np.std(array)),
    }


def orientation_metrics(orientations: list[float]) -> dict[str, float | None]:
    if not orientations:
        return {"orientation_entropy": None, "circular_variance": None}
    angles = np.asarray(orientations, dtype=np.float64)
    hist, _ = np.histogram(angles, bins=ORIENTATION_BINS, range=(-math.pi / 2.0, math.pi / 2.0))
    probabilities = hist[hist > 0] / hist.sum()
    entropy = float(-np.sum(probabilities * np.log2(probabilities))) if probabilities.size else None
    mean_resultant_length = float(np.abs(np.mean(np.exp(1j * 2.0 * angles))))
    return {"orientation_entropy": entropy, "circular_variance": float(1.0 - mean_resultant_length)}


def particle_records(regions: list[Any], gray_u8: np.ndarray) -> list[dict[str, float]]:
    records = []
    for region in regions:
        perimeter = float(region.perimeter or 0.0)
        area = float(region.area)
        major_axis = float(region.major_axis_length or 0.0)
        minor_axis = float(region.minor_axis_length or 0.0)
        aspect_ratio = major_axis / minor_axis if minor_axis > 0 else major_axis
        coords = region.coords
        intensities = gray_u8[coords[:, 0], coords[:, 1]].astype(np.float64) if coords.size else np.array([])
        raw_circularity = (4.0 * math.pi * area / (perimeter**2)) if perimeter > 0 else 0.0
        records.append(
            {
                "area": area,
                "solidity": float(region.solidity or 0.0),
                "aspect_ratio": float(aspect_ratio),
                "feret": float(getattr(region, "feret_diameter_max", 0.0) or 0.0),
                "equivalent_diameter": float(region.equivalent_diameter_area or 0.0),
                "eccentricity": float(region.eccentricity or 0.0),
                "circularity": float(min(max(raw_circularity, 0.0), 1.0)),
                "mean_intensity": float(np.mean(intensities)) if intensities.size else 0.0,
                "orientation": float(region.orientation or 0.0),
            }
        )
    return records


def compute_color_features(roi_rgb: np.ndarray, particle_mask: np.ndarray) -> dict[str, Any]:
    color_features: dict[str, Any] = {column: None for column in COLOR_FEATURE_COLUMNS}
    rgb_float = roi_rgb.astype(np.float64)
    bgr_float = rgb_float[:, :, ::-1]

    for channel_name, channel_index in (("b", 0), ("g", 1), ("r", 2)):
        color_features[f"roi_{channel_name}_mean"] = float(np.mean(bgr_float[:, :, channel_index]))
        color_features[f"roi_{channel_name}_std"] = float(np.std(bgr_float[:, :, channel_index]))

    hsv = color.rgb2hsv(roi_rgb).astype(np.float64)
    hsv_scaled = np.stack([hsv[:, :, 0] * 179.0, hsv[:, :, 1] * 255.0, hsv[:, :, 2] * 255.0], axis=2)
    for channel_name, channel_index in (("h", 0), ("s", 1), ("v", 2)):
        color_features[f"roi_{channel_name}_mean"] = float(np.mean(hsv_scaled[:, :, channel_index]))
        color_features[f"roi_{channel_name}_std"] = float(np.std(hsv_scaled[:, :, channel_index]))

    lab = color.rgb2lab(roi_rgb).astype(np.float64)
    lab_scaled = np.stack(
        [
            lab[:, :, 0] * 255.0 / 100.0,
            lab[:, :, 1] + 128.0,
            lab[:, :, 2] + 128.0,
        ],
        axis=2,
    )
    for channel_name, channel_index in (("l", 0), ("a", 1), ("b", 2)):
        color_features[f"roi_lab_{channel_name}_mean"] = float(np.mean(lab_scaled[:, :, channel_index]))
        color_features[f"roi_lab_{channel_name}_std"] = float(np.std(lab_scaled[:, :, channel_index]))

    red = rgb_float[:, :, 0]
    green = rgb_float[:, :, 1]
    blue = rgb_float[:, :, 2]
    rg = red - green
    yb = (0.5 * (red + green)) - blue
    color_features["colorfulness"] = float(
        np.sqrt(np.std(rg) ** 2 + np.std(yb) ** 2)
        + 0.3 * np.sqrt(np.mean(rg) ** 2 + np.mean(yb) ** 2)
    )

    if np.any(particle_mask) and np.any(~particle_mask):
        particle_pixels = rgb_float[particle_mask]
        background_pixels = rgb_float[~particle_mask]
        particle_mean_rgb = np.mean(particle_pixels, axis=0)
        background_mean_rgb = np.mean(background_pixels, axis=0)
        color_features["particle_mask_mean_rgb_contrast"] = float(np.mean(np.abs(particle_mean_rgb - background_mean_rgb)))
        color_features["particle_mask_mean_v_contrast"] = float(
            abs(np.mean(hsv_scaled[:, :, 2][particle_mask]) - np.mean(hsv_scaled[:, :, 2][~particle_mask]))
        )

    return color_features


def overlay_particles(roi_rgb: np.ndarray, regions: list[Any]) -> np.ndarray:
    image = Image.fromarray(roi_rgb.copy())
    draw = ImageDraw.Draw(image)
    for region in regions:
        minr, minc, maxr, maxc = region.bbox
        draw.rectangle((minc, minr, maxc, maxr), outline=(0, 180, 90), width=2)
    return np.asarray(image, dtype=np.uint8)


def extract_features_from_upload(file_bytes: bytes, filename: str = "") -> dict[str, Any]:
    image_rgb = decode_uploaded_image(file_bytes)
    if image_rgb is None:
        return {"status": "error", "message": "The uploaded file could not be decoded as an image."}

    roi_raw, roi_detected, preview = extract_roi(image_rgb)
    roi_rgb = resize_rgb(roi_raw)
    gray_u8 = preprocess_gray(roi_rgb)
    particle_mask, regions = segment_particles(gray_u8)
    records = particle_records(regions, gray_u8)

    roi_area_px = int(gray_u8.shape[0] * gray_u8.shape[1])
    total_particle_area = float(sum(record["area"] for record in records))
    feature_profile: dict[str, Any] = {
        "image_id": f"upload_{uuid.uuid4().hex[:12]}",
        "sensor_id": filename or "uploaded_image",
        "roi_area_px": roi_area_px,
        "num_particles": len(records),
        "area_percentage": float((total_particle_area / roi_area_px) * 100.0) if roi_area_px else 0.0,
        "particle_density": float(len(records) / roi_area_px) if roi_area_px else 0.0,
        "mean_pixel_intensity": float(np.mean(gray_u8)),
        "std_pixel_intensity": float(np.std(gray_u8)),
        "zero_particle_flag": bool(len(records) == 0),
    }
    feature_profile.update(orientation_metrics([record["orientation"] for record in records]))

    for source_key, feature_prefix in (
        ("area", "area"),
        ("solidity", "solidity"),
        ("aspect_ratio", "aspect_ratio"),
        ("feret", "feret"),
        ("equivalent_diameter", "equivalent_diameter"),
        ("eccentricity", "eccentricity"),
        ("circularity", "circularity"),
        ("mean_intensity", "mean_intensity"),
    ):
        summary = summarize([record[source_key] for record in records])
        for suffix, value in summary.items():
            feature_profile[f"{feature_prefix}_{suffix}"] = value

    feature_profile.update(compute_color_features(roi_rgb, particle_mask))

    particle_count = len(records)
    area_percentage = float(feature_profile["area_percentage"])
    pm10_estimate = 6.763489480198955 + 0.8 * area_percentage
    pm25_estimate = 5.412905369227905 + 0.45 * area_percentage

    return {
        "status": "ok",
        "roi_detected": roi_detected,
        "feature_profile": feature_profile,
        "analysis": {
            "num_contours": particle_count,
            "area_percentage": area_percentage,
            "total_area": int(total_particle_area),
        },
        "pollution": {
            "concentration_standard_pm10": float(pm10_estimate),
            "concentration_standard_pm25": float(pm25_estimate),
        },
        "preview_b64": encode_png_b64(preview),
        "roi_b64": encode_png_b64(roi_rgb),
        "overlay_b64": encode_png_b64(overlay_particles(roi_rgb, regions)),
        "binary_mask_b64": encode_png_b64((particle_mask.astype(np.uint8) * 255)),
    }
