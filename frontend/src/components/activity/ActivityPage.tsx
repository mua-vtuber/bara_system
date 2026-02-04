import { useEffect, useState, useCallback } from 'react'
import { useActivities } from '@/hooks/useActivities'
import { ActivityFilters } from './ActivityFilters'
import { Timeline } from './Timeline'
import { ActivityDetail } from './ActivityDetail'
import { DailySummary } from './DailySummary'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import type { Activity, ActivityFilters as ActivityFiltersType } from '@/types'

export function ActivityPage() {
  const { activities, loading, fetchActivities } = useActivities()
  const [selectedActivity, setSelectedActivity] = useState<Activity | null>(null)

  useEffect(() => {
    void fetchActivities()
  }, [fetchActivities])

  const handleFilter = useCallback(
    (filters: ActivityFiltersType) => {
      void fetchActivities(filters)
    },
    [fetchActivities],
  )

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <DailySummary activities={activities} />
      <ActivityFilters onFilter={handleFilter} />

      {loading ? (
        <div className="flex flex-1 items-center justify-center">
          <LoadingSpinner />
        </div>
      ) : (
        <Timeline activities={activities} onSelect={setSelectedActivity} />
      )}

      <ActivityDetail
        activity={selectedActivity}
        onClose={() => setSelectedActivity(null)}
      />
    </div>
  )
}
