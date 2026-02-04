import { fetchApi } from './api'

export interface MissionResponse {
  id: number
  created_at: string
  topic: string
  question_hint: string
  urgency: string
  status: string
  target_platform: string
  target_community: string
  warmup_count: number
  warmup_target: number
  post_id: string
  post_platform: string
  collected_responses: Array<{
    comment_id?: string
    author: string
    content: string
    platform?: string
  }>
  summary: string
  completed_at: string | null
  user_notes: string
}

export interface MissionListResponse {
  missions: MissionResponse[]
  total: number
}

export interface MissionCreateRequest {
  topic: string
  question_hint?: string
  urgency?: string
  target_platform?: string
  target_community?: string
  user_notes?: string
}

export function listMissions(
  limit = 50,
  offset = 0,
  status?: string,
): Promise<MissionListResponse> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (status) params.set('status', status)
  return fetchApi<MissionListResponse>(`/api/missions?${params}`)
}

export function getMission(id: number): Promise<MissionResponse> {
  return fetchApi<MissionResponse>(`/api/missions/${id}`)
}

export function createMission(data: MissionCreateRequest): Promise<MissionResponse> {
  return fetchApi<MissionResponse>('/api/missions', {
    method: 'POST',
    body: data,
  })
}

export function cancelMission(id: number): Promise<{ detail: string }> {
  return fetchApi<{ detail: string }>(`/api/missions/${id}/cancel`, {
    method: 'PUT',
  })
}

export function completeMission(id: number): Promise<{ detail: string; summary: string }> {
  return fetchApi<{ detail: string; summary: string }>(`/api/missions/${id}/complete`, {
    method: 'PUT',
  })
}

export function getMissionSummary(
  id: number,
  regenerate = false,
): Promise<{ summary: string }> {
  return fetchApi<{ summary: string }>(
    `/api/missions/${id}/summary?regenerate=${regenerate}`,
  )
}
