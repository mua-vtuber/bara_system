/**
 * API request/response types.
 *
 * These mirror the Pydantic request/response schemas defined in
 * the backend route modules.
 */

import type { Activity, Conversation, SettingsSnapshot } from './models'

// -- Auth ------------------------------------------------------------------

export interface LoginRequest {
  password: string
}

export interface LoginResponse {
  success: boolean
  error: string | null
}

export interface SetupPasswordRequest {
  password: string
}

export interface SetupPasswordResponse {
  success: boolean
  message: string
}

export interface AuthStatusResponse {
  authenticated: boolean
  setup_complete: boolean
}

// -- Chat ------------------------------------------------------------------

export interface ChatRequest {
  message: string
  platform: string
}

export interface ChatResponse {
  response: string
  conversation_id: number
}

export interface HistoryResponse {
  conversations: Conversation[]
  total: number
}

// -- Commands --------------------------------------------------------------

export interface CommandRequest {
  command: string
  args: Record<string, unknown>
}

export interface CommandResponse {
  success: boolean
  command: string
  result: Record<string, unknown> | null
  error: string | null
}

// -- Setup Wizard ----------------------------------------------------------

export interface SetupStatus {
  completed: boolean
  current_step: number
  steps: string[]
}

export interface SystemCheckItem {
  name: string
  passed: boolean
  message: string
}

export interface SystemCheckResponse {
  checks: SystemCheckItem[]
}

export interface ModelInfo {
  name: string
  size: number | null
  modified_at: string | null
}

export interface ModelsResponse {
  models: ModelInfo[]
}

export interface ModelSelectRequest {
  model: string
}

export interface BotConfigRequest {
  name: string
  owner_name: string
  wake_words: string[]
}

export interface PlatformCredentials {
  enabled: boolean
  api_key: string
}

export interface PlatformsConfigRequest {
  moltbook: PlatformCredentials
  botmadang: PlatformCredentials
}

export interface BehaviorConfigRequest {
  auto_mode: boolean
  approval_mode: boolean
  interest_keywords: string[]
  monitoring_interval_minutes: number
}

export interface VoiceConfigRequest {
  enabled: boolean
  wake_word_engine: string
  stt_model: string
}

export interface SetupCompleteResponse {
  success: boolean
  message: string
}

// -- Settings --------------------------------------------------------------

export interface SettingsUpdateRequest {
  section: string
  data: Record<string, unknown>
}

export interface SettingsUpdateResponse {
  detail: string
  current: Record<string, unknown>
}

export interface SettingsHistoryResponse {
  items: SettingsSnapshot[]
  total: number
}

// -- Platform validation ---------------------------------------------------

export interface PlatformValidateRequest {
  platform: string
}

export interface PlatformValidateResponse {
  platform: string
  valid: boolean
}

// -- Activities ------------------------------------------------------------

export interface ActivityFilters {
  platform?: string
  type?: string
  status?: string
  start?: string
  end?: string
  limit?: number
  offset?: number
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

// -- Notifications ---------------------------------------------------------

export interface NotificationFilters {
  platform?: string
  unread?: boolean
  limit?: number
}

// -- Collected info --------------------------------------------------------

export interface CollectedInfoFilters {
  q?: string
  category?: string
  bookmarked?: boolean
  limit?: number
  offset?: number
}

export interface CategoriesResponse {
  categories: string[]
}

export interface BookmarkToggleResponse {
  id: number
  bookmarked: boolean
}

// -- Backup ----------------------------------------------------------------

export interface BackupExportResponse {
  detail: string
  filename: string
  data: Record<string, unknown>
}

export interface BackupImportResponse {
  detail: string
}

// -- Health ----------------------------------------------------------------

export interface HealthResponse {
  status: string
  checks: Array<{ name: string; status: string; message: string }>
  uptime_seconds: number
}
