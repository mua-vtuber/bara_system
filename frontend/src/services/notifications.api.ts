import { fetchApi } from './api'
import type { NotificationFilters, NotificationLog, PaginatedResponse } from '@/types'

/** Return a list of notification log entries. */
export function getNotifications(
  filters: NotificationFilters = {},
): Promise<PaginatedResponse<NotificationLog>> {
  const params = new URLSearchParams()

  if (filters.platform) params.set('platform', filters.platform)
  if (filters.unread !== undefined) params.set('unread', String(filters.unread))
  if (filters.limit !== undefined) params.set('limit', String(filters.limit))

  const qs = params.toString()
  return fetchApi<PaginatedResponse<NotificationLog>>(
    `/api/notifications${qs ? `?${qs}` : ''}`,
  )
}

/** Mark a notification as read. */
export function markRead(id: number): Promise<{ detail: string }> {
  return fetchApi<{ detail: string }>(`/api/notifications/${id}/read`, {
    method: 'POST',
  })
}
