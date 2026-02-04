import { fetchApi } from './api'
import type {
  BookmarkToggleResponse,
  CategoriesResponse,
  CollectedInfo,
  CollectedInfoFilters,
  PaginatedResponse,
} from '@/types'

/** Return a list of collected information items. */
export function getCollectedInfo(
  filters: CollectedInfoFilters = {},
): Promise<PaginatedResponse<CollectedInfo>> {
  const params = new URLSearchParams()

  if (filters.q) params.set('q', filters.q)
  if (filters.category) params.set('category', filters.category)
  if (filters.bookmarked) params.set('bookmarked', 'true')
  if (filters.limit !== undefined) params.set('limit', String(filters.limit))
  if (filters.offset !== undefined) params.set('offset', String(filters.offset))

  const qs = params.toString()
  return fetchApi<PaginatedResponse<CollectedInfo>>(
    `/api/collected-info${qs ? `?${qs}` : ''}`,
  )
}

/** Return all distinct categories. */
export function getCategories(): Promise<CategoriesResponse> {
  return fetchApi<CategoriesResponse>('/api/collected-info/categories')
}

/** Toggle the bookmark flag on a collected-info entry. */
export function toggleBookmark(id: number): Promise<BookmarkToggleResponse> {
  return fetchApi<BookmarkToggleResponse>(`/api/collected-info/${id}/bookmark`, {
    method: 'POST',
  })
}
