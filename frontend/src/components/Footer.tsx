interface FooterProps {
    onNavigate: (view: 'analysis' | 'map') => void;
}

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
                        <button
                            type="button"
                            onClick={() => onNavigate('analysis')}
                            className="text-gray-500 hover:text-ami-azul bg-transparent border-0 cursor-pointer p-0"
                        >
                            Herramienta Análisis de polución
                        </button>
                    </li>
                    <li>
                        <button
                            type="button"
                            onClick={() => onNavigate('map')}
                            className="text-gray-500 hover:text-ami-azul bg-transparent border-0 cursor-pointer p-0"
                        >
                            Mapa de AmiAire
                        </button>
                    </li>
                </ul>
            </div>
        </footer>
    );
}
