import { create } from 'zustand'
import * as settingsApi from '@/services/settings.api'
import type { AppConfig } from '@/types'

interface ConfigState {
  config: AppConfig | null
  loading: boolean
  error: string | null
  fetchConfig: () => Promise<void>
  updateConfig: (section: string, data: Partial<AppConfig>) => Promise<void>
}

export const useConfigStore = create<ConfigState>()((set) => ({
  config: null,
  loading: false,
  error: null,

  fetchConfig: async (): Promise<void> => {
    set({ loading: true, error: null })
    try {
      const config = await settingsApi.getSettings()
      set({ config, loading: false })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch config'
      set({ error: message, loading: false })
    }
  },

  updateConfig: async (section: string, data: Partial<AppConfig>): Promise<void> => {
    set({ loading: true, error: null })
    try {
      await settingsApi.updateSettings(section, data as Record<string, unknown>)
      // Re-fetch to get the full updated config
      const config = await settingsApi.getSettings()
      set({ config, loading: false })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update config'
      set({ error: message, loading: false })
    }
  },
}))
