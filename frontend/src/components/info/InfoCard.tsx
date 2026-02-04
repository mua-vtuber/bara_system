import { Badge } from '@/components/common/Badge'
import { formatRelativeTime } from '@/utils/format'
import type { CollectedInfo } from '@/types'

interface InfoCardProps {
  info: CollectedInfo
  onSelect: (info: CollectedInfo) => void
  onToggleBookmark: (id: number) => void
}

export function InfoCard({ info, onSelect, onToggleBookmark }: InfoCardProps) {
  return (
    <div
      className="cursor-pointer rounded-lg border border-gray-100 bg-white p-4 shadow-sm transition-shadow hover:shadow-md"
      onClick={() => onSelect(info)}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            {info.title && (
              <h3 className="text-sm font-medium text-gray-900 line-clamp-1">
                {info.title}
              </h3>
            )}
            {info.category && (
              <Badge variant="info">{info.category}</Badge>
            )}
          </div>
          {info.content && (
            <p className="mt-1 text-sm text-gray-600 line-clamp-2">
              {info.content}
            </p>
          )}
          <div className="mt-2 flex items-center gap-3 text-xs text-gray-400">
            <span>{info.platform}</span>
            {info.author && <span>{info.author}</span>}
            <span>{formatRelativeTime(info.timestamp)}</span>
          </div>
        </div>

        <button
          onClick={(e) => {
            e.stopPropagation()
            onToggleBookmark(info.id)
          }}
          className="ml-2 shrink-0 rounded p-1 text-gray-300 transition-colors hover:text-yellow-500"
        >
          <svg
            className="h-5 w-5"
            fill={info.bookmarked ? 'currentColor' : 'none'}
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={info.bookmarked ? 0 : 1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"
            />
          </svg>
        </button>
      </div>
    </div>
  )
}
