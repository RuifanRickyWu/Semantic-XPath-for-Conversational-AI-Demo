/**
 * API client for the Chat endpoint.
 *
 * Sends user messages to POST /api/chat and returns typed responses.
 * The backend automatically routes to the correct intent handler
 * (CHAT, PLAN_CREATE, etc.) based on the message content.
 */

import type { ChatResponse } from "../types/chat";

import { API_BASE } from "./apiBase";

/**
 * Send a chat message to the backend.
 *
 * @param message - The user's message text.
 * @param sessionId - Session identifier for conversation continuity.
 * @returns The typed ChatResponse from the backend.
 */
export async function postChat(
  message: string,
  sessionId: string
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message, session_id: sessionId }),
  });

  const data: ChatResponse = await response.json();
  return data;
}
