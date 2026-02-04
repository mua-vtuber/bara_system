interface StreamingIndicatorProps {
  content: string
}

export function StreamingIndicator({ content }: StreamingIndicatorProps) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[70%] rounded-lg border border-gray-100 bg-white px-4 py-2.5 shadow-sm">
        {content ? (
          <p className="whitespace-pre-wrap break-words text-sm text-gray-900">
            {content}
            <span className="inline-block h-4 w-1 animate-pulse bg-blue-600 ml-0.5 align-text-bottom" />
          </p>
        ) : (
          <div className="flex items-center gap-1">
            <span className="text-sm text-gray-500">봇이 입력 중</span>
            <span className="flex gap-0.5">
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400" style={{ animationDelay: '0ms' }} />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400" style={{ animationDelay: '150ms' }} />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400" style={{ animationDelay: '300ms' }} />
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
