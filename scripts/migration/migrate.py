import json
import base64
import uuid
from pymongo import MongoClient
from minio import Minio
from minio.error import S3Error
from dotenv import load_dotenv
import os
from io import BytesIO
from bson import ObjectId, decode_all
from bson.binary import Binary
from tqdm import tqdm

# Load env vars
load_dotenv()


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            "Set it in your shell or .env file before running the migration."
        )
    return value

# MongoDB
mongo_client = MongoClient(require_env("MONGO_URI"))
db = mongo_client["tfg"]
collection = db["records"]

# MinIO
minio_client = Minio(
    require_env("MINIO_ENDPOINT"),
    access_key=require_env("MINIO_ACCESS_KEY"),
    secret_key=require_env("MINIO_SECRET_KEY"),
    secure=False
)

bucket_name = require_env("MINIO_BUCKET")

input_path = "../../new_data.bson"


def load_data(path):
    _, ext = os.path.splitext(path.lower())

    if ext == ".json":
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            return loaded if isinstance(loaded, list) else [loaded]

    if ext == ".bson":
        with open(path, "rb") as f:
            return decode_all(f.read())

    raise ValueError(f"Unsupported file extension '{ext}'. Use .json or .bson.")


def decode_image_value(value):
    if isinstance(value, str):
        return base64.b64decode(value)
    if isinstance(value, (bytes, bytearray, Binary)):
        return bytes(value)
    raise ValueError("Unsupported image format in 'Imagen de entrada'")


data = load_data(input_path)

print(f"Starting migration of {len(data)} records...")

# Wrap the data loop with tqdm
for record in tqdm(data, desc="Migrating records", unit="record"):
    try:
        # Extract and decode image (base64 text in JSON, binary in BSON)
        image_value = record.pop("Imagen de entrada")
        image_bytes = decode_image_value(image_value)

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

        # Transform schema: Rename "Concentración estándar" to "PM10"
        if "Concentración estándar" in record:
            record["PM10"] = record.pop("Concentración estándar")

        # Create "PM2.5" as duplicate of "PM10"
        if "PM10" in record:
            record["PM2.5"] = record["PM10"]

        # Split "Nivel de polución" into two attributes
        if "Nivel de polución" in record:
            pollution_level = record.pop("Nivel de polución")
            record["Nivel de polución PM10"] = pollution_level
            record["Nivel de polución PM2.5"] = pollution_level

        # Fix MongoDB ObjectId if present
        if "_id" in record and isinstance(record["_id"], dict) and "$oid" in record["_id"]:
            record["_id"] = ObjectId(record["_id"]["$oid"])

        # Insert into MongoDB
        collection.insert_one(record)

    except (S3Error, Exception) as e:
        print(f"Error migrating record: {e}")

print("Migration completed!")
