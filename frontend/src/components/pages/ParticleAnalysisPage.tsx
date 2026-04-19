import { useEffect, useRef, useState, type ChangeEvent } from 'react';
import L from 'leaflet';
import {
    geocode,
    processAnalysisImage,
    submitExperiment,
    validateSensorImage,
    type ProcessedAnalysis,
} from '../../services/api';

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
    const [isValidatingImage, setIsValidatingImage] = useState(false);
    const [showInvalidSensorModal, setShowInvalidSensorModal] = useState(false);

    const mapContainerRef = useRef<HTMLDivElement | null>(null);
    const mapRef = useRef<L.Map | null>(null);
    const markerRef = useRef<L.Marker | null>(null);

    const openNativeDatePicker = (input: HTMLInputElement) => {
        const pickerInput = input as HTMLInputElement & { showPicker?: () => void };
        if (typeof pickerInput.showPicker === 'function') {
            try {
                pickerInput.showPicker();
            } catch {
                // Some browsers restrict showPicker in specific interaction contexts.
            }
        }
    };

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

        const currentZoom = mapRef.current.getZoom();
        mapRef.current.setView([latitude, longitude], currentZoom);
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

    const resetImageSelection = () => {
        setImagePreview('');
        setImageBase64('');
        setProcessed(null);
    };

    const handleImageChange = (event: ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;
        if (file.size > 10 * 1024 * 1024) {
            setErrorMessage('La imagen es demasiado pesada, por favor usa una menor a 10 MB.');
            event.target.value = '';
            return;
        }

        const reader = new FileReader();
        reader.onload = async () => {
            const result = typeof reader.result === 'string' ? reader.result : '';
            setErrorMessage('');
            setSuccessMessage('');
            setIsValidatingImage(true);

            const nextImageBase64 = result.includes(',') ? result.split(',')[1] : result;

            try {
                const validation = await validateSensorImage(nextImageBase64);
                if (!validation.is_sensor) {
                    resetImageSelection();
                    event.target.value = '';
                    setShowInvalidSensorModal(true);
                    return;
                }

                setImagePreview(result);
                setImageBase64(nextImageBase64);
                setProcessed(null);
            } catch (error) {
                resetImageSelection();
                event.target.value = '';
                if (error instanceof Error && error.message) {
                    setErrorMessage(error.message);
                } else {
                    setErrorMessage('No se pudo validar la imagen del sensor.');
                }
            } finally {
                setIsValidatingImage(false);
            }
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

        const pm10Concentration = Number(
            processed.pollutionData?.PM10?.concentration_standard ??
            processed.pollutionData?.concentration_standard_pm10 ??
            0
        );
        const pm25Concentration = Number(
            processed.pollutionData?.PM25?.concentration_standard ??
            processed.pollutionData?.concentration_standard_pm25 ??
            0
        );
        const pollutionLevelPM10 =
            processed.pollutionLevels?.PM10 || 'Sin clasificar';
        const pollutionLevelPM25 =
            processed.pollutionLevels?.PM25 || 'Sin clasificar';

        setIsSubmitting(true);
        setErrorMessage('');
        setSuccessMessage('');

        try {
            await submitExperiment({
                startDate,
                endDate,
                latitude,
                longitude,
                pm10Concentration,
                pm25Concentration,
                pollutionLevelPM10,
                pollutionLevelPM25,
                inputImageB64: imageBase64,
                analysisResults: {
                    numContours: Number(processed.analysisResults?.num_contours || 0),
                    areaPercentage: Number(processed.analysisResults?.area_percentage || 0),
                },
            });
            setSuccessMessage('Experimento guardado en la base de datos.');
            setStep(5);
        } catch (error) {
            console.error(error);
            if (error instanceof Error && error.message) {
                setErrorMessage(error.message);
            } else {
                setErrorMessage('No se pudo guardar el experimento.');
            }
        } finally {
            setIsSubmitting(false);
        }
    };

    const pm10Concentration = Number(
        processed?.pollutionData?.PM10?.concentration_standard ??
        processed?.pollutionData?.concentration_standard_pm10 ??
        0
    );
    const pm25Concentration = Number(
        processed?.pollutionData?.PM25?.concentration_standard ??
        processed?.pollutionData?.concentration_standard_pm25 ??
        0
    );
    const pollutionLevelPM10 =
        processed?.pollutionLevels?.PM10 || 'Sin clasificar';
    const pollutionLevelPM25 =
        processed?.pollutionLevels?.PM25 || 'Sin clasificar';

    return (
        <div className="container mx-auto px-4 py-6">
            {showInvalidSensorModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 px-4">
                    <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
                        <h2 className="text-xl font-bold text-ami-azul">Imagen no valida</h2>
                        <p className="mt-3 text-sm leading-6 text-gray-700">
                            La imagen subida no parece corresponder a un sensor. Por favor, selecciona una foto real del sensor para continuar.
                        </p>
                        <div className="mt-5 flex justify-end">
                            <button
                                type="button"
                                onClick={() => setShowInvalidSensorModal(false)}
                                className="rounded-lg bg-ami-azul px-4 py-2 text-white"
                            >
                                Entendido
                            </button>
                        </div>
                    </div>
                </div>
            )}

            <div className="max-w-4xl mx-auto bg-white rounded-xl shadow-sm p-6">
                <h1 className="text-2xl font-bold text-ami-azul mb-4">
                    Herramienta de análisis de calidad del aire
                </h1>

                {errorMessage && <div className="mb-4 rounded bg-red-100 text-red-800 px-3 py-2">{errorMessage}</div>}
                {successMessage && <div className="mb-4 rounded bg-green-100 text-green-800 px-3 py-2">{successMessage}</div>}

                {step === 1 && (
                    <form
                        className="space-y-4"
                        onSubmit={(e) => {
                            e.preventDefault();
                            handleDatesNext();
                        }}
                    >
                        <h2 className="font-semibold text-lg">Paso 1. ¿Cuándo se hizo el experimento?</h2>
                        <div>
                            <label className="block text-sm mb-1">Fecha de colocación</label>
                            <input
                                type="date"
                                value={startDate}
                                onChange={(e) => setStartDate(e.target.value)}
                                onFocus={(e) => openNativeDatePicker(e.currentTarget)}
                                onClick={(e) => openNativeDatePicker(e.currentTarget)}
                                className="w-full border border-gray-300 rounded px-3 py-2"
                            />
                        </div>
                        <div>
                            <label className="block text-sm mb-1">Fecha de retirada</label>
                            <input
                                type="date"
                                value={endDate}
                                onChange={(e) => setEndDate(e.target.value)}
                                onFocus={(e) => openNativeDatePicker(e.currentTarget)}
                                onClick={(e) => openNativeDatePicker(e.currentTarget)}
                                className="w-full border border-gray-300 rounded px-3 py-2"
                            />
                        </div>
                        <button
                            type="submit"
                            className="px-4 py-2 rounded bg-ami-azul text-white"
                        >
                            Siguiente
                        </button>
                    </form>
                )}

                {step === 2 && (
                    <form
                        className="space-y-4"
                        onSubmit={(e) => {
                            e.preventDefault();
                            if (latitude !== null && longitude !== null) {
                                handleConfirmLocation();
                                return;
                            }
                            void handleSearchLocation();
                        }}
                    >
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
                                type="submit"
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
                    </form>
                )}

                {step === 3 && (
                    <form
                        className="space-y-4"
                        onSubmit={(e) => {
                            e.preventDefault();
                            void handleAnalyzeImage();
                        }}
                    >
                        <h2 className="font-semibold text-lg">Paso 3. Carga la imagen del sensor</h2>
                        <p className="text-sm text-gray-700">
                            El análisis calcula automáticamente PM10 y PM2.5.
                        </p>
                        <input type="file" accept="image/*" onChange={handleImageChange} />
                        {isValidatingImage && (
                            <p className="text-sm text-gray-600">
                                Validando que la imagen corresponda a un sensor...
                            </p>
                        )}
                        {imagePreview && (
                            <img
                                src={imagePreview}
                                alt="Vista previa"
                                className="max-h-[320px] rounded border border-gray-200"
                            />
                        )}
                        <button
                            type="submit"
                            disabled={isProcessing || isValidatingImage}
                            className="px-4 py-2 rounded bg-ami-azul text-white disabled:opacity-50"
                        >
                            {isProcessing ? 'Analizando...' : 'Analizar imagen'}
                        </button>
                    </form>
                )}

                {step === 4 && processed && (
                    <form
                        className="space-y-4"
                        onSubmit={(e) => {
                            e.preventDefault();
                            void handleSubmit();
                        }}
                    >
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
                                type="submit"
                                disabled={isSubmitting}
                                className="px-4 py-2 rounded bg-green-600 text-white disabled:opacity-50"
                            >
                                {isSubmitting ? 'Guardando...' : 'Sí, guardar resultado'}
                            </button>
                        </div>
                    </form>
                )}

                {step === 5 && processed && (
                    <div className="space-y-4">
                        <h2 className="font-semibold text-lg">Resultados del análisis</h2>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {processed.contourImageB64 && (
                                <img
                                    src={`data:image/png;base64,${processed.contourImageB64}`}
                                    alt="Contour"
                                    className="w-full h-64 object-contain rounded border border-gray-200 bg-white"
                                />
                            )}
                            {processed.roiImageB64 && (
                                <img
                                    src={`data:image/png;base64,${processed.roiImageB64}`}
                                    alt="ROI"
                                    className="w-full h-64 object-contain rounded border border-gray-200 bg-white"
                                />
                            )}
                            {processed.binaryB64 && (
                                <img
                                    src={`data:image/png;base64,${processed.binaryB64}`}
                                    alt="Binary"
                                    className="w-full h-64 object-contain rounded border border-gray-200 bg-white"
                                />
                            )}
                            {processed.overlayB64 && (
                                <img
                                    src={`data:image/png;base64,${processed.overlayB64}`}
                                    alt="Overlay"
                                    className="w-full h-64 object-contain rounded border border-gray-200 bg-white"
                                />
                            )}
                        </div>

                        <div className="bg-gray-50 rounded p-4 border border-gray-200 text-sm">
                            <p><strong>Concentración PM10:</strong> {pm10Concentration.toFixed(2)} μg/m³</p>
                            <p><strong>Nivel de polución PM10:</strong> {pollutionLevelPM10}</p>
                            <p><strong>Concentración PM2.5:</strong> {pm25Concentration.toFixed(2)} μg/m³</p>
                            <p><strong>Nivel de polución PM2.5:</strong> {pollutionLevelPM25}</p>
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
