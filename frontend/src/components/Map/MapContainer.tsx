import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet.heat';
import type { Sensor } from '../../types/sensor';
import { getColor, getCategoria, getWeight } from '../../utils/sensorUtils';

interface MapContainerProps {
    sensors: Sensor[];
    showHeatmap: boolean;
    center?: [number, number];
    zoom?: number;
    radiusCircle?: {
        center: [number, number];
        radiusKm: number;
    } | null;
    onSensorClick?: (sensor: Sensor) => void;
}

export default function MapContainer({
    sensors,
    showHeatmap,
    center = [40.4168, -3.7038],
    zoom = 5,
    radiusCircle,
    onSensorClick,
}: MapContainerProps) {
    const mapRef = useRef<L.Map | null>(null);
    const markerLayerRef = useRef<L.LayerGroup | null>(null);
    const heatLayerRef = useRef<any>(null);
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
        if (mapRef.current && center && zoom) {
            mapRef.current.setView(center, zoom);
        }
    }, [center, zoom]);

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

            const marker = L.circleMarker([latitud, longitud], {
                radius: 8,
                fillColor: getColor(sensor),
                color: '#333',
                weight: 1,
                opacity: 1,
                fillOpacity: 0.75,
            });

            marker.bindPopup(
                `<strong>ID:</strong> ${sensor.id}<br>` +
                `<strong>Categoría:</strong> ${getCategoria(sensor)}<br>` +
                `<strong>Conc.:</strong> ${sensor.metricas?.concentracion?.toFixed(1) ?? '–'} μg/m³`
            );

            if (onSensorClick) {
                marker.on('click', () => onSensorClick(sensor));
            }

            markerLayerRef.current!.addLayer(marker);
        });
    }, [sensors, onSensorClick]);

    // Update heatmap
    useEffect(() => {
        if (!mapRef.current) return;

        const heatData = sensors
            .filter(s =>
                s.ubicacion &&
                typeof s.ubicacion.latitud === 'number' &&
                typeof s.ubicacion.longitud === 'number' &&
                isFinite(s.ubicacion.latitud) &&
                isFinite(s.ubicacion.longitud)
            )
            .map((s) => [
                s.ubicacion.latitud,
                s.ubicacion.longitud,
                getWeight(s),
            ]) as [number, number, number][];

        if (heatLayerRef.current) {
            mapRef.current.removeLayer(heatLayerRef.current);
        }

        if (heatData.length > 0) {
            // @ts-ignore - leaflet.heat types
            heatLayerRef.current = L.heatLayer(heatData, {
                radius: 35,
                blur: 35,
                maxZoom: 10,
                gradient: {
                    0: '#0000ff',
                    0.25: '#00ffff',
                    0.5: '#00ff00',
                    0.75: '#ffff00',
                    1: '#ff0000',
                },
            });
        }
    }, [sensors]);

    // Toggle between normal and heatmap view
    useEffect(() => {
        if (!mapRef.current || !markerLayerRef.current) return;

        if (showHeatmap) {
            mapRef.current.removeLayer(markerLayerRef.current);
            if (heatLayerRef.current) {
                heatLayerRef.current.addTo(mapRef.current);
            }
        } else {
            if (heatLayerRef.current) {
                mapRef.current.removeLayer(heatLayerRef.current);
            }
            markerLayerRef.current.addTo(mapRef.current);
        }
    }, [showHeatmap]);

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
