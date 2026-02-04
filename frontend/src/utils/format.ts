import { format, formatDistanceToNow, parseISO } from 'date-fns'
import { ko } from 'date-fns/locale'

/**
 * Format an ISO date string to a readable date (e.g. "2025-01-15").
 */
export function formatDate(iso: string): string {
  return format(parseISO(iso), 'yyyy-MM-dd')
}

/**
 * Format an ISO date string to a readable time (e.g. "14:32:05").
 */
export function formatTime(iso: string): string {
  return format(parseISO(iso), 'HH:mm:ss')
}

/**
 * Format a duration in seconds to a human-readable string.
 *
 * Examples:
 * - 45       -> "45s"
 * - 125      -> "2m 5s"
 * - 3661     -> "1h 1m 1s"
 * - 90061    -> "1d 1h 1m"
 */
export function formatDuration(totalSeconds: number): string {
  if (totalSeconds < 0) return '0s'

  const days = Math.floor(totalSeconds / 86400)
  const hours = Math.floor((totalSeconds % 86400) / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = Math.floor(totalSeconds % 60)

  const parts: string[] = []
  if (days > 0) parts.push(`${days}d`)
  if (hours > 0) parts.push(`${hours}h`)
  if (minutes > 0) parts.push(`${minutes}m`)
  if (seconds > 0 && days === 0) parts.push(`${seconds}s`)

  return parts.length > 0 ? parts.join(' ') : '0s'
}

/**
 * Format an ISO date string as a relative time (e.g. "3분 전").
 *
 * Uses Korean locale.
 */
export function formatRelativeTime(iso: string): string {
  return formatDistanceToNow(parseISO(iso), { addSuffix: true, locale: ko })
}
