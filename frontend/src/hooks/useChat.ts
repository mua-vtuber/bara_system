import { useCallback, useEffect } from 'react'
import { useChatStore } from '@/stores/chatStore'
import { useWebSocket } from './useWebSocket'
import type { ChatWSEvent, ChatWSMessage } from '@/types'

/**
 * Chat hook integrating chatStore with the /ws/chat WebSocket.
 * Handles streaming tokens and done events from the server.
 */
export function useChat() {
  const messages = useChatStore((s) => s.messages)
  const isStreaming = useChatStore((s) => s.isStreaming)
  const streamingContent = useChatStore((s) => s.streamingContent)
  const loading = useChatStore((s) => s.loading)
  const fetchHistory = useChatStore((s) => s.fetchHistory)
  const appendStreamToken = useChatStore((s) => s.appendStreamToken)
  const finishStream = useChatStore((s) => s.finishStream)
  const clearStreaming = useChatStore((s) => s.clearStreaming)

  const handleWSMessage = useCallback(
    (data: unknown) => {
      const event = data as ChatWSEvent
      switch (event.type) {
        case 'token':
          appendStreamToken(event.content)
          break
        case 'done':
          finishStream(event.full_response)
          break
        case 'error':
          clearStreaming()
          break
      }
    },
    [appendStreamToken, finishStream, clearStreaming],
  )

  const { send, isConnected } = useWebSocket({
    path: '/ws/chat',
    onMessage: handleWSMessage,
  })

  const sendMessage = useCallback(
    (content: string, platform = 'chat') => {
      if (isConnected) {
        // Add user message optimistically
        const userMsg = {
          id: Date.now(),
          timestamp: new Date().toISOString(),
          role: 'user',
          content,
          platform,
        }
        useChatStore.setState((state) => ({
          messages: [...state.messages, userMsg],
          isStreaming: true,
          streamingContent: '',
        }))

        const wsMsg: ChatWSMessage = {
          type: 'message',
          content,
          platform,
        }
        send(wsMsg)
      } else {
        // Fallback to REST
        void useChatStore.getState().sendMessage(content, platform)
      }
    },
    [isConnected, send],
  )

  useEffect(() => {
    void fetchHistory()
  }, [fetchHistory])

  return {
    messages,
    isStreaming,
    streamingContent,
    loading,
    sendMessage,
    fetchHistory,
    isConnected,
  }
}
