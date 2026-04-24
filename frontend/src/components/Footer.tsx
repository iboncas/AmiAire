interface FooterProps {
    onNavigate: (view: 'analysis' | 'map') => void;
}

const ANALYSIS_PATH = '/';
const MAP_PATH = '/map_contributions';

export default function Footer({ onNavigate }: FooterProps) {
    return (
        <footer className="bg-white mt-8 border-t border-gray-200">
            <div className="w-full">
                <img
                    src="/AmIAirelogos.jpg"
                    alt="Entidades colaboradoras de AmiAire"
                    className="w-full h-auto object-contain"
                />
            </div>
            <div className="container mx-auto px-4 py-6 text-center text-gray-500 border-t border-gray-200">
                <p className="mb-2">&copy; 2026 AmiAire. All Rights Reserved.</p>
                <p className="mb-2">Desarrollado por DeustoTech, University of Deusto, Bilbao, Spain.</p>
                <ul className="flex items-center justify-center gap-4 text-sm">
                    <li>
                        <a
                            href={ANALYSIS_PATH}
                            onClick={(event) => {
                                event.preventDefault();
                                onNavigate('analysis');
                            }}
                            className="text-gray-500 hover:text-ami-azul"
                        >
                            Herramienta Análisis de contaminación
                        </a>
                    </li>
                    <li>
                        <a
                            href={MAP_PATH}
                            onClick={(event) => {
                                event.preventDefault();
                                onNavigate('map');
                            }}
                            className="text-gray-500 hover:text-ami-azul"
                        >
                            Mapa de AmiAire
                        </a>
                    </li>
                </ul>
            </div>
        </footer>
    );
}
