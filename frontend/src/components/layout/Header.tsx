import { useConfig } from '@/hooks/useConfig'
import { useAuth } from '@/hooks/useAuth'
import { Button } from '@/components/common/Button'

export function Header() {
  const { config } = useConfig()
  const { logout } = useAuth()

  const botName = config?.bot.name ?? 'BARA'

  return (
    <header className="flex h-14 items-center justify-between border-b border-gray-200 bg-white px-6">
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-bold text-gray-900">{botName}</h1>
        <span className="text-xs text-gray-400">System</span>
      </div>
      <Button variant="secondary" size="sm" onClick={() => void logout()}>
        로그아웃
      </Button>
    </header>
  )
}
