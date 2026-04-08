import base64
import os
import traceback

import cv2
import numpy as np
from flask import Flask, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

from pipeline import process_roi
from roi_extraction import extract_roi_from_image_array
from sensor_classifier import (
    SensorImageValidationError,
    classify_sensor_image,
)


app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024


@app.errorhandler(Exception)
def handle_unexpected_error(err):
    traceback.print_exc()
    return jsonify({
        'success': False,
        'error': 'Internal analysis error',
        'details': str(err),
    }), 500


@app.errorhandler(RequestEntityTooLarge)
def handle_too_large(_err):
    return jsonify({
        'success': False,
        'error': 'Image too large for analysis service',
    }), 413


def decode_base64_image(image_b64: str):
    if not image_b64 or not isinstance(image_b64, str):
        return None

    payload = image_b64
    if ',' in image_b64 and image_b64.startswith('data:'):
        payload = image_b64.split(',', 1)[1]

    try:
        image_bytes = base64.b64decode(payload)
    except Exception:
        return None

    np_data = np.frombuffer(image_bytes, np.uint8)
    image_bgr = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
    return image_bgr


def encode_png_b64(image_bgr):
    ok, encoded = cv2.imencode('.png', image_bgr)
    if not ok:
        return ''
    return base64.b64encode(encoded).decode('utf-8')


@app.get('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'analysis-service'})


@app.post('/validate-sensor-image')
def validate_sensor_image_endpoint():
    payload = request.get_json(silent=True) or {}
    image_b64 = payload.get('image_b64')

    image_bgr = decode_base64_image(image_b64)
    if image_bgr is None:
        return jsonify({'success': False, 'error': 'Invalid image payload'}), 400

    try:
        validation = classify_sensor_image(image_bgr)
    except SensorImageValidationError as err:
        return jsonify({'success': False, 'error': str(err)}), 500

    return jsonify({
        'success': True,
        'data': validation,
    })


@app.post('/process-image')
def process_image_endpoint():
    payload = request.get_json(silent=True) or {}
    image_b64 = payload.get('image_b64')
    model_type = payload.get('model_type', 'PM10')

    image_bgr = decode_base64_image(image_b64)
    if image_bgr is None:
        return jsonify({'success': False, 'error': 'Invalid image payload'}), 400

    try:
        validation = classify_sensor_image(image_bgr)
    except SensorImageValidationError as err:
        return jsonify({'success': False, 'error': str(err)}), 500

    if not validation['is_sensor']:
        return jsonify({
            'success': False,
            'error': 'La imagen subida no parece corresponder a un sensor',
            'validation': validation,
        }), 422

    image_with_contour, roi = extract_roi_from_image_array(image_bgr)
    if roi is None:
        return jsonify({
            'success': False,
            'error': 'No se ha detectado la región de interés, por favor prueba de nuevo',
        }), 422

    pipeline_results = process_roi(roi, model_type=model_type)

    return jsonify({
        'success': True,
        'contour_image_b64': encode_png_b64(image_with_contour) if image_with_contour is not None else '',
        'roi_image_b64': encode_png_b64(roi),
        'analysis_results': pipeline_results['analysis_results'],
        'pollution_data': pipeline_results['pollution_data'],
        'pollution_level': pipeline_results['classification'],
        'binary_b64': pipeline_results['binary_mask_b64'],
        'overlay_b64': pipeline_results['overlay_b64'],
        'validation': validation,
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8000'))
    app.run(host='0.0.0.0', port=port)
