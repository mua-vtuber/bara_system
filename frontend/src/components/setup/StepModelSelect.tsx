import { useEffect, useState } from 'react'
import * as setupApi from '@/services/setup.api'
import { Button } from '@/components/common/Button'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import clsx from 'clsx'
import type { ModelInfo } from '@/types'

interface StepModelSelectProps {
  onNext: () => void
}

export function StepModelSelect({ onNext }: StepModelSelectProps) {
  const [models, setModels] = useState<ModelInfo[]>([])
  const [selected, setSelected] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const fetchModels = async () => {
      try {
        const res = await setupApi.getModels()
        setModels(res.models)
        if (res.models.length > 0) {
          setSelected(res.models[0].name)
        }
      } catch {
        // silent
      } finally {
        setLoading(false)
      }
    }
    void fetchModels()
  }, [])

  const handleNext = async () => {
    if (!selected) return
    setSaving(true)
    try {
      await setupApi.setModel(selected)
      onNext()
    } catch {
      // silent
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <LoadingSpinner />
      </div>
    )
  }

  return (
    <div>
      <h2 className="mb-2 text-lg font-semibold text-gray-900">모델 선택</h2>
      <p className="mb-6 text-sm text-gray-500">
        사용할 AI 모델을 선택하세요
      </p>

      {models.length === 0 ? (
        <p className="text-sm text-gray-400">
          사용 가능한 모델이 없습니다. Ollama에 모델을 설치해주세요.
        </p>
      ) : (
        <div className="space-y-2">
          {models.map((model) => (
            <button
              key={model.name}
              onClick={() => setSelected(model.name)}
              className={clsx(
                'flex w-full items-center justify-between rounded-lg border p-3 text-left transition-colors',
                selected === model.name
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-200 hover:bg-gray-50',
              )}
            >
              <span className="text-sm font-medium text-gray-900">
                {model.name}
              </span>
              {model.size && (
                <span className="text-xs text-gray-400">
                  {(model.size / 1e9).toFixed(1)} GB
                </span>
              )}
            </button>
          ))}
        </div>
      )}

      <Button
        variant="primary"
        className="mt-6 w-full"
        disabled={!selected}
        loading={saving}
        onClick={() => void handleNext()}
      >
        다음
      </Button>
    </div>
  )
}
