import { useCallback, useEffect, useRef, useState } from 'react'
import { ReconnectingWebSocket } from '@/utils/websocket'

interface UseWebSocketOptions {
  /** WebSocket path, e.g. '/ws/chat'. Appended to host automatically. */
  path: string
  /** Called when a parsed JSON message is received. */
  onMessage?: (data: unknown) => void
  /** Whether to connect immediately. Default: true. */
  enabled?: boolean
}

interface UseWebSocketReturn {
  isConnected: boolean
  send: (data: unknown) => void
  lastMessage: unknown
}

/**
 * React hook for managing a ReconnectingWebSocket connection.
 * Automatically connects on mount and disconnects on unmount.
 */
export function useWebSocket({
  path,
  onMessage,
  enabled = true,
}: UseWebSocketOptions): UseWebSocketReturn {
  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<unknown>(null)
  const wsRef = useRef<ReconnectingWebSocket | null>(null)
  const onMessageRef = useRef(onMessage)

  // Keep onMessage ref fresh without triggering reconnect
  onMessageRef.current = onMessage

  const send = useCallback((data: unknown) => {
    wsRef.current?.send(data)
  }, [])

  useEffect(() => {
    if (!enabled) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}${path}`

    const ws = new ReconnectingWebSocket(url)
    wsRef.current = ws

    ws.onOpen(() => {
      setIsConnected(true)
    })

    ws.onClose(() => {
      setIsConnected(false)
    })

    ws.onMessage((data: unknown) => {
      setLastMessage(data)
      onMessageRef.current?.(data)
    })

    ws.connect()

    return () => {
      ws.close()
      wsRef.current = null
      setIsConnected(false)
    }
  }, [path, enabled])

  return { isConnected, send, lastMessage }
}
