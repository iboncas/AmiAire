import { useState, useEffect, useRef } from 'react';
import Header from './components/Header';
import MapContainer from './components/Map/MapContainer';
import FilterControls from './components/Map/FilterControls';
import Legend from './components/Legend';
import SensorDetails from './components/SensorDetails';

import LoadingSpinner from './components/LoadingSpinner';
import type { Sensor } from './types/sensor';
import { fetchSensores, fetchEstacionesOficiales, geocode } from './services/api';
import { haversineKm } from './utils/sensorUtils';

function App() {
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
  const didMountRef = useRef(false);

  // New State for Filters
  const [showDIY, setShowDIY] = useState(true);
  const [showOfficial, setShowOfficial] = useState(true);
  const [showPM10, setShowPM10] = useState(true);
  const [showPM25, setShowPM25] = useState(true);
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

  // Load sensors on mount
  useEffect(() => {
    loadSensors();
  }, []);

  const loadSensors = async () => {
    setIsLoading(true);
    try {
      const [diySensorsResult, officialSensorsResult] = await Promise.all([
        fetchSensores(),
        fetchEstacionesOficiales(activeSearch.startDate, activeSearch.endDate),
      ]);

      const diySensors = Array.isArray(diySensorsResult) ? diySensorsResult : [];
      const officialSensors = Array.isArray(officialSensorsResult) ? officialSensorsResult : [];

      const all = [
        ...diySensors.map(s => ({ ...s, type: 'diy' as const })),
        ...officialSensors.map(s => ({ ...s, type: 'official' as const })),
      ];

      setAllSensors(all);
      const filtered = applyFilters(all, activeSearch, showDIY, showOfficial, showPM10, showPM25);
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
    official: boolean,
    pm10: boolean,
    pm25: boolean
  ) => {
    return sensors.filter((sensor) => {
      // Sensor Type Filter
      if (sensor.type === 'diy' && !diy) return false;
      if (sensor.type === 'official') {
        if (!official) return false;

        // If official is enabled, filter by PM type if at least one PM filter is ON
        // If both are OFF, we show nothing for official (or could show all, but usually user wants selection)
        // Request says: "select PM10 and PM2.5". 
        // Logic: Show if station has PM10 AND showPM10 is ON, OR station has PM25 AND showPM25 is ON.
        const hasPmInfo =
          typeof sensor.hasPM10 === 'boolean' || typeof sensor.hasPM25 === 'boolean';
        if (hasPmInfo) {
          const matchesPM10 = Boolean(sensor.hasPM10 && pm10);
          const matchesPM25 = Boolean(sensor.hasPM25 && pm25);
          if (!matchesPM10 && !matchesPM25) return false;
        }
      }

      let ok = true;

      // Location filter (only if a search has been performed)
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

      // Date filters
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

  // Run filtering when type selection changes
  useEffect(() => {
    const filtered = applyFilters(allSensors, activeSearch, showDIY, showOfficial, showPM10, showPM25);
    setFilteredSensors(filtered);
  }, [showDIY, showOfficial, showPM10, showPM25, allSensors, activeSearch]);

  const heatmapSensors = applyFilters(
    allSensors,
    activeSearch,
    showDIY,
    showOfficial,
    showPM10,
    showPM25
  );

  useEffect(() => {
    if (!didMountRef.current) {
      didMountRef.current = true;
      return;
    }
    loadSensors();
  }, [activeSearch.startDate, activeSearch.endDate]);

  const handleSearch = async (
    city: string,
    radius: number,
    startDate: string,
    endDate: string,
    strictDates: boolean
  ) => {
    // Validation: Require either a city OR at least one date
    if (!city && !startDate && !endDate) {
      alert('Introduce una ciudad o un rango de fechas');
      return;
    }

    // If city is provided, but radius is invalid
    if (city && (isNaN(radius) || radius <= 0)) {
      alert('Introduce un radio válido');
      return;
    }

    setIsLoading(true);
    try {
      let centro = null;

      if (city) {
        centro = await geocode(city);

        setMapCenter([centro.lat, centro.lon]);
        setMapZoom(11);
        setRadiusCircle({
          center: [centro.lat, centro.lon],
          radiusKm: radius,
        });
      } else {
        // If no city, reset map view and clear radius circle
        setMapCenter([40.4168, -3.7038]);
        setMapZoom(5);
        setRadiusCircle(null);
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
      // Filtering will happen automatically via useEffect because activeSearch changed
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

  const handlePMChange = (type: 'pm10' | 'pm25', value: boolean) => {
    if (type === 'pm10') setShowPM10(value);
    if (type === 'pm25') setShowPM25(value);
  };

  const handleReset = () => {
    setFilteredSensors(allSensors);
    setMapCenter([40.4168, -3.7038]);
    setMapZoom(5);
    setRadiusCircle(null);
    setSelectedSensor(null);
    setShowDIY(true);
    setShowOfficial(true);
    setShowPM10(true);
    setShowPM25(true);
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
    <div className="min-h-screen bg-ami-gris">
      <Header />
      <LoadingSpinner isLoading={isLoading} />

      <div className="container mx-auto px-4 mt-4">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
          {/* Map Section */}
          <div className="md:col-span-8">
            <div className="bg-white rounded-lg shadow-md overflow-hidden mb-4">
              <div className="bg-ami-azul-claro text-white px-4 py-3">
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
                  showPM10={showPM10}
                  showPM25={showPM25}
                  onTypeChange={handleTypeChange}
                  onPMChange={handlePMChange}
                />
                <MapContainer
                  key={`${showHeatmap ? 'heat' : 'normal'}-${showDIY}-${showOfficial}-${showPM10}-${showPM25}`}
                  sensors={filteredSensors}
                  heatmapSensors={heatmapSensors}
                  showHeatmap={showHeatmap}
                  showPM10={showPM10}
                  showPM25={showPM25}
                  center={mapCenter}
                  zoom={mapZoom}
                  radiusCircle={radiusCircle}
                  onSensorClick={handleSensorClick}
                />
              </div>
            </div>
          </div>

          {/* Sidebar */}
          <div className="md:col-span-4">
            <Legend />
            <SensorDetails sensor={selectedSensor} />
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
