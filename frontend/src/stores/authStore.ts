import { create } from 'zustand'
import * as authApi from '@/services/auth.api'

interface AuthState {
  isLoggedIn: boolean
  isSetupComplete: boolean
  loading: boolean
  login: (password: string) => Promise<boolean>
  logout: () => Promise<void>
  checkStatus: () => Promise<void>
  setupPassword: (password: string) => Promise<boolean>
}

export const useAuthStore = create<AuthState>()((set) => ({
  isLoggedIn: false,
  isSetupComplete: false,
  loading: true,

  login: async (password: string): Promise<boolean> => {
    set({ loading: true })
    try {
      const res = await authApi.login(password)
      if (res.success) {
        set({ isLoggedIn: true, loading: false })
        return true
      }
      set({ loading: false })
      return false
    } catch {
      set({ loading: false })
      return false
    }
  },

  logout: async (): Promise<void> => {
    try {
      await authApi.logout()
    } finally {
      set({ isLoggedIn: false })
    }
  },

  checkStatus: async (): Promise<void> => {
    set({ loading: true })
    try {
      const res = await authApi.getStatus()
      set({
        isLoggedIn: res.authenticated,
        isSetupComplete: res.setup_complete,
        loading: false,
      })
    } catch {
      set({ isLoggedIn: false, isSetupComplete: false, loading: false })
    }
  },

  setupPassword: async (password: string): Promise<boolean> => {
    set({ loading: true })
    try {
      const res = await authApi.setupPassword(password)
      if (res.success) {
        set({ isSetupComplete: true, loading: false })
        return true
      }
      set({ loading: false })
      return false
    } catch {
      set({ loading: false })
      return false
    }
  },
}))
