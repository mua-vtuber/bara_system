import { Modal } from '@/components/common/Modal'
import { Badge } from '@/components/common/Badge'
import { formatDate, formatTime } from '@/utils/format'
import type { Activity, ActivityStatus } from '@/types'

interface ActivityDetailProps {
  activity: Activity | null
  onClose: () => void
}

const statusVariant: Record<ActivityStatus, 'success' | 'warning' | 'danger' | 'info'> = {
  pending: 'warning',
  approved: 'info',
  posted: 'success',
  rejected: 'danger',
  failed: 'danger',
}

const statusLabels: Record<ActivityStatus, string> = {
  pending: '대기',
  approved: '승인',
  posted: '완료',
  rejected: '거부',
  failed: '실패',
}

export function ActivityDetail({ activity, onClose }: ActivityDetailProps) {
  if (!activity) return null

  return (
    <Modal isOpen={!!activity} onClose={onClose} title="활동 상세">
      <div className="space-y-4">
        {/* Meta */}
        <div className="flex items-center gap-3">
          <Badge variant={statusVariant[activity.status]}>
            {statusLabels[activity.status]}
          </Badge>
          <span className="text-sm text-gray-500">{activity.platform}</span>
          <span className="text-sm text-gray-400">
            {formatDate(activity.timestamp)} {formatTime(activity.timestamp)}
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
        {activity.bot_response && (
          <div>
            <h4 className="mb-1 text-xs font-medium uppercase text-gray-400">
              봇 응답
            </h4>
            <p className="rounded-md bg-blue-50 p-3 text-sm text-gray-700">
              {activity.bot_response}
            </p>
          </div>
        )}

        {/* Translation */}
        {activity.translated_content && (
          <div>
            <h4 className="mb-1 text-xs font-medium uppercase text-gray-400">
              번역 ({activity.translation_direction ?? ''})
            </h4>
            <p className="rounded-md bg-gray-50 p-3 text-sm text-gray-700">
              {activity.translated_content}
            </p>
          </div>
        )}

        {/* URL */}
        {activity.url && (
          <div>
            <h4 className="mb-1 text-xs font-medium uppercase text-gray-400">
              링크
            </h4>
            <a
              href={activity.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-blue-600 hover:underline"
            >
              {activity.url}
            </a>
          </div>
        )}

        {/* Error */}
        {activity.error_message && (
          <div>
            <h4 className="mb-1 text-xs font-medium uppercase text-gray-400">
              오류
            </h4>
            <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">
              {activity.error_message}
            </p>
          </div>
        )}

        {/* IDs */}
        <div className="grid grid-cols-2 gap-2 border-t border-gray-100 pt-3 text-xs text-gray-400">
          <span>ID: {activity.id}</span>
          {activity.platform_post_id && (
            <span>게시글 ID: {activity.platform_post_id}</span>
          )}
          {activity.platform_comment_id && (
            <span>댓글 ID: {activity.platform_comment_id}</span>
          )}
          {activity.parent_id && (
            <span>상위 ID: {activity.parent_id}</span>
          )}
        </div>
      </div>
    </Modal>
  )
}
