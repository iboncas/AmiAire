import base64
import json
import os
from json import JSONDecodeError

import cv2
import numpy as np
from skimage import exposure, filters, measure
from skimage.util import img_as_ubyte

DEFAULT_REGRESSION_MODELS = {
    "PM10": {"slope": 5.912886205097057e-05, "intercept": 6.763489480198955},
    "PM25": {"slope": 0.00021507963691545865, "intercept": 5.412905369227905},
}


def convert_to_grayscale_8bit_inmemory(image_bgr: np.ndarray, target_size: tuple = (1000, 1000)) -> np.ndarray:
    if image_bgr is None or not isinstance(image_bgr, np.ndarray):
        raise ValueError("Input must be a valid numpy array representing an image.")

    if image_bgr.ndim == 3:
        if image_bgr.shape[2] == 4:
            image_bgr = cv2.cvtColor(image_bgr, cv2.COLOR_BGRA2BGR)
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    elif image_bgr.ndim == 2:
        gray = image_bgr
    else:
        raise ValueError("Unsupported image format")

    return cv2.resize(gray, target_size, interpolation=cv2.INTER_CUBIC)


def improve_background_inmemory(gray_image: np.ndarray, kernel_size: tuple = (21, 21), sigma: float = 10.0) -> np.ndarray:
    if gray_image is None or gray_image.ndim != 2:
        raise ValueError("Input must be a valid 2D grayscale numpy array")

    blurred = cv2.GaussianBlur(gray_image, kernel_size, sigmaX=sigma)
    subtracted = gray_image.astype(np.float32) - blurred.astype(np.float32)
    result_norm = cv2.normalize(subtracted, None, 0, 255, cv2.NORM_MINMAX)
    return result_norm.astype(np.uint8)


def rescale_intensity_inmemory(gray_image: np.ndarray, in_range_percent=(0, 20)) -> np.ndarray:
    if gray_image is None or gray_image.ndim != 2:
        raise ValueError("Must be a valid grayscale image")

    img_float = gray_image.astype(np.float32) / 255.0
    p_low, p_high = np.percentile(img_float, in_range_percent)
    rescaled = exposure.rescale_intensity(img_float, in_range=(p_low, p_high))
    return img_as_ubyte(rescaled)


def clahe_skimage_inmemory(gray_image: np.ndarray, clip_limit: float = 0.004, nbins: int = 12) -> np.ndarray:
    if gray_image is None or gray_image.ndim != 2:
        raise ValueError("Must be a valid grayscale image")

    img_float = gray_image.astype(np.float32) / 255.0
    clahe_img = exposure.equalize_adapthist(img_float, clip_limit=clip_limit, nbins=nbins)
    return img_as_ubyte(clahe_img)


def apply_sauvola_threshold_inmemory(gray_image: np.ndarray, window_size: int = 21, k: float = 0.18, invert: bool = False) -> np.ndarray:
    if gray_image is None or gray_image.ndim != 2:
        raise ValueError("Must be a valid grayscale image")

    img_float = gray_image.astype(np.float32) / 255.0
    thresh = filters.threshold_sauvola(img_float, window_size=window_size, k=k)
    binary = (img_float > thresh).astype(np.uint8) * 255

    if invert:
        binary = cv2.bitwise_not(binary)

    return binary


def analyze_particles_inmemory(binary_image: np.ndarray, original_bgr: np.ndarray = None, filter_params: dict = None):
    if binary_image is None or binary_image.ndim != 2:
        raise ValueError("binary_image must be a 2D grayscale binary")

    if filter_params is None:
        filter_params = {
            'min_area': 0.00,
            'max_area': 300,
            'min_solidity': 0.3,
            'max_solidity': 1.0,
            'min_aspect_ratio': 0.0,
            'max_aspect_ratio': 4.0,
            'min_feret': 0.0,
            'max_feret': 50.0,
        }

    label_image = measure.label(binary_image > 0)
    regions = measure.regionprops(label_image)

    filtered_regions = []
    for region in regions:
        area = region.area
        solidity = region.solidity if hasattr(region, 'solidity') else 0.0
        if region.minor_axis_length > 0:
            aspect_ratio = region.major_axis_length / region.minor_axis_length
        else:
            aspect_ratio = region.major_axis_length

        feret_diameter = getattr(region, 'feret_diameter_max', 0.0)

        if not (filter_params['min_area'] <= area <= filter_params['max_area']):
            continue
        if not (filter_params['min_solidity'] <= solidity <= filter_params['max_solidity']):
            continue
        if not (filter_params['min_aspect_ratio'] <= aspect_ratio <= filter_params['max_aspect_ratio']):
            continue
        if not (filter_params['min_feret'] <= feret_diameter <= filter_params['max_feret']):
            continue

        filtered_regions.append(region)

    filtered_mask = np.zeros_like(binary_image, dtype=np.uint8)
    for region in filtered_regions:
        coords = region.coords
        filtered_mask[coords[:, 0], coords[:, 1]] = 255

    image_area = filtered_mask.shape[0] * filtered_mask.shape[1]
    particle_area = int(np.count_nonzero(filtered_mask))
    area_percentage = (particle_area / image_area) * 100 if image_area > 0 else 0

    overlay_bgr = None
    if original_bgr is not None and original_bgr.ndim == 3:
        overlay_bgr = original_bgr.copy()
        for region in filtered_regions:
            (minr, minc, maxr, maxc) = region.bbox
            cv2.rectangle(overlay_bgr, (minc, minr), (maxc, maxr), (0, 255, 0), 2)

    return {
        'num_contours': len(filtered_regions),
        'area_percentage': float(area_percentage),
        'total_area': particle_area,
        'filtered_mask': filtered_mask,
        'overlay_bgr': overlay_bgr,
    }


