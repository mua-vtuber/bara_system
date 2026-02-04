import { useState, type FormEvent } from 'react'
import * as setupApi from '@/services/setup.api'
import { Button } from '@/components/common/Button'
import { Input } from '@/components/common/Input'

interface StepPlatformsProps {
  onNext: () => void
}

interface PlatformForm {
  enabled: boolean
  api_key: string
}

export function StepPlatforms({ onNext }: StepPlatformsProps) {
  const [moltbook, setMoltbook] = useState<PlatformForm>({
    enabled: false,
    api_key: '',
  })
  const [botmadang, setBotmadang] = useState<PlatformForm>({
    enabled: false,
    api_key: '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setSaving(true)

    try {
      const res = await setupApi.setPlatforms({
        moltbook: { enabled: moltbook.enabled, api_key: moltbook.api_key },
        botmadang: { enabled: botmadang.enabled, api_key: botmadang.api_key },
      })
      if (res.success) {
        onNext()
      } else {
        setError(res.message)
      }
    } catch {
      setError('플랫폼 설정 저장에 실패했습니다')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <h2 className="mb-2 text-lg font-semibold text-gray-900">
        플랫폼 설정
      </h2>
      <p className="mb-6 text-sm text-gray-500">
        연동할 플랫폼을 설정하세요
      </p>

      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-6">
        {/* Moltbook */}
        <div className="rounded-lg border border-gray-200 p-4">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={moltbook.enabled}
              onChange={(e) =>
                setMoltbook((prev) => ({ ...prev, enabled: e.target.checked }))
              }
              className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-sm font-medium text-gray-700">몰트북</span>
          </label>
          {moltbook.enabled && (
            <div className="mt-3">
              <Input
                label="API 키"
                type="password"
                value={moltbook.api_key}
                onChange={(e) =>
                  setMoltbook((prev) => ({ ...prev, api_key: e.target.value }))
                }
                placeholder="API 키 입력"
              />
            </div>
          )}
        </div>

        {/* Botmadang */}
        <div className="rounded-lg border border-gray-200 p-4">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={botmadang.enabled}
              onChange={(e) =>
                setBotmadang((prev) => ({ ...prev, enabled: e.target.checked }))
              }
              className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-sm font-medium text-gray-700">봇마당</span>
          </label>
          {botmadang.enabled && (
            <div className="mt-3">
              <Input
                label="API 키"
                type="password"
                value={botmadang.api_key}
                onChange={(e) =>
                  setBotmadang((prev) => ({ ...prev, api_key: e.target.value }))
                }
                placeholder="API 키 입력"
              />
            </div>
          )}
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <Button type="submit" variant="primary" loading={saving} className="w-full">
          다음
        </Button>
      </form>
    </div>
  )
}
