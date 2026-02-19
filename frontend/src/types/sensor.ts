export interface Sensor {
    id: string;
    nombre: string;
    ubicacion: {
        latitud: number;
        longitud: number;
    };
    nivelPolucion: string;
    metricas?: {
        concentracion?: number;
    };
    fechaInicio: string;
    fechaRecogida: string;
    imagen?: string;
}

export interface FilterOptions {
    centro?: {
        lat: number;
        lon: number;
    };
    radioKm?: number;
    fechaInicio?: string;
    fechaFin?: string;
    showDIY?: boolean;
    showOfficial?: boolean;
}

export interface SensoresResponse {
    data: Sensor[];
}

export interface GeocodingResult {
    lat: string;
    lon: string;
}

export interface ImageData {
    id: string;
    base64: string;
}
