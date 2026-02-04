import { fetchApi } from './api'
import type { PlatformValidateResponse } from '@/types'

/** Return the status summary of all known platforms. */
export function getPlatforms(): Promise<Record<string, unknown>> {
  return fetchApi<Record<string, unknown>>('/api/platforms')
}

/** Test whether the API key for a platform is valid. */
export function validatePlatform(platform: string): Promise<PlatformValidateResponse> {
  return fetchApi<PlatformValidateResponse>('/api/platforms/validate', {
    method: 'POST',
    body: { platform },
  })
}
