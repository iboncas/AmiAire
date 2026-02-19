import { useState, useEffect } from 'react';
import Header from './components/Header';
import MapContainer from './components/Map/MapContainer';
import FilterControls from './components/Map/FilterControls';
import Legend from './components/Legend';
import SensorDetails from './components/SensorDetails';

import LoadingSpinner from './components/LoadingSpinner';
import type { Sensor, FilterOptions } from './types/sensor';
import { fetchSensores, geocode } from './services/api';
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

  // New State for Filters
  const [showDIY, setShowDIY] = useState(true);
  const [showOfficial, setShowOfficial] = useState(false);
  const [activeSearch, setActiveSearch] = useState<{
    city: string;
    radius: number;
    startDate: string;
    endDate: string;
    center: { lat: number; lon: number } | null;
  }>({
    city: '',
    radius: 10,
    startDate: '',
    endDate: '',
    center: null,
  });

  // Load sensors on mount
  useEffect(() => {
    loadSensors();
  }, []);

  const loadSensors = async () => {
    setIsLoading(true);
    try {
      const sensors = await fetchSensores();
      setAllSensors(sensors);
      // Initial filtering
      const filtered = applyFilters(sensors, activeSearch, showDIY, showOfficial);
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
      let ok = true;

      // Sensor Type Filter
      if (!diy) {
        // Assuming all current sensors are DIY.
        return false;
      }
      // Future: if (sensor.type === 'official' && !official) return false;

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
      if (ok && searchState.startDate) {
        ok = new Date(sensor.fechaInicio) >= new Date(searchState.startDate);
      }
      if (ok && searchState.endDate) {
        ok = new Date(sensor.fechaRecogida) <= new Date(searchState.endDate);
      }

      return ok;
    });
  };

  // Run filtering when type selection changes
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
    if (!city || isNaN(radius)) {
      alert('Introduce ciudad y radio válidos');
      return;
    }

    setIsLoading(true);
    try {
      const centro = await geocode(city);

      const newSearchState = {
        city,
        radius,
        startDate,
        endDate,
        center: centro,
      };

      setActiveSearch(newSearchState);

      // Filtering will happen automatically via useEffect because activeSearch changed

      setMapCenter([centro.lat, centro.lon]);
      setMapZoom(11);
      setRadiusCircle({
        center: [centro.lat, centro.lon],
        radiusKm: radius,
      });
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
    setFilteredSensors(allSensors);
    setMapCenter([40.4168, -3.7038]);
    setMapZoom(5);
    setRadiusCircle(null);
    setSelectedSensor(null);
    setShowDIY(true);
    setShowOfficial(false);
    setActiveSearch({
      city: '',
      radius: 10,
      startDate: '',
      endDate: '',
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
                  onTypeChange={handleTypeChange}
                />
                <MapContainer
                  sensors={filteredSensors}
                  showHeatmap={showHeatmap}
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
