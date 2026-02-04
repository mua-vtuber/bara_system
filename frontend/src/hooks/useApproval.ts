import { useCallback } from 'react'
import { useApprovalStore } from '@/stores/approvalStore'
import { useWebSocket } from './useWebSocket'
import type { Activity } from '@/types'

interface ApprovalWSEvent {
  type: string
  data?: {
    activity?: Activity
  }
}

/**
 * Approval hook integrating approvalStore with WS events.
 * Listens for approval_requested events to add pending approvals.
 */
export function useApproval() {
  const pendingApprovals = useApprovalStore((s) => s.pendingApprovals)
  const addApproval = useApprovalStore((s) => s.addApproval)
  const removeApproval = useApprovalStore((s) => s.removeApproval)

  const handleWSMessage = useCallback(
    (data: unknown) => {
      const event = data as ApprovalWSEvent
      if (event.type === 'approval_requested' && event.data?.activity) {
        addApproval(event.data.activity)
      }
    },
    [addApproval],
  )

  useWebSocket({
    path: '/ws/status',
    onMessage: handleWSMessage,
  })

  return { pendingApprovals, addApproval, removeApproval }
}
