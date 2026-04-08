import express from 'express';
import dotenv from 'dotenv';
import { Client as MinioClient } from 'minio';
import { ObjectId } from 'mongodb';
import { getDatabase } from '../config/database.js';

dotenv.config();

const router = express.Router();

const MINIO_ENDPOINT = process.env.MINIO_ENDPOINT || 'localhost';
const MINIO_PORT = Number(process.env.MINIO_PORT || 9000);
const MINIO_ACCESS_KEY = process.env.MINIO_ACCESS_KEY || 'minioadmin';
const MINIO_SECRET_KEY = process.env.MINIO_SECRET_KEY || 'minioadmin';
const MINIO_BUCKET = process.env.MINIO_BUCKET || 'images';

const minioClient = new MinioClient({
    endPoint: MINIO_ENDPOINT,
    port: MINIO_PORT,
    useSSL: false,
    accessKey: MINIO_ACCESS_KEY,
    secretKey: MINIO_SECRET_KEY,
});

function parseMinioUrl(url) {
    if (!url || typeof url !== 'string') return null;
    try {
        const parsed = new URL(url);
        const parts = parsed.pathname.split('/').filter(Boolean);
        if (parts.length >= 2) {
            return { bucket: parts[0], object: parts.slice(1).join('/') };
        }
        return null;
    } catch {
        return null;
    }
}

function getContentType(objectName) {
    const lower = objectName.toLowerCase();
    if (lower.endsWith('.png')) return 'image/png';
    if (lower.endsWith('.jpg') || lower.endsWith('.jpeg')) return 'image/jpeg';
    if (lower.endsWith('.webp')) return 'image/webp';
    return 'application/octet-stream';
}

async function fetchImageBuffer(bucket, objectName) {
    const stream = await minioClient.getObject(bucket, objectName);
    const chunks = [];
    for await (const chunk of stream) {
        chunks.push(chunk);
    }
    return Buffer.concat(chunks);
}

async function handleFetchImages(ids, res) {
    const validIds = ids.filter((id) => ObjectId.isValid(id));
    const objectIds = validIds.map((id) => new ObjectId(id));

    if (!objectIds.length) {
        return res.json([]);
    }

    const db = getDatabase();
    const collection = db.collection(process.env.MONGODB_COLLECTION || 'records');
    const docs = await collection
        .find({ _id: { $in: objectIds } }, { projection: { 'Imagen de entrada': 1 } })
        .toArray();

    const images = [];
    for (const doc of docs) {
        if (!doc['Imagen de entrada']) continue;
        const info = parseMinioUrl(doc['Imagen de entrada']);
        const bucket = info?.bucket || MINIO_BUCKET;
        const objectName = info?.object || doc['Imagen de entrada'];
        try {
            const buffer = await fetchImageBuffer(bucket, objectName);
            images.push({
                id: doc._id.toString(),
                base64: buffer.toString('base64'),
            });
        } catch (err) {
            console.error(`Failed to fetch image ${objectName}:`, err);
        }
    }

    return res.json(images);
}

async function handleEstimateImages(ids, res) {
    const validIds = ids.filter((id) => ObjectId.isValid(id));
    const objectIds = validIds.map((id) => new ObjectId(id));

    if (!objectIds.length) {
        return res.json({
            requestedIds: ids.length,
            validIds: 0,
            foundImages: 0,
            estimatedBytes: 0,
        });
    }

    const db = getDatabase();
    const collection = db.collection(process.env.MONGODB_COLLECTION || 'records');
    const docs = await collection
        .find({ _id: { $in: objectIds } }, { projection: { 'Imagen de entrada': 1 } })
        .toArray();

    let foundImages = 0;
    let estimatedBytes = 0;

    for (const doc of docs) {
        if (!doc['Imagen de entrada']) continue;
        const info = parseMinioUrl(doc['Imagen de entrada']);
        const bucket = info?.bucket || MINIO_BUCKET;
        const objectName = info?.object || doc['Imagen de entrada'];

        try {
            const stat = await minioClient.statObject(bucket, objectName);
            foundImages += 1;
            estimatedBytes += Number(stat?.size || 0);
        } catch (err) {
            console.error(`Failed to stat image ${objectName}:`, err);
        }
    }

    return res.json({
        requestedIds: ids.length,
        validIds: validIds.length,
        foundImages,
        estimatedBytes,
    });
}

router.get('/imagen', async (req, res) => {
    try {
        const id = typeof req.query.id === 'string' ? req.query.id : '';
        if (!id) {
            return res.status(400).json({ success: false, error: 'Missing id' });
        }

        const db = getDatabase();
        const collection = db.collection(process.env.MONGODB_COLLECTION || 'records');
        const doc = await collection.findOne(
            { _id: new ObjectId(id) },
            { projection: { 'Imagen de entrada': 1 } }
        );

        if (!doc || !doc['Imagen de entrada']) {
            return res.status(404).json({ success: false, error: 'Imagen no encontrada' });
        }

        const info = parseMinioUrl(doc['Imagen de entrada']);
        const bucket = info?.bucket || MINIO_BUCKET;
        const objectName = info?.object || doc['Imagen de entrada'];

        const stream = await minioClient.getObject(bucket, objectName);
        res.setHeader('Content-Type', getContentType(objectName));
        stream.on('error', (err) => {
            console.error('MinIO stream error:', err);
            res.status(500).end();
        });
        stream.pipe(res);
    } catch (error) {
        console.error('Error in GET /api/imagen:', error);
        res.status(500).json({
            success: false,
            error: 'Error al obtener la imagen',
            message: error.message,
        });
    }
});

router.get('/imagenes', async (req, res) => {
    try {
        const idsParam = typeof req.query.ids === 'string' ? req.query.ids : '';
        if (!idsParam) {
            return res.status(400).json({ success: false, error: 'Missing ids' });
        }

        const ids = idsParam.split(',').map((id) => id.trim()).filter(Boolean);
        return handleFetchImages(ids, res);
    } catch (error) {
        console.error('Error in GET /api/imagenes:', error);
        res.status(500).json({
            success: false,
            error: 'Error al obtener imágenes',
            message: error.message,
        });
    }
});

router.post('/imagenes', async (req, res) => {
    try {
        const rawIds = Array.isArray(req.body?.ids) ? req.body.ids : [];
        const ids = rawIds
            .map((id) => (typeof id === 'string' ? id.trim() : ''))
            .filter(Boolean);
        if (!ids.length) {
            return res.status(400).json({ success: false, error: 'Missing ids' });
        }

        return handleFetchImages(ids, res);
    } catch (error) {
        console.error('Error in POST /api/imagenes:', error);
        res.status(500).json({
            success: false,
            error: 'Error al obtener imágenes',
            message: error.message,
        });
    }
});

router.post('/imagenes/estimacion', async (req, res) => {
    try {
        const rawIds = Array.isArray(req.body?.ids) ? req.body.ids : [];
        const ids = rawIds
            .map((id) => (typeof id === 'string' ? id.trim() : ''))
            .filter(Boolean);
        if (!ids.length) {
            return res.status(400).json({ success: false, error: 'Missing ids' });
        }

        return handleEstimateImages(ids, res);
    } catch (error) {
        console.error('Error in POST /api/imagenes/estimacion:', error);
        res.status(500).json({
            success: false,
            error: 'Error al estimar imágenes',
            message: error.message,
        });
    }
});

export default router;
