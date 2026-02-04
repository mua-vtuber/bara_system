import { useBotStatus } from '@/hooks/useBotStatus'
import { ConnectionIndicator } from '@/components/common/ConnectionIndicator'
import { Badge } from '@/components/common/Badge'
import { formatDuration } from '@/utils/format'
import type { BotStatus } from '@/types'

const statusBadgeVariant: Record<BotStatus, 'success' | 'warning' | 'danger' | 'info'> = {
  active: 'success',
  idle: 'info',
  offline: 'danger',
  stopped: 'warning',
}

const statusLabel: Record<BotStatus, string> = {
  active: '활성',
  idle: '대기',
  offline: '오프라인',
  stopped: '중지',
}

export function StatusBar() {
  const { botStatus, platforms, uptimeSeconds, isConnected } = useBotStatus()

  const platformEntries = Object.entries(platforms)

  return (
    <footer className="flex h-8 items-center justify-between border-t border-gray-200 bg-gray-50 px-4 text-xs text-gray-500">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <span className="text-gray-400">봇:</span>
          <Badge variant={statusBadgeVariant[botStatus]}>
            {statusLabel[botStatus]}
          </Badge>
        </div>

        {platformEntries.length > 0 && (
          <div className="flex items-center gap-2">
            {platformEntries.map(([name, status]) => (
              <div key={name} className="flex items-center gap-1">
                <span className="text-gray-400">{name}:</span>
                <span
                  className={
                    status.enabled && status.authenticated
                      ? 'text-green-600'
                      : 'text-gray-400'
                  }
                >
                  {status.enabled
                    ? status.authenticated
                      ? '연결됨'
                      : '인증 실패'
                    : '비활성'}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="flex items-center gap-4">
        <span>가동: {formatDuration(uptimeSeconds)}</span>
        <ConnectionIndicator connected={isConnected} />
      </div>
    </footer>
  )
}
