/**
 * Base API client using the Fetch API.
 *
 * All service modules build on top of {@link fetchApi} which handles:
 * - Automatic JSON serialisation/deserialisation
 * - Session cookie forwarding (httpOnly cookies are sent automatically)
 * - CSRF token management for mutating requests
 * - 401 -> redirect to login
 * - Generic error propagation
 */

// Redirect HTTP → HTTPS in production (skip localhost for development).
if (
  typeof window !== 'undefined' &&
  window.location.protocol === 'http:' &&
  !window.location.hostname.match(/^(localhost|127\.0\.0\.1)$/)
) {
  window.location.href = window.location.href.replace('http:', 'https:')
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(detail)
    this.name = 'ApiError'
  }
}

interface FetchOptions extends Omit<RequestInit, 'body'> {
  body?: unknown
}

/**
 * Cached CSRF token for mutating requests.
 */
let _csrfToken: string | null = null

/**
 * Fetch a fresh CSRF token from the backend.
 * @returns The CSRF token string, or null on error.
 */
async function fetchCsrfToken(): Promise<string | null> {
  try {
    const response = await fetch('/api/auth/csrf-token', {
      credentials: 'same-origin',
    })
    if (!response.ok) {
      console.error('Failed to fetch CSRF token:', response.status)
      return null
    }
    const data = await response.json() as { csrf_token: string }
    _csrfToken = data.csrf_token
    return _csrfToken
  } catch (error) {
    console.error('Error fetching CSRF token:', error)
    return null
  }
}

/**
 * Clear the cached CSRF token (e.g., on logout).
 */
export function clearCsrfToken(): void {
  _csrfToken = null
}

/**
 * Typed fetch wrapper for backend API calls.
 *
 * @param path  - API path starting with `/api/...`
 * @param options - Standard fetch options; `body` is auto-serialised to JSON.
 * @returns Parsed JSON response typed as `T`.
 */
export async function fetchApi<T>(path: string, options: FetchOptions = {}): Promise<T> {
  return _fetchApiInternal(path, options, false)
}

async function _fetchApiInternal<T>(
  path: string,
  options: FetchOptions = {},
  isRetry: boolean = false
): Promise<T> {
  const { body, headers: extraHeaders, method = 'GET', ...rest } = options

  const headers: Record<string, string> = {
    ...(extraHeaders as Record<string, string>),
  }

  let fetchBody: BodyInit | undefined
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    fetchBody = JSON.stringify(body)
  }

  // Add CSRF token for mutating methods
  const isMutating = ['POST', 'PUT', 'DELETE', 'PATCH'].includes(method.toUpperCase())
  if (isMutating) {
    if (_csrfToken === null) {
      await fetchCsrfToken()
    }
    if (_csrfToken !== null) {
      headers['X-CSRF-Token'] = _csrfToken
    }
  }

  const response = await fetch(path, {
    ...rest,
    method,
    headers,
    body: fetchBody,
    credentials: 'same-origin',
  })

  // Handle 401 -> redirect to login
  if (response.status === 401) {
    // Only redirect if we are not already on the login page
    if (!window.location.pathname.startsWith('/login')) {
      window.location.href = '/login'
    }
    throw new ApiError(401, 'Unauthorized')
  }

  // Handle 403 -> CSRF token expired, retry once
  if (response.status === 403 && !isRetry && isMutating) {
    _csrfToken = null
    await fetchCsrfToken()
    return _fetchApiInternal(path, options, true)
  }

  // Handle non-2xx responses
  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const errorBody = await response.json()
      detail = errorBody.detail ?? errorBody.message ?? errorBody.error ?? detail
    } catch {
      // Response body was not JSON; use status text
      detail = response.statusText || detail
    }
    throw new ApiError(response.status, detail)
  }

  // 204 No Content
  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}
