import { useState, type KeyboardEvent } from "react";
import "./ChatInput.css";

interface ChatInputProps {
  onSubmit: (query: string) => void;
  isLoading?: boolean;
}

export default function ChatInput({ onSubmit, isLoading = false }: ChatInputProps) {
  const [value, setValue] = useState("");

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (trimmed && !isLoading) {
      onSubmit(trimmed);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="chat-input-wrapper">
      <div className="chat-input-container">
        <textarea
          className="chat-input"
          placeholder="Ask anything..."
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          disabled={isLoading}
        />
        <div className="chat-input-actions">
          <button className="chat-action-btn small" aria-label="Add" disabled={isLoading}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <line x1="8" y1="2" x2="8" y2="14" stroke="#666" strokeWidth="2" strokeLinecap="round" />
              <line x1="2" y1="8" x2="14" y2="8" stroke="#666" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
          <button className="chat-action-btn small" aria-label="Voice" disabled={isLoading}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <rect x="5.5" y="1" width="5" height="9" rx="2.5" stroke="#666" strokeWidth="1.5" />
              <path d="M3 7.5a5 5 0 0 0 10 0" stroke="#666" strokeWidth="1.5" strokeLinecap="round" />
              <line x1="8" y1="12.5" x2="8" y2="15" stroke="#666" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
          <div className="chat-input-spacer" />
          <button
            className={`chat-submit-btn ${isLoading ? "loading" : ""}`}
            onClick={handleSubmit}
            disabled={!value.trim() || isLoading}
            aria-label="Submit"
          >
            {isLoading ? (
              <div className="spinner" />
            ) : (
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                <path
                  d="M9 15V3m0 0L4 8m5-5l5 5"
                  stroke="white"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
