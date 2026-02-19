import JSZip from 'jszip';
import type { Sensor } from '../types/sensor';

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
        'nivelPolucion',
    ];
    const rows = sensors.map((s) =>
        [
            s.id,
            s.nombre,
            s.ubicacion.latitud,
            s.ubicacion.longitud,
            s.fechaInicio,
            s.fechaRecogida,
            s.nivelPolucion,
        ].join(',')
    );

    const blob = new Blob([header.join(',') + '\n' + rows.join('\n')], {
        type: 'text/csv;charset=utf-8;',
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `sensores_${Date.now()}.csv`;
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
