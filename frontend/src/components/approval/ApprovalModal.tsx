import { useState } from 'react'
import { Modal } from '@/components/common/Modal'
import { Button } from '@/components/common/Button'
import { Badge } from '@/components/common/Badge'
import { formatRelativeTime } from '@/utils/format'
import type { Activity } from '@/types'

interface ApprovalModalProps {
  activity: Activity | null
  onClose: () => void
  onApprove: (activityId: number) => void
  onReject: (activityId: number) => void
  onEdit: (activityId: number, editedContent: string) => void
}

export function ApprovalModal({
  activity,
  onClose,
  onApprove,
  onReject,
  onEdit,
}: ApprovalModalProps) {
  const [editMode, setEditMode] = useState(false)
  const [editedContent, setEditedContent] = useState('')

  if (!activity) return null

  const handleEditStart = () => {
    setEditedContent(activity.bot_response ?? '')
    setEditMode(true)
  }

  const handleEditSubmit = () => {
    onEdit(activity.id, editedContent)
    setEditMode(false)
  }

  return (
    <Modal isOpen={!!activity} onClose={onClose} title="승인 요청">
      <div className="space-y-4">
        {/* Meta */}
        <div className="flex items-center gap-3">
          <Badge variant="warning">승인 대기</Badge>
          <span className="text-sm text-gray-500">{activity.platform}</span>
          <span className="text-xs text-gray-400">
            {formatRelativeTime(activity.timestamp)}
          </span>
        </div>

        {/* Original content */}
        {activity.original_content && (
          <div>
            <h4 className="mb-1 text-xs font-medium uppercase text-gray-400">
              원본 내용
            </h4>
            <p className="rounded-md bg-gray-50 p-3 text-sm text-gray-700">
              {activity.original_content}
            </p>
          </div>
        )}

        {/* Bot response */}
        <div>
          <h4 className="mb-1 text-xs font-medium uppercase text-gray-400">
            봇 응답
          </h4>
          {editMode ? (
            <textarea
              value={editedContent}
              onChange={(e) => setEditedContent(e.target.value)}
              rows={4}
              className="w-full rounded-md border border-gray-300 p-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              autoFocus
            />
          ) : (
            <p className="rounded-md bg-blue-50 p-3 text-sm text-gray-700">
              {activity.bot_response ?? '(응답 없음)'}
            </p>
          )}
        </div>

        {/* Actions */}
        <div className="flex gap-2 border-t border-gray-100 pt-4">
          {editMode ? (
            <>
              <Button variant="primary" size="sm" onClick={handleEditSubmit}>
                수정 후 승인
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setEditMode(false)}
              >
                취소
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="primary"
                size="sm"
                onClick={() => onApprove(activity.id)}
              >
                승인
              </Button>
              <Button variant="secondary" size="sm" onClick={handleEditStart}>
                수정
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={() => onReject(activity.id)}
              >
                거부
              </Button>
            </>
          )}
        </div>
      </div>
    </Modal>
  )
}
