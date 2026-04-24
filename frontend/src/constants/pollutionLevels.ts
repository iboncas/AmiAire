export interface PollutionLevelDefinition {
    name: string;
    color: string;
    range: string;
}

export const POLLUTION_LEVELS: PollutionLevelDefinition[] = [
    { name: 'Extremo', color: '#d73027', range: '≥ 150 μg/m³' },
    { name: 'Alto', color: '#fc8d59', range: '50 – 149 μg/m³' },
    { name: 'Moderado', color: '#fee08b', range: '20 – 49 μg/m³' },
    { name: 'Bueno', color: '#91cf60', range: '10 – 19 μg/m³' },
    { name: 'Bajo', color: '#1a9850', range: '< 10 μg/m³' },
];
