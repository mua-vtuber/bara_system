import { useEffect } from 'react'
import { useAuthStore } from '@/stores/authStore'

/**
 * Auth hook wrapping the auth store.
 * Automatically checks authentication status on first mount.
 */
export function useAuth() {
  const isLoggedIn = useAuthStore((s) => s.isLoggedIn)
  const isSetupComplete = useAuthStore((s) => s.isSetupComplete)
  const loading = useAuthStore((s) => s.loading)
  const login = useAuthStore((s) => s.login)
  const logout = useAuthStore((s) => s.logout)
  const setupPassword = useAuthStore((s) => s.setupPassword)
  const checkStatus = useAuthStore((s) => s.checkStatus)

  useEffect(() => {
    void checkStatus()
  }, [checkStatus])

  return { isLoggedIn, isSetupComplete, loading, login, logout, setupPassword }
}
