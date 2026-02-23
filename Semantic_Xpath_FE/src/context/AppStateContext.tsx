/* eslint-disable react-refresh/only-export-components */
/**
 * AppStateContext — shared state across pages.
 */

import {
  createContext,
  useState,
  useRef,
  useEffect,
  type ReactNode,
  type SetStateAction,
  type Dispatch,
} from "react";
import type {
  AffectedNodePath,
  ChatResponseType,
  CrudAction,
} from "../types/chat";
import type { PerNodeDetail, ScoringTraceStep } from "../types/scoring";
import type { TaskSummary } from "../types/task";

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
  affectedNodePaths?: AffectedNodePath[];
  scoringTrace?: ScoringTraceStep[];
  perNodeDetail?: PerNodeDetail[];
  snapshotTaskId?: string;
  snapshotVersionId?: string;
}

/* ── Context value ── */

export interface AppState {
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
  highlightedPaths: AffectedNodePath[] | null;
  setHighlightedPaths: React.Dispatch<
    React.SetStateAction<AffectedNodePath[] | null>
  >;

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

export const AppStateContext = createContext<AppState | null>(null);

const SESSION_ID_STORAGE_KEY = "semantic_xpath.current_session_id";
const SESSION_STATE_STORAGE_PREFIX = "semantic_xpath.state.";

interface PersistedSessionState {
  messages: ChatMessage[];
  tasks: TaskSummary[];
  activeTaskId: string | null;
  activePlanXml: string | null;
  highlightMode: CrudAction | null;
  highlightedPaths: AffectedNodePath[] | null;
  latestXpathQuery: string | null;
  latestOriginalQuery: string | null;
  selectedMessageIndex: number | null;
  currentTaskId: string | null;
  currentVersionId: string | null;
}

function getSessionStateStorageKey(sessionId: string): string {
  return `${SESSION_STATE_STORAGE_PREFIX}${sessionId}`;
}

function storageAvailable(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function readStoredSessionId(): string {
  if (!storageAvailable()) return crypto.randomUUID();
  const storedSessionId = localStorage.getItem(SESSION_ID_STORAGE_KEY);
  if (storedSessionId) return storedSessionId;
  const newSessionId = crypto.randomUUID();
  localStorage.setItem(SESSION_ID_STORAGE_KEY, newSessionId);
  return newSessionId;
}

function readPersistedSessionState(sessionId: string): PersistedSessionState | null {
  if (!storageAvailable()) return null;
  const raw = localStorage.getItem(getSessionStateStorageKey(sessionId));
  if (!raw) return null;
  try {
    return JSON.parse(raw) as PersistedSessionState;
  } catch {
    return null;
  }
}

function writePersistedSessionState(sessionId: string, state: PersistedSessionState): void {
  if (!storageAvailable()) return;
  localStorage.setItem(getSessionStateStorageKey(sessionId), JSON.stringify(state));
}

function clearPersistedSessionState(sessionId: string): void {
  if (!storageAvailable()) return;
  localStorage.removeItem(getSessionStateStorageKey(sessionId));
}

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [sessionId, setSessionId] = useState<string>(() => readStoredSessionId());
  const persistedStateRef = useRef<PersistedSessionState | null>(
    readPersistedSessionState(sessionId)
  );

  const [messages, setMessages] = useState<ChatMessage[]>(
    () => persistedStateRef.current?.messages ?? []
  );
  const [tasks, setTasks] = useState<TaskSummary[]>(
    () => persistedStateRef.current?.tasks ?? []
  );
  const [activeTaskId, setActiveTaskId] = useState<string | null>(
    () => persistedStateRef.current?.activeTaskId ?? null
  );
  const [activePlanXml, setActivePlanXml] = useState<string | null>(
    () => persistedStateRef.current?.activePlanXml ?? null
  );
  const [highlightMode, setHighlightMode] = useState<CrudAction | null>(
    () => persistedStateRef.current?.highlightMode ?? null
  );
  const [highlightedPaths, setHighlightedPaths] = useState<AffectedNodePath[] | null>(
    () => persistedStateRef.current?.highlightedPaths ?? null
  );
  const [latestXpathQuery, setLatestXpathQuery] = useState<string | null>(
    () => persistedStateRef.current?.latestXpathQuery ?? null
  );
  const [latestOriginalQuery, setLatestOriginalQuery] = useState<string | null>(
    () => persistedStateRef.current?.latestOriginalQuery ?? null
  );
  const [selectedMessageIndex, setSelectedMessageIndex] = useState<number | null>(
    () => persistedStateRef.current?.selectedMessageIndex ?? null
  );
  const [isLoading, setIsLoading] = useState(false);
  const [headerSlot, setHeaderSlot] = useState<ReactNode>(null);
  const currentTaskIdRef = useRef<string | null>(
    persistedStateRef.current?.currentTaskId ?? null
  );
  const currentVersionIdRef = useRef<string | null>(
    persistedStateRef.current?.currentVersionId ?? null
  );

  const startNewSession = (): string => {
    const previous = sessionId;
    clearPersistedSessionState(previous);

    const nextSessionId = crypto.randomUUID();
    setSessionId(nextSessionId);
    if (storageAvailable()) {
      localStorage.setItem(SESSION_ID_STORAGE_KEY, nextSessionId);
    }

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
    clearPersistedSessionState(nextSessionId);
    return previous;
  };

  useEffect(() => {
    if (storageAvailable()) {
      localStorage.setItem(SESSION_ID_STORAGE_KEY, sessionId);
    }
  }, [sessionId]);

  useEffect(() => {
    writePersistedSessionState(sessionId, {
      messages,
      tasks,
      activeTaskId,
      activePlanXml,
      highlightMode,
      highlightedPaths,
      latestXpathQuery,
      latestOriginalQuery,
      selectedMessageIndex,
      currentTaskId: currentTaskIdRef.current,
      currentVersionId: currentVersionIdRef.current,
    });
  }, [
    sessionId,
    messages,
    tasks,
    activeTaskId,
    activePlanXml,
    highlightMode,
    highlightedPaths,
    latestXpathQuery,
    latestOriginalQuery,
    selectedMessageIndex,
  ]);

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
