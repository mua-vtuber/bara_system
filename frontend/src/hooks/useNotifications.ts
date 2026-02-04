import { useCallback, useEffect } from 'react'
import { useNotificationStore } from '@/stores/notificationStore'
import { useWebSocket } from './useWebSocket'

interface NotificationWSEvent {
  type: string
  data?: unknown
}

/**
 * Notifications hook integrating notificationStore with WS events.
 * Listens for notification_received events to increment unread count.
 */
export function useNotifications() {
  const notifications = useNotificationStore((s) => s.notifications)
  const unreadCount = useNotificationStore((s) => s.unreadCount)
  const loading = useNotificationStore((s) => s.loading)
  const fetchNotifications = useNotificationStore((s) => s.fetchNotifications)
  const markRead = useNotificationStore((s) => s.markRead)
  const incrementUnread = useNotificationStore((s) => s.incrementUnread)

  const handleWSMessage = useCallback(
    (data: unknown) => {
      const event = data as NotificationWSEvent
      if (event.type === 'notification_received') {
        incrementUnread()
      }
    },
    [incrementUnread],
  )

  useWebSocket({
    path: '/ws/status',
    onMessage: handleWSMessage,
  })

  useEffect(() => {
    void fetchNotifications()
  }, [fetchNotifications])

  return { notifications, unreadCount, loading, fetchNotifications, markRead }
}
