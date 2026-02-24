import { useState } from 'react';
import type { Sensor } from '../../types/sensor';
import { downloadCSV, downloadImagesZip } from '../../utils/downloadUtils';
import { fetchImages } from '../../services/api';

interface FilterControlsProps {
    onFilter: (
        city: string,
        radius: number,
        startDate: string,
        endDate: string,
        strictDates: boolean
    ) => void;
    onReset: () => void;
    onToggleHeatmap: (showHeatmap: boolean) => void;
    filteredSensors: Sensor[];
    isLoading: boolean;
    showDIY: boolean;
    showOfficial: boolean;
    showPM10: boolean;
    showPM25: boolean;
    onTypeChange: (type: 'diy' | 'official', value: boolean) => void;
    onPMChange: (type: 'pm10' | 'pm25', value: boolean) => void;
}

export default function FilterControls({
    onFilter,
    onReset,
    onToggleHeatmap,
    filteredSensors,
    isLoading,
    showDIY,
    showOfficial,
    showPM10,
    showPM25,
    onTypeChange,
    onPMChange,
}: FilterControlsProps) {
    const [city, setCity] = useState('');
    const [radius, setRadius] = useState('10');
    const [startDate, setStartDate] = useState('');
    const [endDate, setEndDate] = useState('');
    const [strictDates, setStrictDates] = useState(false);
    const [showHeatmap, setShowHeatmap] = useState(false);

    const handleFilter = () => {
        onFilter(city, parseFloat(radius), startDate, endDate, strictDates);
    };

    const handleReset = () => {
        setCity('');
        setRadius('10');
        setStartDate('');
        setEndDate('');
        setStrictDates(false);
        setShowHeatmap(false);
        onReset();
    };

    const handleToggleMap = (heatmap: boolean) => {
        setShowHeatmap(heatmap);
        onToggleHeatmap(heatmap);
    };

    const handleDownloadCSV = () => {
        downloadCSV(filteredSensors);
    };

    const handleDownloadZip = async () => {
        if (!filteredSensors.length) return;

        try {
            const ids = filteredSensors.map((s) => s.id);
            const imageData = await fetchImages(ids);
            await downloadImagesZip(filteredSensors, imageData);
        } catch (error) {
            console.error('ZIP error', error);
            alert('Problema al generar el ZIP (ver consola)');
        }
    };

    const hasResults = filteredSensors.length > 0;

    return (
        <div>
            {/* Map type buttons */}
            <div className="flex justify-end mb-2 gap-2">
                <button
                    onClick={() => handleToggleMap(false)}
                    className={`px-4 py-2 rounded border ${!showHeatmap
                        ? 'bg-ami-azul text-white border-ami-azul'
                        : 'bg-white text-ami-azul border-ami-azul hover:bg-gray-50'
                        }`}
                >
                    Mapa Normal
                </button>
                <button
                    onClick={() => handleToggleMap(true)}
                    className={`px-4 py-2 rounded border ${showHeatmap
                        ? 'bg-ami-azul text-white border-ami-azul'
                        : 'bg-white text-ami-azul border-ami-azul hover:bg-gray-50'
                        }`}
                >
                    Ver Mapa de Calor
                </button>
            </div>

            {/* Location filter */}
            <p className="text-gray-600 text-sm mb-1">
                Añade la ciudad y el perímetro que quieras filtrar:
            </p>
            <div className="flex flex-wrap items-center mb-3 gap-2">
                <label htmlFor="ciudad" className="font-semibold">
                    Ciudad:
                </label>
                <input
                    type="text"
                    id="ciudad"
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    placeholder="Ej.: Madrid"
                    className="border border-gray-300 rounded px-3 py-1"
                />
                <label htmlFor="radio" className="font-semibold">
                    Radio (km):
                </label>
                <input
                    type="number"
                    id="radio"
                    value={radius}
                    onChange={(e) => setRadius(e.target.value)}
                    min="1"
                    className="border border-gray-300 rounded px-3 py-1 w-20"
                />
            </div>

            {/* Date filter */}
            <p className="text-gray-600 text-sm mb-1">
                Añade la franja de tiempo que quieras filtrar:
            </p>
            <div className="flex flex-wrap gap-3 mb-3">
                <div>
                    <label htmlFor="fechaInicio" className="block text-sm mb-1">
                        Fecha inicio:
                    </label>
                    <input
                        type="date"
                        id="fechaInicio"
                        value={startDate}
                        onChange={(e) => setStartDate(e.target.value)}
                        className="border border-gray-300 rounded px-3 py-1"
                    />
                </div>
                <div>
                    <label htmlFor="fechaFin" className="block text-sm mb-1">
                        Fecha fin:
                    </label>
                    <input
                        type="date"
                        id="fechaFin"
                        value={endDate}
                        onChange={(e) => setEndDate(e.target.value)}
                        className="border border-gray-300 rounded px-3 py-1"
                    />
                </div>
                <label className="flex items-center gap-2 text-sm mt-6">
                    <input
                        type="checkbox"
                        checked={strictDates}
                        onChange={(e) => setStrictDates(e.target.checked)}
                        className="w-4 h-4 text-ami-azul rounded focus:ring-ami-azul"
                    />
                    <span>Filtro estricto (solo dentro del rango)</span>
                </label>
            </div>

            {/* Sensor Type Filter */}
            <div className="flex flex-wrap gap-4 mb-3">
                <label className="flex items-center gap-2 cursor-pointer">
                    <input
                        type="checkbox"
                        checked={showDIY}
                        onChange={(e) => onTypeChange('diy', e.target.checked)}
                        className="w-4 h-4 text-ami-azul rounded focus:ring-ami-azul"
                    />
                    <span>Sensores DIY</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                    <input
                        type="checkbox"
                        checked={showOfficial}
                        onChange={(e) => onTypeChange('official', e.target.checked)}
                        className="w-4 h-4 text-ami-azul rounded focus:ring-ami-azul"
                    />
                    <span>Estaciones Oficiales</span>
                </label>

                {showOfficial && (
                    <>
                        <label className="flex items-center gap-2 cursor-pointer ml-4">
                            <input
                                type="checkbox"
                                checked={showPM10}
                                onChange={(e) => onPMChange('pm10', e.target.checked)}
                                className="w-4 h-4 text-ami-azul rounded focus:ring-ami-azul"
                            />
                            <span className="text-sm">PM10</span>
                        </label>
                        <label className="flex items-center gap-2 cursor-pointer">
                            <input
                                type="checkbox"
                                checked={showPM25}
                                onChange={(e) => onPMChange('pm25', e.target.checked)}
                                className="w-4 h-4 text-ami-azul rounded focus:ring-ami-azul"
                            />
                            <span className="text-sm">PM2.5</span>
                        </label>
                    </>
                )}
            </div>

            {/* Action buttons */}
            <p className="text-gray-600 text-sm mb-1">
                Despues de filtrar, puedes descargar los sensores y/o las imagenes de los
                sensores:
            </p>
            <div className="flex flex-wrap gap-2 mb-3">
                <button
                    onClick={handleFilter}
                    disabled={isLoading}
                    className="px-4 py-2 bg-ami-azul-claro text-white rounded hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
                >
                    Filtrar
                </button>
                <button
                    onClick={handleReset}
                    disabled={isLoading}
                    className="px-4 py-2 bg-gray-400 text-white rounded hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
                >
                    Reset
                </button>
                <button
                    onClick={handleDownloadCSV}
                    disabled={!hasResults || isLoading}
                    className="px-4 py-2 bg-ami-oro text-white rounded hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
                >
                    Descargar CSV
                </button>
                <button
                    onClick={handleDownloadZip}
                    disabled={!hasResults || isLoading}
                    className="px-4 py-2 bg-yellow-500 text-gray-900 rounded hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
                >
                    Descargar imágenes
                </button>
            </div>
        </div>
    );
}
