import { fetchApi } from './api'
import type {
  AuthStatusResponse,
  LoginRequest,
  LoginResponse,
  SetupPasswordRequest,
  SetupPasswordResponse,
} from '@/types'

/** Authenticate with a password. Sets an httpOnly session cookie. */
export function login(password: string): Promise<LoginResponse> {
  return fetchApi<LoginResponse>('/api/auth/login', {
    method: 'POST',
    body: { password } satisfies LoginRequest,
  })
}

/** Invalidate the current session and clear the cookie. */
export function logout(): Promise<{ detail: string }> {
  return fetchApi<{ detail: string }>('/api/auth/logout', {
    method: 'POST',
  })
}

/** Check current authentication state. */
export function getStatus(): Promise<AuthStatusResponse> {
  return fetchApi<AuthStatusResponse>('/api/auth/status')
}

/** Set the initial password during first-time setup. */
export function setupPassword(password: string): Promise<SetupPasswordResponse> {
  return fetchApi<SetupPasswordResponse>('/api/auth/setup-password', {
    method: 'POST',
    body: { password } satisfies SetupPasswordRequest,
  })
}
