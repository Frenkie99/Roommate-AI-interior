import { Routes, Route } from 'react-router-dom';
import LandingPage from './pages/LandingPage';
import PlaygroundPage from './pages/PlaygroundPage';
import HistoryPage from './pages/HistoryPage';

function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/playground" element={<PlaygroundPage />} />
      <Route path="/history" element={<HistoryPage />} />
    </Routes>
  );
}

export default App;
