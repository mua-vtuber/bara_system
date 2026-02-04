import clsx from 'clsx'
import { formatTime } from '@/utils/format'
import type { Conversation } from '@/types'

interface MessageBubbleProps {
  message: Conversation
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  return (
    <div
      className={clsx(
        'flex w-full',
        isUser ? 'justify-end' : 'justify-start',
      )}
    >
      <div
        className={clsx(
          'max-w-[70%] rounded-lg px-4 py-2.5',
          isUser
            ? 'bg-blue-600 text-white'
            : 'bg-white text-gray-900 shadow-sm border border-gray-100',
        )}
      >
        <p className="whitespace-pre-wrap break-words text-sm">
          {message.content}
        </p>
        <p
          className={clsx(
            'mt-1 text-right text-xs',
            isUser ? 'text-blue-200' : 'text-gray-400',
          )}
        >
          {formatTime(message.timestamp)}
        </p>
      </div>
    </div>
  )
}
