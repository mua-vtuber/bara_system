import type { ReactNode } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { LoginPage } from './LoginPage'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'

interface AuthGateProps {
  children: ReactNode
}

export function AuthGate({ children }: AuthGateProps) {
  const { isLoggedIn, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-100">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (!isLoggedIn) {
    return <LoginPage />
  }

  return <>{children}</>
}
