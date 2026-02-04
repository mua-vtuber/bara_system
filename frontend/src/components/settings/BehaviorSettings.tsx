import { useState, useEffect } from 'react'
import { useConfig } from '@/hooks/useConfig'
import { Button } from '@/components/common/Button'
import { Input } from '@/components/common/Input'
import { useToast } from '@/components/common/Toast'

export function BehaviorSettings() {
  const { config, updateConfig, loading } = useConfig()
  const { addToast } = useToast()

  const [keywords, setKeywords] = useState('')
  const [maxComments, setMaxComments] = useState(10)
  const [maxPosts, setMaxPosts] = useState(5)
  const [monitoringInterval, setMonitoringInterval] = useState(30)
  const [autoMode, setAutoMode] = useState(false)
  const [approvalMode, setApprovalMode] = useState(true)

  useEffect(() => {
    if (config) {
      setKeywords(config.behavior.interest_keywords.join(', '))
      setMaxComments(config.behavior.daily_limits.max_comments)
      setMaxPosts(config.behavior.daily_limits.max_posts)
      setMonitoringInterval(config.behavior.monitoring_interval_minutes)
      setAutoMode(config.behavior.auto_mode)
      setApprovalMode(config.behavior.approval_mode)
    }
  }, [config])

  const handleSave = async () => {
    if (!config) return
    try {
      await updateConfig('behavior', {
        behavior: {
          ...config.behavior,
          interest_keywords: keywords.split(',').map((k) => k.trim()).filter(Boolean),
          daily_limits: {
            ...config.behavior.daily_limits,
            max_comments: maxComments,
            max_posts: maxPosts,
          },
          monitoring_interval_minutes: monitoringInterval,
          auto_mode: autoMode,
          approval_mode: approvalMode,
        },
      } as never)
      addToast('success', '행동 설정이 저장되었습니다')
    } catch {
      addToast('error', '설정 저장에 실패했습니다')
    }
  }

  return (
    <div className="space-y-4">
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
        label="관심 키워드 (쉼표로 구분)"
        value={keywords}
        onChange={(e) => setKeywords(e.target.value)}
        placeholder="예: AI, 프로그래밍, 자동화"
      />

      <div className="grid grid-cols-3 gap-4">
        <Input
          label="일일 최대 댓글"
          type="number"
          value={String(maxComments)}
          onChange={(e) => setMaxComments(Number(e.target.value))}
        />
        <Input
          label="일일 최대 글"
          type="number"
          value={String(maxPosts)}
          onChange={(e) => setMaxPosts(Number(e.target.value))}
        />
        <Input
          label="모니터링 간격 (분)"
          type="number"
          value={String(monitoringInterval)}
          onChange={(e) => setMonitoringInterval(Number(e.target.value))}
        />
      </div>

      <Button
        variant="primary"
        size="sm"
        loading={loading}
        onClick={() => void handleSave()}
      >
        저장
      </Button>
    </div>
  )
}
