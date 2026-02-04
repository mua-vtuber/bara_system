/** Mirrors backend app.core.constants enums */

export type Platform = 'botmadang' | 'moltbook'

export type ActivityType =
  | 'comment'
  | 'post'
  | 'reply'
  | 'upvote'
  | 'downvote'
  | 'follow'

export type ActivityStatus =
  | 'pending'
  | 'approved'
  | 'posted'
  | 'rejected'
  | 'failed'

export type BotStatus = 'active' | 'idle' | 'offline' | 'stopped'

export type PlatformCapability =
  | 'semantic_search'
  | 'follow'
  | 'nested_comments'
  | 'notifications'
  | 'agent_registration'
  | 'downvote'
