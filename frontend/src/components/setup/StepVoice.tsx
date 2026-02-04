import { useState, type FormEvent } from 'react'
import * as setupApi from '@/services/setup.api'
import { Button } from '@/components/common/Button'

interface StepVoiceProps {
  onNext: () => void
}

export function StepVoice({ onNext }: StepVoiceProps) {
  const [enabled, setEnabled] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setSaving(true)

    try {
      await setupApi.setVoice({
        enabled,
        wake_word_engine: 'porcupine',
        stt_model: 'whisper-small',
      })
      onNext()
    } catch {
      setError('음성 설정 저장에 실패했습니다')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <h2 className="mb-2 text-lg font-semibold text-gray-900">음성 설정</h2>
      <p className="mb-6 text-sm text-gray-500">
        음성 인식 기능을 사용하시겠습니까?
      </p>

      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
        <label className="flex items-center justify-between rounded-lg border border-gray-200 p-4">
          <div>
            <span className="text-sm font-medium text-gray-700">
              음성 인식 활성화
            </span>
            <p className="text-xs text-gray-400">
              음성 명령으로 봇을 제어할 수 있습니다
            </p>
          </div>
          <button
            type="button"
            onClick={() => setEnabled(!enabled)}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              enabled ? 'bg-blue-600' : 'bg-gray-300'
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                enabled ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </label>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <Button type="submit" variant="primary" loading={saving} className="w-full">
          다음
        </Button>
      </form>
    </div>
  )
}
