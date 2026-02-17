/**
 * TypeScript types for the Chat API response.
 *
 * The `type` field is the key discriminator for FE rendering behavior.
 */

export type ChatResponseType =
  | "CHAT"
  | "PLAN_CREATE"
  | "PLAN_QA"
  | "PLAN_ADD"
  | "PLAN_UPDATE"
  | "PLAN_DELETE"
  | "REGISTRY_QA"
  | "REGISTRY_EDIT"
  | "REGISTRY_DELETE";

export type CrudAction = "create" | "read" | "update" | "delete";

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
  xpath_query?: string;
  original_query?: string;
  affected_node_paths?: any[][];
  error?: string;
}

/**
 * Map a ChatResponseType to its CRUD action category, or null for non-CRUD types.
 */
export function typeToCrudAction(type?: ChatResponseType): CrudAction | null {
  switch (type) {
    case "PLAN_QA":
      return "read";
    case "PLAN_ADD":
      return "create";
    case "PLAN_UPDATE":
      return "update";
    case "PLAN_DELETE":
      return "delete";
    default:
      return null;
  }
}

/** CRUD badge configuration per action */
export const CRUD_CONFIG: Record<
  CrudAction,
  { label: string; icon: string; bgColor: string; borderColor: string }
> = {
  read: {
    label: "Read",
    icon: "/assets/default_read.svg",
    bgColor: "#ffffff",
    borderColor: "#e5e7eb",
  },
  create: {
    label: "Create",
    icon: "/assets/default_add.svg",
    bgColor: "#ffffff",
    borderColor: "#e5e7eb",
  },
  update: {
    label: "Update",
    icon: "/assets/default_update_icon.svg",
    bgColor: "#ffffff",
    borderColor: "#e5e7eb",
  },
  delete: {
    label: "Delete",
    icon: "/assets/default_delete_icon.svg",
    bgColor: "#ffffff",
    borderColor: "#e5e7eb",
  },
};
