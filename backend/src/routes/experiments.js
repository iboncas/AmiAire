import express from 'express';
import { Client as MinioClient } from 'minio';
import { getDatabase } from '../config/database.js';

const router = express.Router();

const MINIO_ENDPOINT = process.env.MINIO_ENDPOINT || 'localhost';
const MINIO_PORT = Number(process.env.MINIO_PORT || 9000);
const MINIO_ACCESS_KEY = process.env.MINIO_ACCESS_KEY || 'minioadmin';
const MINIO_SECRET_KEY = process.env.MINIO_SECRET_KEY || 'minioadmin';
const MINIO_BUCKET = 'images';
const MINIO_PUBLIC_BASE_URL = process.env.MINIO_PUBLIC_BASE_URL || 'http://localhost:9000';

const minioClient = new MinioClient({
    endPoint: MINIO_ENDPOINT,
    port: MINIO_PORT,
    useSSL: false,
    accessKey: MINIO_ACCESS_KEY,
    secretKey: MINIO_SECRET_KEY,
});

function parseImagePayload(imageValue) {
    if (!imageValue || typeof imageValue !== 'string') return null;

    const dataUrlMatch = imageValue.match(/^data:(image\/[a-zA-Z0-9.+-]+);base64,(.+)$/);
    if (dataUrlMatch) {
        const [, mimeType, payload] = dataUrlMatch;
        return { mimeType, payload };
    }

    return { mimeType: 'image/png', payload: imageValue };
}

function getExtensionFromMime(mimeType) {
    if (mimeType === 'image/jpeg') return 'jpg';
    if (mimeType === 'image/webp') return 'webp';
    return 'png';
}

async function uploadInputImageToMinio(inputImageB64) {
    const parsed = parseImagePayload(inputImageB64);
    if (!parsed) return null;

    const { mimeType, payload } = parsed;
    let buffer;
    try {
        buffer = Buffer.from(payload, 'base64');
    } catch {
        throw new Error('Imagen de entrada inválida en base64');
    }

    if (!buffer || buffer.length === 0) {
        throw new Error('Imagen de entrada vacía');
    }

    const exists = await minioClient.bucketExists(MINIO_BUCKET);
    if (!exists) {
        throw new Error(`Bucket '${MINIO_BUCKET}' no existe en MinIO`);
    }

    const ext = getExtensionFromMime(mimeType);
    const objectName = `${Date.now()}-${Math.random().toString(36).slice(2)}.${ext}`;

    await minioClient.putObject(MINIO_BUCKET, objectName, buffer, buffer.length, {
        'Content-Type': mimeType,
    });

    const normalizedBase = MINIO_PUBLIC_BASE_URL.replace(/\/+$/, '');
    return `${normalizedBase}/${MINIO_BUCKET}/${objectName}`;
}

router.post('/experimentos', async (req, res) => {
    try {
        const {
            startDate,
            endDate,
            latitude,
            longitude,
            concentration,
            pollutionLevel,
            inputImageB64,
            analysisResults,
        } = req.body || {};

        if (!startDate || !endDate) {
            return res.status(400).json({ success: false, error: 'Faltan fechas del experimento' });
        }

        if (
            typeof latitude !== 'number' ||
            typeof longitude !== 'number' ||
            !Number.isFinite(latitude) ||
            !Number.isFinite(longitude)
        ) {
            return res.status(400).json({ success: false, error: 'Coordenadas inválidas' });
        }

        if (typeof concentration !== 'number' || Number.isNaN(concentration) || concentration < 0) {
            return res.status(400).json({ success: false, error: 'Concentración inválida' });
        }

        const db = getDatabase();
        const collection = db.collection(process.env.MONGODB_COLLECTION || 'records');
        const inputImageUrl = inputImageB64 ? await uploadInputImageToMinio(inputImageB64) : null;

        const doc = {
            'Fecha de inicio': startDate,
            'Fecha de recogida': endDate,
            'Localización longitud': longitude,
            'Localización latitud': latitude,
            'Número de contornos detectados': Number(analysisResults?.numContours || 0),
            'Porcentaje de área detectada': Number(analysisResults?.areaPercentage || 0),
            'Concentración estándar': concentration,
            'Nivel de polución': pollutionLevel || 'Sin clasificar',
            'Imagen de entrada': inputImageUrl,
        };

        const result = await collection.insertOne(doc);

        res.status(201).json({
            success: true,
            id: result.insertedId.toString(),
            imageUrl: inputImageUrl,
        });
    } catch (error) {
        console.error('Error in POST /api/experimentos:', error);
        res.status(500).json({
            success: false,
            error: 'Error al guardar el experimento',
            message: error.message,
        });
    }
});

export default router;
