import { useState, type FormEvent } from 'react'
import * as setupApi from '@/services/setup.api'
import { Button } from '@/components/common/Button'
import { Input } from '@/components/common/Input'

interface StepBehaviorProps {
  onNext: () => void
}

export function StepBehavior({ onNext }: StepBehaviorProps) {
  const [autoMode, setAutoMode] = useState(false)
  const [approvalMode, setApprovalMode] = useState(true)
  const [keywords, setKeywords] = useState('')
  const [monitoringInterval, setMonitoringInterval] = useState(30)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setSaving(true)

    try {
      await setupApi.setBehavior({
        auto_mode: autoMode,
        approval_mode: approvalMode,
        interest_keywords: keywords.split(',').map((k) => k.trim()).filter(Boolean),
        monitoring_interval_minutes: monitoringInterval,
      })
      onNext()
    } catch {
      setError('행동 설정 저장에 실패했습니다')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <h2 className="mb-2 text-lg font-semibold text-gray-900">행동 설정</h2>
      <p className="mb-6 text-sm text-gray-500">
        봇의 자동 활동 방식을 설정하세요
      </p>

      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
        <div className="flex gap-4">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={autoMode}
              onChange={(e) => setAutoMode(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-sm text-gray-700">자동 모드</span>
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={approvalMode}
              onChange={(e) => setApprovalMode(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-sm text-gray-700">승인 모드</span>
          </label>
        </div>

        <Input
          label="관심 키워드 (쉼표 구분)"
          value={keywords}
          onChange={(e) => setKeywords(e.target.value)}
          placeholder="예: AI, 프로그래밍, 자동화"
        />

        <Input
          label="모니터링 간격 (분)"
          type="number"
          value={String(monitoringInterval)}
          onChange={(e) => setMonitoringInterval(Number(e.target.value))}
        />

        {error && <p className="text-sm text-red-600">{error}</p>}

        <Button type="submit" variant="primary" loading={saving} className="w-full">
          다음
        </Button>
      </form>
    </div>
  )
}
