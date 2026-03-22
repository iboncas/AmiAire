import { useState } from 'react';
import Header from './components/Header';
import ParticleAnalysisPage from './components/pages/ParticleAnalysisPage';
import MapPage from './components/pages/MapPage';
import Footer from './components/Footer';
import ErrorBoundary from './components/ErrorBoundary';

type View = 'analysis' | 'map';

function App() {
  const [view, setView] = useState<View>('analysis');

  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-ami-gris">
        <Header activeView={view} onNavigate={setView} />

        {view === 'analysis' && (
          <ParticleAnalysisPage onOpenMap={() => setView('map')} />
        )}

        {view === 'map' && <MapPage />}
        <Footer onNavigate={setView} />
      </div>
    </ErrorBoundary>
  );
}

export default App;
