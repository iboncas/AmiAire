import { POLLUTION_LEVELS } from '../constants/pollutionLevels';

export default function Legend() {
    return (
        <div className="bg-white rounded-lg shadow-md overflow-hidden mb-4">
            <div className="bg-ami-azul text-white px-4 py-3">
                <h5 className="text-lg font-semibold m-0">Niveles de Contaminación</h5>
            </div>
            <div className="p-4">
                <div className="mb-4 text-sm text-gray-700">
                    <div className="flex items-center gap-2 mb-2">
                        <span className="w-[14px] h-[14px] inline-block rounded-full border border-gray-700 bg-gray-200"></span>
                        <span>Círculo: sensores DIY</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="inline-block" style={{ width: 18, height: 16 }}>
                            <svg width="18" height="16" viewBox="0 0 18 16" xmlns="http://www.w3.org/2000/svg">
                                <defs>
                                    <linearGradient id="legend-official-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                                        <stop offset="50%" stopColor="#fc8d59" />
                                        <stop offset="50%" stopColor="#fee08b" />
                                    </linearGradient>
                                </defs>
                                <path
                                    d="M9 1 L17 15 L1 15 Z"
                                    fill="url(#legend-official-gradient)"
                                    stroke="#1f2937"
                                    strokeWidth="1.2"
                                />
                            </svg>
                        </span>
                        <span>Triángulo: estaciones oficiales. Izquierda PM10, derecha PM2.5.</span>
                    </div>
                </div>
                {POLLUTION_LEVELS.map((level) => (
                    <div key={level.name} className="flex items-center gap-2 mb-2 text-sm">
                        <span
                            className="w-[18px] h-[18px] inline-block border border-gray-800 rounded"
                            style={{ backgroundColor: level.color }}
                        ></span>
                        <span>
                            {level.name} ({level.range})
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
}
