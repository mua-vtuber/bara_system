import { fetchApi } from './api'
import type { CommandRequest, CommandResponse } from '@/types'

/** Execute a slash command (e.g. /post, /search, /status, /stop). */
export function executeCommand(
  command: string,
  args: Record<string, unknown> = {},
): Promise<CommandResponse> {
  return fetchApi<CommandResponse>('/api/commands', {
    method: 'POST',
    body: { command, args } satisfies CommandRequest,
  })
}
