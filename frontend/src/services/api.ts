import type {
    Sensor,
    SensoresResponse,
    GeocodingResult,
    ImageData,
} from '../types/sensor';

const API_URL =
    '/api/sensores?fields=id,nombre,ubicacion,nivelPolucion,metricas.concentracion,fechaInicio,fechaRecogida';

export async function fetchSensores(): Promise<Sensor[]> {
    const response = await fetch(API_URL);
    const data: SensoresResponse = await response.json();
    return data.data;
}

export async function geocode(city: string): Promise<{ lat: number; lon: number }> {
    const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(
        city
    )}`;
    const response = await fetch(url);
    const data: GeocodingResult[] = await response.json();
    if (!data.length) throw new Error('Ciudad no encontrada');
    return { lat: +data[0].lat, lon: +data[0].lon };
}

export async function fetchImages(ids: string[]): Promise<ImageData[]> {
    const idsStr = ids.join(',');
    const response = await fetch(`/api/imagenes?ids=${idsStr}`);
    if (!response.ok) throw new Error('Error obteniendo imágenes');
    return response.json();
}
