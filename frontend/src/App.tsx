import { useEffect, useState } from 'react';
import Header from './components/Header';
import ParticleAnalysisPage from './components/pages/ParticleAnalysisPage';
import MapPage from './components/pages/MapPage';
import Footer from './components/Footer';
import ErrorBoundary from './components/ErrorBoundary';

type View = 'analysis' | 'map';
const ANALYSIS_PATH = '/';
const MAP_PATH = '/map_contributions';

function readInitialView(): View {
  if (typeof window === 'undefined') return 'analysis';
  return window.location.pathname === MAP_PATH ? 'map' : 'analysis';
}

function pathForView(view: View): string {
  return view === 'map' ? MAP_PATH : ANALYSIS_PATH;
}

function App() {
  const [view, setView] = useState<View>(readInitialView);

  const handleNavigate = (nextView: View) => {
    const nextPath = pathForView(nextView);

    if (typeof window !== 'undefined' && window.location.pathname !== nextPath) {
      window.history.pushState({}, '', nextPath);
    }

    setView(nextView);
  };

  useEffect(() => {
    const handlePopState = () => {
      setView(readInitialView());
    };

    window.addEventListener('popstate', handlePopState);
    return () => {
      window.removeEventListener('popstate', handlePopState);
    };
  }, []);

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
