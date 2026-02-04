import { useCallback, useMemo, useState } from 'react'
import * as commandsApi from '@/services/commands.api'

interface SlashCommand {
  name: string
  description: string
  usage: string
}

const COMMANDS: SlashCommand[] = [
  {
    name: '/post',
    description: 'Create a new post on a platform',
    usage: '/post <platform> <content>',
  },
  {
    name: '/search',
    description: 'Search posts by keyword',
    usage: '/search <query>',
  },
  {
    name: '/status',
    description: 'Show current bot status',
    usage: '/status',
  },
  {
    name: '/stop',
    description: 'Stop the bot',
    usage: '/stop',
  },
]

interface UseSlashCommandsReturn {
  commands: SlashCommand[]
  filteredCommands: SlashCommand[]
  showSuggestions: boolean
  filterCommands: (input: string) => void
  executeCommand: (input: string) => Promise<{ success: boolean; result?: string; error?: string }>
}

/**
 * Slash commands hook for chat autocomplete.
 * Detects '/' prefix in input and provides filtered command suggestions.
 */
export function useSlashCommands(): UseSlashCommandsReturn {
  const [filter, setFilter] = useState('')
  const [showSuggestions, setShowSuggestions] = useState(false)

  const filteredCommands = useMemo(() => {
    if (!filter.startsWith('/')) return []
    const query = filter.toLowerCase()
    return COMMANDS.filter((cmd) => cmd.name.toLowerCase().startsWith(query))
  }, [filter])

  const filterCommands = useCallback((input: string) => {
    setFilter(input)
    setShowSuggestions(input.startsWith('/') && input.length > 0)
  }, [])

  const executeCommand = useCallback(
    async (
      input: string,
    ): Promise<{ success: boolean; result?: string; error?: string }> => {
      setShowSuggestions(false)

      const parts = input.trim().split(/\s+/)
      const command = parts[0]?.replace('/', '') ?? ''
      const args: Record<string, unknown> = {}

      // Parse simple positional args based on command
      if (command === 'post' && parts.length >= 3) {
        args['platform'] = parts[1]
        args['content'] = parts.slice(2).join(' ')
      } else if (command === 'search' && parts.length >= 2) {
        args['query'] = parts.slice(1).join(' ')
      }

      try {
        const res = await commandsApi.executeCommand(command, args)
        if (res.success) {
          return {
            success: true,
            result: res.result ? JSON.stringify(res.result) : 'Command executed',
          }
        }
        return { success: false, error: res.error ?? 'Command failed' }
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Command execution failed'
        return { success: false, error: message }
      }
    },
    [],
  )

  return {
    commands: COMMANDS,
    filteredCommands,
    showSuggestions,
    filterCommands,
    executeCommand,
  }
}
