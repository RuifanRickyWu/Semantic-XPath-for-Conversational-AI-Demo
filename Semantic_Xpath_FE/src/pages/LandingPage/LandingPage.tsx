import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import ChatInput from "../../components/ChatInput/ChatInput";
import {
  clearSession,
  listExampleTemplates,
  seedSessionWithExample,
  type ExampleTemplate,
  type ExampleTemplateKey,
} from "../../api/sessionApi";
import type { ChatMessage } from "../../context/AppStateContext";
import { typeToCrudAction } from "../../types/chat";
import { useAppState } from "../../context/useAppState";
import "./LandingPage.css";

export default function LandingPage() {
  const navigate = useNavigate();
  const {
    sessionId,
    startNewSession,
    setMessages,
    setTasks,
    setActiveTaskId,
    setActivePlanXml,
    setHighlightMode,
    setHighlightedPaths,
    setLatestXpathQuery,
    setLatestOriginalQuery,
    setSelectedMessageIndex,
    currentTaskIdRef,
    currentVersionIdRef,
  } = useAppState();
  const [isSeeding, setIsSeeding] = useState(false);
  const [examples, setExamples] = useState<ExampleTemplate[]>([]);

  useEffect(() => {
    const oldSession = startNewSession();
    void clearSession(oldSession).catch(() => {});
    // Intentionally run once on landing mount to always start fresh.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let cancelled = false;
    void listExampleTemplates()
      .then((templates) => {
        if (!cancelled) {
          setExamples(templates);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setExamples([]);
        }
      });
    return () => {
      cancelled = true;
    };
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

      const seededMessages = ((res.seeded_messages ?? []) as ChatMessage[]).map(
        (msg) => {
          if (msg.role !== "system") return msg;
          return {
            ...msg,
            crudAction: typeToCrudAction(msg.type),
            snapshotTaskId: msg.snapshotTaskId ?? res.active_task_id,
            snapshotVersionId: msg.snapshotVersionId ?? res.active_version_id,
          };
        }
      );
      setMessages(seededMessages);
      setTasks([]);
      setActivePlanXml(null);
      setActiveTaskId(res.active_task_id);
      currentTaskIdRef.current = res.active_task_id;
      currentVersionIdRef.current = res.active_version_id;

      let selectedCrudIndex: number | null = null;
      for (let i = seededMessages.length - 1; i >= 0; i--) {
        const msg = seededMessages[i];
        if (msg.role !== "system") continue;
        const crud = typeToCrudAction(msg.type);
        if (!crud) continue;
        selectedCrudIndex = i;
        setHighlightMode(crud);
        setHighlightedPaths(msg.affectedNodePaths ?? null);
        setLatestXpathQuery(msg.xpathQuery ?? null);
        setLatestOriginalQuery(msg.originalQuery ?? null);
        break;
      }
      if (selectedCrudIndex === null) {
        setHighlightMode(null);
        setHighlightedPaths(null);
        setLatestXpathQuery(null);
        setLatestOriginalQuery(null);
      }
      setSelectedMessageIndex(selectedCrudIndex);
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
        <h1 className="home-title">SemanticXpath Chat</h1>
        <p className="home-subtitle">Navigate to only what matters.</p>
        <p className="home-description">
          Query, navigate, and update structured conversational memory with
          precision
        </p>
      </div>

      {/* Input section */}
      <div className="home-input-section">
        <div className="home-example-buttons">
          {examples.map((example) => (
            <button
              key={example.template_key}
              className="home-example-btn"
              onClick={() => handleSeedExample(example.template_key)}
              disabled={isSeeding}
            >
              <span>{example.label}</span>
              <span className="home-example-arrow" aria-hidden="true">
                <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                  <path
                    d="M2 10.5L10.5 2M10.5 2H4.5M10.5 2V8"
                    stroke="#7C3AED"
                    strokeWidth="1.6"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </span>
            </button>
          ))}
        </div>
        <ChatInput onSubmit={handleSubmit} />
      </div>
    </div>
  );
}
