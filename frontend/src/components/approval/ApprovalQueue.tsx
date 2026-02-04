import { useState, useCallback } from 'react'
import { useApproval } from '@/hooks/useApproval'
import { ApprovalModal } from './ApprovalModal'
import { Badge } from '@/components/common/Badge'
import { useToast } from '@/components/common/Toast'
import type { Activity } from '@/types'

export function ApprovalQueue() {
  const { pendingApprovals, removeApproval } = useApproval()
  const { addToast } = useToast()
  const [selectedActivity, setSelectedActivity] = useState<Activity | null>(null)

  const handleApprove = useCallback(
    (activityId: number) => {
      removeApproval(activityId)
      setSelectedActivity(null)
      addToast('success', '활동이 승인되었습니다')
    },
    [removeApproval, addToast],
  )

  const handleReject = useCallback(
    (activityId: number) => {
      removeApproval(activityId)
      setSelectedActivity(null)
      addToast('info', '활동이 거부되었습니다')
    },
    [removeApproval, addToast],
  )

  const handleEdit = useCallback(
    (activityId: number, _editedContent: string) => {
      removeApproval(activityId)
      setSelectedActivity(null)
      addToast('success', '수정 후 승인되었습니다')
    },
    [removeApproval, addToast],
  )

  if (pendingApprovals.length === 0) return null

  return (
    <>
      {/* Floating badge */}
      <div className="fixed bottom-12 left-4 z-40">
        <button
          onClick={() => setSelectedActivity(pendingApprovals[0])}
          className="flex items-center gap-2 rounded-full bg-yellow-500 px-4 py-2 text-sm font-medium text-white shadow-lg transition-colors hover:bg-yellow-600"
        >
          승인 대기
          <Badge variant="danger" className="bg-white text-yellow-700">
            {pendingApprovals.length}
          </Badge>
        </button>
      </div>

      {/* Modal */}
      <ApprovalModal
        activity={selectedActivity}
        onClose={() => setSelectedActivity(null)}
        onApprove={handleApprove}
        onReject={handleReject}
        onEdit={handleEdit}
      />
    </>
  )
}
