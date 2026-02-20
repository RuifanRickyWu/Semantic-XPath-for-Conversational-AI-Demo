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
