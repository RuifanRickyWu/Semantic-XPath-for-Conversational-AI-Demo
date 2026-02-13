import { useNavigate } from "react-router-dom";
import ChatInput from "../../components/ChatInput/ChatInput";
import QuickActions from "../../components/QuickActions/QuickActions";
import "./LandingPage.css";

export default function LandingPage() {
  const navigate = useNavigate();

  const handleSubmit = (query: string) => {
    // Navigate to main page with the query — API call happens there
    navigate("/main", { state: { query } });
  };

  return (
    <div className="home-page">
      {/* Dot grid pattern overlay */}
      <div className="home-bg-dots" />
      {/* Background tree structure */}
      <img className="home-bg-tree" src="/assets/tree-bg.svg?v=2" alt="" />
      {/* Inner glow halo */}
      <img className="home-bg-inner-glow" src="/assets/halo-glow.svg" alt="" />
      {/* Background arc decoration */}
      <div className="home-bg-arc-container">
        <div className="home-bg-arc-ring arc-ring-1" />
        <div className="home-bg-arc-ring arc-ring-2" />
        <div className="home-bg-arc-ring arc-ring-3" />
        <div className="home-bg-arc-ring arc-ring-4" />
        <div className="home-bg-arc-ring arc-ring-5" />
        <div className="home-bg-arc-ring arc-glow" />
        <div className="home-bg-arc-ring arc-ring-6" />
      </div>

      {/* Hero section */}
      <div className="home-hero">
        <h1 className="home-title">Semantic XPath for Conversational AI</h1>
        <p className="home-subtitle">Navigate to only what matters.</p>
        <p className="home-description">
          Query, navigate, and update structured conversational memory with
          precision
        </p>
      </div>

      {/* Input section */}
      <div className="home-input-section">
        <ChatInput onSubmit={handleSubmit} />
        <QuickActions onSelect={handleSubmit} />
      </div>
    </div>
  );
}
