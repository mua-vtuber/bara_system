import { fetchApi } from './api'
import type { Activity, ActivityFilters, PaginatedResponse } from '@/types'

/** Return a paginated timeline of bot activities. */
export function getActivities(
  filters: ActivityFilters = {},
): Promise<PaginatedResponse<Activity>> {
  const params = new URLSearchParams()

  if (filters.platform) params.set('platform', filters.platform)
  if (filters.type) params.set('type', filters.type)
  if (filters.status) params.set('status', filters.status)
  if (filters.start) params.set('start', filters.start)
  if (filters.end) params.set('end', filters.end)
  if (filters.limit !== undefined) params.set('limit', String(filters.limit))
  if (filters.offset !== undefined) params.set('offset', String(filters.offset))

  const qs = params.toString()
  return fetchApi<PaginatedResponse<Activity>>(
    `/api/activities${qs ? `?${qs}` : ''}`,
  )
}

/** Return details for a single activity. */
export function getActivity(id: number): Promise<Activity> {
  return fetchApi<Activity>(`/api/activities/${id}`)
}
