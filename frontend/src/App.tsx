import { useAuth } from '@/hooks/useAuth'
import { SetupWizard } from '@/components/setup/SetupWizard'
import { AuthGate } from '@/components/auth/AuthGate'
import { AppShell } from '@/components/layout/AppShell'
import { ErrorBoundary } from '@/components/common/ErrorBoundary'
import { ToastProvider } from '@/components/common/Toast'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'

function AppContent() {
  const { isSetupComplete, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-100">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (!isSetupComplete) {
    return (
      <SetupWizard
        onComplete={() => {
          window.location.reload()
        }}
      />
    )
  }

  return (
    <AuthGate>
      <AppShell />
    </AuthGate>
  )
}

export default function App() {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <AppContent />
      </ToastProvider>
    </ErrorBoundary>
  )
}
