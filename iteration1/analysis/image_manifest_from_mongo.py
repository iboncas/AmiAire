#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path

from common import ensure_directory, write_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Export an image_id to image_path manifest from MongoDB records.")
    parser.add_argument("--mongo-uri", default=os.getenv("MONGO_URI") or os.getenv("MONGODB_URI"), help="MongoDB connection string")
    parser.add_argument("--db", default=os.getenv("MONGODB_DATABASE", "tfg"), help="MongoDB database name")
    parser.add_argument("--collection", default=os.getenv("MONGODB_COLLECTION", "records"), help="MongoDB collection name")
    parser.add_argument("--output-csv", default="iteration1/output/dataset/image_manifest.csv", help="Where to write the manifest CSV")
    args = parser.parse_args()

    if not args.mongo_uri:
        try:
            from dotenv import load_dotenv

            load_dotenv(".env")
        except ImportError:
            pass
        args.mongo_uri = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")

    if not args.mongo_uri:
        raise SystemExit("Missing Mongo URI. Set MONGO_URI or pass --mongo-uri.")

    try:
        from pymongo import MongoClient
    except ImportError as error:
        raise SystemExit("pymongo is required to export the image manifest.") from error

    output_csv = Path(args.output_csv).resolve()
    ensure_directory(output_csv.parent)

    client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=10_000)
    collection = client[args.db][args.collection]

    rows = []
    for doc in collection.find({}, {"Imagen de entrada": 1}):
        image_id = str(doc.get("_id"))
        image_path = doc.get("Imagen de entrada") or ""
        if not image_id or not image_path:
            continue
        rows.append(
            {
                "image_id": image_id,
                "image_path": image_path,
            }
        )

    if not rows:
        raise SystemExit("No manifest rows were exported from MongoDB.")

    write_csv(output_csv, rows, ["image_id", "image_path"])
    print(f"Exported {len(rows)} image references to {output_csv}")


if __name__ == "__main__":
    main()
