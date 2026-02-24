import { API_BASE } from "./apiBase";

export type ExampleTemplateKey =
  | "sandiego_trip_3d"
  | "10day_toronto_trip"
  | "acl_2026_conference";

interface SeedSessionResponse {
  success: boolean;
  active_task_id: string;
  active_version_id: string;
  task_name: string;
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

export async function clearSession(
  sessionId: string,
  opts?: { keepalive?: boolean },
): Promise<void> {
  await fetch(`${API_BASE}/session/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
    keepalive: !!opts?.keepalive,
  });
}
