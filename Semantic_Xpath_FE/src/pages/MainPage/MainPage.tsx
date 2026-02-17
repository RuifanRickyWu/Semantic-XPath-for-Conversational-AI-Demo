import { useState, useEffect, useRef, useCallback } from "react";
import { useLocation } from "react-router-dom";
import { postChat } from "../../api/chatApi";
import { getTasks, getTaskPlan, activateTask } from "../../api/tasksApi";
import type { ChatResponseType, CrudAction } from "../../types/chat";
import { typeToCrudAction, CRUD_CONFIG } from "../../types/chat";
import type { TaskSummary } from "../../types/task";
import PlanTreeView from "../../components/PlanTreeView/PlanTreeView";
import "./MainPage.css";

interface ChatMessage {
  role: "user" | "system";
  content: string;
  /** Response type from backend — drives rendering behavior */
  type?: ChatResponseType;
  title?: string;
  isLoading?: boolean;
  crudAction?: CrudAction | null;
  xpathQuery?: string;
  originalQuery?: string;
  affectedNodePaths?: any[][];
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

  // Generate a stable session ID for this page instance
  const sessionIdRef = useRef<string>(crypto.randomUUID());

  // Task tab bar state
  const [tasks, setTasks] = useState<TaskSummary[]>([]);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [activePlanXml, setActivePlanXml] = useState<string | null>(null);

  // Tree highlight state — driven by the latest CRUD operation
  const [highlightMode, setHighlightMode] = useState<CrudAction | null>(null);
  const [highlightedPaths, setHighlightedPaths] = useState<any[][] | null>(null);

  // Latest query display (shown on both left chat and right panel)
  const [latestXpathQuery, setLatestXpathQuery] = useState<string | null>(null);
  const [latestOriginalQuery, setLatestOriginalQuery] = useState<string | null>(null);

  /** Refresh the task list from the backend and optionally load a plan. */
  const refreshTasks = useCallback(async (loadPlanForTaskId?: string) => {
    try {
      const res = await getTasks();
      setTasks(res.tasks);
      setActiveTaskId(res.active_task_id);
      const taskToLoad = loadPlanForTaskId || res.active_task_id;
      if (taskToLoad) {
        try {
          const planRes = await getTaskPlan(taskToLoad);
          setActivePlanXml(planRes.plan_xml);
        } catch {
          setActivePlanXml(null);
        }
      }
    } catch {
      // Backend may not be running yet; keep empty state
    }
  }, []);

  // Load task list on mount
  useEffect(() => {
    refreshTasks();
  }, [refreshTasks]);

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
      const result = await postChat(query, sessionIdRef.current);

      if (result.success) {
        const crud = typeToCrudAction(result.type);
        const systemMessage: ChatMessage = {
          role: "system",
          content: result.message || "Done.",
          type: result.type,
          title: result.type === "PLAN_CREATE"
            ? extractTitle(result.message)
            : undefined,
          crudAction: crud,
          xpathQuery: result.xpath_query,
          originalQuery: result.original_query,
          affectedNodePaths: result.affected_node_paths,
        };
        setMessages((prev) => [...prev.slice(0, -1), systemMessage]);

        // Update tree highlight state and query bars
        if (crud && result.affected_node_paths?.length) {
          setHighlightMode(crud);
          setHighlightedPaths(result.affected_node_paths);
        } else {
          setHighlightMode(null);
          setHighlightedPaths(null);
        }
        setLatestXpathQuery(result.xpath_query || null);
        setLatestOriginalQuery(result.original_query || null);

        // Refresh task tab bar when backend state may have changed
        const newTaskId = result.session_updates?.active_task_id;
        refreshTasks(newTaskId || undefined);
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

  /* ── Task tab bar handler ────────────────────────── */

  const handleTabClick = async (taskId: string) => {
    if (taskId === activeTaskId) return;
    try {
      const res = await activateTask(taskId, sessionIdRef.current);
      setActiveTaskId(res.active_task_id);
      const planRes = await getTaskPlan(res.active_task_id);
      setActivePlanXml(planRes.plan_xml);
    } catch {
      // Activation failed; keep current state
    }
  };

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

  /** Render a single system message block — dispatches by response type */
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

    // Dispatch rendering based on response type
    switch (msg.type) {
      case "CHAT":
        return renderChatMessage(msg, index);
      case "PLAN_CREATE":
        return renderPlanCreateMessage(msg, index);
      case "PLAN_QA":
      case "PLAN_ADD":
      case "PLAN_UPDATE":
      case "PLAN_DELETE":
      case "REGISTRY_QA":
      case "REGISTRY_EDIT":
      case "REGISTRY_DELETE":
        return renderCrudMessage(msg, index);
      default:
        return renderDefaultMessage(msg, index);
    }
  }

