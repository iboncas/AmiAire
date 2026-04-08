import express from 'express';
import { getDatabase } from '../config/database.js';

const router = express.Router();
const OPEN_METEO_URL = 'https://air-quality-api.open-meteo.com/v1/air-quality';
const OPEN_METEO_CONCURRENCY = Number(process.env.OPEN_METEO_CONCURRENCY || 8);
const OPEN_METEO_MAX_ATTEMPTS = Number(process.env.OPEN_METEO_MAX_ATTEMPTS || 2);
const OPEN_METEO_TIMEOUT_MS = Number(process.env.OPEN_METEO_TIMEOUT_MS || 6000);
const OPEN_METEO_CACHE_TTL_MS = Number(process.env.OPEN_METEO_CACHE_TTL_MS || 30 * 60 * 1000);
const openMeteoCache = new Map();

function classifyPollution(value) {
    if (!Number.isFinite(value)) return 'Sin datos';
    if (value >= 150) return 'Extremo';
    if (value >= 50) return 'Alto';
    if (value >= 20) return 'Moderado';
    if (value >= 10) return 'Bueno';
    return 'Bajo';
}

function toNullableMetric(value) {
    if (typeof value === 'number' && Number.isFinite(value)) return value;
    if (typeof value === 'string' && value.trim() !== '') {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : null;
    }
    return null;
}

function normalizeDateInput(value) {
    if (typeof value !== 'string') return null;
    const trimmed = value.trim();
    if (!/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) return null;
    return trimmed;
}

function average(values) {
    if (!Array.isArray(values)) return null;
    const numbers = values
        .map((value) => Number(value))
        .filter((value) => Number.isFinite(value));
    if (!numbers.length) return null;
    const sum = numbers.reduce((acc, value) => acc + value, 0);
    return sum / numbers.length;
}

async function fetchPeriodAverages(lat, lon, startDate, endDate) {
    const cacheKey = `${lat}|${lon}|${startDate}|${endDate}`;
    const cached = openMeteoCache.get(cacheKey);
    if (cached && cached.expiresAt > Date.now()) {
        return cached.value;
    }

    const params = new URLSearchParams({
        latitude: String(lat),
        longitude: String(lon),
        hourly: 'pm10,pm2_5',
        start_date: startDate,
        end_date: endDate,
        timezone: 'auto',
    });
    const url = `${OPEN_METEO_URL}?${params.toString()}`;
    const maxAttempts = Math.max(1, OPEN_METEO_MAX_ATTEMPTS);

    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), OPEN_METEO_TIMEOUT_MS);
        let response;
        try {
            response = await fetch(url, { signal: controller.signal });
        } catch (error) {
            const canRetry = attempt < maxAttempts;
            if (!canRetry) {
                throw error;
            }
            await new Promise((resolve) => setTimeout(resolve, 100 * attempt));
            continue;
        } finally {
            clearTimeout(timeout);
        }
        if (response.ok) {
            const data = await response.json();
            const hourly = data?.hourly || {};
            const value = {
                pm10: average(hourly.pm10),
                pm25: average(hourly.pm2_5),
            };
            openMeteoCache.set(cacheKey, {
                value,
                expiresAt: Date.now() + OPEN_METEO_CACHE_TTL_MS,
            });
            if (openMeteoCache.size > 5000) {
                const now = Date.now();
                for (const [key, entry] of openMeteoCache.entries()) {
                    if (!entry || entry.expiresAt <= now) {
                        openMeteoCache.delete(key);
                    }
                }
            }
            return value;
        }

        const canRetry = response.status === 429 || response.status >= 500;
        if (!canRetry || attempt === maxAttempts) {
            throw new Error(`Open-Meteo returned ${response.status}`);
        }

        const retryAfterHeader = response.headers.get('retry-after');
        const retryAfterSeconds = retryAfterHeader ? Number(retryAfterHeader) : NaN;
        const retryAfterMs = Number.isFinite(retryAfterSeconds) ? retryAfterSeconds * 1000 : 0;
        const waitMs = Math.max(Math.min(retryAfterMs, 1500), 100 * attempt);
        await new Promise((resolve) => setTimeout(resolve, waitMs));
    }

    return { pm10: null, pm25: null };
}

