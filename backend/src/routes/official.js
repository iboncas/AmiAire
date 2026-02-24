import express from 'express';
import dotenv from 'dotenv';
import { getDatabase } from '../config/database.js';

dotenv.config();

const router = express.Router();
const CACHE_TTL_MS = 5 * 60 * 1000;
const cacheByRange = new Map();

function normalizeParameterName(name) {
    if (!name || typeof name !== 'string') return '';
    return name.toLowerCase().replace('.', '');
}

function parseDateRange(startDate, endDate) {
    const hasStart = Boolean(startDate);
    const hasEnd = Boolean(endDate);
    if (!hasStart && !hasEnd) return null;

    const start = hasStart ? new Date(`${startDate}T00:00:00.000Z`) : new Date(`${endDate}T00:00:00.000Z`);
    const end = hasEnd ? new Date(`${endDate}T23:59:59.999Z`) : new Date(`${startDate}T23:59:59.999Z`);

    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return null;
    return { start, end };
}

router.get('/estaciones-oficiales', async (req, res) => {
    try {
        const startDate = typeof req.query.startDate === 'string' ? req.query.startDate : '';
        const endDate = typeof req.query.endDate === 'string' ? req.query.endDate : '';
        const cacheKey = `${startDate}|${endDate}`;
        const cached = cacheByRange.get(cacheKey);

        if (cached && Date.now() - cached.cachedAt < CACHE_TTL_MS) {
            return res.json({
                success: true,
                count: cached.data.length,
                data: cached.data
            });
        }

        const db = getDatabase();
        const collection = db.collection('official');

        const range = parseDateRange(startDate, endDate);
        const hasDateFilter = Boolean(range);

        const pipeline = hasDateFilter
            ? [
                { $match: { ts: { $gte: range.start, $lte: range.end } } },
                {
                    $group: {
                        _id: {
                            location_id: '$meta.location_id',
                            parameter_name: '$meta.parameter_name'
                        },
                        avgValue: { $avg: '$value' },
                        minTs: { $min: '$ts' },
                        maxTs: { $max: '$ts' },
                        meta: { $first: '$meta' }
                    }
                },
                {
                    $group: {
                        _id: '$_id.location_id',
                        location_name: { $first: '$meta.location_name' },
                        latitude: { $first: '$meta.latitude' },
                        longitude: { $first: '$meta.longitude' },
                        minTs: { $min: '$minTs' },
                        maxTs: { $max: '$maxTs' },
                        values: {
                            $push: {
                                parameter: '$_id.parameter_name',
                                value: '$avgValue'
                            }
                        }
                    }
                },
                {
                    $project: {
                        _id: 0,
                        location_id: '$_id',
                        location_name: 1,
                        latitude: 1,
                        longitude: 1,
                        minTs: 1,
                        maxTs: 1,
                        values: 1
                    }
                }
            ]
            : [
                { $sort: { 'meta.location_id': 1, 'meta.parameter_name': 1, ts: -1 } },
                {
                    $group: {
                        _id: {
                            location_id: '$meta.location_id',
                            parameter_name: '$meta.parameter_name'
                        },
                        doc: { $first: '$$ROOT' }
                    }
                },
                {
                    $project: {
                        _id: 0,
                        location_id: '$_id.location_id',
                        parameter_name: '$_id.parameter_name',
                        value: '$doc.value',
                        ts: '$doc.ts',
                        meta: '$doc.meta'
                    }
                },
                {
                    $group: {
                        _id: '$location_id',
                        location_name: { $first: '$meta.location_name' },
                        latitude: { $first: '$meta.latitude' },
                        longitude: { $first: '$meta.longitude' },
                        minTs: { $min: '$ts' },
                        maxTs: { $max: '$ts' },
                        values: {
                            $push: {
                                parameter: '$parameter_name',
                                value: '$value'
                            }
                        }
                    }
                },
                {
                    $project: {
                        _id: 0,
                        location_id: '$_id',
                        location_name: 1,
                        latitude: 1,
                        longitude: 1,
                        minTs: 1,
                        maxTs: 1,
                        values: 1
                    }
                }
            ];

        const rows = await collection.aggregate(pipeline, { allowDiskUse: true }).toArray();

        const officialStations = rows.map((row) => {
            const values = Array.isArray(row.values) ? row.values : [];
            const pm25Entry = values.find(v => normalizeParameterName(v.parameter) === 'pm25');
            const pm10Entry = values.find(v => normalizeParameterName(v.parameter) === 'pm10');
            const pm25Value = pm25Entry?.value;
            const pm10Value = pm10Entry?.value;
            const bestConcentration =
                typeof pm25Value === 'number'
                    ? pm25Value
                    : typeof pm10Value === 'number'
                        ? pm10Value
                        : null;

            return {
                id: `official-${row.location_id}`,
                nombre: row.location_name || `Estación ${row.location_id}`,
                ubicacion: {
                    latitud: row.latitude,
                    longitud: row.longitude
                },
                nivelPolucion: 'Oficial',
                metricas: {
                    concentracion: typeof bestConcentration === 'number' ? bestConcentration : null,
                    pm25: typeof pm25Value === 'number' ? pm25Value : null,
                    pm10: typeof pm10Value === 'number' ? pm10Value : null
                },
                fechaInicio: row.minTs || null,
                fechaRecogida: row.maxTs || null,
                type: 'official',
                hasPM25: typeof pm25Value === 'number',
                hasPM10: typeof pm10Value === 'number'
            };
        });

        cacheByRange.set(cacheKey, { data: officialStations, cachedAt: Date.now() });

        res.json({
            success: true,
            count: officialStations.length,
            data: officialStations
        });
    } catch (error) {
        console.error('Error in GET /api/estaciones-oficiales:', error);

        // Attempt one last fallback to cache in case of catastrophic failure
        const startDate = typeof req.query.startDate === 'string' ? req.query.startDate : '';
        const endDate = typeof req.query.endDate === 'string' ? req.query.endDate : '';
        const cacheKey = `${startDate}|${endDate}`;
        const cached = cacheByRange.get(cacheKey);

        if (cached) {
            return res.json({
                success: true,
                count: cached.data.length,
                data: cached.data,
                message: 'Error inesperado. Mostrando datos en caché.'
            });
        }

        res.status(500).json({
            success: false,
            error: 'Error al obtener las estaciones oficiales',
            message: error.message
        });
    }
});

export default router;
