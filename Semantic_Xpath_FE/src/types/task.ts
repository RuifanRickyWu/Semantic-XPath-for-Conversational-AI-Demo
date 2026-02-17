/**
 * TypeScript types for the Task REST API responses.
 *
 * Used by the task tab bar and plan viewer.
 */

export interface TaskSummary {
  task_id: string;
  task_name: string | null;
  active_version_id: string;
  version_count: number;
  updated_at: string;
}

export interface TaskListResponse {
  active_task_id: string | null;
  tasks: TaskSummary[];
}

export interface TaskPlanResponse {
  task_id: string;
  version_id: string;
  plan_xml: string;
}

export interface ActivateTaskResponse {
  active_task_id: string;
  active_version_id: string;
}
