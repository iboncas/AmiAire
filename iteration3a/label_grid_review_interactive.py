#!/usr/bin/env python3
import argparse
import base64
import csv
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_SRC = REPO_ROOT / "analysis-service" / "src"
DATA_DIR = REPO_ROOT / "data"
if str(ANALYSIS_SRC) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_SRC))
if str(DATA_DIR) not in sys.path:
    sys.path.insert(0, str(DATA_DIR))

from combine import iter_json_array  # type: ignore
from roi_extraction import extract_roi_from_image_array  # type: ignore


WINDOW_NAME = "Grid Review"


def load_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    required = {"image_id", "roi_grid_label", "manual_grid_label"}
    missing = sorted(required - set(fieldnames))
    if missing:
        raise ValueError(f"Missing required columns in {path}: {', '.join(missing)}")
    return rows, fieldnames


def write_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize_mongo_value(value: Any) -> Any:
    if isinstance(value, dict):
        if "$oid" in value:
            return str(value["$oid"])
        if "$numberDouble" in value:
            return float(value["$numberDouble"])
        if "$numberInt" in value:
            return int(value["$numberInt"])
        if "$numberLong" in value:
            return int(value["$numberLong"])
        if "$numberDecimal" in value:
            return float(value["$numberDecimal"])
        return {key: normalize_mongo_value(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [normalize_mongo_value(inner) for inner in value]
    return value


def first_present(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return None


def decode_base64_image(image_b64: str | None) -> np.ndarray | None:
    if not image_b64 or not isinstance(image_b64, str):
        return None
    payload = image_b64.split(",", 1)[1] if image_b64.startswith("data:") and "," in image_b64 else image_b64
    try:
        image_bytes = base64.b64decode(payload)
    except Exception:
        return None
    image_array = np.frombuffer(image_bytes, np.uint8)
    return cv2.imdecode(image_array, cv2.IMREAD_COLOR)


def load_needed_images(combined_json: Path, target_ids: set[str]) -> dict[str, np.ndarray]:
    images: dict[str, np.ndarray] = {}
    for record in iter_json_array(combined_json):
        normalized = normalize_mongo_value(record)
        image_id = str(first_present(normalized, "_id", "id") or "")
        if not image_id or image_id not in target_ids or image_id in images:
            continue
        image_b64 = first_present(
            normalized,
            "Imagen de entrada",
            "imagen",
            "image",
            "base64",
            "imageB64",
            "image_b64",
        )
        image_bgr = decode_base64_image(image_b64)
        if image_bgr is not None:
            images[image_id] = image_bgr
        if len(images) >= len(target_ids):
            break
    return images


def fit_to_height(image: np.ndarray, target_height: int) -> np.ndarray:
    if image is None or image.size == 0:
        return np.full((target_height, target_height, 3), 240, dtype=np.uint8)
    height, width = image.shape[:2]
    if height <= 0 or width <= 0:
        return np.full((target_height, target_height, 3), 240, dtype=np.uint8)
    scale = target_height / float(height)
    target_width = max(1, int(round(width * scale)))
    return cv2.resize(image, (target_width, target_height), interpolation=cv2.INTER_AREA)


def pad_to_height(image: np.ndarray, target_height: int) -> np.ndarray:
    height = image.shape[0]
    if height == target_height:
        return image
    pad_total = max(0, target_height - height)
    pad_top = pad_total // 2
    pad_bottom = pad_total - pad_top
    return cv2.copyMakeBorder(
        image,
        pad_top,
        pad_bottom,
        0,
        0,
        cv2.BORDER_CONSTANT,
        value=(245, 245, 245),
    )


def add_header(canvas: np.ndarray, lines: list[str]) -> np.ndarray:
    header_height = 34 + (28 * len(lines))
    header = np.full((header_height, canvas.shape[1], 3), 250, dtype=np.uint8)
    y = 34
    for line in lines:
        cv2.putText(header, line, (16, y), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (25, 25, 25), 2, cv2.LINE_AA)
        y += 28
    return np.vstack([header, canvas])


def build_preview(image_bgr: np.ndarray | None, image_id: str, predicted_label: str) -> np.ndarray:
    if image_bgr is None:
        canvas = np.full((720, 960, 3), 245, dtype=np.uint8)
        cv2.putText(canvas, "Image not found in combined.json", (60, 360), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 180), 2, cv2.LINE_AA)
        return add_header(canvas, [f"image_id: {image_id}", f"predicted: {predicted_label}"])

    contour_bgr, roi_bgr = extract_roi_from_image_array(image_bgr)
    full_panel = image_bgr if contour_bgr is None else contour_bgr
    roi_panel = roi_bgr if roi_bgr is not None else np.full((300, 300, 3), 255, dtype=np.uint8)

    target_height = 720
    left = fit_to_height(full_panel, target_height)
    right = fit_to_height(roi_panel, target_height)
    left = pad_to_height(left, target_height)
    right = pad_to_height(right, target_height)
    spacer = np.full((target_height, 16, 3), 235, dtype=np.uint8)
    canvas = np.hstack([left, spacer, right])

    lines = [
        f"image_id: {image_id}",
        f"predicted: {predicted_label}",
        "type: [g] grid  [n] no_grid  [s] skip  [q] quit",
    ]
    return add_header(canvas, lines)


def normalize_manual_label(value: str) -> str:
    cleaned = value.strip().lower()
    if cleaned in {"g", "grid"}:
        return "grid"
    if cleaned in {"n", "no_grid", "nogrid", "no-grid"}:
        return "no_grid"
    if cleaned in {"s", "skip", ""}:
        return ""
    if cleaned in {"q", "quit"}:
        return "__quit__"
    return "__invalid__"


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactively label grid/no-grid rows from grid_review_simple.csv.")
    parser.add_argument(
        "--input-csv",
        default="iteration3a/output/grid_review/grid_review_simple.csv",
        help="Minimal review CSV with image_id, roi_grid_label, and manual_grid_label.",
    )
    parser.add_argument(
        "--combined-json",
        default="data/combined.json",
        help="Path to combined.json containing the base64 input images.",
    )
    parser.add_argument(
        "--show-all",
        action="store_true",
        help="Show already labeled rows too. By default only unlabeled rows are shown.",
    )
    args = parser.parse_args()

    input_csv = Path(args.input_csv).resolve()
    combined_json = Path(args.combined_json).resolve()
    rows, fieldnames = load_rows(input_csv)

    target_rows = [row for row in rows if args.show_all or not row.get("manual_grid_label", "").strip()]
    target_ids = {row.get("image_id", "").strip() for row in target_rows if row.get("image_id", "").strip()}
    images_by_id = load_needed_images(combined_json, target_ids)

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)

    total = len(target_rows)
    completed = 0
    for row in rows:
        current_label = row.get("manual_grid_label", "").strip()
        if not args.show_all and current_label:
            continue

        image_id = row.get("image_id", "").strip()
        predicted_label = row.get("roi_grid_label", "").strip()
        preview = build_preview(images_by_id.get(image_id), image_id, predicted_label)
        cv2.imshow(WINDOW_NAME, preview)
        cv2.waitKey(1)

        prompt = f"[{completed + 1}/{total}] {image_id} predicted={predicted_label} -> g/n/s/q: "
        while True:
            answer = input(prompt)
            normalized = normalize_manual_label(answer)
            if normalized == "__invalid__":
                print("Use g, n, s, or q.")
                continue
            if normalized == "__quit__":
                write_rows(input_csv, rows, fieldnames)
                cv2.destroyAllWindows()
                print(f"Progress saved to {input_csv}")
                return
            row["manual_grid_label"] = normalized
            write_rows(input_csv, rows, fieldnames)
            completed += 1
            break

    cv2.destroyAllWindows()
    print(f"Finished labeling. Saved to {input_csv}")


if __name__ == "__main__":
    main()
