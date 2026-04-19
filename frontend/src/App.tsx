import { useState } from 'react';
import Header from './components/Header';
import ParticleAnalysisPage from './components/pages/ParticleAnalysisPage';
import MapPage from './components/pages/MapPage';
import Footer from './components/Footer';
import ErrorBoundary from './components/ErrorBoundary';

type View = 'analysis' | 'map';
const VIEW_STORAGE_KEY = 'amiaire.activeView';

function readInitialView(): View {
  if (typeof window === 'undefined') return 'analysis';
  try {
    const saved = window.sessionStorage.getItem(VIEW_STORAGE_KEY);
    return saved === 'map' ? 'map' : 'analysis';
  } catch {
    return 'analysis';
  }
}

function App() {
  const [view, setView] = useState<View>(readInitialView);

  const handleNavigate = (nextView: View) => {
    try {
      window.sessionStorage.setItem(VIEW_STORAGE_KEY, nextView);
    } catch {
      // Ignore storage errors.
    }
    setView(nextView);
  };

  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-ami-gris">
        <Header activeView={view} onNavigate={handleNavigate} />

        <div
          className={
            view === 'analysis'
              ? 'block'
              : 'absolute -left-[99999px] top-auto w-px h-px overflow-hidden'
          }
          aria-hidden={view !== 'analysis'}
        >
          <ParticleAnalysisPage onOpenMap={() => handleNavigate('map')} />
        </div>

        <div
          className={
            view === 'map'
              ? 'block'
              : 'absolute -left-[99999px] top-auto w-px h-px overflow-hidden'
          }
          aria-hidden={view !== 'map'}
        >
          <MapPage isActive={view === 'map'} />
        </div>
        <Footer onNavigate={handleNavigate} />
      </div>
    </ErrorBoundary>
  );
}

export default App;
