import { create } from 'zustand'
import type { BotStatus, PlatformStatus, StateSyncData } from '@/types'

interface StatusState {
  botStatus: BotStatus
  platforms: Record<string, PlatformStatus>
  queueSizes: Record<string, number>
  uptimeSeconds: number
  updateFromSync: (data: StateSyncData) => void
  updateBotStatus: (status: BotStatus) => void
  updatePlatformError: (platform: string, error: string) => void
}

export const useStatusStore = create<StatusState>()((set) => ({
  botStatus: 'offline',
  platforms: {},
  queueSizes: {},
  uptimeSeconds: 0,

  updateFromSync: (data: StateSyncData): void => {
    const platforms: Record<string, PlatformStatus> = {}
    for (const [key, value] of Object.entries(data.platforms)) {
      platforms[key] = value as PlatformStatus
    }
    set({
      botStatus: data.bot_status,
      platforms,
      uptimeSeconds: data.uptime_seconds,
    })
  },

  updateBotStatus: (status: BotStatus): void => {
    set({ botStatus: status })
  },

  updatePlatformError: (platform: string, _error: string): void => {
    set((state) => {
      const existing = state.platforms[platform]
      if (!existing) return state
      return {
        platforms: {
          ...state.platforms,
          [platform]: { ...existing, authenticated: false },
        },
      }
    })
  },
}))
