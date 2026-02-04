/**
 * WebSocket event types.
 *
 * These mirror the JSON frames sent over the two WS endpoints:
 * - /ws/chat   (streaming chat)
 * - /ws/status (real-time system events)
 */

import type { BotStatus } from './enums'

// -- Chat WS (client -> server) --------------------------------------------

export interface ChatWSMessage {
  type: 'message'
  content: string
  platform: string
}

// -- Chat WS (server -> client) --------------------------------------------

export interface ChatToken {
  type: 'token'
  content: string
}

export interface ChatDone {
  type: 'done'
  full_response: string
}

export interface ChatError {
  type: 'error'
  message: string
}

export type ChatWSEvent = ChatToken | ChatDone | ChatError

// -- Status WS (server -> client) ------------------------------------------

export interface StateSyncData {
  bot_status: BotStatus
  platforms: Record<string, unknown>
  uptime_seconds: number
}

export interface StateSync {
  type: 'state_sync'
  data: StateSyncData
}

export interface BotStatusEvent {
  type: 'bot_status'
  data: {
    timestamp: string
    old_status: string
    new_status: string
    reason: string
  }
}

export interface PlatformErrorEvent {
  type: 'platform_error'
  data: {
    timestamp: string
    platform: string
    error_type: string
    message: string
    status_code: number | null
  }
}

export interface HealthEvent {
  type: 'health'
  data: {
    timestamp: string
    status: string
    checks: Array<Record<string, unknown>>
  }
}

export interface TaskQueuedEvent {
  type: 'task_queued'
  data: {
    timestamp: string
    platform: string
    action_type: string
    priority: number
  }
}

export interface TaskCompletedEvent {
  type: 'task_completed'
  data: {
    timestamp: string
    platform: string
    action_type: string
    success: boolean
    error: string | null
  }
}

export interface CommentPostedEvent {
  type: 'comment_posted'
  data: {
    timestamp: string
    platform: string
    activity_id: number
    post_id: string
    comment_id: string
  }
}

export interface PostCreatedEvent {
  type: 'post_created'
  data: {
    timestamp: string
    platform: string
    activity_id: number
    post_id: string
    url: string
  }
}

export type StatusWSEvent =
  | StateSync
  | BotStatusEvent
  | PlatformErrorEvent
  | HealthEvent
  | TaskQueuedEvent
  | TaskCompletedEvent
  | CommentPostedEvent
  | PostCreatedEvent

/** Generic wrapper matching the JSON wire format for status WS. */
export interface WSMessage {
  type: string
  data?: unknown
}
