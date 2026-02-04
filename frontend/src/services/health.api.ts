import { fetchApi } from './api'
import type { HealthResponse } from '@/types'

/** Retrieve the current system health status. */
export function getHealth(): Promise<HealthResponse> {
  return fetchApi<HealthResponse>('/api/health')
}
