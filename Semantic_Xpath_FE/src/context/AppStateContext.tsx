/**
 * AppStateContext — shared state across pages.
 */

import {
  createContext,
  useContext,
  useState,
  useRef,
  useEffect,
  type ReactNode,
  type SetStateAction,
  type Dispatch,
} from "react";
import type { ChatResponseType, CrudAction } from "../types/chat";
import type { TaskSummary } from "../types/task";
import { clearSession } from "../api/sessionApi";

/* ── Chat message shape (shared between pages) ── */

export interface ChatMessage {
  role: "user" | "system";
  content: string;
  type?: ChatResponseType;
  title?: string;
  isLoading?: boolean;
  crudAction?: CrudAction | null;
  xpathQuery?: string;
  originalQuery?: string;
  affectedNodePaths?: any[][];
  scoringTrace?: any[];
  perNodeDetail?: any[];
  snapshotTaskId?: string;
  snapshotVersionId?: string;
}

/* ── Context value ── */

interface AppState {
  /* Chat */
  messages: ChatMessage[];
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>;

  /* Tasks */
  tasks: TaskSummary[];
  setTasks: React.Dispatch<React.SetStateAction<TaskSummary[]>>;
  activeTaskId: string | null;
  setActiveTaskId: React.Dispatch<React.SetStateAction<string | null>>;
  activePlanXml: string | null;
  setActivePlanXml: React.Dispatch<React.SetStateAction<string | null>>;

  /* Highlight */
  highlightMode: CrudAction | null;
  setHighlightMode: React.Dispatch<React.SetStateAction<CrudAction | null>>;
  highlightedPaths: any[][] | null;
  setHighlightedPaths: React.Dispatch<React.SetStateAction<any[][] | null>>;

  /* Query display */
  latestXpathQuery: string | null;
  setLatestXpathQuery: React.Dispatch<React.SetStateAction<string | null>>;
  latestOriginalQuery: string | null;
  setLatestOriginalQuery: React.Dispatch<React.SetStateAction<string | null>>;

  /* Selected CRUD message (for history replay) */
  selectedMessageIndex: number | null;
  setSelectedMessageIndex: React.Dispatch<React.SetStateAction<number | null>>;

  /* Synchronous refs tracking latest task/version ids (avoids async state lag) */
  currentTaskIdRef: React.MutableRefObject<string | null>;
  currentVersionIdRef: React.MutableRefObject<string | null>;

  /* Session */
  sessionId: string;
  startNewSession: () => string;

  /* Loading */
  isLoading: boolean;
  setIsLoading: React.Dispatch<React.SetStateAction<boolean>>;

  /* Header slot — pages can inject center content into the Header */
  headerSlot: ReactNode;
  setHeaderSlot: Dispatch<SetStateAction<ReactNode>>;
}

const AppStateContext = createContext<AppState | null>(null);

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [tasks, setTasks] = useState<TaskSummary[]>([]);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [activePlanXml, setActivePlanXml] = useState<string | null>(null);
  const [highlightMode, setHighlightMode] = useState<CrudAction | null>(null);
  const [highlightedPaths, setHighlightedPaths] = useState<any[][] | null>(null);
  const [latestXpathQuery, setLatestXpathQuery] = useState<string | null>(null);
  const [latestOriginalQuery, setLatestOriginalQuery] = useState<string | null>(null);
  const [selectedMessageIndex, setSelectedMessageIndex] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [headerSlot, setHeaderSlot] = useState<ReactNode>(null);

  const [sessionId, setSessionId] = useState<string>(crypto.randomUUID());
  const currentTaskIdRef = useRef<string | null>(null);
  const currentVersionIdRef = useRef<string | null>(null);

  const startNewSession = (): string => {
    const previous = sessionId;
    setSessionId(crypto.randomUUID());
    setMessages([]);
    setTasks([]);
    setActiveTaskId(null);
    setActivePlanXml(null);
    setHighlightMode(null);
    setHighlightedPaths(null);
    setLatestXpathQuery(null);
    setLatestOriginalQuery(null);
    setSelectedMessageIndex(null);
    setIsLoading(false);
    currentTaskIdRef.current = null;
    currentVersionIdRef.current = null;
    return previous;
  };

  useEffect(() => {
    const handleBeforeUnload = () => {
      void clearSession(sessionId, { keepalive: true }).catch(() => {});
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [sessionId]);

  const value: AppState = {
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
    startNewSession,
    isLoading,
    setIsLoading,
    headerSlot,
    setHeaderSlot,
  };

  return (
    <AppStateContext.Provider value={value}>
      {children}
    </AppStateContext.Provider>
  );
}

export function useAppState(): AppState {
  const ctx = useContext(AppStateContext);
  if (!ctx) {
    throw new Error("useAppState must be used within <AppStateProvider>");
  }
  return ctx;
}
