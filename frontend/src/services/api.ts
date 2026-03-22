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

export interface ProcessedAnalysis {
    contourImageB64: string;
    roiImageB64: string;
    binaryB64: string;
    overlayB64: string;
    analysisResults: {
        num_contours?: number;
        area_percentage?: number;
        total_area?: number;
    };
    pollutionData: {
        concentration_standard?: number;
        concentration_sensor?: number;
        num_particles?: number;
        particles_per_contour?: number;
        model_type?: string;
    };
    pollutionLevel: string;
}

export async function processAnalysisImage(
    imageB64: string,
    modelType: 'PM10' | 'PM25' = 'PM10'
): Promise<ProcessedAnalysis> {
    const response = await fetch('/api/analysis/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ imageB64, modelType }),
    });
    const data = await response.json();
    if (!response.ok || !data?.success) {
        throw new Error(
            data?.details ? `${data?.error}: ${data.details}` : (data?.error || 'Error procesando imagen')
        );
    }
    return data.data as ProcessedAnalysis;
}

export async function submitExperiment(payload: {
    startDate: string;
    endDate: string;
    latitude: number;
    longitude: number;
    concentration: number;
    pollutionLevel: string;
    inputImageB64: string;
    roiImageB64?: string;
    binaryB64?: string;
    overlayB64?: string;
    analysisResults: {
        numContours: number;
        areaPercentage: number;
    };
}): Promise<{ success: boolean; id?: string; imageUrl?: string }> {
    const response = await fetch('/api/experimentos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });

    if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(data?.error || 'Error guardando experimento');
    }

    return response.json();
}
