import { useState } from "react";
import { useNavigate } from "react-router-dom";
import ChatInput from "../../components/ChatInput/ChatInput";
import QuickActions from "../../components/QuickActions/QuickActions";
import { postColdStart } from "../../api/coldStartApi";
import type { ColdStartResponse } from "../../types/coldStart";
import "./HomePage.css";

export default function HomePage() {
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (query: string) => {
    setIsLoading(true);
    setError(null);

    try {
      const result: ColdStartResponse = await postColdStart(query);

      if (result.success) {
        navigate("/result", { state: { result, query } });
      } else {
        setError(result.error || "Cold start generation failed.");
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to connect to the server."
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="home-page">
      {/* Background decoration */}
      <div className="home-bg-arc" />

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
        <ChatInput onSubmit={handleSubmit} isLoading={isLoading} />
        <QuickActions onSelect={handleSubmit} />
        {error && <div className="home-error">{error}</div>}
        {isLoading && (
          <div className="home-loading-text">
            Generating plan and schema... This may take a moment.
          </div>
        )}
      </div>
    </div>
  );
}
