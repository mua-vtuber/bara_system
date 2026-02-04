import { useState, type FormEvent } from 'react'
import * as setupApi from '@/services/setup.api'
import { Button } from '@/components/common/Button'
import { Input } from '@/components/common/Input'

interface StepPlatformsProps {
  onNext: () => void
}

type PlatformMode = 'register' | 'manual'

interface PlatformState {
  enabled: boolean
  mode: PlatformMode
  api_key: string
  description: string
  registered: boolean
  registering: boolean
  registerMessage: string
}

const INITIAL_STATE: PlatformState = {
  enabled: false,
  mode: 'register',
  api_key: '',
  description: '',
  registered: false,
  registering: false,
  registerMessage: '',
}

function PlatformSection({
  label,
  state,
  onChange,
  onRegister,
}: {
  label: string
  state: PlatformState
  onChange: (update: Partial<PlatformState>) => void
  onRegister: () => void
}) {
  return (
    <div className="rounded-lg border border-gray-200 p-4">
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={state.enabled}
          onChange={(e) => onChange({ enabled: e.target.checked })}
          className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
        />
        <span className="text-sm font-medium text-gray-700">{label}</span>
        {state.registered && (
          <span className="rounded bg-green-100 px-2 py-0.5 text-xs text-green-700">
            가입 완료
          </span>
        )}
      </label>

      {state.enabled && !state.registered && (
        <div className="mt-3 space-y-3">
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => onChange({ mode: 'register' })}
              className={`rounded px-3 py-1 text-xs ${
                state.mode === 'register'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-600'
              }`}
            >
              새로 가입
            </button>
            <button
              type="button"
              onClick={() => onChange({ mode: 'manual' })}
              className={`rounded px-3 py-1 text-xs ${
                state.mode === 'manual'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-600'
              }`}
            >
              API 키 입력
            </button>
          </div>

          {state.mode === 'register' ? (
            <div className="space-y-2">
              <Input
                label="봇 소개 (선택)"
                value={state.description}
                onChange={(e) => onChange({ description: e.target.value })}
                placeholder="이 봇은 어떤 봇인지 간단히 소개..."
              />
              <button
                type="button"
                onClick={onRegister}
                disabled={state.registering}
                className="rounded bg-green-600 px-4 py-2 text-sm text-white hover:bg-green-700 disabled:opacity-50"
              >
                {state.registering ? '가입 중...' : `${label}에 가입하기`}
              </button>
              {state.registerMessage && (
                <p className={`text-xs ${
                  state.registerMessage.includes('실패') ? 'text-red-600' : 'text-green-600'
                }`}>
                  {state.registerMessage}
                </p>
              )}
            </div>
          ) : (
            <Input
              label="API 키"
              type="password"
              value={state.api_key}
              onChange={(e) => onChange({ api_key: e.target.value })}
              placeholder="API 키 입력"
            />
          )}
        </div>
      )}
    </div>
  )
}

export function StepPlatforms({ onNext }: StepPlatformsProps) {
  const [moltbook, setMoltbook] = useState<PlatformState>({ ...INITIAL_STATE })
  const [botmadang, setBotmadang] = useState<PlatformState>({ ...INITIAL_STATE })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const updateMoltbook = (update: Partial<PlatformState>) =>
    setMoltbook((prev) => ({ ...prev, ...update }))
  const updateBotmadang = (update: Partial<PlatformState>) =>
    setBotmadang((prev) => ({ ...prev, ...update }))

  const handleRegister = async (
    platform: string,
    state: PlatformState,
    update: (u: Partial<PlatformState>) => void,
  ) => {
    update({ registering: true, registerMessage: '' })
    try {
      const res = await setupApi.registerOnPlatform(platform, state.description)
      if (res.success) {
        update({
          registered: true,
          api_key: res.api_key || '',
          registerMessage: res.message,
          registering: false,
        })
      } else {
        update({ registerMessage: res.message || '가입 실패', registering: false })
      }
    } catch {
      update({ registerMessage: '가입 요청 실패', registering: false })
    }
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setSaving(true)

    try {
      const res = await setupApi.setPlatforms({
        moltbook: {
          enabled: moltbook.enabled,
          api_key: moltbook.mode === 'manual' ? moltbook.api_key : '',
        },
        botmadang: {
          enabled: botmadang.enabled,
          api_key: botmadang.mode === 'manual' ? botmadang.api_key : '',
        },
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
        사용할 플랫폼을 선택하세요. 새로 가입하거나 기존 API 키를 입력할 수 있습니다.
      </p>

      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-6">
        <PlatformSection
          label="몰트북"

          state={moltbook}
          onChange={updateMoltbook}
          onRegister={() => void handleRegister('moltbook', moltbook, updateMoltbook)}
        />

        <PlatformSection
          label="봇마당"
          state={botmadang}
          onChange={updateBotmadang}
          onRegister={() => void handleRegister('botmadang', botmadang, updateBotmadang)}
        />

        {error && <p className="text-sm text-red-600">{error}</p>}

        <Button type="submit" variant="primary" loading={saving} className="w-full">
          다음
        </Button>
      </form>
    </div>
  )
}
