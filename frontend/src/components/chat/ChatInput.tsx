import { useState, useCallback, type FormEvent, type KeyboardEvent } from 'react'
import { useSlashCommands } from '@/hooks/useSlashCommands'
import { SlashCommandMenu } from './SlashCommandMenu'
import { Button } from '@/components/common/Button'

interface ChatInputProps {
  onSend: (content: string) => void
  disabled?: boolean
}

export function ChatInput({ onSend, disabled = false }: ChatInputProps) {
  const [input, setInput] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const { filteredCommands, showSuggestions, filterCommands, executeCommand } =
    useSlashCommands()

  const handleInputChange = (value: string) => {
    setInput(value)
    filterCommands(value)
    setSelectedIndex(0)
  }

  const handleSubmit = useCallback(
    async (e?: FormEvent) => {
      e?.preventDefault()
      const trimmed = input.trim()
      if (!trimmed) return

      if (trimmed.startsWith('/')) {
        const result = await executeCommand(trimmed)
        if (result.success) {
          onSend(`[명령 결과] ${result.result ?? '성공'}`)
        } else {
          onSend(`[명령 오류] ${result.error ?? '실패'}`)
        }
      } else {
        onSend(trimmed)
      }

      setInput('')
      filterCommands('')
    },
    [input, onSend, executeCommand, filterCommands],
  )

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (showSuggestions && filteredCommands.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIndex((prev) =>
          prev < filteredCommands.length - 1 ? prev + 1 : 0,
        )
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIndex((prev) =>
          prev > 0 ? prev - 1 : filteredCommands.length - 1,
        )
        return
      }
      if (e.key === 'Tab' || e.key === 'Enter') {
        e.preventDefault()
        const cmd = filteredCommands[selectedIndex]
        if (cmd) {
          setInput(cmd.name + ' ')
          filterCommands('')
        }
        return
      }
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void handleSubmit()
    }
  }

  const handleCommandSelect = (command: string) => {
    setInput(command + ' ')
    filterCommands('')
  }

  return (
    <form
      onSubmit={(e) => void handleSubmit(e)}
      className="relative border-t border-gray-200 bg-white p-4"
    >
      <SlashCommandMenu
        commands={filteredCommands}
        visible={showSuggestions}
        selectedIndex={selectedIndex}
        onSelect={handleCommandSelect}
      />
      <div className="flex gap-2">
        <textarea
          value={input}
          onChange={(e) => handleInputChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="메시지를 입력하세요... (/ 로 명령어 사용)"
          disabled={disabled}
          rows={1}
          className="flex-1 resize-none rounded-lg border border-gray-300 px-4 py-2.5 text-sm text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <Button
          type="submit"
          variant="primary"
          disabled={disabled || !input.trim()}
        >
          전송
        </Button>
      </div>
    </form>
  )
}
