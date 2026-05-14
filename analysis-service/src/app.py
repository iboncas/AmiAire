import base64
import os
import traceback

import cv2
import numpy as np
from flask import Flask, jsonify, render_template_string, request
from werkzeug.exceptions import RequestEntityTooLarge

from pipeline import process_roi
from roi_extraction import extract_roi_from_image_array
from sensor_classifier import (
    SensorImageValidationError,
    classify_sensor_image,
)
from dataset_features import (
    build_empty_image_feature_record,
    build_image_metadata_record,
    get_feature_set_catalog,
)
from taxonomy_model import (
    get_default_taxonomy_scorer,
    get_default_feature_profile_scorer,
    score_sensor_query,
)
from taxonomy_upload_features import extract_features_from_upload


app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024


TAXONOMY_COMPATIBILITY_PAGE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Taxonomy Compatibility Scorer</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #172026;
      --muted: #5d6974;
      --line: #d9e0e6;
      --bg: #f7f8fa;
      --panel: #ffffff;
      --accent: #16697a;
      --accent-soft: #e4f2f5;
      --warn: #8a5a00;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--bg);
    }
    main {
      width: min(1120px, calc(100vw - 32px));
      margin: 32px auto;
    }
    h1 {
      margin: 0 0 8px;
      font-size: 28px;
      line-height: 1.15;
    }
    p {
      margin: 0;
      color: var(--muted);
      line-height: 1.45;
    }
    .toolbar {
      margin-top: 24px;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      align-items: center;
    }
    .upload-panel {
      margin-top: 16px;
      display: grid;
      grid-template-columns: 1fr minmax(220px, 340px) auto;
      gap: 12px;
      align-items: center;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
    }
    .upload-panel strong {
      display: block;
      margin-bottom: 4px;
    }
    input {
      width: 100%;
      min-height: 44px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px 12px;
      font-size: 15px;
      background: var(--panel);
      color: var(--ink);
    }
    input[type="file"] {
      padding: 8px;
    }
    button {
      min-height: 44px;
      border: 0;
      border-radius: 6px;
      padding: 0 18px;
      background: var(--accent);
      color: white;
      font-weight: 700;
      cursor: pointer;
    }
    .grid {
      display: grid;
      grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.65fr);
      gap: 20px;
      margin-top: 24px;
      align-items: start;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
    }
    .panel h2 {
      margin: 0 0 14px;
      font-size: 17px;
    }
    .result-row {
      display: grid;
      grid-template-columns: minmax(190px, 260px) 1fr 76px;
      gap: 12px;
      align-items: center;
      padding: 12px 0;
      border-top: 1px solid var(--line);
    }
    .result-row:first-of-type { border-top: 0; }
    .label {
      font-weight: 700;
      overflow-wrap: anywhere;
    }
    .score {
      text-align: right;
      font-variant-numeric: tabular-nums;
      font-weight: 700;
    }
    .bar {
      height: 12px;
      background: #e8edf1;
      border-radius: 999px;
      overflow: hidden;
    }
    .bar span {
      display: block;
      height: 100%;
      min-width: 2px;
      background: var(--accent);
    }
    dl {
      display: grid;
      grid-template-columns: 132px 1fr;
      gap: 8px 12px;
      margin: 0;
      font-size: 14px;
    }
    dt { color: var(--muted); }
    dd { margin: 0; overflow-wrap: anywhere; }
    .evidence {
      margin-top: 18px;
      border-top: 1px solid var(--line);
      padding-top: 16px;
    }
    .evidence h3 {
      margin: 0 0 10px;
      font-size: 15px;
    }
    .evidence ul {
      margin: 0;
      padding-left: 18px;
      color: var(--muted);
      line-height: 1.45;
    }
    .note {
      margin-top: 14px;
      color: var(--warn);
      font-size: 14px;
    }
    .examples {
      margin-top: 12px;
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    .chip {
      border: 1px solid var(--line);
      background: var(--accent-soft);
      color: var(--accent);
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 13px;
      cursor: pointer;
    }
    .empty {
      margin-top: 24px;
      background: var(--panel);
      border: 1px dashed var(--line);
      border-radius: 8px;
      padding: 18px;
    }
    .preview {
      width: 100%;
      border-radius: 6px;
      border: 1px solid var(--line);
      margin-top: 12px;
      display: block;
    }
    @media (max-width: 780px) {
      main { width: min(100vw - 20px, 1120px); margin: 20px auto; }
      .toolbar, .upload-panel, .grid, .result-row { grid-template-columns: 1fr; }
      .score { text-align: left; }
    }
  </style>
</head>
<body>
  <main>
    <h1>Taxonomy Compatibility Scorer</h1>
    <p>Enter a sensor id or upload a picture to score it directly against the taxonomy formulas. This does not use cluster assignments.</p>

    <form class="toolbar" id="score-form">
      <input id="sensor-input" name="sensor_id" list="sensor-list" placeholder="Paste or type a sensor_id" autocomplete="off">
      <datalist id="sensor-list">
        {% for sensor_id in example_sensor_ids %}
        <option value="{{ sensor_id }}"></option>
        {% endfor %}
      </datalist>
      <button type="submit">Score</button>
    </form>

    <form class="upload-panel" id="upload-form">
      <div>
        <strong>Score Uploaded Picture</strong>
        <p>The app extracts the ROI when possible, computes image features, and scores all taxonomy classes.</p>
      </div>
      <input id="image-input" name="image" type="file" accept="image/*">
      <button type="submit">Upload</button>
    </form>

    <div class="examples">
      {% for sensor_id in example_sensor_ids[:8] %}
      <button class="chip" type="button" data-sensor="{{ sensor_id }}">{{ sensor_id[:10] }}...</button>
      {% endfor %}
    </div>

    <section id="output" class="empty">
      <p>No input scored yet.</p>
    </section>
  </main>

  <script>
    const form = document.getElementById("score-form");
    const uploadForm = document.getElementById("upload-form");
    const input = document.getElementById("sensor-input");
    const imageInput = document.getElementById("image-input");
    const output = document.getElementById("output");

    function fmt(value) {
      return `${Number(value).toFixed(1)}%`;
    }

    function evidenceList(items) {
      if (!items || !items.length) return "<p>No evidence terms available.</p>";
      const rendered = items.map((item) => {
        const direction = item.z >= 0 ? "higher" : "lower";
        return `<li>${direction} <code>${item.feature}</code>: z=${Number(item.z).toFixed(2)}, contribution=${Number(item.contribution).toFixed(2)}</li>`;
      });
      return `<ul>${rendered.join("")}</ul>`;
    }

    function sideBody(data) {
      if (data.source_type === "image") {
        return `
          <dt>ROI detected</dt><dd>${data.roi_detected ? "yes" : "no, full image used"}</dd>
          <dt>Particles</dt><dd>${data.analysis?.num_contours ?? ""}</dd>
          <dt>Area %</dt><dd>${Number(data.analysis?.area_percentage ?? 0).toFixed(4)}</dd>
          <dt>PM10 estimate</dt><dd>${Number(data.pollution?.concentration_standard_pm10 ?? 0).toFixed(2)}</dd>
          <dt>PM2.5 estimate</dt><dd>${Number(data.pollution?.concentration_standard_pm25 ?? 0).toFixed(2)}</dd>
          <dt>Formula features</dt><dd>${data.used_formula_features?.length ?? ""}</dd>
        `;
      }
      return `
        <dt>Sensor</dt><dd>${data.metadata.sensor_id || ""}</dd>
        <dt>Image</dt><dd>${data.metadata.image_id || ""}</dd>
        <dt>Rows</dt><dd>${data.matched_rows}</dd>
        <dt>Capture</dt><dd>${data.metadata.capture_datetime || ""}</dd>
        <dt>Station</dt><dd>${data.metadata.official_station_name || data.metadata.official_station_id || ""}</dd>
        <dt>Record PM10</dt><dd>${data.metadata.record_pm10 || ""}</dd>
        <dt>Record PM2.5</dt><dd>${data.metadata.record_pm25 || ""}</dd>
      `;
    }

    function render(data) {
      if (data.status !== "ok") {
        output.className = "empty";
        output.innerHTML = `<p>${data.message || "Input could not be scored."}</p>`;
        return;
      }

      const rows = data.ranked_categories.map((item) => `
        <div class="result-row">
          <div class="label">${item.label || item.category}</div>
          <div class="bar"><span style="width: ${Math.max(0, Math.min(100, item.percentage))}%"></span></div>
          <div class="score">${fmt(item.percentage)}</div>
        </div>
      `).join("");

      const top = data.ranked_categories[0];
      const preview = data.preview_b64
        ? `<img class="preview" src="data:image/png;base64,${data.preview_b64}" alt="Uploaded image preview">`
        : "";

      output.className = "grid";
      output.innerHTML = `
        <section class="panel">
          <h2>Compatibility Percentages</h2>
          ${rows}
          <div class="evidence">
            <h3>Top Evidence For ${(top.label || top.category)}</h3>
            ${evidenceList(top.evidence)}
          </div>
          <p class="note">${data.note}</p>
        </section>
        <aside class="panel">
          <h2>${data.source_type === "image" ? "Image Summary" : "Sensor Summary"}</h2>
          <dl>${sideBody(data)}</dl>
          ${preview}
        </aside>
      `;
    }

    async function score(sensorId) {
      output.className = "empty";
      output.innerHTML = "<p>Scoring...</p>";
      const response = await fetch(`/taxonomy-score?sensor_id=${encodeURIComponent(sensorId)}`);
      render(await response.json());
    }

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      score(input.value);
    });

    uploadForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const file = imageInput.files[0];
      if (!file) {
        output.className = "empty";
        output.innerHTML = "<p>Please choose an image first.</p>";
        return;
      }
      output.className = "empty";
      output.innerHTML = "<p>Extracting image features...</p>";
      const payload = new FormData();
      payload.append("image", file);
      const response = await fetch("/taxonomy-score-image", { method: "POST", body: payload });
      render(await response.json());
    });

    document.querySelectorAll(".chip").forEach((button) => {
      button.addEventListener("click", () => {
        input.value = button.dataset.sensor;
        score(input.value);
      });
    });
  </script>
