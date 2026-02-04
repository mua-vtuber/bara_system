import { useState } from 'react'
import * as setupApi from '@/services/setup.api'
import { Button } from '@/components/common/Button'

interface StepCompleteProps {
  onComplete: () => void
}

export function StepComplete({ onComplete }: StepCompleteProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleComplete = async () => {
    setLoading(true)
    setError('')

    try {
      const res = await setupApi.completeSetup()
      if (res.success) {
        onComplete()
      } else {
        setError(res.message)
      }
    } catch {
      setError('설정 완료에 실패했습니다')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="text-center">
      <div className="mb-6">
        <svg
          className="mx-auto h-16 w-16 text-green-500"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
      </div>

      <h2 className="mb-2 text-lg font-semibold text-gray-900">
        설정 완료
      </h2>
      <p className="mb-6 text-sm text-gray-500">
        모든 설정이 완료되었습니다. 시작 버튼을 눌러 봇을 실행하세요.
      </p>

      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

      <Button
        variant="primary"
        size="lg"
        loading={loading}
        onClick={() => void handleComplete()}
        className="w-full"
      >
        시작하기
      </Button>
    </div>
  )
}
