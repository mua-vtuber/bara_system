import { Modal } from '@/components/common/Modal'
import { Badge } from '@/components/common/Badge'
import { formatDate, formatTime } from '@/utils/format'
import type { CollectedInfo } from '@/types'

interface InfoDetailProps {
  info: CollectedInfo | null
  onClose: () => void
}

export function InfoDetail({ info, onClose }: InfoDetailProps) {
  if (!info) return null

  return (
    <Modal isOpen={!!info} onClose={onClose} title={info.title ?? '정보 상세'}>
      <div className="space-y-4">
        {/* Meta */}
        <div className="flex items-center gap-3">
          {info.category && <Badge variant="info">{info.category}</Badge>}
          <span className="text-sm text-gray-500">{info.platform}</span>
          <span className="text-sm text-gray-400">
            {formatDate(info.timestamp)} {formatTime(info.timestamp)}
          </span>
        </div>

        {/* Author */}
        {info.author && (
          <div>
            <h4 className="mb-1 text-xs font-medium uppercase text-gray-400">
              작성자
            </h4>
            <p className="text-sm text-gray-700">{info.author}</p>
          </div>
        )}

        {/* Content */}
        {info.content && (
          <div>
            <h4 className="mb-1 text-xs font-medium uppercase text-gray-400">
              내용
            </h4>
            <p className="whitespace-pre-wrap rounded-md bg-gray-50 p-3 text-sm text-gray-700">
              {info.content}
            </p>
          </div>
        )}

        {/* Tags */}
        {info.tags && (
          <div>
            <h4 className="mb-1 text-xs font-medium uppercase text-gray-400">
              태그
            </h4>
            <div className="flex flex-wrap gap-1">
              {info.tags.split(',').map((tag) => (
                <span
                  key={tag.trim()}
                  className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600"
                >
                  {tag.trim()}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Source URL */}
        {info.source_url && (
          <div>
            <h4 className="mb-1 text-xs font-medium uppercase text-gray-400">
              원본 링크
            </h4>
            <a
              href={info.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-blue-600 hover:underline"
            >
              {info.source_url}
            </a>
          </div>
        )}
      </div>
    </Modal>
  )
}
