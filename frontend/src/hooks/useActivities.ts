import { useActivityStore } from '@/stores/activityStore'
import type { ActivityFilters } from '@/types'

/**
 * Activities hook wrapping the activity store.
 */
export function useActivities() {
  const activities = useActivityStore((s) => s.activities)
  const loading = useActivityStore((s) => s.loading)
  const total = useActivityStore((s) => s.total)
  const fetchActivities = useActivityStore((s) => s.fetchActivities)

  const fetch = (filters?: ActivityFilters) => fetchActivities(filters)

  return { activities, loading, total, fetchActivities: fetch }
}
