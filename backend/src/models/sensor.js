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

function buildPollutionLabel(concentration) {
    const value = numberOrNull(concentration);
    if (value === null || value < 0) return 'Sin datos';
    if (value <= 10) return 'Nivel de contaminación Muy bueno, menos de 10 μg/m³';
    if (value < 20) return 'Nivel de contaminación Bueno, entre 10 to 19 μg/m³';
    if (value < 50) return 'Nivel de contaminación Moderado, entre 20 to 49 ug/m^3';
    if (value < 100) return 'Nivel de contaminación Malo, entre 50 to 99 μg/m³';
    if (value < 150) return 'Nivel de contaminación Muy Malo, entre 100 to 150 μg/m³';
    return 'Nivel de contaminación Extremo, mas de 150 μg/m³';
}

/**
 * Maps MongoDB sensor document to frontend format
 */
function mapSensorToFrontend(doc) {
    const legacyConcentration =
        numberOrNull(doc['Concentración estándar']) ??
        numberOrNull(doc['Concentracion estándar']) ??
        numberOrNull(doc['Concentración estandar']) ??
        numberOrNull(doc['Concentracion estandar']) ??
        numberOrNull(doc['concentration']);
    const pm25Raw =
        numberOrNull(doc['PM2.5']) ??
        numberOrNull(doc['PM25']) ??
        numberOrNull(doc['pm25']) ??
        numberOrNull(doc['pm2.5']);
    const pm10Raw = numberOrNull(doc['PM10']) ?? numberOrNull(doc['pm10']);
    const pm25 = pm25Raw ?? legacyConcentration;
    const pm10 = pm10Raw ?? legacyConcentration;
    const latitude =
        numberOrNull(doc['Localización latitud']) ?? numberOrNull(doc['Localizacion latitud']);
    const longitude =
        numberOrNull(doc['Localización longitud']) ?? numberOrNull(doc['Localizacion longitud']);
    const effectiveConcentration = pm25Raw ?? pm10Raw ?? legacyConcentration;
    const pollutionLabel = buildPollutionLabel(effectiveConcentration);

    return {
        id: doc._id.toString(),
        nombre: `Sensor ${doc._id.toString().slice(-6)}`,
        ubicacion: {
            latitud: latitude ?? Number.NaN,
            longitud: longitude ?? Number.NaN,
        },
        nivelPolucion: pollutionLabel,
        metricas: {
            concentracion: effectiveConcentration ?? 0,
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
