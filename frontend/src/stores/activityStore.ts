import { create } from 'zustand'
import * as activitiesApi from '@/services/activities.api'
import type { Activity, ActivityFilters } from '@/types'

interface ActivityState {
  activities: Activity[]
  loading: boolean
  total: number
  fetchActivities: (filters?: ActivityFilters) => Promise<void>
}

export const useActivityStore = create<ActivityState>()((set) => ({
  activities: [],
  loading: false,
  total: 0,

  fetchActivities: async (filters: ActivityFilters = {}): Promise<void> => {
    set({ loading: true })
    try {
      const res = await activitiesApi.getActivities(filters)
      set({ activities: res.items, total: res.total, loading: false })
    } catch {
      set({ loading: false })
    }
  },
}))
