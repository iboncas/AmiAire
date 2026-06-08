import { useState, useEffect, useCallback } from 'react';
import MapContainer from '../Map/MapContainer';
import FilterControls from '../Map/FilterControls';
import Legend from '../Legend';
import SensorDetails from '../SensorDetails';
import LoadingSpinner from '../LoadingSpinner';
import type { Sensor } from '../../types/sensor';
import {
    fetchSensores,
    fetchEstacionesOficiales,
    fetchSensorById,
    geocode,
} from '../../services/api';
import { haversineKm } from '../../utils/sensorUtils';

interface MapPageProps {
    isActive: boolean;
}

interface SearchState {
    city: string;
    radius: number;
    startDate: string;
    endDate: string;
    center: { lat: number; lon: number } | null;
}

const TAXONOMY_CATEGORY_DESCRIPTIONS: Record<string, string> = {
    combustion_related:
        'Suele agrupar partículas pequeñas y compactas, compatibles con procesos de combustión. Puede relacionarse con tráfico, humo u otras emisiones por quema.',
    mechanical_non_combustion_particulate:
        'Hace referencia a partículas generadas por desgaste o fricción, no por combustión. Puede incluir polvo mineral, abrasión de materiales o resuspensión mecánica.',
    biological:
        'Incluye formas compatibles con material de origen biológico. Puede estar asociado a polen, restos vegetales, esporas u otras partículas naturales.',
    fibrous_synthetic_materials:
        'Describe partículas alargadas o fibrosas, compatibles con fibras sintéticas. Puede relacionarse con textiles, plásticos u otros materiales manufacturados.',
    industrial:
        'Agrupa partículas con patrones compatibles con procesos industriales. Puede reflejar mezclas complejas asociadas a manufactura, manipulación o emisiones técnicas.',
    mixed_unknown:
        'Indica una mezcla poco definida de rasgos morfológicos. Se usa cuando no hay una afinidad clara con una sola categoría interpretativa.',
};

const applyFilters = (
    sensors: Sensor[],
    searchState: SearchState,
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

            if (hasStart && validStart) ok = sensorStart! >= start!;
            if (ok && hasEnd && validEnd) ok = sensorEnd! <= end!;
        }

        return ok;
    });
};

