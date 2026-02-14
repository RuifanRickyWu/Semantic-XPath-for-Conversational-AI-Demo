/**
 * TypeScript types for the Chat API response.
 *
 * The `type` field is the key discriminator for FE rendering behavior.
 */

export type ChatResponseType =
  | "CHAT"
  | "PLAN_CREATE"
  // Future intent types (reserved):
  | "PLAN_QA"
  | "PLAN_EDIT"
  | "REGISTRY_QA"
  | "REGISTRY_EDIT";

export interface ChatSessionUpdates {
  active_task_id?: string;
  active_version_id?: string;
}

export interface ChatResponse {
  success: boolean;
  type: ChatResponseType;
  message: string;
  session_id: string;
  session_updates: ChatSessionUpdates;
  error?: string;
}
