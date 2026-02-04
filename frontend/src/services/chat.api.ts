import { fetchApi } from './api'
import type { ChatRequest, ChatResponse, HistoryResponse } from '@/types'

/** Send a chat message and receive the LLM response (non-streaming). */
export function sendMessage(message: string, platform = 'chat'): Promise<ChatResponse> {
  return fetchApi<ChatResponse>('/api/chat', {
    method: 'POST',
    body: { message, platform } satisfies ChatRequest,
  })
}

/** Retrieve conversation history with optional platform filter. */
export function getHistory(
  limit = 50,
  offset = 0,
  platform?: string,
): Promise<HistoryResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  })
  if (platform) {
    params.set('platform', platform)
  }
  return fetchApi<HistoryResponse>(`/api/chat/history?${params}`)
}
