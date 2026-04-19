import { useEffect, useRef } from 'react';
import L from 'leaflet';
import type { Sensor } from '../../types/sensor';
import { getColor, getCategoria, getColorByConcentration } from '../../utils/sensorUtils';

interface MapContainerProps {
    sensors: Sensor[];
    center?: [number, number];
    zoom?: number;
    isVisible?: boolean;
    radiusCircle?: {
        center: [number, number];
        radiusKm: number;
    } | null;
    onSensorClick?: (sensor: Sensor) => void;
}

export default function MapContainer({
    sensors,
    center = [40.4168, -3.7038],
    zoom = 5,
    isVisible = true,
    radiusCircle,
    onSensorClick,
}: MapContainerProps) {
    const mapRef = useRef<L.Map | null>(null);
    const markerLayerRef = useRef<L.LayerGroup | null>(null);
    const circleRef = useRef<L.Circle | null>(null);

    // Initialize map
    useEffect(() => {
        if (!mapRef.current) {
            const map = L.map('map').setView(center, zoom);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap',
            }).addTo(map);

            mapRef.current = map;
            markerLayerRef.current = L.layerGroup().addTo(map);
        }

        return () => {
            if (mapRef.current) {
                mapRef.current.remove();
                mapRef.current = null;
            }
        };
    }, []);

    // Update map view when center/zoom changes
    useEffect(() => {
        if (!mapRef.current) return;
        mapRef.current.setView(center, zoom);
    }, [center, zoom]);

    useEffect(() => {
        if (!mapRef.current || !isVisible) return;

        const raf = window.requestAnimationFrame(() => {
            if (!mapRef.current) return;
            mapRef.current.invalidateSize();
            mapRef.current.setView(center, zoom, { animate: false });
        });

        return () => window.cancelAnimationFrame(raf);
    }, [isVisible, center, zoom]);

    // Update markers
    useEffect(() => {
        if (!markerLayerRef.current) return;

        markerLayerRef.current.clearLayers();

        sensors.forEach((sensor) => {
            if (!sensor.ubicacion) return;
            const { latitud, longitud } = sensor.ubicacion;
            if (
                typeof latitud !== 'number' ||
                typeof longitud !== 'number' ||
                !isFinite(latitud) ||
                !isFinite(longitud)
            ) return;

            const isOfficial = sensor.type === 'official';
            const marker = isOfficial
                ? (() => {
                    const pm10 =
                        typeof sensor.metricas?.pm10 === 'number' ? sensor.metricas.pm10 : null;
                    const pm25 =
                        typeof sensor.metricas?.pm25 === 'number' ? sensor.metricas.pm25 : null;
                    const pm10Color = getColorByConcentration(pm10);
                    const pm25Color = getColorByConcentration(pm25);
                    const gradientId = `official-grad-${sensor.id.replace(/[^a-zA-Z0-9_-]/g, '')}`;

                    return L.marker([latitud, longitud], {
                        icon: L.divIcon({
                            className: '',
                            html: `
                                <div style="width:20px;height:18px;display:block;">
                                    <svg width="20" height="18" viewBox="0 0 20 18" xmlns="http://www.w3.org/2000/svg">
                                        <defs>
                                            <linearGradient id="${gradientId}" x1="0%" y1="0%" x2="100%" y2="0%">
                                                <stop offset="50%" stop-color="${pm10Color}"/>
                                                <stop offset="50%" stop-color="${pm25Color}"/>
                                            </linearGradient>
                                        </defs>
                                        <path d="M10 1 L19 17 L1 17 Z" fill="url(#${gradientId})" stroke="#1f2937" stroke-width="1.5"/>
                                    </svg>
                                </div>
                            `,
                            iconSize: [20, 18],
                            iconAnchor: [10, 17],
                            popupAnchor: [0, -12],
                        }),
                    });
                })()
                : L.circleMarker([latitud, longitud], {
                    radius: 8,
                    fillColor: getColor(sensor),
                    color: '#333',
                    weight: 1,
                    opacity: 1,
                    fillOpacity: 0.75,
                });

            if (isOfficial) {
                const isOfficialAverage =
                    typeof sensor.fechaInicio === 'string' && sensor.fechaInicio.trim() !== '';
                const pm25 =
                    typeof sensor.metricas?.pm25 === 'number'
                        ? `${sensor.metricas.pm25.toFixed(1)} μg/m³`
                        : 'N/A';
                const pm10 =
                    typeof sensor.metricas?.pm10 === 'number'
                        ? `${sensor.metricas.pm10.toFixed(1)} μg/m³`
                        : 'N/A';
                const pm25Label = isOfficialAverage ? 'Media PM2.5' : 'PM2.5';
                const pm10Label = isOfficialAverage ? 'Media PM10' : 'PM10';
                const dateRangeHtml = isOfficialAverage
                    ? `<strong>Fecha Inicio:</strong> ${sensor.fechaInicio}<br>` +
                    `<strong>Fecha Recogida:</strong> ${sensor.fechaRecogida}<br>`
                    : '';

                marker.bindPopup(
                    `<strong>Estación oficial:</strong> ${sensor.nombre}<br>` +
                    `<strong>ID:</strong> ${sensor.id}<br>` +
                    dateRangeHtml +
                    `<strong>${pm25Label}:</strong> ${pm25}<br>` +
                    `<strong>${pm10Label}:</strong> ${pm10}`
                );
            } else {
                marker.bindPopup(
                    `<strong>ID:</strong> ${sensor.id}<br>` +
                    `<strong>Categoría:</strong> ${getCategoria(sensor)}<br>` +
                    `<strong>Conc.:</strong> ${sensor.metricas?.concentracion?.toFixed(1) ?? '–'} μg/m³`
                );
            }

            if (onSensorClick) {
                marker.on('click', () => onSensorClick(sensor));
            }

            markerLayerRef.current!.addLayer(marker);
        });
    }, [sensors, onSensorClick]);

    // Update radius circle
    useEffect(() => {
        if (!mapRef.current) return;

        if (circleRef.current) {
            mapRef.current.removeLayer(circleRef.current);
            circleRef.current = null;
        }

        if (radiusCircle) {
            circleRef.current = L.circle(radiusCircle.center, {
                radius: radiusCircle.radiusKm * 1000,
                color: 'blue',
                fillOpacity: 0.1,
                interactive: false,
            }).addTo(mapRef.current);
        }
    }, [radiusCircle]);

    return <div id="map" className="h-[500px] rounded-lg border-2 border-ami-azul-claro"></div>;
}