async function mapWithConcurrency(items, concurrency, mapper) {
    const results = new Array(items.length);
    let nextIndex = 0;

    async function worker() {
        while (true) {
            const index = nextIndex;
            nextIndex += 1;
            if (index >= items.length) return;
            results[index] = await mapper(items[index], index);
        }
    }

    const workers = Array.from(
        { length: Math.max(1, Math.min(concurrency, items.length)) },
        () => worker()
    );
    await Promise.all(workers);
    return results;
}

router.get('/estaciones-oficiales', async (req, res) => {
    try {
        const startDateInput = normalizeDateInput(req.query.startDate);
        const endDateInput = normalizeDateInput(req.query.endDate);
        const hasDateFilter = Boolean(startDateInput || endDateInput);
        const startDate = startDateInput || endDateInput;
        const endDate = endDateInput || startDateInput;

        const db = getDatabase();
        const collection = db.collection(process.env.OFFICIAL_COLLECTION || 'official');
        const docs = await collection
            .find(
                {},
                {
                    projection: {
                        _id: 0,
                        id: 1,
                        name: 1,
                        lat: 1,
                        long: 1,
                        pm25: 1,
                        pm10: 1,
                        fetched_at: 1,
                    },
                }
            )
            .toArray();

        const validDocs = docs
            .filter((doc) =>
                doc?.id &&
                doc?.name &&
                Number.isFinite(Number(doc?.lat)) &&
                Number.isFinite(Number(doc?.long))
            );

        const stationPayloads = await mapWithConcurrency(validDocs, OPEN_METEO_CONCURRENCY, async (doc, index) => {
            let pm25 = toNullableMetric(doc.pm25);
            let pm10 = toNullableMetric(doc.pm10);

            if (hasDateFilter && startDate && endDate) {
                try {
                    const averages = await fetchPeriodAverages(
                        Number(doc.lat),
                        Number(doc.long),
                        startDate,
                        endDate
                    );
                    pm25 = averages.pm25;
                    pm10 = averages.pm10;
                } catch (apiError) {
                    console.error(`Open-Meteo error for station ${doc.id}:`, apiError);
                    pm25 = null;
                    pm10 = null;
                }
            }

            const referenceValue = typeof pm25 === 'number' ? pm25 : pm10;
            return {
                id: doc.id || `official-${index + 1}`,
                nombre: doc.name,
                ubicacion: {
                    latitud: Number(doc.lat),
                    longitud: Number(doc.long),
                },
                metricas: {
                    pm10,
                    pm25,
                    concentracion:
                        typeof referenceValue === 'number' ? Number(referenceValue) : undefined,
                },
                nivelPolucion:
                    typeof referenceValue === 'number'
                        ? classifyPollution(referenceValue)
                        : 'Sin datos',
                fechaInicio: hasDateFilter && startDate ? startDate : '',
                fechaRecogida:
                    hasDateFilter && endDate
                        ? endDate
                        : (typeof doc.fetched_at === 'string' ? doc.fetched_at : ''),
                type: 'official',
                hasPM10: typeof pm10 === 'number',
                hasPM25: typeof pm25 === 'number',
            };
        });

        const stations = stationPayloads;

        res.json({
            success: true,
            count: stations.length,
            data: stations,
            source: hasDateFilter ? 'open-meteo-avg' : 'mongodb',
            dateRange: hasDateFilter && startDate && endDate
                ? { startDate, endDate }
                : null,
        });
    } catch (error) {
        console.error('Error in GET /api/estaciones-oficiales:', error);
        res.status(500).json({
            success: false,
            error: 'Error al obtener las estaciones oficiales',
            message: error.message,
        });
    }
});

export default router;
