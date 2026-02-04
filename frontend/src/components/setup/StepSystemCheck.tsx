import { useEffect, useState } from 'react'
import * as setupApi from '@/services/setup.api'
import { Button } from '@/components/common/Button'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import type { SystemCheckItem } from '@/types'

interface StepSystemCheckProps {
  onNext: () => void
}

export function StepSystemCheck({ onNext }: StepSystemCheckProps) {
  const [checks, setChecks] = useState<SystemCheckItem[]>([])
  const [loading, setLoading] = useState(true)
  const [allPassed, setAllPassed] = useState(false)

  const runCheck = async () => {
    setLoading(true)
    try {
      const res = await setupApi.systemCheck()
      setChecks(res.checks)
      setAllPassed(res.checks.every((c) => c.passed))
    } catch {
      setChecks([{ name: '시스템 검사', passed: false, message: '검사 실행 실패' }])
      setAllPassed(false)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void runCheck()
  }, [])

  return (
    <div>
      <h2 className="mb-2 text-lg font-semibold text-gray-900">
        시스템 확인
      </h2>
      <p className="mb-6 text-sm text-gray-500">
        시스템 요구 사항을 확인합니다
      </p>

      {loading ? (
        <div className="flex items-center justify-center py-8">
          <LoadingSpinner />
        </div>
      ) : (
        <div className="space-y-3">
          {checks.map((check) => (
            <div
              key={check.name}
              className="flex items-center gap-3 rounded-lg border border-gray-200 p-3"
            >
              {check.passed ? (
                <svg className="h-5 w-5 text-green-500" viewBox="0 0 20 20" fill="currentColor">
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                    clipRule="evenodd"
                  />
                </svg>
              ) : (
                <svg className="h-5 w-5 text-red-500" viewBox="0 0 20 20" fill="currentColor">
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                    clipRule="evenodd"
                  />
                </svg>
              )}
              <div className="flex-1">
                <span className="text-sm font-medium text-gray-900">
                  {check.name}
                </span>
                <p className="text-xs text-gray-500">{check.message}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="mt-6 flex gap-3">
        {!allPassed && !loading && (
          <Button
            variant="secondary"
            onClick={() => void runCheck()}
          >
            다시 검사
          </Button>
        )}
        <Button
          variant="primary"
          onClick={onNext}
          disabled={!allPassed}
          className="flex-1"
        >
          다음
        </Button>
      </div>
    </div>
  )
}