def load_regression_models():
    params_path = os.path.join(os.path.dirname(__file__), 'regression_params.json')
    try:
        with open(params_path, 'r', encoding='utf-8') as f:
            params = json.load(f)
        if isinstance(params, dict) and "PM10" in params:
            return params
    except (FileNotFoundError, JSONDecodeError, TypeError, ValueError):
        pass
    return DEFAULT_REGRESSION_MODELS.copy()


def polution_level_inmemory(
    analysis_results: dict,
    model_type: str = "PM10",
    papersensor_size: tuple = (0.06, 0.06),
    particle_diameter_microns: float = 10.0,
    particle_density_g_cm3: float = 1.65,
):
    particle_diameter_m = particle_diameter_microns * 1e-6
    particle_density_kg_m3 = particle_density_g_cm3 * 1000.0

    area_sensor_m2 = papersensor_size[0] * papersensor_size[1]
    area_particle_m2 = np.pi * (particle_diameter_m / 2) ** 2
    volume_sensor_m3 = papersensor_size[0] * papersensor_size[1] * papersensor_size[0]
    volume_particle_m3 = (4 / 3) * np.pi * (particle_diameter_m / 2) ** 3

    particles = (area_sensor_m2 * (analysis_results['area_percentage'] / 100)) / area_particle_m2
    particles_per_contour = particles / analysis_results['num_contours'] if analysis_results['num_contours'] > 0 else 0

    mass_particles_kg = particles * volume_particle_m3 * particle_density_kg_m3
    concentration_sensor_kg_m3 = mass_particles_kg / volume_sensor_m3 if volume_sensor_m3 > 0 else 0
    concentration_sensor_ug_m3 = concentration_sensor_kg_m3 * 1e9

    models = load_regression_models()
    model = models.get(model_type, models.get("PM10", DEFAULT_REGRESSION_MODELS["PM10"]))
    slope = float(model.get("slope", DEFAULT_REGRESSION_MODELS["PM10"]["slope"]))
    intercept = float(model.get("intercept", DEFAULT_REGRESSION_MODELS["PM10"]["intercept"]))
    concentration_standard = intercept + slope * concentration_sensor_ug_m3

    return {
        'model_type': model_type,
        'num_particles': float(particles),
        'concentration_sensor': float(concentration_sensor_ug_m3),
        'particles_per_contour': float(particles_per_contour),
        'concentration_standard': float(concentration_standard),
    }


def classification_inmemory(concentration: float) -> str:
    if concentration <= 10:
        return "Nivel de polución Muy bueno, menos de 10 μg/m³"
    if concentration < 20:
        return "Nivel de polución Bueno, entre 10 to 19 μg/m³"
    if concentration < 50:
        return "Nivel de polución Moderado, entre 20 to 49 ug/m^3"
    if concentration < 100:
        return "Nivel de polución Malo, entre 50 to 99 μg/m³"
    if concentration < 150:
        return "Nivel de polución Muy Malo, entre 100 to 150 μg/m³"
    return "Nivel de polución Extremo, mas de 150 μg/m³"


def process_roi(roi_bgr: np.ndarray, model_type: str = "PM10"):
    gray = convert_to_grayscale_8bit_inmemory(roi_bgr, (1000, 1000))
    bg_improved = improve_background_inmemory(gray, kernel_size=(21, 21), sigma=10.0)
    rescaled = rescale_intensity_inmemory(bg_improved, in_range_percent=(0, 20))
    clahe_result = clahe_skimage_inmemory(rescaled, clip_limit=0.004, nbins=12)
    binary_mask = apply_sauvola_threshold_inmemory(clahe_result, window_size=21, k=0.18, invert=True)
    resized_bgr = cv2.resize(roi_bgr, (1000, 1000), interpolation=cv2.INTER_CUBIC)

    analysis_results = analyze_particles_inmemory(binary_mask, resized_bgr)
    model_type_norm = (model_type or "PM10").upper()
    if model_type_norm not in {"PM10", "PM25"}:
        model_type_norm = "PM10"

    particle_diameter = 10.0 if model_type_norm == "PM10" else 2.5
    pollution_data = polution_level_inmemory(
        analysis_results,
        model_type=model_type_norm,
        particle_diameter_microns=particle_diameter,
        particle_density_g_cm3=1.65,
    )
    classification_str = classification_inmemory(pollution_data['concentration_standard'])

    _, mask_encoded = cv2.imencode('.png', analysis_results['filtered_mask'])
    binary_mask_b64 = base64.b64encode(mask_encoded).decode('utf-8')

    overlay_b64 = ""
    if analysis_results['overlay_bgr'] is not None:
        _, overlay_encoded = cv2.imencode('.png', analysis_results['overlay_bgr'])
        overlay_b64 = base64.b64encode(overlay_encoded).decode('utf-8')

    return {
        "analysis_results": {
            "num_contours": analysis_results["num_contours"],
            "area_percentage": analysis_results["area_percentage"],
            "total_area": analysis_results["total_area"],
        },
        "pollution_data": pollution_data,
        "classification": classification_str,
        "binary_mask_b64": binary_mask_b64,
        "overlay_b64": overlay_b64,
    }
