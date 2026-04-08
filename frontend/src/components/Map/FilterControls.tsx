import { useState } from 'react';
import type { Sensor } from '../../types/sensor';
import { downloadCSV, downloadImagesZip } from '../../utils/downloadUtils';
import { estimateImagesDownload, fetchImages, type ImagesEstimate } from '../../services/api';

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
    onTypeChange: (type: 'diy' | 'official', value: boolean) => void;
    heatmapMode: 'realtime' | 'filtered';
}

export default function FilterControls({
    onFilter,
    onReset,
    onToggleHeatmap,
    filteredSensors,
    isLoading,
    showDIY,
    showOfficial,
    onTypeChange,
    heatmapMode,
}: FilterControlsProps) {
    const [city, setCity] = useState('');
    const [radius, setRadius] = useState('10');
    const [startDate, setStartDate] = useState('');
    const [endDate, setEndDate] = useState('');
    const [strictDates, setStrictDates] = useState(false);
    const [showHeatmap, setShowHeatmap] = useState(false);
    const [isPreparingDownload, setIsPreparingDownload] = useState(false);
    const [isDownloadingZip, setIsDownloadingZip] = useState(false);
    const [downloadConfirmData, setDownloadConfirmData] = useState<{
        sensors: Sensor[];
        estimate: ImagesEstimate;
    } | null>(null);

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

    const formatBytes = (bytes: number): string => {
        if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
        const units = ['B', 'KB', 'MB', 'GB'];
        let value = bytes;
        let unitIndex = 0;
        while (value >= 1024 && unitIndex < units.length - 1) {
            value /= 1024;
            unitIndex += 1;
        }
        const precision = unitIndex === 0 ? 0 : unitIndex === 1 ? 0 : 1;
        return `${value.toFixed(precision)} ${units[unitIndex]}`;
    };

    const handleDownloadZip = async (): Promise<void> => {
        if (!filteredSensors.length || isPreparingDownload || isDownloadingZip) return;

        try {
            setIsPreparingDownload(true);
            const sensorsWithImage = filteredSensors.filter((s) => s.type !== 'official');
            if (!sensorsWithImage.length) {
                alert('No hay imágenes disponibles para los sensores seleccionados.');
                return;
            }

            const ids = sensorsWithImage.map((s) => s.id);
            const estimate = await estimateImagesDownload(ids);
            if (!estimate.foundImages) {
                alert('No se encontraron imágenes para los sensores seleccionados.');
                return;
            }

            setDownloadConfirmData({
                sensors: sensorsWithImage,
                estimate,
            });
        } catch (error) {
            console.error('ZIP error', error);
            alert('Problema al generar el ZIP (ver consola)');
        } finally {
            setIsPreparingDownload(false);
        }
    };

    const handleConfirmDownload = async (): Promise<void> => {
        if (!downloadConfirmData) return;

        try {
            setIsDownloadingZip(true);
            const ids = downloadConfirmData.sensors.map((s) => s.id);
            const imageData = await fetchImages(ids);
            if (!imageData.length) {
                alert('No se encontraron imágenes para los sensores seleccionados.');
                setDownloadConfirmData(null);
                return;
            }

            await downloadImagesZip(downloadConfirmData.sensors, imageData);
            setDownloadConfirmData(null);
        } catch (error) {
            console.error('ZIP error', error);
            alert('Problema al generar el ZIP (ver consola)');
        } finally {
            setIsDownloadingZip(false);
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
            <p className="mb-3 text-right text-xs text-gray-600">
                {heatmapMode === 'realtime'
                    ? 'Mapa de calor por defecto: mediciones oficiales en tiempo real.'
                    : 'Mapa de calor filtrado: usa los sensores del area y periodo aplicados.'}
            </p>

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
            </div>

            {/* Action buttons */}
            <p className="text-gray-600 text-sm mb-1">
                Despues de filtrar, puedes descargar los sensores y/o las imagenes de los
                sensores:
            </p>
            <div className="flex flex-wrap gap-2 mb-3">
                <button
                    onClick={handleFilter}
                    disabled={isLoading || isPreparingDownload || isDownloadingZip}
                    className="px-4 py-2 bg-ami-azul-claro text-white rounded hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
                >
                    Filtrar
                </button>
                <button
                    onClick={handleReset}
                    disabled={isLoading || isPreparingDownload || isDownloadingZip}
                    className="px-4 py-2 bg-gray-400 text-white rounded hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
                >
                    Reset
                </button>
                <button
                    onClick={handleDownloadCSV}
                    disabled={!hasResults || isLoading || isPreparingDownload || isDownloadingZip}
                    className="px-4 py-2 bg-ami-oro text-white rounded hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
                >
                    Descargar CSV
                </button>
                <button
                    onClick={handleDownloadZip}
                    disabled={!hasResults || isLoading || isPreparingDownload || isDownloadingZip}
                    className="px-4 py-2 bg-yellow-500 text-gray-900 rounded hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
                >
                    {isPreparingDownload
                        ? 'Calculando tamaño...'
                        : isDownloadingZip
                            ? 'Descargando imágenes...'
                            : 'Descargar imágenes'}
                </button>
            </div>

            {downloadConfirmData && (
                <div className="fixed inset-0 z-[2000] bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
                    <div className="w-full max-w-md rounded-2xl shadow-2xl overflow-hidden border border-slate-200">
                        <div className="bg-gradient-to-r from-amber-400 via-yellow-400 to-amber-300 px-5 py-4">
                            <h3 className="text-lg font-bold text-slate-900">Confirmar descarga</h3>
                            <p className="text-sm text-slate-800">Revisa el volumen antes de continuar.</p>
                        </div>
                        <div className="bg-white px-5 py-4 space-y-3 text-slate-700">
                            <p>
                                Se descargarán <span className="font-semibold text-slate-900">{downloadConfirmData.estimate.foundImages}</span> imágenes.
                            </p>
                            <p>
                                Tamaño estimado total:{' '}
                                <span className="font-semibold text-slate-900">
                                    {formatBytes(downloadConfirmData.estimate.estimatedBytes)}
                                </span>
                                .
                            </p>
                            {downloadConfirmData.estimate.requestedIds > downloadConfirmData.estimate.foundImages && (
                                <p className="text-sm text-amber-700">
                                    Aviso: {downloadConfirmData.estimate.requestedIds - downloadConfirmData.estimate.foundImages} sensores no tienen imagen disponible.
                                </p>
                            )}
                        </div>
                        <div className="bg-slate-50 px-5 py-4 flex justify-end gap-2">
                            <button
                                onClick={() => setDownloadConfirmData(null)}
                                disabled={isDownloadingZip}
                                className="px-4 py-2 rounded-md border border-slate-300 text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                            >
                                Cancelar
                            </button>
                            <button
                                onClick={handleConfirmDownload}
                                disabled={isDownloadingZip}
                                className="px-4 py-2 rounded-md bg-ami-azul text-white hover:opacity-90 disabled:opacity-50"
                            >
                                {isDownloadingZip ? 'Descargando...' : 'Continuar descarga'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
