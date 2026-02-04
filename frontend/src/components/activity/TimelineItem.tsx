import clsx from 'clsx'
import { Badge } from '@/components/common/Badge'
import { formatRelativeTime } from '@/utils/format'
import type { Activity, ActivityType, ActivityStatus } from '@/types'

interface TimelineItemProps {
  activity: Activity
  onSelect: (activity: Activity) => void
}

const typeIcons: Record<ActivityType, string> = {
  comment:
    'M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z',
  post: 'M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z',
  reply:
    'M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6',
  upvote: 'M5 15l7-7 7 7',
  downvote: 'M19 9l-7 7-7-7',
  follow: 'M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z',
}

const typeLabels: Record<ActivityType, string> = {
  comment: '댓글',
  post: '글',
  reply: '답글',
  upvote: '추천',
  downvote: '비추천',
  follow: '팔로우',
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

export function TimelineItem({ activity, onSelect }: TimelineItemProps) {
  const icon = typeIcons[activity.type] ?? typeIcons.comment

  return (
    <div className="relative flex gap-4 pb-6">
      {/* Vertical line */}
      <div className="absolute left-[17px] top-8 h-full w-px bg-gray-200" />

      {/* Icon */}
      <div className="relative z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blue-100">
        <svg
          className="h-4 w-4 text-blue-600"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d={icon} />
        </svg>
      </div>

      {/* Content */}
      <button
        onClick={() => onSelect(activity)}
        className="flex-1 rounded-lg border border-gray-100 bg-white p-3 text-left shadow-sm transition-shadow hover:shadow-md"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-gray-900">
              {typeLabels[activity.type]}
            </span>
            <Badge variant={statusVariant[activity.status]}>
              {statusLabels[activity.status]}
            </Badge>
            <span className={clsx(
              'text-xs px-1.5 py-0.5 rounded',
              'bg-gray-100 text-gray-600',
            )}>
              {activity.platform}
            </span>
          </div>
          <span className="text-xs text-gray-400">
            {formatRelativeTime(activity.timestamp)}
          </span>
        </div>
        {activity.bot_response && (
          <p className="mt-1.5 line-clamp-2 text-sm text-gray-600">
            {activity.bot_response}
          </p>
        )}
        {activity.original_content && !activity.bot_response && (
          <p className="mt-1.5 line-clamp-2 text-sm text-gray-600">
            {activity.original_content}
          </p>
        )}
      </button>
    </div>
  )
}
