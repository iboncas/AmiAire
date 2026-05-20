#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
import traceback
from urllib.parse import urlencode
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from pymongo import MongoClient, UpdateOne


REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_SRC = REPO_ROOT / "analysis-service" / "src"
if str(ANALYSIS_SRC) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_SRC))

from pipeline import process_roi  # noqa: E402
from roi_extraction import extract_roi_from_image_array  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill 'Posibles fuentes contaminantes' in MongoDB records "
            "using the existing analysis-service taxonomy pipeline."
        )
    )
    parser.add_argument(
        "--mongo-uri",
        default=os.getenv("MONGO_URI") or os.getenv("MONGODB_URI"),
        help="MongoDB connection string.",
    )
    parser.add_argument(
        "--db",
        default=os.getenv("MONGODB_DATABASE", "tfg"),
        help="MongoDB database name.",
    )
    parser.add_argument(
        "--collection",
        default=os.getenv("MONGODB_COLLECTION", "records"),
        help="MongoDB collection name.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional max number of documents to process. 0 means no limit.",
    )
    parser.add_argument(
        "--skip",
        type=int,
        default=0,
        help="Optional number of matching documents to skip before processing.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=25,
        help="How many updates to buffer before writing to MongoDB.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recompute taxonomy even for documents that already have it.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze and report, but do not write changes to MongoDB.",
    )
    parser.add_argument(
        "--backend-base-url",
        default=os.getenv("BACKEND_BASE_URL", "http://localhost:3001"),
        help="Backend base URL used to fetch stored images through /api/imagen.",
    )
    return parser.parse_args()


def require_arg(value: str | None, message: str) -> str:
    if value and value.strip():
        return value.strip()
    raise SystemExit(message)


def decode_image_from_url(image_url: str) -> np.ndarray | None:
    request = urllib.request.Request(
        image_url,
        headers={"User-Agent": "taxonomy-backfill/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        image_bytes = response.read()

    if not image_bytes:
        return None

    np_buffer = np.frombuffer(image_bytes, np.uint8)
    return cv2.imdecode(np_buffer, cv2.IMREAD_COLOR)


def decode_image_for_record(record_id: str, image_url: str, backend_base_url: str) -> np.ndarray | None:
    backend_url = backend_base_url.rstrip("/") + "/api/imagen?" + urlencode({"id": record_id})

    last_error: Exception | None = None
    for candidate_url in (backend_url, image_url):
        try:
            image = decode_image_from_url(candidate_url)
            if image is not None:
                return image
        except Exception as err:
            last_error = err

    if last_error:
        raise last_error
    return None


def build_query(force: bool) -> dict[str, Any]:
    base_conditions: list[dict[str, Any]] = [
        {"Imagen de entrada": {"$exists": True, "$type": "string", "$ne": ""}},
    ]
    if not force:
        base_conditions.append(
            {
                "$or": [
                    {"Posibles fuentes contaminantes": {"$exists": False}},
                    {"Posibles fuentes contaminantes": None},
                ]
            }
        )
    return {"$and": base_conditions}


def main() -> None:
    args = parse_args()
    mongo_uri = require_arg(args.mongo_uri, "Missing Mongo URI. Set MONGO_URI or pass --mongo-uri.")

    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=10_000)
    db = client[args.db]
    collection = db[args.collection]

    query = build_query(args.force)
    total_matches = collection.count_documents(query)
    print(f"Collection: {args.db}.{args.collection}")
    print(f"Matching documents: {total_matches}")

    cursor = (
        collection.find(query, {"Imagen de entrada": 1, "Posibles fuentes contaminantes": 1})
        .skip(max(args.skip, 0))
    )
    if args.limit > 0:
        cursor = cursor.limit(args.limit)

    updates: list[UpdateOne] = []
    processed = 0
    updated = 0
    skipped = 0
    failed = 0

    for doc in cursor:
        processed += 1
        image_url = doc.get("Imagen de entrada")
        if not isinstance(image_url, str) or not image_url.strip():
            skipped += 1
            print(f"[skip] {doc['_id']} missing image URL")
            continue

        try:
            image_bgr = decode_image_for_record(
                str(doc["_id"]),
                image_url,
                args.backend_base_url,
            )
            if image_bgr is None:
                skipped += 1
                print(f"[skip] {doc['_id']} could not decode image")
                continue

            _image_with_contour, roi = extract_roi_from_image_array(image_bgr)
            if roi is None:
                skipped += 1
                print(f"[skip] {doc['_id']} ROI not detected")
                continue

            pipeline_results = process_roi(roi, model_type="PM10")
            taxonomy_model = pipeline_results.get("taxonomy_model")
            if not taxonomy_model:
                skipped += 1
                print(f"[skip] {doc['_id']} taxonomy model unavailable")
                continue

            updated += 1
            print(
                f"[ok] {doc['_id']} -> "
                f"{taxonomy_model.get('top_category_label', 'sin categoria')}"
            )

            if not args.dry_run:
                updates.append(
                    UpdateOne(
                        {"_id": doc["_id"]},
                        {
                            "$set": {
                                "Posibles fuentes contaminantes": taxonomy_model,
                            }
                        },
                    )
                )
                if len(updates) >= max(args.batch_size, 1):
                    result = collection.bulk_write(updates, ordered=False)
                    print(f"[write] modified={result.modified_count}")
                    updates.clear()
        except urllib.error.URLError as err:
            failed += 1
            print(f"[error] {doc['_id']} image download failed: {err}")
        except Exception:
            failed += 1
            print(f"[error] {doc['_id']} unexpected failure")
            traceback.print_exc()

    if updates and not args.dry_run:
        result = collection.bulk_write(updates, ordered=False)
        print(f"[write] modified={result.modified_count}")

    print(
        "Summary: "
        f"processed={processed} updated={updated} skipped={skipped} failed={failed} "
        f"dry_run={args.dry_run}"
    )


if __name__ == "__main__":
    main()
