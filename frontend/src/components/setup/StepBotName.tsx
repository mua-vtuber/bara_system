import { useState, type FormEvent } from 'react'
import * as setupApi from '@/services/setup.api'
import { Button } from '@/components/common/Button'
import { Input } from '@/components/common/Input'

interface StepBotNameProps {
  onNext: () => void
}

export function StepBotName({ onNext }: StepBotNameProps) {
  const [name, setName] = useState('BARA')
  const [ownerName, setOwnerName] = useState('')
  const [wakeWords, setWakeWords] = useState('바라')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')

    if (!name.trim()) {
      setError('봇 이름을 입력해주세요')
      return
    }

    setSaving(true)
    try {
      await setupApi.setBotConfig({
        name: name.trim(),
        owner_name: ownerName.trim(),
        wake_words: wakeWords.split(',').map((w) => w.trim()).filter(Boolean),
      })
      onNext()
    } catch {
      setError('설정 저장에 실패했습니다')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <h2 className="mb-2 text-lg font-semibold text-gray-900">봇 설정</h2>
      <p className="mb-6 text-sm text-gray-500">
        봇의 이름과 기본 정보를 설정하세요
      </p>

      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
        <Input
          label="봇 이름"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="봇 이름"
          error={error}
          autoFocus
        />
        <Input
          label="운영자 이름"
          value={ownerName}
          onChange={(e) => setOwnerName(e.target.value)}
          placeholder="운영자 이름 (선택)"
        />
        <Input
          label="웨이크 워드 (쉼표 구분)"
          value={wakeWords}
          onChange={(e) => setWakeWords(e.target.value)}
          placeholder="예: 바라, BARA"
        />
        <Button type="submit" variant="primary" loading={saving} className="w-full">
          다음
        </Button>
      </form>
    </div>
  )
}
