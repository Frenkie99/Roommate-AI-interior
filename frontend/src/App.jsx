import { lazy, Suspense } from 'react';
import { Routes, Route } from 'react-router-dom';
import LandingPage from './pages/LandingPage';
import AuthModal from './components/AuthModal';
import { useAuth } from './context/AuthContext';

const PlaygroundPage = lazy(() => import('./pages/PlaygroundPage'));
const HistoryPage = lazy(() => import('./pages/HistoryPage'));

function App() {
  const { authModalOpen, closeAuth } = useAuth();
  return (
    <><Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-warm-gold/30 border-t-warm-gold rounded-full animate-spin" />
      </div>
    }>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/playground" element={<PlaygroundPage />} />
        <Route path="/history" element={<HistoryPage />} />
      </Routes>
    </Suspense><AuthModal isOpen={authModalOpen} onClose={closeAuth} /></>
  );
}

export default App;
