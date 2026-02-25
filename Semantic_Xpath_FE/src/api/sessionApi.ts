import { API_BASE } from "./apiBase";
import type { AffectedNodePath, ChatResponseType } from "../types/chat";

export type ExampleTemplateKey =
  | "sandiego_trip_3d"
  | "10day_toronto_trip"
  | "acl_2026_conference"
  | "todolist";

export interface ExampleTemplate {
  template_key: ExampleTemplateKey;
  label: string;
  task_name: string;
}

interface SeedSessionResponse {
  success: boolean;
  active_task_id: string;
  active_version_id: string;
  task_name: string;
  seeded_messages?: SeededChatMessage[];
}

export interface SeededChatMessage {
  role: "user" | "system";
  content: string;
  type?: ChatResponseType;
  xpathQuery?: string;
  originalQuery?: string;
  affectedNodePaths?: AffectedNodePath[];
  snapshotTaskId?: string;
  snapshotVersionId?: string;
}

export async function seedSessionWithExample(
  sessionId: string,
  templateKey: ExampleTemplateKey,
): Promise<SeedSessionResponse> {
  const response = await fetch(`${API_BASE}/session/seed`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      session_id: sessionId,
      template_key: templateKey,
    }),
  });
  return response.json();
}

interface ListExamplesResponse {
  success: boolean;
  templates?: ExampleTemplate[];
}

export async function listExampleTemplates(): Promise<ExampleTemplate[]> {
  const response = await fetch(`${API_BASE}/session/examples`);
  const payload = (await response.json()) as ListExamplesResponse;
  if (!response.ok || !payload.success) {
    throw new Error("Failed to load example templates.");
  }
  return payload.templates ?? [];
}

export async function clearSession(
  sessionId: string,
  opts?: { keepalive?: boolean },
): Promise<void> {
  await fetch(`${API_BASE}/session/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
    keepalive: !!opts?.keepalive,
  });
}
