import { useEffect, useState } from 'react';
import Header from './components/Header';
import ParticleAnalysisPage from './components/pages/ParticleAnalysisPage';
import MapPage from './components/pages/MapPage';
import Footer from './components/Footer';
import ErrorBoundary from './components/ErrorBoundary';

type View = 'analysis' | 'map';
const ANALYSIS_PATH = '/';
const MAP_PATH = '/map_contributions';

interface NavigateOptions {
  scrollToTop?: boolean;
}

declare global {
  interface Window {
    gtag?: (...args: unknown[]) => void;
  }
}

function readInitialView(): View {
  if (typeof window === 'undefined') return 'analysis';
  return window.location.pathname === MAP_PATH ? 'map' : 'analysis';
}

function pathForView(view: View): string {
  return view === 'map' ? MAP_PATH : ANALYSIS_PATH;
}

function trackPageView() {
  if (typeof window === 'undefined' || typeof window.gtag !== 'function') {
    return;
  }

  window.gtag('event', 'page_view', {
    page_title: document.title,
    page_location: window.location.href,
    page_path: window.location.pathname,
  });
}

function App() {
  const [view, setView] = useState<View>(readInitialView);

  const handleNavigate = (nextView: View, options: NavigateOptions = {}) => {
    const nextPath = pathForView(nextView);

    if (typeof window !== 'undefined' && window.location.pathname !== nextPath) {
      window.history.pushState({}, '', nextPath);
    }

    setView(nextView);

    if (options.scrollToTop && typeof window !== 'undefined') {
      window.scrollTo({ top: 0, behavior: 'auto' });
    }
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

  useEffect(() => {
    trackPageView();
  }, [view]);

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
          <ParticleAnalysisPage onOpenMap={() => handleNavigate('map', { scrollToTop: true })} />
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
