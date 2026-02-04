import clsx from 'clsx'

interface SlashCommand {
  name: string
  description: string
  usage: string
}

interface SlashCommandMenuProps {
  commands: SlashCommand[]
  visible: boolean
  selectedIndex: number
  onSelect: (command: string) => void
}

export function SlashCommandMenu({
  commands,
  visible,
  selectedIndex,
  onSelect,
}: SlashCommandMenuProps) {
  if (!visible || commands.length === 0) return null

  return (
    <div className="absolute bottom-full left-0 mb-1 w-72 rounded-lg border border-gray-200 bg-white py-1 shadow-lg">
      {commands.map((cmd, idx) => (
        <button
          key={cmd.name}
          onClick={() => onSelect(cmd.name)}
          className={clsx(
            'flex w-full flex-col px-3 py-2 text-left transition-colors',
            idx === selectedIndex ? 'bg-blue-50' : 'hover:bg-gray-50',
          )}
        >
          <span className="text-sm font-medium text-blue-600">{cmd.name}</span>
          <span className="text-xs text-gray-500">{cmd.description}</span>
        </button>
      ))}
    </div>
  )
}
