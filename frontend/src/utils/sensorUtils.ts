import type { Sensor } from '../types/sensor';

const MAX_POLLUTION = 150;

export function getCategoria(sensor: Sensor): string {
    // 1) If numeric concentration exists, use thresholds
    if (sensor.metricas?.concentracion !== undefined && sensor.metricas.concentracion > 0) {
        const c = sensor.metricas.concentracion;
        if (c >= 150) return 'Extremo';
        if (c >= 50) return 'Alto';
        if (c >= 20) return 'Moderado';
        if (c >= 10) return 'Bueno';
        return 'Bajo'; // < 10 µg/m³
    }
    // 2) Otherwise use the string level
    if (sensor.nivelPolucion && sensor.nivelPolucion !== 'Sin datos') return sensor.nivelPolucion;
    // 3) No data
    return 'SinDatos';
}

export function getColor(sensor: Sensor): string {
    const cat = getCategoria(sensor).toLowerCase();
    if (cat.includes('extremo')) return '#d73027'; // red
    if (cat.includes('alto')) return '#fc8d59'; // orange
    if (cat.includes('moderado')) return '#fee08b'; // yellow
    if (cat.includes('bueno')) return '#91cf60'; // light green (better)
    if (cat.includes('bajo')) return '#1a9850'; // green (worse)
    return '#999'; // gray "no data"
}

export function getColorByConcentration(value: number | null | undefined): string {
    if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) return '#999';
    if (value >= 150) return '#d73027';
    if (value >= 50) return '#fc8d59';
    if (value >= 20) return '#fee08b';
    if (value >= 10) return '#91cf60';
    return '#1a9850';
}

export function getWeight(sensor: Sensor): number {
    // Heatmap will use concentration if exists, otherwise default by category
    const concentracion =
        typeof sensor.metricas?.concentracion === 'number' &&
        Number.isFinite(sensor.metricas.concentracion)
            ? sensor.metricas.concentracion
            : null;
    if (concentracion !== null) {
        return Math.min(concentracion / MAX_POLLUTION, 1);
    }

    const pm25 =
        typeof sensor.metricas?.pm25 === 'number' && Number.isFinite(sensor.metricas.pm25)
            ? sensor.metricas.pm25
            : null;
    if (pm25 !== null) {
        return Math.min(pm25 / MAX_POLLUTION, 1);
    }

    const pm10 =
        typeof sensor.metricas?.pm10 === 'number' && Number.isFinite(sensor.metricas.pm10)
            ? sensor.metricas.pm10
            : null;
    if (pm10 !== null) {
        return Math.min(pm10 / MAX_POLLUTION, 1);
    }
    const cat = getCategoria(sensor).toLowerCase();
    if (cat.includes('extremo')) return 1;
    if (cat.includes('alto')) return 0.7;
    if (cat.includes('moderado')) return 0.4;
    if (cat.includes('bueno')) return 0.1;
    return 0.05; // No data
}

export function haversineKm(
    lat1: number,
    lon1: number,
    lat2: number,
    lon2: number
): number {
    const R = 6371;
    const dLat = ((lat2 - lat1) * Math.PI) / 180;
    const dLon = ((lon2 - lon1) * Math.PI) / 180;
    const a =
        Math.sin(dLat / 2) ** 2 +
        Math.cos((lat1 * Math.PI) / 180) *
        Math.cos((lat2 * Math.PI) / 180) *
        Math.sin(dLon / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}
