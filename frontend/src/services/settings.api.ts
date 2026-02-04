import { fetchApi } from './api'
import type {
  AppConfig,
  SettingsHistoryResponse,
  SettingsUpdateRequest,
  SettingsUpdateResponse,
} from '@/types'

/** Return the full current configuration (excluding secrets). */
export function getSettings(): Promise<AppConfig> {
  return fetchApi<AppConfig>('/api/settings')
}

/** Update a configuration section at runtime. */
export function updateSettings(
  section: string,
  data: Record<string, unknown>,
): Promise<SettingsUpdateResponse> {
  return fetchApi<SettingsUpdateResponse>('/api/settings', {
    method: 'PUT',
    body: { section, data } satisfies SettingsUpdateRequest,
  })
}

/** Return the settings change history. */
export function getSettingsHistory(limit = 20): Promise<SettingsHistoryResponse> {
  return fetchApi<SettingsHistoryResponse>(`/api/settings/history?limit=${limit}`)
}
