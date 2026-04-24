interface HeaderProps {
    activeView: 'analysis' | 'map';
    onNavigate: (view: 'analysis' | 'map') => void;
}

const ANALYSIS_PATH = '/';
const MAP_PATH = '/map_contributions';

export default function Header({ activeView, onNavigate }: HeaderProps) {
    return (
        <header className="bg-white shadow-sm px-4 py-2 sticky top-0 z-50">
            <div className="max-w-7xl mx-auto flex items-center justify-between">
                <a
                    href={ANALYSIS_PATH}
                    onClick={(event) => {
                        event.preventDefault();
                        onNavigate('analysis');
                    }}
                    className="flex items-center text-gray-900 no-underline"
                >
                    <img src="/icono.png" alt="AmIAire" className="h-10 mr-2" />
                </a>

                <nav className="flex items-center gap-2">
                    <a
                        href={ANALYSIS_PATH}
                        onClick={(event) => {
                            event.preventDefault();
                            onNavigate('analysis');
                        }}
                        className={`px-3 py-2 rounded text-sm font-medium ${activeView === 'analysis'
                            ? 'bg-ami-azul text-white'
                            : 'text-ami-azul hover:bg-gray-100'
                            }`}
                    >
                        Herramienta
                    </a>
                    <a
                        href={MAP_PATH}
                        onClick={(event) => {
                            event.preventDefault();
                            onNavigate('map');
                        }}
                        className={`px-3 py-2 rounded text-sm font-medium ${activeView === 'map'
                            ? 'bg-ami-azul text-white'
                            : 'text-ami-azul hover:bg-gray-100'
                            }`}
                    >
                        Mapa
                    </a>
                </nav>
            </div>
        </header>
    );
}
