import { BrowserRouter, Routes, Route } from "react-router-dom";
import Header from "./components/Header/Header";
import LandingPage from "./pages/LandingPage/LandingPage";
import MainPage from "./pages/MainPage/MainPage";
import ResultPage from "./pages/ResultPage/ResultPage";
import ScoringPage from "./pages/ScoringPage/ScoringPage";
import { AppStateProvider } from "./context/AppStateContext";

export default function App() {
  return (
    <BrowserRouter>
      <AppStateProvider>
        <Header />
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/main" element={<MainPage />} />
          <Route path="/result" element={<ResultPage />} />
          <Route path="/scoring" element={<ScoringPage />} />
        </Routes>
      </AppStateProvider>
    </BrowserRouter>
  );
}
