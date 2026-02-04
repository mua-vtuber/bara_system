import { useState, useEffect } from 'react'
import { useConfig } from '@/hooks/useConfig'
import { Button } from '@/components/common/Button'
import { useToast } from '@/components/common/Toast'

export function VoiceSettings() {
  const { config, updateConfig, loading } = useConfig()
  const { addToast } = useToast()
  const [enabled, setEnabled] = useState(false)

  useEffect(() => {
    if (config) {
      setEnabled(config.voice.enabled)
    }
  }, [config])

  const handleSave = async () => {
    if (!config) return
    try {
      await updateConfig('voice', {
        voice: { ...config.voice, enabled },
      } as never)
      addToast('success', '음성 설정이 저장되었습니다')
    } catch {
      addToast('error', '설정 저장에 실패했습니다')
    }
  }

  return (
    <div className="space-y-4">
      <label className="flex items-center justify-between rounded-lg border border-gray-200 p-3">
        <div>
          <span className="text-sm font-medium text-gray-700">음성 인식</span>
          <p className="text-xs text-gray-400">
            음성 명령으로 봇을 제어합니다
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

      {enabled && (
        <div className="rounded-lg bg-gray-50 p-3 text-sm text-gray-600">
          <p>웨이크 워드 엔진: {config?.voice.wake_word_engine ?? '-'}</p>
          <p>STT 모델: {config?.voice.stt_model ?? '-'}</p>
          <p>언어: {config?.voice.language ?? '-'}</p>
        </div>
      )}

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
