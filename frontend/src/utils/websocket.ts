/**
 * Reconnecting WebSocket wrapper with exponential backoff.
 *
 * Automatically reconnects when the connection drops, with delays
 * of 1s, 2s, 4s, 8s, ... up to a configurable maximum (default 30s).
 */

export type WSEventHandler = (data: unknown) => void

interface ReconnectingWSOptions {
  /** Maximum reconnect delay in milliseconds. Default: 30000 (30s). */
  maxDelay?: number
  /** Initial reconnect delay in milliseconds. Default: 1000 (1s). */
  initialDelay?: number
  /** Whether to automatically reconnect on close. Default: true. */
  autoReconnect?: boolean
}

export class ReconnectingWebSocket {
  private ws: WebSocket | null = null
  private url: string
  private reconnectDelay: number
  private readonly maxDelay: number
  private readonly initialDelay: number
  private autoReconnect: boolean
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private intentionalClose = false

  private onMessageHandler: WSEventHandler | null = null
  private onOpenHandler: (() => void) | null = null
  private onCloseHandler: ((code: number, reason: string) => void) | null = null
  private onErrorHandler: ((error: Event) => void) | null = null

  constructor(url: string, options: ReconnectingWSOptions = {}) {
    this.url = url
    this.initialDelay = options.initialDelay ?? 1000
    this.maxDelay = options.maxDelay ?? 30000
    this.reconnectDelay = this.initialDelay
    this.autoReconnect = options.autoReconnect ?? true
  }

  /** Set the handler for incoming messages (parsed JSON). */
  onMessage(handler: WSEventHandler): void {
    this.onMessageHandler = handler
  }

  /** Set the handler called when the connection opens. */
  onOpen(handler: () => void): void {
    this.onOpenHandler = handler
  }

  /** Set the handler called when the connection closes. */
  onClose(handler: (code: number, reason: string) => void): void {
    this.onCloseHandler = handler
  }

  /** Set the handler called on WebSocket errors. */
  onError(handler: (error: Event) => void): void {
    this.onErrorHandler = handler
  }

  /** Open the WebSocket connection. */
  connect(): void {
    this.intentionalClose = false
    this._connect()
  }

  /** Send a JSON-serialisable message. */
  send(data: unknown): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    }
  }

  /** Close the connection without reconnecting. */
  close(): void {
    this.intentionalClose = true
    this.autoReconnect = false
    this._clearReconnectTimer()
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  /** Return true if the underlying WebSocket is open. */
  get isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN
  }

  // -- Internal ------------------------------------------------------------

  private _connect(): void {
    try {
      this.ws = new WebSocket(this.url)
    } catch {
      this._scheduleReconnect()
      return
    }

    this.ws.onopen = () => {
      // Reset backoff on successful connection
      this.reconnectDelay = this.initialDelay
      this.onOpenHandler?.()
    }

    this.ws.onmessage = (event: MessageEvent) => {
      if (this.onMessageHandler) {
        try {
          const data: unknown = JSON.parse(event.data as string)
          this.onMessageHandler(data)
        } catch {
          // Non-JSON message; forward raw string
          this.onMessageHandler(event.data)
        }
      }
    }

    this.ws.onclose = (event: CloseEvent) => {
      this.onCloseHandler?.(event.code, event.reason)
      if (!this.intentionalClose && this.autoReconnect) {
        this._scheduleReconnect()
      }
    }

    this.ws.onerror = (event: Event) => {
      this.onErrorHandler?.(event)
    }
  }

  private _scheduleReconnect(): void {
    this._clearReconnectTimer()
    this.reconnectTimer = setTimeout(() => {
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxDelay)
      this._connect()
    }, this.reconnectDelay)
  }

  private _clearReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
  }
}
