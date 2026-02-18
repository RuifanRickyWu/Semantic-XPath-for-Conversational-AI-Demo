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
  scoring_trace?: any[];
  per_node_detail?: any[];
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
  {
    label: string;
    icon: string;
    bgColor: string;
    borderColor: string;
    selectedBgColor: string;
    selectedBorderColor: string;
  }
> = {
  read: {
    label: "Read Memory",
    icon: "/assets/default_read.svg",
    bgColor: "#ffffff",
    borderColor: "#e5e7eb",
    selectedBgColor: "#8561D6",
    selectedBorderColor: "#8561D6",
  },
  create: {
    label: "Write Memory",
    icon: "/assets/default_add.svg",
    bgColor: "#ffffff",
    borderColor: "#e5e7eb",
    selectedBgColor: "#4AB584",
    selectedBorderColor: "#4AB584",
  },
  update: {
    label: "Update Memory",
    icon: "/assets/default_update_icon.svg",
    bgColor: "#ffffff",
    borderColor: "#e5e7eb",
    selectedBgColor: "#EF8D15",
    selectedBorderColor: "#EF8D15",
  },
  delete: {
    label: "Delete Memory",
    icon: "/assets/default_delete_icon.svg",
    bgColor: "#ffffff",
    borderColor: "#e5e7eb",
    selectedBgColor: "#F04344",
    selectedBorderColor: "#F04344",
  },
};