</body>
</html>
"""


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


@app.get('/taxonomy-compatibility')
def taxonomy_compatibility_page():
    example_sensor_ids = get_default_taxonomy_scorer().sensor_ids[:24]
    return render_template_string(
        TAXONOMY_COMPATIBILITY_PAGE,
        example_sensor_ids=example_sensor_ids,
    )


@app.get('/taxonomy-score')
def taxonomy_score_endpoint():
    sensor_id = request.args.get('sensor_id', '')
    result = score_sensor_query(sensor_id)
    if result.get('status') == 'ok':
        result['source_type'] = 'sensor'
    return jsonify(result)


@app.post('/taxonomy-score-image')
def taxonomy_score_image_endpoint():
    uploaded = request.files.get('image')
    if uploaded is None:
        return jsonify({'status': 'error', 'message': 'No image file was uploaded.'}), 400

    extracted = extract_features_from_upload(uploaded.read(), uploaded.filename or 'uploaded_image')
    if extracted.get('status') != 'ok':
        return jsonify(extracted), 400

    result = get_default_feature_profile_scorer().score_profile(extracted['feature_profile'])
    if result.get('status') != 'ok':
        return jsonify(result), 400

    result.update(
        {
            'source_type': 'image',
            'roi_detected': extracted['roi_detected'],
            'analysis': extracted['analysis'],
            'pollution': extracted['pollution'],
            'preview_b64': extracted['preview_b64'],
            'roi_b64': extracted['roi_b64'],
            'overlay_b64': extracted['overlay_b64'],
            'binary_mask_b64': extracted['binary_mask_b64'],
        }
    )
    return jsonify(result)


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
    image_metadata = payload.get('metadata') if isinstance(payload.get('metadata'), dict) else {}
    contextual_data = payload.get('contextual_data') if isinstance(payload.get('contextual_data'), dict) else {}

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
        failed_metadata = build_image_metadata_record(
            metadata=image_metadata,
            roi_shape=None,
            roi_detected=False,
            analysis_success=False,
            segmentation_success=False,
            failure_reason='roi_not_detected',
        )
        return jsonify({
            'success': False,
            'error': 'No se ha detectado la región de interés, por favor prueba de nuevo',
            'dataset_outputs': {
                'execution_scope': ['phase_1', 'phase_2', 'phase_3', 'phase_4'],
                'images_metadata': failed_metadata,
                'particles': [],
                'image_features': build_empty_image_feature_record(
                    failed_metadata,
                    contextual_data=contextual_data,
                ),
                'feature_sets': get_feature_set_catalog(),
            },
        }), 422

    pipeline_results = process_roi(
        roi,
        model_type=model_type,
        image_metadata=image_metadata,
        contextual_data=contextual_data,
    )

    return jsonify({
        'success': True,
        'contour_image_b64': encode_png_b64(image_with_contour) if image_with_contour is not None else '',
        'roi_image_b64': encode_png_b64(roi),
        'analysis_results': pipeline_results['analysis_results'],
        'pollution_data': pipeline_results['pollution_data'],
        'pollution_level': pipeline_results['classification'],
        'pollution_levels': pipeline_results.get('classifications', {}),
        'taxonomy_model': pipeline_results.get('taxonomy_model'),
        'binary_b64': pipeline_results['binary_mask_b64'],
        'overlay_b64': pipeline_results['overlay_b64'],
        'validation': validation,
        'dataset_outputs': pipeline_results['dataset_outputs'],
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8000'))
    app.run(host='0.0.0.0', port=port)
