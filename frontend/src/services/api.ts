import type {
    Sensor,
    SensoresResponse,
    GeocodingResult,
    ImageData,
} from '../types/sensor';

const API_URL =
    '/api/sensores?fields=id,nombre,ubicacion,nivelPolucion,metricas.concentracion,metricas.pm25,metricas.pm10,fechaInicio,fechaRecogida';

function parseOfficialStationsCsv(csvText: string): Sensor[] {
    const rawLines = csvText.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    if (!rawLines.length) return [];

    const headerParts = rawLines[0].split(',').map((item) => item.trim().toLowerCase());
    const headerIndexMap = {
        gml_id: headerParts.indexOf('gml_id'),
        name: headerParts.indexOf('name'),
        latitude: headerParts.indexOf('latitude'),
        longitude: headerParts.indexOf('longitude'),
    };
    const hasNewHeader =
        headerIndexMap.name >= 0 &&
        headerIndexMap.latitude >= 0 &&
        headerIndexMap.longitude >= 0;
    const lines = rawLines.slice(1);

    return lines
        .map((line, index) => {
            const parts = line.split(',');
            if (parts.length < 3) return null;

            const latitude = hasNewHeader
                ? Number(parts[headerIndexMap.latitude])
                : Number(parts[parts.length - 1]);
            const longitude = hasNewHeader
                ? Number(parts[headerIndexMap.longitude])
                : Number(parts[parts.length - 2]);
            const name = hasNewHeader
                ? parts[headerIndexMap.name]?.trim()
                : parts.slice(0, parts.length - 2).join(',').trim();
            const gmlId =
                hasNewHeader && headerIndexMap.gml_id >= 0
                    ? parts[headerIndexMap.gml_id]?.trim()
                    : '';
            if (!name || !Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;

            return {
                id: gmlId || `official-csv-${index + 1}`,
                nombre: name,
                ubicacion: {
                    latitud: latitude,
                    longitud: longitude,
                },
                metricas: {
                    pm25: null,
                    pm10: null,
                },
                nivelPolucion: 'Sin datos',
                fechaInicio: '',
                fechaRecogida: '',
                type: 'official' as const,
            } satisfies Sensor;
        })
        .filter((station): station is Sensor => station !== null);
}

async function fetchOfficialStationsCsvFallback(): Promise<Sensor[]> {
    try {
        const response = await fetch('/official_stations_coordinates.csv');
        if (!response.ok) return [];
        const csvText = await response.text();
        return parseOfficialStationsCsv(csvText);
    } catch (error) {
        console.error('Error loading official stations CSV fallback:', error);
        return [];
    }
}

function withFetchedAtForOfficialStations(stations: Sensor[]): Sensor[] {
    const fetchedAt = new Date().toISOString();
    return stations.map((station) => ({
        ...station,
        type: 'official',
        fechaRecogida: station.fechaRecogida || fetchedAt,
    }));
}

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
            const fallbackStations = await fetchOfficialStationsCsvFallback();
            return withFetchedAtForOfficialStations(fallbackStations);
        }
        const data: SensoresResponse = await response.json();
        const stations = Array.isArray(data.data) ? data.data : [];
        if (stations.length > 0) return withFetchedAtForOfficialStations(stations);
        const fallbackStations = await fetchOfficialStationsCsvFallback();
        return withFetchedAtForOfficialStations(fallbackStations);
    } catch (error) {
        console.error('Error fetching official stations:', error);
        const fallbackStations = await fetchOfficialStationsCsvFallback();
        return withFetchedAtForOfficialStations(fallbackStations);
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
    if (!ids.length) return [];

    const CHUNK_SIZE = 100;
    const chunks: string[][] = [];
    for (let i = 0; i < ids.length; i += CHUNK_SIZE) {
        chunks.push(ids.slice(i, i + CHUNK_SIZE));
    }

    const results: ImageData[] = [];
    for (const chunk of chunks) {
        const response = await fetch('/api/imagenes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids: chunk }),
        });
        if (!response.ok) {
            throw new Error(`Error obteniendo imágenes (lote de ${chunk.length})`);
        }
        const data = (await response.json()) as ImageData[];
        if (Array.isArray(data) && data.length) {
            results.push(...data);
        }
    }

    return results;
}

export interface ImagesEstimate {
    requestedIds: number;
    validIds: number;
    foundImages: number;
    estimatedBytes: number;
}

export async function estimateImagesDownload(ids: string[]): Promise<ImagesEstimate> {
    const response = await fetch('/api/imagenes/estimacion', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids }),
    });
    if (!response.ok) {
        throw new Error('Error estimando la descarga de imágenes');
    }
    return response.json();
}

export interface ProcessedAnalysis {
    contourImageB64: string;
    roiImageB64: string;
    binaryB64: string;
    overlayB64: string;
    validation?: SensorValidationResult;
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

export interface SensorValidationResult {
    is_sensor: boolean;
    sensor_probability: number;
    non_sensor_probability: number;
    threshold: number;
    model_input_size: {
        width: number;
        height: number;
    };
}

export async function validateSensorImage(imageB64: string): Promise<SensorValidationResult> {
    const response = await fetch('/api/analysis/validate-sensor', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ imageB64 }),
    });
    const data = await response.json();
    if (!response.ok || !data?.success) {
        throw new Error(
            data?.details ? `${data?.error}: ${data.details}` : (data?.error || 'Error validando la imagen')
        );
    }
    return data.data as SensorValidationResult;
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
