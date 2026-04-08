import os
from functools import lru_cache

import cv2
import numpy as np
import tensorflow as tf


MODEL_INPUT_SIZE = (128, 128)
DEFAULT_THRESHOLD = 0.5


class SensorImageValidationError(RuntimeError):
    pass


def _model_path() -> str:
    default_path = os.path.join(
        os.path.dirname(__file__),
        '..',
        'models',
        'sensor_classifier.h5',
    )
    return os.path.abspath(os.environ.get('SENSOR_CLASSIFIER_MODEL_PATH', default_path))


@lru_cache(maxsize=1)
def load_sensor_classifier():
    model_path = _model_path()
    if not os.path.exists(model_path):
        raise SensorImageValidationError(
            f'Sensor classifier model not found at {model_path}'
        )

    try:
        return tf.keras.models.load_model(model_path, compile=False)
    except Exception as err:
        raise SensorImageValidationError(
            f'Unable to load sensor classifier model: {err}'
        ) from err


def _prepare_image(image_bgr: np.ndarray) -> np.ndarray:
    if image_bgr is None or not isinstance(image_bgr, np.ndarray):
        raise SensorImageValidationError('Invalid image for sensor classification')

    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(image_rgb, MODEL_INPUT_SIZE, interpolation=cv2.INTER_AREA)
    normalized = resized.astype(np.float32) / 255.0
    return np.expand_dims(normalized, axis=0)


def classify_sensor_image(image_bgr: np.ndarray, threshold: float = DEFAULT_THRESHOLD) -> dict:
    model = load_sensor_classifier()
    image_batch = _prepare_image(image_bgr)

    prediction = model.predict(image_batch, verbose=0)
    sensor_probability = float(np.squeeze(prediction))
    sensor_probability = max(0.0, min(1.0, sensor_probability))
    is_sensor = sensor_probability >= threshold

    return {
        'is_sensor': is_sensor,
        'sensor_probability': sensor_probability,
        'non_sensor_probability': 1.0 - sensor_probability,
        'threshold': threshold,
        'model_input_size': {
            'width': MODEL_INPUT_SIZE[0],
            'height': MODEL_INPUT_SIZE[1],
        },
    }