  /** CHAT type: simple conversational reply — inline text next to logo, no title */
  function renderChatMessage(msg: ChatMessage, index: number) {
    return (
      <div key={index} className="msg-block msg-block-system">
        <div className="msg-chat-row">
          <div className="msg-system-logo">
            <img src="/assets/logo-icon.svg" alt="" width="24" height="24" />
          </div>
          <p className="msg-chat-text">{msg.content}</p>
        </div>
        <div className="msg-divider msg-divider-full" />
      </div>
    );
  }

  /** PLAN_CREATE type: title + plan icon + formatted plan content */
  function renderPlanCreateMessage(msg: ChatMessage, index: number) {
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
          <div
            className="crud-badge"
            style={{ backgroundColor: "#ffffff", borderColor: "#e5e7eb" }}
          >
            <img src="/assets/itin_icon.svg" alt="" width="20" height="20" />
            <span className="crud-badge-label">Itinerary</span>
          </div>
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
        <div className="msg-divider msg-divider-full" />
      </div>
    );
  }

  /** Render CRUD badge pill */
  function renderCrudBadge(action: CrudAction) {
    const config = CRUD_CONFIG[action];
    return (
      <div
        className="crud-badge"
        style={{
          backgroundColor: config.bgColor,
          borderColor: config.borderColor,
        }}
      >
        <img src={config.icon} alt="" width="20" height="20" />
        <span className="crud-badge-label">{config.label}</span>
      </div>
    );
  }

  /** Render XPath + Original Query display bars */
  function renderQueryBars(xpathQuery?: string, originalQuery?: string) {
    if (!xpathQuery && !originalQuery) return null;
    return (
      <div className="query-bars">
        {xpathQuery && (
          <div className="xpath-query-bar">
            <span className="query-bar-label">XPath :</span>
            <span className="query-bar-value">{xpathQuery}</span>
          </div>
        )}
        {originalQuery && (
          <div className="xpath-query-bar">
            <span className="query-bar-label">Original :</span>
            <span className="query-bar-value">{originalQuery}</span>
          </div>
        )}
      </div>
    );
  }

  /** CRUD intent types: logo + text + CRUD badge + query bars */
  function renderCrudMessage(msg: ChatMessage, index: number) {
    const crud = msg.crudAction;
    return (
      <div key={index} className="msg-block msg-block-system">
        <div className="msg-system-title-row">
          <div className="msg-system-logo">
            <img src="/assets/logo-icon.svg" alt="" width="24" height="24" />
          </div>
          <p className="msg-chat-text msg-chat-text-flex">{msg.content}</p>
          {crud && renderCrudBadge(crud)}
        </div>
        {renderQueryBars(msg.xpathQuery, msg.originalQuery)}
        <div className="msg-divider msg-divider-full" />
      </div>
    );
  }

  /** Default rendering for unimplemented or unknown types */
  function renderDefaultMessage(msg: ChatMessage, index: number) {
    return (
      <div key={index} className="msg-block msg-block-system">
        <div className="msg-chat-row">
          <div className="msg-system-logo">
            <img src="/assets/logo-icon.svg" alt="" width="24" height="24" />
          </div>
          <p className="msg-chat-text">{msg.content}</p>
        </div>
        <div className="msg-divider msg-divider-full" />
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

      {/* Right Panel — Task Tab Bar + Tree Visualization */}
      <div className="main-right-panel">
        {/* Task Tab Bar */}
        {tasks.length > 0 && (
          <div className="task-tab-bar">
            {tasks.map((t) => (
              <button
                key={t.task_id}
                className={`task-tab ${t.task_id === activeTaskId ? "active" : ""}`}
                onClick={() => handleTabClick(t.task_id)}
              >
                {t.task_name || t.task_id}
              </button>
            ))}
          </div>
        )}

        {/* Right-side Query Bars */}
        {(latestXpathQuery || latestOriginalQuery) && (
          <div className="right-query-bars">
            {latestXpathQuery && (
              <div className="xpath-query-bar right-query-bar">
                <span className="query-bar-label">XPath :</span>
                <span className="query-bar-value">{latestXpathQuery}</span>
              </div>
            )}
            {latestOriginalQuery && (
              <div className="xpath-query-bar right-query-bar">
                <span className="query-bar-label">Original :</span>
                <span className="query-bar-value">{latestOriginalQuery}</span>
              </div>
            )}
          </div>
        )}

        {/* Tree View Area */}
        <div className="tree-view-area">
          {activePlanXml ? (
            <PlanTreeView
              planXml={activePlanXml}
              highlightMode={highlightMode}
              highlightedPaths={highlightedPaths}
            />
          ) : (
            <div className="right-panel-placeholder">
              <p>Tree Visualization</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
