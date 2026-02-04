import { create } from 'zustand'
import * as chatApi from '@/services/chat.api'
import type { Conversation } from '@/types'

interface ChatState {
  messages: Conversation[]
  isStreaming: boolean
  streamingContent: string
  loading: boolean
  fetchHistory: (limit?: number, platform?: string) => Promise<void>
  sendMessage: (content: string, platform?: string) => Promise<void>
  appendStreamToken: (token: string) => void
  finishStream: (fullResponse: string) => void
  clearStreaming: () => void
}

export const useChatStore = create<ChatState>()((set, get) => ({
  messages: [],
  isStreaming: false,
  streamingContent: '',
  loading: false,

  fetchHistory: async (limit = 50, platform?: string): Promise<void> => {
    set({ loading: true })
    try {
      const res = await chatApi.getHistory(limit, 0, platform)
      set({ messages: res.conversations, loading: false })
    } catch {
      set({ loading: false })
    }
  },

  sendMessage: async (content: string, platform = 'chat'): Promise<void> => {
    // Optimistically add user message
    const userMsg: Conversation = {
      id: Date.now(),
      timestamp: new Date().toISOString(),
      role: 'user',
      content,
      platform,
    }
    set((state) => ({
      messages: [...state.messages, userMsg],
    }))

    // Non-streaming fallback via REST
    try {
      const res = await chatApi.sendMessage(content, platform)
      const botMsg: Conversation = {
        id: res.conversation_id,
        timestamp: new Date().toISOString(),
        role: 'assistant',
        content: res.response,
        platform,
      }
      set((state) => ({
        messages: [...state.messages, botMsg],
      }))
    } catch {
      // Error handled silently; UI can check messages
    }
  },

  appendStreamToken: (token: string): void => {
    set((state) => ({
      isStreaming: true,
      streamingContent: state.streamingContent + token,
    }))
  },

  finishStream: (fullResponse: string): void => {
    const msgs = get().messages
    const platform = msgs.length > 0 ? msgs[msgs.length - 1].platform : 'chat'
    const botMsg: Conversation = {
      id: Date.now(),
      timestamp: new Date().toISOString(),
      role: 'assistant',
      content: fullResponse,
      platform,
    }
    set((state) => ({
      messages: [...state.messages, botMsg],
      isStreaming: false,
      streamingContent: '',
    }))
  },

  clearStreaming: (): void => {
    set({ isStreaming: false, streamingContent: '' })
  },
}))
