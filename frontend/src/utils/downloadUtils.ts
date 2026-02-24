import JSZip from 'jszip';
import type { Sensor } from '../types/sensor';
import { formatDate } from './dateUtils';

export function downloadCSV(sensors: Sensor[]): void {
    if (!sensors.length) {
        alert('No hay datos para exportar');
        return;
    }

    const header = [
        'id',
        'nombre',
        'latitud',
        'longitud',
        'fechaInicio',
        'fechaRecogida',
        'PM10',
        'PM2.5',
    ];
    const rows = sensors.map((s) =>
        [
            s.id,
            s.nombre,
            s.ubicacion.latitud,
            s.ubicacion.longitud,
            formatDate(s.fechaInicio),
            formatDate(s.fechaRecogida),
            typeof s.metricas?.pm10 === 'number' ? s.metricas.pm10.toFixed(1) : 'N/A',
            typeof s.metricas?.pm25 === 'number' ? s.metricas.pm25.toFixed(1) : 'N/A',
        ].join(',')
    );

    const blob = new Blob([header.join(',') + '\n' + rows.join('\n')], {
        type: 'text/csv;charset=utf-8;',
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    const now = new Date();
    const yyyy = now.getFullYear();
    const mm = String(now.getMonth() + 1).padStart(2, '0');
    const dd = String(now.getDate()).padStart(2, '0');
    const hh = String(now.getHours()).padStart(2, '0');
    const min = String(now.getMinutes()).padStart(2, '0');
    link.download = `data_${yyyy}${mm}${dd}${hh}${min}.csv`;
    link.click();
    URL.revokeObjectURL(url);
}

export async function downloadImagesZip(
    sensors: Sensor[],
    imageData: { id: string; base64: string }[]
): Promise<void> {
    if (!sensors.length) {
        alert('No hay sensores tras el filtro.');
        return;
    }

    const zip = new JSZip();
    imageData.forEach(({ id, base64 }) => {
        const blob = b64ToBlob(base64, 'image/jpeg');
        zip.file(`${id}.jpg`, blob);
    });

    const zipBlob = await zip.generateAsync({ type: 'blob' });
    const url = URL.createObjectURL(zipBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `sensores_${Date.now()}.zip`;
    link.click();
    URL.revokeObjectURL(url);
}

function b64ToBlob(b64: string, mime: string): Blob {
    const byteStr = atob(b64);
    const len = byteStr.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
        bytes[i] = byteStr.charCodeAt(i);
    }
    return new Blob([bytes], { type: mime });
}
