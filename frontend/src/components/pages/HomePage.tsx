interface HomePageProps {
    onStartAnalysis: () => void;
    onOpenMap: () => void;
}

export default function HomePage({ onStartAnalysis, onOpenMap }: HomePageProps) {
    return (
        <div className="container mx-auto px-4 py-8">
            <section className="bg-white rounded-xl shadow-sm p-8 text-center mb-6">
                <h1 className="text-4xl font-bold text-ami-azul mb-3">Air Pollution Analysis</h1>
                <p className="text-gray-700 mb-6">
                    Analiza y monitoriza la calidad del aire con sensores y contribuciones ciudadanas.
                </p>
                <div className="flex flex-wrap justify-center gap-3">
                    <button
                        type="button"
                        onClick={onStartAnalysis}
                        className="px-5 py-3 rounded bg-ami-azul text-white hover:opacity-90"
                    >
                        Empezar análisis
                    </button>
                    <button
                        type="button"
                        onClick={onOpenMap}
                        className="px-5 py-3 rounded border border-ami-azul text-ami-azul hover:bg-gray-100"
                    >
                        Ver mapa
                    </button>
                </div>
            </section>

            <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                {[
                    ['Combustión doméstica', 'Calefacción y cocinado con combustibles.'],
                    ['Vehículos', 'Emisiones urbanas del tráfico.'],
                    ['Industrias', 'Procesos industriales y energía.'],
                    ['Incendios', 'Eventos naturales y provocados.'],
                ].map(([title, text]) => (
                    <article key={title} className="bg-white rounded-xl p-4 shadow-sm">
                        <h3 className="font-semibold text-ami-azul mb-2">{title}</h3>
                        <p className="text-sm text-gray-700">{text}</p>
                    </article>
                ))}
            </section>

            <section className="bg-ami-azul text-white rounded-xl p-6">
                <h2 className="text-xl font-semibold mb-2">Dato clave</h2>
                <p>
                    Una parte muy alta de la población mundial respira aire que supera límites recomendados
                    de calidad.
                </p>
            </section>
        </div>
    );
}
