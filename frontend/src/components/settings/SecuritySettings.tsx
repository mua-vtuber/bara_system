import { useState, useEffect } from 'react'
import { useConfig } from '@/hooks/useConfig'
import { Button } from '@/components/common/Button'
import { Input } from '@/components/common/Input'
import { useToast } from '@/components/common/Toast'

export function SecuritySettings() {
  const { config, updateConfig, loading } = useConfig()
  const { addToast } = useToast()
  const [blockedKeywords, setBlockedKeywords] = useState('')
  const [blockedPatterns, setBlockedPatterns] = useState('')

  useEffect(() => {
    if (config) {
      setBlockedKeywords(config.security.blocked_keywords.join(', '))
      setBlockedPatterns(config.security.blocked_patterns.join('\n'))
    }
  }, [config])

  const handleSave = async () => {
    if (!config) return
    try {
      await updateConfig('security', {
        security: {
          blocked_keywords: blockedKeywords.split(',').map((k) => k.trim()).filter(Boolean),
          blocked_patterns: blockedPatterns.split('\n').map((p) => p.trim()).filter(Boolean),
        },
      } as never)
      addToast('success', '보안 설정이 저장되었습니다')
    } catch {
      addToast('error', '설정 저장에 실패했습니다')
    }
  }

  return (
    <div className="space-y-4">
      <Input
        label="차단 키워드 (쉼표로 구분)"
        value={blockedKeywords}
        onChange={(e) => setBlockedKeywords(e.target.value)}
        placeholder="예: 스팸, 광고"
      />

      <div>
        <label className="mb-1 block text-sm font-medium text-gray-700">
          차단 패턴 (줄별 정규식)
        </label>
        <textarea
          value={blockedPatterns}
          onChange={(e) => setBlockedPatterns(e.target.value)}
          rows={4}
          className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="정규식 패턴을 한 줄에 하나씩 입력"
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
