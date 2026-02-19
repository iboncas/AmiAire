export default function Legend() {
    const levels = [
        { name: 'Extremo', color: '#d73027', range: '≥ 150 μg/m³' },
        { name: 'Alto', color: '#fc8d59', range: '50 – 149 μg/m³' },
        { name: 'Moderado', color: '#fee08b', range: '20 – 49 μg/m³' },
        { name: 'Bueno', color: '#1a9850', range: '10 – 19 μg/m³' },
        { name: 'Bajo', color: '#91cf60', range: '< 10 μg/m³' },
    ];

    return (
        <div className="bg-white rounded-lg shadow-md overflow-hidden mb-4">
            <div className="bg-ami-azul-claro text-white px-4 py-3">
                <h5 className="text-lg font-semibold m-0">Niveles de Polución</h5>
            </div>
            <div className="p-4">
                {levels.map((level) => (
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
