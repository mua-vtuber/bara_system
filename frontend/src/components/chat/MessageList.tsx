import { useEffect, useRef } from 'react'
import { MessageBubble } from './MessageBubble'
import { StreamingIndicator } from './StreamingIndicator'
import type { Conversation } from '@/types'

interface MessageListProps {
  messages: Conversation[]
  isStreaming: boolean
  streamingContent: string
}

export function MessageList({
  messages,
  isStreaming,
  streamingContent,
}: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  if (messages.length === 0 && !isStreaming) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <p className="text-sm text-gray-400">
          메시지가 없습니다. 대화를 시작해보세요.
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-1 flex-col gap-3 overflow-y-auto p-4">
      {messages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} />
      ))}
      {isStreaming && <StreamingIndicator content={streamingContent} />}
      <div ref={bottomRef} />
    </div>
  )
}
