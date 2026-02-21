import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import ChatInput from "../../components/ChatInput/ChatInput";
import {
  clearSession,
  seedSessionWithExample,
  type ExampleTemplateKey,
} from "../../api/sessionApi";
import { useAppState } from "../../context/useAppState";
import "./LandingPage.css";

export default function LandingPage() {
  const navigate = useNavigate();
  const { sessionId, startNewSession } = useAppState();
  const [isSeeding, setIsSeeding] = useState(false);

  useEffect(() => {
    const oldSession = startNewSession();
    void clearSession(oldSession).catch(() => {});
  // Intentionally run once on landing mount to always start fresh.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSubmit = (query: string) => {
    // Navigate to main page with the query — API call happens there
    navigate("/main", { state: { query } });
  };

  const handleSeedExample = async (templateKey: ExampleTemplateKey) => {
    if (isSeeding) return;
    setIsSeeding(true);
    try {
      const res = await seedSessionWithExample(sessionId, templateKey);
      if (!res.success) {
        throw new Error("Failed to seed example session.");
      }
      navigate("/main");
    } catch {
      setIsSeeding(false);
    }
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
        <div className="home-example-buttons">
          <button
            className="home-example-btn"
            onClick={() => handleSeedExample("toronto_trip_3d")}
            disabled={isSeeding}
          >
            <span>Show me a 3 Day Trip in San Diego</span>
            <span className="home-example-arrow" aria-hidden="true">
              <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                <path d="M2 10.5L10.5 2M10.5 2H4.5M10.5 2V8" stroke="#7C3AED" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
          </button>
          <button
            className="home-example-btn"
            onClick={() => handleSeedExample("acl_2026_conference")}
            disabled={isSeeding}
          >
            <span>Show me the ACL 2026 Conference case</span>
            <span className="home-example-arrow" aria-hidden="true">
              <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                <path d="M2 10.5L10.5 2M10.5 2H4.5M10.5 2V8" stroke="#7C3AED" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
          </button>
          <button
            className="home-example-btn"
            onClick={() => handleSeedExample("phd_todo_sample")}
            disabled={isSeeding}
          >
            <span>Show me a sample Todo list from a PHD student</span>
            <span className="home-example-arrow" aria-hidden="true">
              <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                <path d="M2 10.5L10.5 2M10.5 2H4.5M10.5 2V8" stroke="#7C3AED" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
          </button>
        </div>
        <ChatInput onSubmit={handleSubmit} />
      </div>
    </div>
  );
}
