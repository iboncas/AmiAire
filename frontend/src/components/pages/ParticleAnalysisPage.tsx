import { useEffect, useRef, useState, type ChangeEvent } from 'react';
import L from 'leaflet';
import { geocode, processAnalysisImage, submitExperiment, type ProcessedAnalysis } from '../../services/api';

interface ParticleAnalysisPageProps {
    onOpenMap: () => void;
}

type Step = 1 | 2 | 3 | 4 | 5;

export default function ParticleAnalysisPage({ onOpenMap }: ParticleAnalysisPageProps) {
    const [step, setStep] = useState<Step>(1);
    const [startDate, setStartDate] = useState('');
    const [endDate, setEndDate] = useState('');
    const [locationName, setLocationName] = useState('');
    const [latitude, setLatitude] = useState<number | null>(null);
    const [longitude, setLongitude] = useState<number | null>(null);
    const [imageBase64, setImageBase64] = useState('');
    const [imagePreview, setImagePreview] = useState('');
    const [processed, setProcessed] = useState<ProcessedAnalysis | null>(null);
    const [errorMessage, setErrorMessage] = useState('');
    const [successMessage, setSuccessMessage] = useState('');
    const [isProcessing, setIsProcessing] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const mapContainerRef = useRef<HTMLDivElement | null>(null);
    const mapRef = useRef<L.Map | null>(null);
    const markerRef = useRef<L.Marker | null>(null);

    useEffect(() => {
        if (step !== 2 || latitude === null || longitude === null || !mapContainerRef.current) return;

        if (!mapRef.current) {
            mapRef.current = L.map(mapContainerRef.current).setView([latitude, longitude], 14);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap',
            }).addTo(mapRef.current);

            markerRef.current = L.marker([latitude, longitude], { draggable: true }).addTo(mapRef.current);
            markerRef.current.on('dragend', () => {
                const pos = markerRef.current?.getLatLng();
                if (pos) {
                    setLatitude(pos.lat);
                    setLongitude(pos.lng);
                }
            });
            return;
        }

        mapRef.current.setView([latitude, longitude], 14);
        if (markerRef.current) {
            markerRef.current.setLatLng([latitude, longitude]);
        }
    }, [step, latitude, longitude]);

    useEffect(() => {
        return () => {
            if (mapRef.current) {
                mapRef.current.remove();
                mapRef.current = null;
            }
        };
    }, []);

    const handleDatesNext = () => {
        setErrorMessage('');
        if (!startDate || !endDate) {
            setErrorMessage('Introduce ambas fechas');
            return;
        }
        if (startDate > endDate) {
            setErrorMessage('La fecha de inicio debe ser anterior a la fecha de retirada');
            return;
        }
        setStep(2);
    };

    const handleSearchLocation = async () => {
        setErrorMessage('');
        if (!locationName.trim()) {
            setErrorMessage('Introduce una ubicación');
            return;
        }
        try {
            const coords = await geocode(locationName);
            setLatitude(coords.lat);
            setLongitude(coords.lon);
        } catch {
            setErrorMessage('Localización no encontrada, por favor prueba de nuevo');
        }
    };

    const handleConfirmLocation = () => {
        setErrorMessage('');
        if (latitude === null || longitude === null) {
            setErrorMessage('Confirma una localización válida');
            return;
        }
        setStep(3);
    };

    const handleImageChange = (event: ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;
        if (file.size > 10 * 1024 * 1024) {
            setErrorMessage('La imagen es demasiado pesada, por favor usa una menor a 10 MB.');
            return;
        }

        const reader = new FileReader();
        reader.onload = () => {
            const result = typeof reader.result === 'string' ? reader.result : '';
            setImagePreview(result);
            setImageBase64(result.includes(',') ? result.split(',')[1] : result);
            setProcessed(null);
            setErrorMessage('');
        };
        reader.readAsDataURL(file);
    };

    const handleAnalyzeImage = async () => {
        if (!imageBase64) {
            setErrorMessage('Sube una imagen del sensor');
            return;
        }

        setErrorMessage('');
        setIsProcessing(true);

        try {
            const results = await processAnalysisImage(imageBase64);
            setProcessed(results);
            setStep(4);
        } catch (error) {
            console.error(error);
            if (error instanceof Error && error.message) {
                setErrorMessage(error.message);
            } else {
                setErrorMessage('No se ha detectado la región de interés o el análisis ha fallado.');
            }
        } finally {
            setIsProcessing(false);
        }
    };

    const handleSubmit = async () => {
        if (latitude === null || longitude === null || !processed) return;

        const concentration = Number(processed.pollutionData?.concentration_standard || 0);

        setIsSubmitting(true);
        setErrorMessage('');
        setSuccessMessage('');

        try {
            await submitExperiment({
                startDate,
                endDate,
                latitude,
                longitude,
                concentration,
                pollutionLevel: processed.pollutionLevel,
                inputImageB64: imageBase64,
                roiImageB64: processed.roiImageB64,
                binaryB64: processed.binaryB64,
                overlayB64: processed.overlayB64,
                analysisResults: {
                    numContours: Number(processed.analysisResults?.num_contours || 0),
                    areaPercentage: Number(processed.analysisResults?.area_percentage || 0),
                },
            });
            setSuccessMessage('Experimento guardado en la base de datos.');
            setStep(5);
        } catch (error) {
            console.error(error);
            setErrorMessage('No se pudo guardar el experimento.');
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="container mx-auto px-4 py-6">
            <div className="max-w-4xl mx-auto bg-white rounded-xl shadow-sm p-6">
                <h1 className="text-2xl font-bold text-ami-azul mb-4">
                    Herramienta de análisis de calidad del aire
                </h1>

                {errorMessage && <div className="mb-4 rounded bg-red-100 text-red-800 px-3 py-2">{errorMessage}</div>}
                {successMessage && <div className="mb-4 rounded bg-green-100 text-green-800 px-3 py-2">{successMessage}</div>}

                {step === 1 && (
                    <div className="space-y-4">
                        <h2 className="font-semibold text-lg">Paso 1. ¿Cuándo se hizo el experimento?</h2>
                        <div>
                            <label className="block text-sm mb-1">Fecha de colocación</label>
                            <input
                                type="date"
                                value={startDate}
                                onChange={(e) => setStartDate(e.target.value)}
                                className="w-full border border-gray-300 rounded px-3 py-2"
                            />
                        </div>
                        <div>
                            <label className="block text-sm mb-1">Fecha de retirada</label>
                            <input
                                type="date"
                                value={endDate}
                                onChange={(e) => setEndDate(e.target.value)}
                                className="w-full border border-gray-300 rounded px-3 py-2"
                            />
                        </div>
                        <button
                            type="button"
                            onClick={handleDatesNext}
                            className="px-4 py-2 rounded bg-ami-azul text-white"
                        >
                            Siguiente
                        </button>
                    </div>
                )}

                {step === 2 && (
                    <div className="space-y-4">
                        <h2 className="font-semibold text-lg">Paso 2. ¿Dónde se hizo el experimento?</h2>
                        <div className="flex gap-2">
                            <input
                                type="text"
                                value={locationName}
                                onChange={(e) => setLocationName(e.target.value)}
                                placeholder="Ej.: Bilbao"
                                className="flex-1 border border-gray-300 rounded px-3 py-2"
                            />
                            <button
                                type="button"
                                onClick={handleSearchLocation}
                                className="px-4 py-2 rounded bg-ami-azul text-white"
                            >
                                Buscar
                            </button>
                        </div>
                        {latitude !== null && longitude !== null && (
                            <>
                                <p className="text-sm text-gray-600">
                                    Arrastra el marcador para fijar la posición exacta.
                                </p>
                                <div ref={mapContainerRef} className="h-[400px] rounded border border-gray-200" />
                                <button
                                    type="button"
                                    onClick={handleConfirmLocation}
                                    className="px-4 py-2 rounded bg-green-600 text-white"
                                >
                                    Confirmar ubicación
                                </button>
                            </>
                        )}
                    </div>
                )}

                {step === 3 && (
                    <div className="space-y-4">
                        <h2 className="font-semibold text-lg">Paso 3. Carga la imagen del sensor</h2>
                        <input type="file" accept="image/*" onChange={handleImageChange} />
                        {imagePreview && (
                            <img
                                src={imagePreview}
                                alt="Vista previa"
                                className="max-h-[320px] rounded border border-gray-200"
                            />
                        )}
                        <button
                            type="button"
                            onClick={handleAnalyzeImage}
                            disabled={isProcessing}
                            className="px-4 py-2 rounded bg-ami-azul text-white disabled:opacity-50"
                        >
                            {isProcessing ? 'Analizando...' : 'Analizar imagen'}
                        </button>
                    </div>
                )}

                {step === 4 && processed && (
                    <div className="space-y-4">
                        <h2 className="font-semibold text-lg">Paso 4. Confirmación del área de interés (ROI)</h2>
                        <p className="text-sm text-gray-700">
                            Revisa que el área detectada sea correcta. Si no lo es, vuelve a cargar otra imagen.
                        </p>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {processed.contourImageB64 && (
                                <div>
                                    <h3 className="font-medium mb-2">Detección de la región</h3>
                                    <img
                                        src={`data:image/png;base64,${processed.contourImageB64}`}
                                        alt="Contour"
                                        className="rounded border border-gray-200"
                                    />
                                </div>
                            )}
                            {processed.roiImageB64 && (
                                <div>
                                    <h3 className="font-medium mb-2">ROI extraído</h3>
                                    <img
                                        src={`data:image/png;base64,${processed.roiImageB64}`}
                                        alt="ROI"
                                        className="rounded border border-gray-200"
                                    />
                                </div>
                            )}
                        </div>
                        <div className="flex gap-2">
                            <button
                                type="button"
                                onClick={() => {
                                    setProcessed(null);
                                    setStep(3);
                                }}
                                className="px-4 py-2 rounded border border-gray-300"
                            >
                                No, reintentar
                            </button>
                            <button
                                type="button"
                                onClick={handleSubmit}
                                disabled={isSubmitting}
                                className="px-4 py-2 rounded bg-green-600 text-white disabled:opacity-50"
                            >
                                {isSubmitting ? 'Guardando...' : 'Sí, guardar resultado'}
                            </button>
                        </div>
                    </div>
                )}

                {step === 5 && processed && (
                    <div className="space-y-4">
                        <h2 className="font-semibold text-lg">Resultados del análisis</h2>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {processed.contourImageB64 && (
                                <img src={`data:image/png;base64,${processed.contourImageB64}`} alt="Contour" className="rounded border border-gray-200" />
                            )}
                            {processed.roiImageB64 && (
                                <img src={`data:image/png;base64,${processed.roiImageB64}`} alt="ROI" className="rounded border border-gray-200" />
                            )}
                            {processed.binaryB64 && (
                                <img src={`data:image/png;base64,${processed.binaryB64}`} alt="Binary" className="rounded border border-gray-200" />
                            )}
                            {processed.overlayB64 && (
                                <img src={`data:image/png;base64,${processed.overlayB64}`} alt="Overlay" className="rounded border border-gray-200" />
                            )}
                        </div>

                        <div className="bg-gray-50 rounded p-4 border border-gray-200 text-sm">
                            <p><strong>Concentración PM10:</strong> {Number(processed.pollutionData?.concentration_standard || 0).toFixed(2)} μg/m³</p>
                            <p><strong>Nivel de polución:</strong> {processed.pollutionLevel}</p>
                            <p><strong>Número de contornos detectados:</strong> {Number(processed.analysisResults?.num_contours || 0)}</p>
                            <p><strong>Porcentaje de área detectada:</strong> {Number(processed.analysisResults?.area_percentage || 0).toFixed(3)}%</p>
                        </div>

                        <div className="overflow-x-auto">
                            <table className="w-full text-sm border border-gray-200">
                                <thead className="bg-gray-100">
                                    <tr>
                                        <th className="text-left p-2 border-b">Concentración μg/m³</th>
                                        <th className="text-left p-2 border-b">Nivel de Polución</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr><td className="p-2 border-b">0 - 10</td><td className="p-2 border-b">Muy Bueno</td></tr>
                                    <tr><td className="p-2 border-b">10 - 20</td><td className="p-2 border-b">Bueno</td></tr>
                                    <tr><td className="p-2 border-b">20 - 50</td><td className="p-2 border-b">Moderado</td></tr>
                                    <tr><td className="p-2 border-b">50 - 100</td><td className="p-2 border-b">Malo</td></tr>
                                    <tr><td className="p-2 border-b">100 - 150</td><td className="p-2 border-b">Muy Malo</td></tr>
                                    <tr><td className="p-2">&gt; 150</td><td className="p-2">Extremo</td></tr>
                                </tbody>
                            </table>
                        </div>

                        <button
                            type="button"
                            onClick={onOpenMap}
                            className="px-4 py-2 rounded bg-ami-azul text-white"
                        >
                            Ver mapa de AmiAire
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
}
