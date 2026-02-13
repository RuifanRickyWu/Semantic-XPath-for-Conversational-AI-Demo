import { useState, useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { postColdStart } from "../../api/coldStartApi";
import type { ColdStartResponse } from "../../types/coldStart";
import "./MainPage.css";

interface ChatMessage {
  role: "user" | "system";
  content: string;
  title?: string;
  isLoading?: boolean;
  result?: ColdStartResponse;
}

interface LocationState {
  query?: string;
}

/* Icons are loaded from /assets/ SVG files */

/* ── Main Component ───────────────────────────────── */

export default function MainPage() {
  const location = useLocation();
  const state = location.state as LocationState | null;

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const initialQueryHandled = useRef(false);

  // Handle initial query from LandingPage
  useEffect(() => {
    if (state?.query && !initialQueryHandled.current) {
      initialQueryHandled.current = true;
      handleSend(state.query);
    }
  }, [state]);

  const scrollToBottom = () => {
    const container = messagesEndRef.current?.parentElement;
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async (query: string) => {
    const userMessage: ChatMessage = { role: "user", content: query };
    setMessages((prev) => [...prev, userMessage]);

    const loadingMessage: ChatMessage = {
      role: "system",
      content: "",
      isLoading: true,
    };
    setMessages((prev) => [...prev, loadingMessage]);
    setIsLoading(true);

    try {
      const result: ColdStartResponse = await postColdStart(query);

      if (result.success) {
        const systemMessage: ChatMessage = {
          role: "system",
          content: result.user_facing || "Plan generated successfully.",
          title: extractTitle(result.user_facing),
          result,
        };
        setMessages((prev) => [...prev.slice(0, -1), systemMessage]);
      } else {
        const errorMessage: ChatMessage = {
          role: "system",
          content: result.error || "Failed to generate response.",
        };
        setMessages((prev) => [...prev.slice(0, -1), errorMessage]);
      }
    } catch (err) {
      const errorMessage: ChatMessage = {
        role: "system",
        content:
          err instanceof Error
            ? err.message
            : "Failed to connect to the server.",
      };
      setMessages((prev) => [...prev.slice(0, -1), errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleInputSubmit = () => {
    const trimmed = inputValue.trim();
    if (trimmed && !isLoading) {
      setInputValue("");
      handleSend(trimmed);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleInputSubmit();
    }
  };

  function extractTitle(text?: string): string | undefined {
    if (!text) return undefined;
    const lines = text.split("\n").filter((l) => l.trim());
    if (lines.length > 0) {
      return lines[0].replace(/^#+\s*/, "").trim();
    }
    return undefined;
  }

  /* ── Render helpers ─────────────────────────────── */

  /** Render a single user message block */
  function renderUserMessage(msg: ChatMessage, index: number) {
    return (
      <div key={index} className="msg-block msg-block-user">
        <div className="msg-user-row">
          <img
            className="msg-user-avatar"
            src="/assets/user-avatar.jpg"
            alt="User"
          />
          <p className="msg-user-text">{msg.content}</p>
        </div>
        <div className="msg-divider msg-divider-full" />
      </div>
    );
  }

  /** Render a single system message block */
  function renderSystemMessage(msg: ChatMessage, index: number) {
    if (msg.isLoading) {
      return (
        <div key={index} className="msg-block msg-block-system">
          <div className="msg-system-title-row">
            <div className="msg-system-logo">
              <img src="/assets/logo-icon.svg" alt="" width="24" height="24" />
            </div>
            <div className="system-loading">
              <div className="loading-dots">
                <span />
                <span />
                <span />
              </div>
              <p className="loading-text">Generating response...</p>
            </div>
          </div>
        </div>
      );
    }

    const lines = msg.content.split("\n");
    const bodyLines = lines.slice(msg.title ? 1 : 0);

    return (
      <div key={index} className="msg-block msg-block-system">
        {/* Title row: logo + title + plan icon */}
        <div className="msg-system-title-row">
          <div className="msg-system-logo">
            <img src="/assets/logo-icon.svg" alt="" width="24" height="24" />
          </div>
          <h2 className="msg-system-title">
            {msg.title || "Response"}
          </h2>
          <button className="msg-plan-icon" aria-label="View plan details">
            <img src="/assets/view-list.svg" alt="" width="24" height="24" />
          </button>
        </div>

        {/* Divider below title */}
        <div className="msg-divider msg-divider-content" />

        {/* Content body */}
        <div className="msg-system-body">
          {bodyLines.map((line, i) => {
            const trimmed = line.trim();
            if (!trimmed) return <div key={i} className="body-spacer" />;

            // Day / section headers
            if (
              /^(#{1,3}\s+)?Day\s*\d/i.test(trimmed) ||
              /^#{1,3}\s+/.test(trimmed)
            ) {
              return (
                <div key={i} className="body-day-section">
                  <div className="msg-divider msg-divider-content" />
                  <h3 className="body-day-title">
                    {trimmed.replace(/^#+\s*/, "")}
                  </h3>
                </div>
              );
            }

            // Bold labels (Morning:, Afternoon:, Evening:, etc.)
            if (/^(\*\*)?[A-Z][\w\s]*:(\*\*)?/.test(trimmed)) {
              const colonIdx = trimmed.indexOf(":");
              const label = trimmed
                .substring(0, colonIdx + 1)
                .replace(/\*\*/g, "");
              const rest = trimmed
                .substring(colonIdx + 1)
                .replace(/\*\*/g, "")
                .trim();
              return (
                <p key={i} className="body-line">
                  <strong className="body-label">{label}</strong>
                  {rest ? ` ${rest}` : ""}
                </p>
              );
            }

            // Regular lines
            return (
              <p key={i} className="body-line">
                {trimmed.replace(/\*\*/g, "")}
              </p>
            );
          })}
        </div>
      </div>
    );
  }

  /* ── JSX ────────────────────────────────────────── */
  return (
    <div className="main-page">
      {/* Left Panel — Chat */}
      <div className="main-left-panel">
        {/* Background glow */}
        <div className="left-panel-glow" />

        <div className="chat-messages-area">
          {messages.length === 0 && (
            <div className="chat-empty">
              <p>Start a conversation...</p>
            </div>
          )}

          {messages.map((msg, index) =>
            msg.role === "user"
              ? renderUserMessage(msg, index)
              : renderSystemMessage(msg, index)
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Chat Input */}
        <div className="main-chat-input-area">
          <div className="main-chat-input-container">
            <textarea
              className="main-chat-input"
              placeholder="Ask anything..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
              disabled={isLoading}
            />
            <div className="main-chat-input-actions">
              <button
                className="main-chat-action-btn"
                aria-label="Add"
                disabled={isLoading}
              >
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <line x1="8" y1="2" x2="8" y2="14" stroke="#666" strokeWidth="2" strokeLinecap="round" />
                  <line x1="2" y1="8" x2="14" y2="8" stroke="#666" strokeWidth="2" strokeLinecap="round" />
                </svg>
              </button>
              <button
                className="main-chat-action-btn"
                aria-label="Voice"
                disabled={isLoading}
              >
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <rect x="5.5" y="1" width="5" height="9" rx="2.5" stroke="#666" strokeWidth="1.5" />
                  <path d="M3 7.5a5 5 0 0 0 10 0" stroke="#666" strokeWidth="1.5" strokeLinecap="round" />
                  <line x1="8" y1="12.5" x2="8" y2="15" stroke="#666" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              </button>
              <div className="main-chat-input-spacer" />
              <button
                className={`main-chat-submit-btn ${isLoading ? "loading" : ""}`}
                onClick={handleInputSubmit}
                disabled={!inputValue.trim() || isLoading}
                aria-label="Submit"
              >
                {isLoading ? (
                  <div className="spinner" />
                ) : (
                  <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                    <path d="M9 15V3m0 0L4 8m5-5l5 5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Right Panel — Tree Visualization (placeholder) */}
      <div className="main-right-panel">
        <div className="right-panel-placeholder">
          <p>Tree Visualization</p>
        </div>
      </div>
    </div>
  );
}
