import clsx from 'clsx'

interface ConnectionIndicatorProps {
  connected: boolean
  className?: string
  label?: boolean
}

export function ConnectionIndicator({
  connected,
  className,
  label = true,
}: ConnectionIndicatorProps) {
  return (
    <div className={clsx('inline-flex items-center gap-1.5', className)}>
      <span
        className={clsx(
          'inline-block h-2.5 w-2.5 rounded-full',
          connected ? 'bg-green-500' : 'bg-red-500',
        )}
      />
      {label && (
        <span className="text-xs text-gray-500">
          {connected ? '연결됨' : '연결 끊김'}
        </span>
      )}
    </div>
  )
}
