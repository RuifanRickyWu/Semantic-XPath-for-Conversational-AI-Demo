import { useState, useEffect, useRef, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { postChat } from "../../api/chatApi";
import { getTasks, getTaskPlan, activateTask } from "../../api/tasksApi";
import type { CrudAction } from "../../types/chat";
import { typeToCrudAction, CRUD_CONFIG } from "../../types/chat";
import type { ChatMessage } from "../../context/AppStateContext";
import { useAppState } from "../../context/useAppState";
import PlanTreeView from "../../components/PlanTreeView/PlanTreeView";
import "./MainPage.css";

interface LocationState {
  query?: string;
}

function toUiXpath(xpath: string): string {
  return xpath.replace(/\bagg_(min|max|avg)\b/gi, (_, op: string) =>
    String(op).toLowerCase()
  );
}

/* ── Main Component ───────────────────────────────── */

export default function MainPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state as LocationState | null;

  const {
    messages,
    setMessages,
    tasks,
    setTasks,
    activeTaskId,
    setActiveTaskId,
    activePlanXml,
    setActivePlanXml,
    highlightMode,
    setHighlightMode,
    highlightedPaths,
    setHighlightedPaths,
    latestXpathQuery,
    setLatestXpathQuery,
    latestOriginalQuery,
    setLatestOriginalQuery,
    selectedMessageIndex,
    setSelectedMessageIndex,
    currentTaskIdRef,
    currentVersionIdRef,
    sessionId,
    isLoading,
    setIsLoading,
  } = useAppState();

  const [inputValue, setInputValue] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const initialQueryHandled = useRef(false);

  /** Refresh the task list from the backend and optionally load a plan. */
  const refreshTasks = useCallback(async (loadPlanForTaskId?: string) => {
    try {
      const res = await getTasks(sessionId);
      setTasks(res.tasks);
      setActiveTaskId(res.active_task_id);
      if (res.active_task_id) {
        currentTaskIdRef.current = res.active_task_id;
      }
      const taskToLoad = loadPlanForTaskId || res.active_task_id;
      if (taskToLoad) {
        try {
          const planRes = await getTaskPlan(taskToLoad, sessionId);
          setActivePlanXml(planRes.plan_xml);
          if (planRes.version_id) {
            currentVersionIdRef.current = planRes.version_id;
          }
        } catch {
          setActivePlanXml(null);
        }
      }
    } catch {
      // Backend may not be running yet; keep empty state
    }
  }, [sessionId, setTasks, setActiveTaskId, setActivePlanXml]);

  // Load task list on mount (only if empty)
  useEffect(() => {
    if (tasks.length === 0) {
      refreshTasks();
    }
  }, [refreshTasks, tasks.length]);

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
      const result = await postChat(query, sessionId);

      if (result.success) {
        const isClarification = result.requires_clarification === true;
        const crud = isClarification ? null : typeToCrudAction(result.type);

        const returnedTaskId = result.session_updates?.active_task_id;
        if (returnedTaskId) {
          currentTaskIdRef.current = returnedTaskId;
        }
        const returnedVersionId = result.session_updates?.active_version_id;
        if (returnedVersionId) {
          currentVersionIdRef.current = returnedVersionId;
        }

        const systemMessage: ChatMessage = {
          role: "system",
          content: result.message || "Done.",
          type: result.type,
          title: undefined,
          crudAction: crud,
          xpathQuery: result.xpath_query,
          originalQuery: result.original_query,
          affectedNodePaths: result.affected_node_paths,
          scoringTrace: result.scoring_trace,
          perNodeDetail: result.per_node_detail,
          snapshotTaskId: currentTaskIdRef.current ?? undefined,
          snapshotVersionId: currentVersionIdRef.current ?? undefined,
        };
        setMessages((prev) => {
          const updated = [...prev.slice(0, -1), systemMessage];
          if (crud) {
            setSelectedMessageIndex(updated.length - 1);
          }
          return updated;
        });

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

  /* ── Task tab bar handler ────────────────────────── */

  const handleTabClick = async (taskId: string) => {
    if (taskId === activeTaskId) return;
    try {
      const res = await activateTask(taskId, sessionId);
      setActiveTaskId(res.active_task_id);
      const planRes = await getTaskPlan(res.active_task_id, sessionId);
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
            src="/assets/actual-user.png"
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

  /** PLAN_CREATE type: inline text + Itinerary badge (same layout as CRUD messages) */
  function renderPlanCreateMessage(msg: ChatMessage, index: number) {
    return (
      <div key={index} className="msg-block msg-block-system">
        <div className="msg-system-title-row">
          <div className="msg-system-logo">
            <img src="/assets/logo-icon.svg" alt="" width="24" height="24" />
          </div>
          <p className="msg-chat-text msg-chat-text-flex">{msg.content}</p>
          <div
            className="crud-badge"
            style={{ backgroundColor: "#ffffff", borderColor: "#e5e7eb" }}
          >
            <img src="/assets/view-list.svg" alt="" width="20" height="20" />
            <span className="crud-badge-label">Itinerary</span>
          </div>
        </div>
        <div className="msg-divider msg-divider-full" />
      </div>
    );
  }

  /** Render CRUD badge pill — clickable, with default/selected states */
  function renderCrudBadge(
    action: CrudAction,
    isSelected: boolean,
    onClick?: (e: React.MouseEvent) => void,
  ) {
    const config = CRUD_CONFIG[action];
    const clickable = !!onClick;
    return (
      <div
        className={`crud-badge${clickable ? " crud-badge-clickable" : ""}${isSelected ? " crud-badge-selected" : ""}`}
        style={{
          backgroundColor: isSelected ? config.selectedBgColor : config.bgColor,
          borderColor: isSelected ? config.selectedBorderColor : config.borderColor,
        }}
        onClick={onClick}
      >
        <img src={config.icon} alt="" width="20" height="20" />
        <span className="crud-badge-label">{config.label}</span>
      </div>
    );
  }

  /** Render Expanded Query + XPath display bars */
  function renderQueryBars(xpathQuery?: string, originalQuery?: string) {
    if (!xpathQuery && !originalQuery) return null;
    const displayXpath = xpathQuery ? toUiXpath(xpathQuery) : "";
    return (
      <div className="query-bars">
        {originalQuery && (
          <div className="xpath-query-bar">
            <span className="query-bar-label">Expanded Query :</span>
            <span className="query-bar-value">{originalQuery}</span>
          </div>
        )}
        {xpathQuery && (
          <div className="xpath-query-bar">
            <span className="query-bar-label">XPath :</span>
            <span className="query-bar-value">{displayXpath}</span>
          </div>
        )}
      </div>
    );
  }

  /** CRUD intent types: logo + text + CRUD badge + query bars */
  function renderCrudMessage(msg: ChatMessage, index: number) {
    const crud = msg.crudAction;
    const isSelected = selectedMessageIndex === index;
    const hasSnapshot = !!(msg.snapshotTaskId && msg.snapshotVersionId);

    const handleBadgeClick = hasSnapshot
      ? async (e: React.MouseEvent) => {
          e.stopPropagation();
          setSelectedMessageIndex(index);

          try {
            const planRes = await getTaskPlan(msg.snapshotTaskId!, sessionId, msg.snapshotVersionId!);
            setActivePlanXml(planRes.plan_xml);
          } catch {
            // Version may no longer exist; keep current tree
          }

          if (crud && msg.affectedNodePaths?.length) {
            setHighlightMode(crud);
            setHighlightedPaths(msg.affectedNodePaths);
          } else {
            setHighlightMode(null);
            setHighlightedPaths(null);
          }
          setLatestXpathQuery(msg.xpathQuery || null);
          setLatestOriginalQuery(msg.originalQuery || null);
        }
      : undefined;

    return (
      <div key={index} className="msg-block msg-block-system">
        {renderQueryBars(msg.xpathQuery, msg.originalQuery)}
        <div className="msg-system-title-row">
          <div className="msg-system-logo">
            <img src="/assets/logo-icon.svg" alt="" width="24" height="24" />
          </div>
          <p className="msg-chat-text msg-chat-text-flex">{msg.content}</p>
          <div className="msg-badges-column">
            {crud && renderCrudBadge(crud, isSelected, handleBadgeClick)}
            {msg.scoringTrace && msg.scoringTrace.length > 0 && (
              <div
                className="crud-badge crud-badge-clickable scoring-badge"
                onClick={() =>
                  navigate("/scoring", {
                    state: {
                      xpathQuery: msg.xpathQuery,
                      originalQuery: msg.originalQuery,
                      scoringTrace: msg.scoringTrace,
                      perNodeDetail: msg.perNodeDetail,
                      planXml: activePlanXml,
                    },
                  })
                }
              >
                <span className="crud-badge-label">Detailed Scoring</span>
              </div>
            )}
          </div>
        </div>
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

        <div className="panel-view-header">
          <div className="panel-view-badge">Conversation View</div>
        </div>

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
        <div className="panel-view-header panel-view-header-right">
          <div className="panel-view-badge">Memory View</div>
        </div>

        {/* Task Tab Bar */}
        {tasks.length > 0 && (
          <div
            className={`task-tab-bar ${tasks.length <= 2 ? "task-tab-bar-sparse" : ""}`}
          >
            {tasks.map((t) => (
              <button
                key={t.task_id}
                className={`task-tab ${t.task_id === activeTaskId ? "active" : ""} ${tasks.length <= 2 ? "task-tab-stretch" : ""}`}
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
            {latestOriginalQuery && (
              <div className="xpath-query-bar right-query-bar">
                <span className="query-bar-label">Expanded Query :</span>
                <span className="query-bar-value">{latestOriginalQuery}</span>
              </div>
            )}
            {latestXpathQuery && (
              <div className="xpath-query-bar right-query-bar">
                <span className="query-bar-label">XPath :</span>
                <span className="query-bar-value">{toUiXpath(latestXpathQuery)}</span>
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
