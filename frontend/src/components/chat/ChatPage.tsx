import { useChat } from '@/hooks/useChat'
import { MessageList } from './MessageList'
import { ChatInput } from './ChatInput'
import { ConnectionIndicator } from '@/components/common/ConnectionIndicator'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'

export function ChatPage() {
  const {
    messages,
    isStreaming,
    streamingContent,
    loading,
    sendMessage,
    isConnected,
  } = useChat()

  return (
    <div className="flex h-full flex-col">
      {/* Connection status */}
      <div className="flex items-center justify-end px-4 py-1">
        <ConnectionIndicator connected={isConnected} />
      </div>

      {/* Messages */}
      {loading ? (
        <div className="flex flex-1 items-center justify-center">
          <LoadingSpinner />
        </div>
      ) : (
        <MessageList
          messages={messages}
          isStreaming={isStreaming}
          streamingContent={streamingContent}
        />
      )}

      {/* Input */}
      <ChatInput onSend={sendMessage} disabled={isStreaming} />
    </div>
  )
}
