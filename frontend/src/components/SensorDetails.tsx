import type { Sensor } from '../types/sensor';
import { formatDate, formatDateTime } from '../utils/dateUtils';

interface SensorDetailsProps {
    sensor: Sensor | null;
}

export default function SensorDetails({ sensor }: SensorDetailsProps) {
    if (!sensor) {
        return (
            <div className="bg-white rounded-lg shadow-md overflow-hidden">
                <div className="bg-ami-azul text-white px-4 py-3">
                    <h5 className="text-lg font-semibold m-0">Datos del Sensor Seleccionado</h5>
                </div>
                <div className="p-4 min-h-[300px] flex items-center justify-center">
                    <p className="text-gray-500 text-center">
                        Seleccione un sensor en el mapa para ver los detalles
                    </p>
                </div>
            </div>
        );
    }

    const isOfficialAverage =
        sensor.type === 'official' &&
        typeof sensor.fechaInicio === 'string' &&
        sensor.fechaInicio.trim() !== '';
    const pm25Label = isOfficialAverage ? 'Concentración media PM2.5' : 'Concentración PM2.5';
    const pm10Label = isOfficialAverage ? 'Concentración media PM10' : 'Concentración PM10';

    return (
        <div className="bg-white rounded-lg shadow-md overflow-hidden">
            <div className="bg-ami-azul text-white px-4 py-3">
                <h5 className="text-lg font-semibold m-0">Datos del Sensor Seleccionado</h5>
            </div>
            <div className="p-4">
                <p>
                    <strong>Nombre:</strong> {sensor.nombre}
                </p>
                <p>
                    <strong>Categoría:</strong>{' '}
                    {sensor.type === 'official' ? 'Oficial' : 'DIY'}
                </p>
                <p>
                    <strong>{pm25Label}:</strong>{' '}
                    {typeof sensor.metricas?.pm25 === 'number'
                        ? `${sensor.metricas.pm25.toFixed(1)} μg/m³`
                        : 'N/A'}
                </p>
                <p>
                    <strong>{pm10Label}:</strong>{' '}
                    {typeof sensor.metricas?.pm10 === 'number'
                        ? `${sensor.metricas.pm10.toFixed(1)} μg/m³`
                        : 'N/A'}
                </p>
                <p>
                    <strong>Ubicación:</strong> {sensor.ubicacion.latitud.toFixed(4)},{' '}
                    {sensor.ubicacion.longitud.toFixed(4)}
                </p>
                {(sensor.type !== 'official' || isOfficialAverage) && (
                    <p>
                        <strong>Fecha Inicio:</strong> {formatDate(sensor.fechaInicio)}
                    </p>
                )}
                <p>
                    <strong>Fecha Recogida:</strong>{' '}
                    {sensor.type === 'official' && !isOfficialAverage
                        ? formatDateTime(sensor.fechaRecogida)
                        : formatDate(sensor.fechaRecogida)}
                </p>
            </div>
        </div>
    );
}
