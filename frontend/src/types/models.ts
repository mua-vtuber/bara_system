/**
 * TypeScript mirrors of backend Pydantic models.
 *
 * Field names and types match the backend exactly so that JSON
 * responses can be used without transformation.
 */

import type {
  ActivityStatus,
  ActivityType,
  Platform,
  PlatformCapability,
} from './enums'

// -- Conversation ----------------------------------------------------------

export interface Conversation {
  id: number
  timestamp: string
  role: string
  content: string
  platform: string
}

// -- Activity --------------------------------------------------------------

export interface Activity {
  id: number
  timestamp: string
  type: ActivityType
  platform: Platform
  platform_post_id: string | null
  platform_comment_id: string | null
  parent_id: string | null
  url: string | null
  original_content: string | null
  bot_response: string | null
  translated_content: string | null
  translation_direction: string | null
  llm_prompt: string | null
  status: ActivityStatus
  error_message: string | null
}

export interface DailyCounts {
  comments: number
  posts: number
  upvotes: number
  downvotes: number
  follows: number
}

export interface DailyLimits {
  max_comments: number
  max_posts: number
  max_upvotes: number
}

// -- Notification ----------------------------------------------------------

export interface NotificationLog {
  id: number
  timestamp: string
  platform: string
  notification_id: string
  notification_type: string
  actor_name: string | null
  post_id: string | null
  is_read: boolean
  response_activity_id: number | null
}

// -- Collected Info --------------------------------------------------------

export interface CollectedInfo {
  id: number
  timestamp: string
  platform: string
  author: string | null
  category: string | null
  title: string | null
  content: string | null
  source_url: string | null
  bookmarked: boolean
  tags: string | null
}

// -- Settings --------------------------------------------------------------

export interface SettingsSnapshot {
  id: number
  timestamp: string
  config_snapshot: string
}

// -- Platform status -------------------------------------------------------

export interface PlatformStatus {
  name: string
  enabled: boolean
  authenticated: boolean
  capabilities: PlatformCapability[]
}

// -- Health ----------------------------------------------------------------

export interface ComponentHealth {
  name: string
  status: string
  message: string | null
  latency_ms: number | null
}

export interface HealthCheckResult {
  status: string
  checks: ComponentHealth[]
  uptime_seconds: number
  timestamp: string
  vram_usage_mb: number | null
  vram_total_mb: number | null
  disk_free_gb: number | null
}

// -- Auth session ----------------------------------------------------------

export interface Session {
  session_id: string
  created_at: string
  expires_at: string
  ip_address: string | null
}
