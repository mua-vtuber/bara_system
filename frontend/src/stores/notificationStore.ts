import { create } from 'zustand'
import * as notificationsApi from '@/services/notifications.api'
import type { NotificationLog } from '@/types'

interface NotificationState {
  notifications: NotificationLog[]
  unreadCount: number
  loading: boolean
  fetchNotifications: () => Promise<void>
  markRead: (id: number) => Promise<void>
  incrementUnread: () => void
}

export const useNotificationStore = create<NotificationState>()((set) => ({
  notifications: [],
  unreadCount: 0,
  loading: false,

  fetchNotifications: async (): Promise<void> => {
    set({ loading: true })
    try {
      const res = await notificationsApi.getNotifications()
      const unreadCount = res.items.filter((n) => !n.is_read).length
      set({ notifications: res.items, unreadCount, loading: false })
    } catch {
      set({ loading: false })
    }
  },

  markRead: async (id: number): Promise<void> => {
    try {
      await notificationsApi.markRead(id)
      set((state) => ({
        notifications: state.notifications.map((n) =>
          n.id === id ? { ...n, is_read: true } : n,
        ),
        unreadCount: Math.max(0, state.unreadCount - 1),
      }))
    } catch {
      // Silently fail; next fetch will reconcile
    }
  },

  incrementUnread: (): void => {
    set((state) => ({ unreadCount: state.unreadCount + 1 }))
  },
}))
