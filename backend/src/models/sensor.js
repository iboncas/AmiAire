import { getDatabase } from '../config/database.js';

/**
 * Maps MongoDB sensor document to frontend format
 */
function mapSensorToFrontend(doc) {
    return {
        id: doc._id.toString(),
        nombre: `Sensor ${doc._id.toString().slice(-6)}`,
        ubicacion: {
            latitud: doc['Localización latitud'],
            longitud: doc['Localización longitud']
        },
        nivelPolucion: doc['Nivel de polución PM2.5'] || doc['Nivel de polución PM10'] || 'Sin datos',
        metricas: {
            concentracion: doc['PM2.5'] || doc['PM10'] || 0
        },
        fechaInicio: doc['Fecha de inicio'],
        fechaRecogida: doc['Fecha de recogida'],
        imagen: doc['Imagen de entrada']
    };
}

/**
 * Get all sensors from MongoDB
 */
export async function getAllSensors() {
    try {
        const db = getDatabase();
        const collection = db.collection(process.env.MONGODB_COLLECTION || 'sensores');

        const sensors = await collection.find({}).toArray();

        return sensors.map(mapSensorToFrontend);
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
        const collection = db.collection(process.env.MONGODB_COLLECTION || 'sensores');

        const { ObjectId } = await import('mongodb');
        const sensor = await collection.findOne({ _id: new ObjectId(id) });

        if (!sensor) {
            return null;
        }

        return mapSensorToFrontend(sensor);
    } catch (error) {
        console.error('Error fetching sensor by ID:', error);
        throw error;
    }
}
