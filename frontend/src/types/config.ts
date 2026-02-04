/**
 * Config structure mirroring backend config.json sections.
 *
 * These types represent the shape of the JSON returned by
 * GET /api/settings and consumed by PUT /api/settings.
 */

// -- Bot -------------------------------------------------------------------

export interface BotConfig {
  name: string
  model: string
  wake_words: string[]
  owner_name: string
}

// -- Platforms -------------------------------------------------------------

export interface PlatformConfig {
  enabled: boolean
  base_url: string
}

export interface PlatformsConfig {
  moltbook: PlatformConfig
  botmadang: PlatformConfig
}

// -- Behavior --------------------------------------------------------------

export interface CommentStrategyConfig {
  min_quality_length: number
  korean_ratio_threshold: number
  jitter_range_seconds: [number, number]
}

export interface DailyLimitsConfig {
  max_comments: number
  max_posts: number
  max_upvotes: number
}

export interface TimeRange {
  start: number
  end: number
}

export interface ActiveHoursConfig {
  weekday: TimeRange
  weekend: TimeRange
}

export interface BehaviorConfig {
  auto_mode: boolean
  approval_mode: boolean
  monitoring_interval_minutes: number
  interest_keywords: string[]
  comment_strategy: CommentStrategyConfig
  daily_limits: DailyLimitsConfig
  active_hours: ActiveHoursConfig
}

// -- Voice -----------------------------------------------------------------

export interface VoiceConfig {
  enabled: boolean
  wake_word_engine: string
  stt_model: string
  language: string
  audio_source: string
}

// -- Security --------------------------------------------------------------

export interface WebSecurityConfig {
  session_timeout_hours: number
  max_login_attempts: number
  lockout_minutes: number
  https_enabled: boolean
  allowed_ips: string[]
  allow_all_local: boolean
}

export interface SecurityConfig {
  blocked_keywords: string[]
  blocked_patterns: string[]
}

// -- UI --------------------------------------------------------------------

export interface UIConfig {
  theme: string
  language: string
}

// -- Personality -----------------------------------------------------------

export interface PersonalityConfig {
  system_prompt: string
  interests: string[]
  expertise: string[]
  style: string
  traits: string[]
  backstory: string
}

// -- Full config -----------------------------------------------------------

export interface AppConfig {
  bot: BotConfig
  platforms: PlatformsConfig
  behavior: BehaviorConfig
  personality: PersonalityConfig
  voice: VoiceConfig
  web_security: WebSecurityConfig
  security: SecurityConfig
  ui: UIConfig
}