export default function MapPage({ isActive }: MapPageProps) {
    const [allSensors, setAllSensors] = useState<Sensor[]>([]);
    const [filteredSensors, setFilteredSensors] = useState<Sensor[]>([]);
    const [selectedSensor, setSelectedSensor] = useState<Sensor | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [isLoadingSelectedSensor, setIsLoadingSelectedSensor] = useState(false);
    const [mapCenter, setMapCenter] = useState<[number, number]>([40.4168, -3.7038]);
    const [mapZoom, setMapZoom] = useState(5);
    const [radiusCircle, setRadiusCircle] = useState<{
        center: [number, number];
        radiusKm: number;
    } | null>(null);
    const [showDIY, setShowDIY] = useState(true);
    const [showOfficial, setShowOfficial] = useState(true);
    const [activeSearch, setActiveSearch] = useState<SearchState>({
        city: '',
        radius: 10,
        startDate: '',
        endDate: '',
        center: null,
    });

    const refreshOfficialSensors = useCallback(async (startDate?: string, endDate?: string) => {
        const official = await fetchEstacionesOficiales(startDate, endDate);
        const normalizedOfficial = official.map((s) => ({ ...s, type: 'official' as const }));
        setAllSensors((prev) => {
            const diy = prev.filter((sensor) => sensor.type !== 'official');
            return [...diy, ...normalizedOfficial];
        });
    }, []);

    const loadSensors = useCallback(async () => {
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
        } catch (error) {
            console.error('Error loading sensors:', error);
            alert('Error al cargar los sensores');
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        void loadSensors();
    }, [loadSensors]);

    useEffect(() => {
        if (!isActive) return;
        void loadSensors();
    }, [isActive, loadSensors]);

    useEffect(() => {
        const filtered = applyFilters(allSensors, activeSearch, showDIY, showOfficial);
        setFilteredSensors(filtered);
    }, [showDIY, showOfficial, allSensors, activeSearch]);

    const handleSearch = async (
        city: string,
        radius: number,
        startDate: string,
        endDate: string
    ) => {
        if (!city && !startDate && !endDate) {
            alert('Introduce una ubicación o un rango de fechas');
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
                center: centro,
            };

            setActiveSearch(newSearchState);
        } catch (error) {
            console.error('Geocoding error:', error);
            alert('Ubicación no encontrada');
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
            center: null,
        });
    };

    const handleSensorClick = async (sensor: Sensor) => {
        setSelectedSensor(sensor);

        if (sensor.type !== 'diy') {
            return;
        }

        setIsLoadingSelectedSensor(true);
        try {
            const fullSensor = await fetchSensorById(sensor.id);
            if (fullSensor) {
                setSelectedSensor({ ...fullSensor, type: 'diy' });
            }
        } finally {
            setIsLoadingSelectedSensor(false);
        }
    };

    const selectedTaxonomyRanking = selectedSensor?.taxonomyModel?.ranked_categories ?? [];
    const selectedTaxonomyTopCategory = selectedSensor?.taxonomyModel?.top_category_label ?? '';

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
                                filteredSensors={filteredSensors}
                                isLoading={isLoading}
                                showDIY={showDIY}
                                showOfficial={showOfficial}
                                onTypeChange={handleTypeChange}
                            />
                            <MapContainer
                                sensors={filteredSensors}
                                center={mapCenter}
                                zoom={mapZoom}
                                radiusCircle={radiusCircle}
                                isVisible={isActive}
                                onSensorClick={handleSensorClick}
                            />
                        </div>
                    </div>
                </div>

                <div className="md:col-span-4">
                    <Legend />
                    <SensorDetails sensor={selectedSensor} />
                    {selectedSensor?.type === 'diy' && (
                        <div className="bg-white rounded-lg shadow-md overflow-visible mt-4">
                            <div className="bg-ami-azul-claro text-white px-4 py-3">
                                <h5 className="text-lg font-semibold m-0">Imagen del Sensor</h5>
                            </div>
                            <div className="p-4">
                                {isLoadingSelectedSensor ? (
                                    <p className="text-sm text-gray-600">
                                        Cargando imagen y posibles fuentes contaminantes...
                                    </p>
                                ) : (
                                    <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
                                        <div className="shrink-0 lg:w-[42%]">
                                            <img
                                                src={`/api/imagen?id=${encodeURIComponent(selectedSensor.id)}`}
                                                alt={`Sensor ${selectedSensor.id}`}
                                                className="max-w-full max-h-[300px] rounded-lg"
                                            />
                                        </div>

                                        <div className="min-w-0 flex-1 rounded-lg border border-amber-200 bg-amber-50 p-3">
                                            <h6 className="text-sm font-semibold text-amber-950">
                                                Posibles fuentes contaminantes
                                            </h6>
                                            {selectedTaxonomyRanking.length > 0 ? (
                                                <>
                                                    {selectedTaxonomyTopCategory && (
                                                        <p className="mt-1 text-xs leading-5 text-amber-900">
                                                            Categoría más compatible:{' '}
                                                            <strong>{selectedTaxonomyTopCategory}</strong>.
                                                        </p>
                                                    )}
                                                    <div className="mt-3 space-y-3">
                                                        {selectedTaxonomyRanking.map((item) => (
                                                            <div key={item.category} className="rounded-lg border border-amber-100 bg-white p-3">
                                                                <div className="flex items-center justify-between gap-3">
                                                                    <div className="relative group max-w-[80%]">
                                                                        <div className="flex items-center gap-2">
                                                                            <p className="text-sm font-medium text-slate-900">
                                                                                {item.label}
                                                                            </p>
                                                                            {TAXONOMY_CATEGORY_DESCRIPTIONS[item.category] && (
                                                                                <span
                                                                                    className="inline-flex h-5 w-5 items-center justify-center rounded-full border border-amber-300 bg-amber-50 text-[11px] font-semibold text-amber-900 cursor-help"
                                                                                    aria-label={`Información sobre ${item.label}`}
                                                                                    title={TAXONOMY_CATEGORY_DESCRIPTIONS[item.category]}
                                                                                >
                                                                                    i
                                                                                </span>
                                                                            )}
                                                                        </div>
                                                                        {TAXONOMY_CATEGORY_DESCRIPTIONS[item.category] && (
                                                                            <div className="pointer-events-none absolute left-0 top-full z-30 mt-2 hidden w-72 rounded-lg border border-amber-200 bg-white p-3 text-xs leading-5 text-slate-700 shadow-lg group-hover:block">
                                                                                {TAXONOMY_CATEGORY_DESCRIPTIONS[item.category]}
                                                                            </div>
                                                                        )}
                                                                    </div>
                                                                    <p className="text-sm font-semibold text-amber-900">
                                                                        {item.percentage.toFixed(1)}%
                                                                    </p>
                                                                </div>
                                                                <div className="mt-2 h-2 overflow-hidden rounded-full bg-amber-100">
                                                                    <div
                                                                        className="h-full rounded-full bg-amber-500"
                                                                        style={{ width: `${Math.max(2, Math.min(100, item.percentage))}%` }}
                                                                    />
                                                                </div>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </>
                                            ) : (
                                                <p className="mt-1 text-xs leading-5 text-amber-900">
                                                    No hay posibles fuentes contaminantes disponibles para este sensor.
                                                </p>
                                            )}
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
