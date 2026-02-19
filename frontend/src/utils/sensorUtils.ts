import type { Sensor } from '../types/sensor';

const MAX_POLLUTION = 150;

export function getCategoria(sensor: Sensor): string {
    // 1) If numeric concentration exists, use thresholds
    if (sensor.metricas?.concentracion !== undefined) {
        const c = sensor.metricas.concentracion;
        if (c >= 150) return 'Extremo';
        if (c >= 50) return 'Alto';
        if (c >= 20) return 'Moderado';
        if (c >= 10) return 'Bueno';
        return 'Bajo'; // < 10 µg/m³
    }
    // 2) Otherwise use the string level
    if (sensor.nivelPolucion) return sensor.nivelPolucion;
    // 3) No data
    return 'SinDatos';
}

export function getColor(sensor: Sensor): string {
    const cat = getCategoria(sensor).toLowerCase();
    if (cat.includes('extremo')) return '#d73027'; // red
    if (cat.includes('alto')) return '#fc8d59'; // orange
    if (cat.includes('moderado')) return '#fee08b'; // yellow
    if (cat.includes('bueno')) return '#1a9850'; // green
    if (cat.includes('bajo')) return '#91cf60'; // light green
    return '#999'; // gray "no data"
}

export function getWeight(sensor: Sensor): number {
    // Heatmap will use concentration if exists, otherwise default by category
    if (sensor.metricas?.concentracion !== undefined) {
        return Math.min(sensor.metricas.concentracion / MAX_POLLUTION, 1);
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
