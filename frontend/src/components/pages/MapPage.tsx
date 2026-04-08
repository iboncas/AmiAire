import { useState, useEffect } from 'react';
import MapContainer from '../Map/MapContainer';
import FilterControls from '../Map/FilterControls';
import Legend from '../Legend';
import SensorDetails from '../SensorDetails';
import LoadingSpinner from '../LoadingSpinner';
import type { Sensor } from '../../types/sensor';
import { fetchSensores, fetchEstacionesOficiales, geocode } from '../../services/api';
import { haversineKm } from '../../utils/sensorUtils';

export default function MapPage() {
    const [allSensors, setAllSensors] = useState<Sensor[]>([]);
    const [filteredSensors, setFilteredSensors] = useState<Sensor[]>([]);
    const [selectedSensor, setSelectedSensor] = useState<Sensor | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [showHeatmap, setShowHeatmap] = useState(false);
    const [mapCenter, setMapCenter] = useState<[number, number]>([40.4168, -3.7038]);
    const [mapZoom, setMapZoom] = useState(5);
    const [radiusCircle, setRadiusCircle] = useState<{
        center: [number, number];
        radiusKm: number;
    } | null>(null);
    const [showDIY, setShowDIY] = useState(true);
    const [showOfficial, setShowOfficial] = useState(true);
    const [activeSearch, setActiveSearch] = useState<{
        city: string;
        radius: number;
        startDate: string;
        endDate: string;
        strictDates: boolean;
        center: { lat: number; lon: number } | null;
    }>({
        city: '',
        radius: 10,
        startDate: '',
        endDate: '',
        strictDates: false,
        center: null,
    });

    useEffect(() => {
        loadSensors();
    }, []);

    const hasDateFilter =
        Boolean(activeSearch.startDate) ||
        Boolean(activeSearch.endDate);

    const refreshOfficialSensors = async (startDate?: string, endDate?: string) => {
        const official = await fetchEstacionesOficiales(startDate, endDate);
        const normalizedOfficial = official.map((s) => ({ ...s, type: 'official' as const }));
        setAllSensors((prev) => {
            const diy = prev.filter((sensor) => sensor.type !== 'official');
            return [...diy, ...normalizedOfficial];
        });
    };

    const loadSensors = async () => {
        setIsLoading(true);
        try {
            const [diySensorsResult, officialSensorsResult] = await Promise.allSettled([
                fetchSensores(),
                fetchEstacionesOficiales(),
            ]);
            const diySensors =
                diySensorsResult.status === 'fulfilled' && Array.isArray(diySensorsResult.value)
                    ? diySensorsResult.value
                    : [];
            const officialSensors =
                officialSensorsResult.status === 'fulfilled' &&
                Array.isArray(officialSensorsResult.value)
                    ? officialSensorsResult.value
                    : [];

            const all = [
                ...diySensors.map((s) => ({ ...s, type: 'diy' as const })),
                ...officialSensors.map((s) => ({ ...s, type: 'official' as const })),
            ];

            setAllSensors(all);
            const filtered = applyFilters(all, activeSearch, showDIY, showOfficial);
            setFilteredSensors(filtered);
        } catch (error) {
            console.error('Error loading sensors:', error);
            alert('Error al cargar los sensores');
        } finally {
            setIsLoading(false);
        }
    };

    const applyFilters = (
        sensors: Sensor[],
        searchState: typeof activeSearch,
        diy: boolean,
        official: boolean
    ) => {
        return sensors.filter((sensor) => {
            if (sensor.type === 'diy' && !diy) return false;
            if (sensor.type === 'official' && !official) return false;

            let ok = true;

            if (searchState.center && searchState.radius) {
                const { latitud, longitud } = sensor.ubicacion;
                const distance = haversineKm(
                    searchState.center.lat,
                    searchState.center.lon,
                    latitud,
                    longitud
                );
                ok = distance <= searchState.radius;
            }

            const hasStart = Boolean(searchState.startDate);
            const hasEnd = Boolean(searchState.endDate);
            if (ok && (hasStart || hasEnd)) {
                const sensorStart = sensor.fechaInicio ? new Date(sensor.fechaInicio) : null;
                const sensorEnd = sensor.fechaRecogida ? new Date(sensor.fechaRecogida) : null;
                const start = hasStart ? new Date(`${searchState.startDate}T00:00:00.000Z`) : null;
                const end = hasEnd ? new Date(`${searchState.endDate}T23:59:59.999Z`) : null;
                const validStart = sensorStart instanceof Date && !Number.isNaN(sensorStart.getTime());
                const validEnd = sensorEnd instanceof Date && !Number.isNaN(sensorEnd.getTime());

                if (searchState.strictDates) {
                    if (hasStart && validStart) ok = sensorStart! >= start!;
                    if (ok && hasEnd && validEnd) ok = sensorEnd! <= end!;
                } else {
                    if (hasStart && validEnd) ok = sensorEnd! >= start!;
                    if (ok && hasEnd && validStart) ok = sensorStart! <= end!;
                }
            }

            return ok;
        });
    };

    useEffect(() => {
        const filtered = applyFilters(allSensors, activeSearch, showDIY, showOfficial);
        setFilteredSensors(filtered);
    }, [showDIY, showOfficial, allSensors, activeSearch]);

    const heatmapSensors = hasDateFilter
        ? filteredSensors
        : applyFilters(
            allSensors,
            {
                ...activeSearch,
                startDate: '',
                endDate: '',
                strictDates: false,
            },
            false,
            showOfficial
        );

    const handleSearch = async (
        city: string,
        radius: number,
        startDate: string,
        endDate: string,
        strictDates: boolean
    ) => {
        if (!city && !startDate && !endDate) {
            alert('Introduce una ciudad o un rango de fechas');
            return;
        }

        if (city && (isNaN(radius) || radius <= 0)) {
            alert('Introduce un radio válido');
            return;
        }

        setIsLoading(true);
        try {
            let centro = null;
            const hasDateFilter = Boolean(startDate || endDate);

            if (city) {
                centro = await geocode(city);

                setMapCenter([centro.lat, centro.lon]);
                setMapZoom(11);
                setRadiusCircle({
                    center: [centro.lat, centro.lon],
                    radiusKm: radius,
                });
            } else {
                setMapCenter([40.4168, -3.7038]);
                setMapZoom(5);
                setRadiusCircle(null);
            }

            if (hasDateFilter) {
                await refreshOfficialSensors(startDate || undefined, endDate || undefined);
            } else {
                await refreshOfficialSensors();
            }

            const newSearchState = {
                city,
                radius,
                startDate,
                endDate,
                strictDates,
                center: centro,
            };

            setActiveSearch(newSearchState);
        } catch (error) {
            console.error('Geocoding error:', error);
            alert('Ciudad no encontrada');
        } finally {
            setIsLoading(false);
        }
    };

    const handleTypeChange = (type: 'diy' | 'official', value: boolean) => {
        if (type === 'diy') setShowDIY(value);
        if (type === 'official') setShowOfficial(value);
    };

    const handleReset = () => {
        void refreshOfficialSensors();
        setMapCenter([40.4168, -3.7038]);
        setMapZoom(5);
        setRadiusCircle(null);
        setSelectedSensor(null);
        setShowDIY(true);
        setShowOfficial(true);
        setActiveSearch({
            city: '',
            radius: 10,
            startDate: '',
            endDate: '',
            strictDates: false,
            center: null,
        });
    };

    const handleToggleHeatmap = (show: boolean) => {
        setShowHeatmap(show);
    };

    const handleSensorClick = (sensor: Sensor) => {
        setSelectedSensor(sensor);
    };

    return (
        <div className="container mx-auto px-4 mt-4">
            <LoadingSpinner isLoading={isLoading} />

            <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
                <div className="md:col-span-8">
                    <div className="bg-white rounded-lg shadow-md overflow-hidden mb-4">
                        <div className="bg-ami-azul text-white px-4 py-3">
                            <h5 className="text-lg font-semibold m-0">Mapa de Sensores</h5>
                        </div>
                        <div className="p-4">
                            <FilterControls
                                onFilter={handleSearch}
                                onReset={handleReset}
                                onToggleHeatmap={handleToggleHeatmap}
                                filteredSensors={filteredSensors}
                                isLoading={isLoading}
                                showDIY={showDIY}
                                showOfficial={showOfficial}
                                onTypeChange={handleTypeChange}
                                heatmapMode={hasDateFilter ? 'filtered' : 'realtime'}
                            />
                            <MapContainer
                                key={`${showHeatmap ? 'heat' : 'normal'}-${showDIY}-${showOfficial}`}
                                sensors={filteredSensors}
                                heatmapSensors={heatmapSensors}
                                showHeatmap={showHeatmap}
                                center={mapCenter}
                                zoom={mapZoom}
                                radiusCircle={radiusCircle}
                                onSensorClick={handleSensorClick}
                            />
                        </div>
                    </div>
                </div>

                <div className="md:col-span-4">
                    <Legend />
                    <SensorDetails sensor={selectedSensor} />
                    {selectedSensor?.type === 'diy' && (
                        <div className="bg-white rounded-lg shadow-md overflow-hidden mt-4">
                            <div className="bg-ami-azul-claro text-white px-4 py-3">
                                <h5 className="text-lg font-semibold m-0">Imagen del Sensor</h5>
                            </div>
                            <div className="p-4">
                                <img
                                    src={`/api/imagen?id=${encodeURIComponent(selectedSensor.id)}`}
                                    alt={`Sensor ${selectedSensor.id}`}
                                    className="max-w-full max-h-[300px] rounded-lg"
                                />
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
