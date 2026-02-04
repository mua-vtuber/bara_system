import { create } from 'zustand'
import type { Activity } from '@/types'

interface ApprovalState {
  pendingApprovals: Activity[]
  addApproval: (activity: Activity) => void
  removeApproval: (activityId: number) => void
}

export const useApprovalStore = create<ApprovalState>()((set) => ({
  pendingApprovals: [],

  addApproval: (activity: Activity): void => {
    set((state) => {
      // Prevent duplicates
      if (state.pendingApprovals.some((a) => a.id === activity.id)) {
        return state
      }
      return { pendingApprovals: [...state.pendingApprovals, activity] }
    })
  },

  removeApproval: (activityId: number): void => {
    set((state) => ({
      pendingApprovals: state.pendingApprovals.filter((a) => a.id !== activityId),
    }))
  },
}))
