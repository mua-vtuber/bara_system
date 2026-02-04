/**
 * Client-side validation utilities.
 *
 * These mirror the backend validation rules so that the UI can give
 * immediate feedback before making API calls.
 */

const MIN_PASSWORD_LENGTH = 8

export interface ValidationResult {
  valid: boolean
  message: string
}

/**
 * Validate a password.
 *
 * Rules:
 * - Minimum 8 characters (mirrors backend setup-password endpoint)
 */
export function validatePassword(password: string): ValidationResult {
  if (!password) {
    return { valid: false, message: '비밀번호를 입력해주세요.' }
  }
  if (password.length < MIN_PASSWORD_LENGTH) {
    return {
      valid: false,
      message: `비밀번호는 최소 ${MIN_PASSWORD_LENGTH}자 이상이어야 합니다.`,
    }
  }
  return { valid: true, message: '' }
}

/**
 * Validate an API key string.
 *
 * Rules:
 * - Must not be empty
 * - Must be at least 10 characters (reasonable minimum for API keys)
 * - Must contain only alphanumeric characters, hyphens, and underscores
 */
export function validateApiKey(apiKey: string): ValidationResult {
  if (!apiKey) {
    return { valid: false, message: 'API 키를 입력해주세요.' }
  }
  if (apiKey.length < 10) {
    return { valid: false, message: 'API 키가 너무 짧습니다.' }
  }
  if (!/^[a-zA-Z0-9_-]+$/.test(apiKey)) {
    return {
      valid: false,
      message: 'API 키에 허용되지 않는 문자가 포함되어 있습니다.',
    }
  }
  return { valid: true, message: '' }
}
