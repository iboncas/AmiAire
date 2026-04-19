import { getDatabase } from '../config/database.js';
import { ObjectId } from 'mongodb';

function getConfiguredCollections() {
    const configured = (process.env.MONGODB_COLLECTION || '')
        .split(',')
        .map((name) => name.trim())
        .filter(Boolean);

    // Keep compatibility with legacy datasets while ensuring new records are visible.
    if (configured.length) return configured;
    return ['records', 'sensores'];
}

function numberOrNull(value) {
    if (typeof value === 'number' && Number.isFinite(value)) return value;
    if (typeof value === 'string') {
        const parsed = Number.parseFloat(value);
        if (Number.isFinite(parsed)) return parsed;
    }
    return null;
}

function textOrNull(value) {
    if (typeof value !== 'string') return null;
    const trimmed = value.trim();
    return trimmed ? trimmed : null;
}

/**
 * Maps MongoDB sensor document to frontend format
 */
function mapSensorToFrontend(doc) {
    const pm25 =
        numberOrNull(doc['PM2.5']) ??
        numberOrNull(doc['PM25']) ??
        numberOrNull(doc['pm25']) ??
        numberOrNull(doc['pm2.5']);
    const pm10 = numberOrNull(doc['PM10']) ?? numberOrNull(doc['pm10']);
    const latitude =
        numberOrNull(doc['Localización latitud']) ?? numberOrNull(doc['Localizacion latitud']);
    const longitude =
        numberOrNull(doc['Localización longitud']) ?? numberOrNull(doc['Localizacion longitud']);
    const effectiveConcentration = pm25 ?? pm10 ?? 0;
    const pollutionLabel =
        textOrNull(doc['Nivel de polución PM2.5']) ??
        textOrNull(doc['Nivel de polución PM10']) ??
        'Sin datos';

    return {
        id: doc._id.toString(),
        nombre: `Sensor ${doc._id.toString().slice(-6)}`,
        ubicacion: {
            latitud: latitude ?? Number.NaN,
            longitud: longitude ?? Number.NaN,
        },
        nivelPolucion: pollutionLabel,
        metricas: {
            concentracion: effectiveConcentration,
            pm25,
            pm10,
        },
        fechaInicio: doc['Fecha de inicio'],
        fechaRecogida: doc['Fecha de recogida'],
        imagen: doc['Imagen de entrada'],
    };
}

/**
 * Get all sensors from MongoDB
 */
export async function getAllSensors() {
    try {
        const db = getDatabase();
        const collections = getConfiguredCollections();
        const docsById = new Map();

        for (const collectionName of collections) {
            const docs = await db.collection(collectionName).find({}).toArray();
            for (const doc of docs) {
                docsById.set(doc._id.toString(), doc);
            }
        }

        return Array.from(docsById.values()).map(mapSensorToFrontend);
    } catch (error) {
        console.error('Error fetching sensors:', error);
        throw error;
    }
}

/**
 * Get sensor by ID
 */
export async function getSensorById(id) {
    try {
        const db = getDatabase();
        const collections = getConfiguredCollections();
        const objectId = new ObjectId(id);
        let sensor = null;

        for (const collectionName of collections) {
            sensor = await db.collection(collectionName).findOne({ _id: objectId });
            if (sensor) break;
        }

        if (!sensor) {
            return null;
        }

        return mapSensorToFrontend(sensor);
    } catch (error) {
        console.error('Error fetching sensor by ID:', error);
        throw error;
    }
}
