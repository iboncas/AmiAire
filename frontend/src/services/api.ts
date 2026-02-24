import type {
    Sensor,
    SensoresResponse,
    GeocodingResult,
    ImageData,
} from '../types/sensor';

const API_URL =
    '/api/sensores?fields=id,nombre,ubicacion,nivelPolucion,metricas.concentracion,metricas.pm25,metricas.pm10,fechaInicio,fechaRecogida';

export async function fetchSensores(): Promise<Sensor[]> {
    try {
        const response = await fetch(API_URL);
        if (!response.ok) {
            console.error(`Error fetching sensors: ${response.status}`);
            return [];
        }
        const data: SensoresResponse = await response.json();
        return Array.isArray(data.data) ? data.data : [];
    } catch (error) {
        console.error('Error fetching sensors:', error);
        return [];
    }
}

export async function fetchEstacionesOficiales(
    startDate?: string,
    endDate?: string
): Promise<Sensor[]> {
    try {
        const params = new URLSearchParams();
        if (startDate) params.set('startDate', startDate);
        if (endDate) params.set('endDate', endDate);
        const query = params.toString();
        const url = query ? `/api/estaciones-oficiales?${query}` : '/api/estaciones-oficiales';

        const response = await fetch(url);
        if (!response.ok) {
            console.error(`Error fetching official stations: ${response.status}`);
            return [];
        }
        const data: SensoresResponse = await response.json();
        return Array.isArray(data.data) ? data.data : [];
    } catch (error) {
        console.error('Error fetching official stations:', error);
        return [];
    }
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
