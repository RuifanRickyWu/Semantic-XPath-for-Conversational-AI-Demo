/**
 * API client for the Cold Start endpoint.
 */

import type { ColdStartResponse } from "../types/coldStart";

import { API_BASE } from "./apiBase";

/**
 * Send a cold start request to generate schemas and memory from a user query.
 */
export async function postColdStart(query: string): Promise<ColdStartResponse> {
  const response = await fetch(`${API_BASE}/cold_start`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ query }),
  });

  const data: ColdStartResponse = await response.json();
  return data;
}
