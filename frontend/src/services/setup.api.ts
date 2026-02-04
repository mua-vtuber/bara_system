import { fetchApi } from './api'
import type {
  BehaviorConfigRequest,
  BotConfigRequest,
  ModelSelectRequest,
  ModelsResponse,
  PlatformsConfigRequest,
  SetupCompleteResponse,
  SetupStatus,
  SystemCheckResponse,
  VoiceConfigRequest,
} from '@/types'

/** Get current setup wizard progress. */
export function getSetupStatus(): Promise<SetupStatus> {
  return fetchApi<SetupStatus>('/api/setup/status')
}

/** Perform system health checks (Ollama, Python, disk). */
export function systemCheck(): Promise<SystemCheckResponse> {
  return fetchApi<SystemCheckResponse>('/api/setup/system-check')
}

/** Get available Ollama models. */
export function getModels(): Promise<ModelsResponse> {
  return fetchApi<ModelsResponse>('/api/setup/models')
}

/** Select the LLM model to use. */
export function setModel(model: string): Promise<{ success: boolean; message: string }> {
  return fetchApi<{ success: boolean; message: string }>('/api/setup/model', {
    method: 'POST',
    body: { model } satisfies ModelSelectRequest,
  })
}

/** Configure bot name and settings. */
export function setBotConfig(
  config: BotConfigRequest,
): Promise<{ success: boolean; message: string }> {
  return fetchApi<{ success: boolean; message: string }>('/api/setup/bot', {
    method: 'POST',
    body: config,
  })
}

/** Configure platform integrations. */
export function setPlatforms(
  config: PlatformsConfigRequest,
): Promise<{ success: boolean; message: string; validation?: Record<string, boolean> }> {
  return fetchApi<{
    success: boolean
    message: string
    validation?: Record<string, boolean>
  }>('/api/setup/platforms', {
    method: 'POST',
    body: config,
  })
}

/** Configure bot behavior settings. */
export function setBehavior(
  config: BehaviorConfigRequest,
): Promise<{ success: boolean; message: string }> {
  return fetchApi<{ success: boolean; message: string }>('/api/setup/behavior', {
    method: 'POST',
    body: config,
  })
}

/** Configure voice/audio settings. */
export function setVoice(
  config: VoiceConfigRequest,
): Promise<{ success: boolean; message: string }> {
  return fetchApi<{ success: boolean; message: string }>('/api/setup/voice', {
    method: 'POST',
    body: config,
  })
}

/** Finalize setup wizard. */
export function completeSetup(): Promise<SetupCompleteResponse> {
  return fetchApi<SetupCompleteResponse>('/api/setup/complete', {
    method: 'POST',
  })
}
