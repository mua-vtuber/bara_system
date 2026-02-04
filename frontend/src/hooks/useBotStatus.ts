import { useCallback } from 'react'
import { useStatusStore } from '@/stores/statusStore'
import { useWebSocket } from './useWebSocket'
import type { BotStatus, StatusWSEvent } from '@/types'

/**
 * Bot status hook integrating statusStore with the /ws/status WebSocket.
 * Receives real-time state_sync and individual event updates.
 */
export function useBotStatus() {
  const botStatus = useStatusStore((s) => s.botStatus)
  const platforms = useStatusStore((s) => s.platforms)
  const queueSizes = useStatusStore((s) => s.queueSizes)
  const uptimeSeconds = useStatusStore((s) => s.uptimeSeconds)
  const updateFromSync = useStatusStore((s) => s.updateFromSync)
  const updateBotStatus = useStatusStore((s) => s.updateBotStatus)
  const updatePlatformError = useStatusStore((s) => s.updatePlatformError)

  const handleWSMessage = useCallback(
    (data: unknown) => {
      const event = data as StatusWSEvent
      switch (event.type) {
        case 'state_sync':
          updateFromSync(event.data)
          break
        case 'bot_status':
          updateBotStatus(event.data.new_status as BotStatus)
          break
        case 'platform_error':
          updatePlatformError(event.data.platform, event.data.message)
          break
        case 'task_queued':
          useStatusStore.setState((state) => ({
            queueSizes: {
              ...state.queueSizes,
              [event.data.platform]: (state.queueSizes[event.data.platform] ?? 0) + 1,
            },
          }))
          break
        case 'task_completed':
          useStatusStore.setState((state) => ({
            queueSizes: {
              ...state.queueSizes,
              [event.data.platform]: Math.max(
                0,
                (state.queueSizes[event.data.platform] ?? 0) - 1,
              ),
            },
          }))
          break
        default:
          // health, comment_posted, post_created -- no state change needed
          break
      }
    },
    [updateFromSync, updateBotStatus, updatePlatformError],
  )

  const { isConnected } = useWebSocket({
    path: '/ws/status',
    onMessage: handleWSMessage,
  })

  return { botStatus, platforms, queueSizes, uptimeSeconds, isConnected }
}
