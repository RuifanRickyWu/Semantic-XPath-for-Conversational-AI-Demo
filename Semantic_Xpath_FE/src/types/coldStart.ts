/**
 * TypeScript types for the Cold Start API response.
 */

export interface ColdStartDisplay {
  summary: string;
  paths: string;
  domain_schema: string;
  task_schema: string;
  memory_xml: string;
}

export interface ColdStartTask {
  name: string;
  title: string;
  description: string;
  domain: string;
}

export interface ColdStartResponse {
  success: boolean;
  error?: string;
  plan_output?: Record<string, unknown>;
  schema_output?: Record<string, unknown>;
  content_output?: Record<string, unknown>;
  user_facing?: string;
  domain?: Record<string, string>;
  task?: ColdStartTask;
  task_schema?: Record<string, unknown>;
  domain_schema?: Record<string, unknown>;
  memory_xml?: string;
  paths?: Record<string, string>;
  warnings?: string[];
  token_usage?: Record<string, unknown>;
  display?: ColdStartDisplay;
}
