/**
 * API client for the Task REST endpoints.
 *
 * GET  /api/tasks                     — list all tasks (tab bar)
 * GET  /api/tasks/<task_id>/plan      — load plan XML
 * PUT  /api/tasks/<task_id>/activate  — switch active task (tab click)
 */

import type {
  TaskListResponse,
  TaskPlanResponse,
  ActivateTaskResponse,
} from "../types/task";

import { API_BASE } from "./apiBase";

/**
 * Fetch lightweight metadata for all tasks (for tab bar rendering).
 */
export async function getTasks(): Promise<TaskListResponse> {
  const response = await fetch(`${API_BASE}/tasks`);
  const data: TaskListResponse = await response.json();
  return data;
}

/**
 * Load plan XML for a specific task (active version by default).
 *
 * @param taskId  - The task to load.
 * @param version - Optional version ID override.
 */
export async function getTaskPlan(
  taskId: string,
  version?: string
): Promise<TaskPlanResponse> {
  const url = version
    ? `${API_BASE}/tasks/${taskId}/plan?version=${version}`
    : `${API_BASE}/tasks/${taskId}/plan`;
  const response = await fetch(url);
  const data: TaskPlanResponse = await response.json();
  return data;
}

/**
 * Activate a task and sync the backend session (for tab click switching).
 *
 * @param taskId    - The task to activate.
 * @param sessionId - Session identifier for conversation continuity.
 */
export async function activateTask(
  taskId: string,
  sessionId: string
): Promise<ActivateTaskResponse> {
  const response = await fetch(`${API_BASE}/tasks/${taskId}/activate`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
  const data: ActivateTaskResponse = await response.json();
  return data;
}
