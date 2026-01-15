import json
import base64
import uuid
from pymongo import MongoClient
from minio import Minio
from minio.error import S3Error
from dotenv import load_dotenv
import os
from io import BytesIO
from bson import ObjectId
from tqdm import tqdm

# Load env vars
load_dotenv()

# MongoDB
mongo_client = MongoClient(os.getenv("MONGO_URI"))
db = mongo_client["tfg"]
collection = db["records"]

# MinIO
minio_client = Minio(
    os.getenv("MINIO_ENDPOINT"),
    access_key=os.getenv("MINIO_ACCESS_KEY"),
    secret_key=os.getenv("MINIO_SECRET_KEY"),
    secure=False
)

bucket_name = os.getenv("MINIO_BUCKET")

# Load JSON data
with open("../../AQ_database_filtered_june_2087.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"Starting migration of {len(data)} records...")

# Wrap the data loop with tqdm
for record in tqdm(data, desc="Migrating records", unit="record"):
    try:
        # Extract and decode base64 image
        image_base64 = record.pop("Imagen de entrada")
        image_bytes = base64.b64decode(image_base64)

        # Generate unique object name
        object_name = f"{uuid.uuid4()}.png"

        # Upload to MinIO
        minio_client.put_object(
            bucket_name=bucket_name,
            object_name=object_name,
            data=BytesIO(image_bytes),
            length=len(image_bytes),
            content_type="image/png"
        )

        # Add MinIO reference to document
        record["Imagen de entrada"] = f"http://localhost:9000/{bucket_name}/{object_name}"

        # Fix MongoDB ObjectId if present
        if "_id" in record and isinstance(record["_id"], dict) and "$oid" in record["_id"]:
            record["_id"] = ObjectId(record["_id"]["$oid"])

        # Insert into MongoDB
        collection.insert_one(record)

    except (S3Error, Exception) as e:
        print(f"Error migrating record: {e}")

print("Migration completed!")
