import { useState, useEffect } from 'react'
import { useConfig } from '@/hooks/useConfig'
import { updateSettings } from '@/services/settings.api'

export function PersonalitySettings() {
  const { config, fetchConfig } = useConfig()
  const personality = config?.personality

  const [systemPrompt, setSystemPrompt] = useState('')
  const [interests, setInterests] = useState('')
  const [expertise, setExpertise] = useState('')
  const [traits, setTraits] = useState('')
  const [backstory, setBackstory] = useState('')
  const [style, setStyle] = useState('casual')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (personality) {
      setSystemPrompt(personality.system_prompt || '')
      setInterests((personality.interests || []).join(', '))
      setExpertise((personality.expertise || []).join(', '))
      setTraits((personality.traits || []).join(', '))
      setBackstory(personality.backstory || '')
      setStyle(personality.style || 'casual')
    }
  }, [personality])

  const handleSave = async () => {
    setSaving(true)
    setSaved(false)
    try {
      const splitTrim = (s: string) =>
        s.split(',').map((x) => x.trim()).filter(Boolean)

      await updateSettings('personality', {
        system_prompt: systemPrompt,
        interests: splitTrim(interests),
        expertise: splitTrim(expertise),
        traits: splitTrim(traits),
        backstory,
        style,
      })
      await fetchConfig()
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      console.error('Failed to save personality:', err)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="mb-1 block text-xs font-medium text-gray-600">
          시스템 프롬프트 (비어있으면 아래 설정으로 자동 생성)
        </label>
        <textarea
          value={systemPrompt}
          onChange={(e) => setSystemPrompt(e.target.value)}
          rows={4}
          className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
          placeholder="봇의 성격을 직접 정의하는 시스템 프롬프트..."
        />
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium text-gray-600">
          관심사 (쉼표로 구분)
        </label>
        <input
          value={interests}
          onChange={(e) => setInterests(e.target.value)}
          className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
          placeholder="AI, 프로그래밍, 기술, 게임"
        />
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium text-gray-600">
          전문 분야 (쉼표로 구분)
        </label>
        <input
          value={expertise}
          onChange={(e) => setExpertise(e.target.value)}
          className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
          placeholder="머신러닝, 웹개발"
        />
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium text-gray-600">
          성격 특성 (쉼표로 구분)
        </label>
        <input
          value={traits}
          onChange={(e) => setTraits(e.target.value)}
          className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
          placeholder="호기심이 많음, 친근함, 유머러스"
        />
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium text-gray-600">
          말투 스타일
        </label>
        <select
          value={style}
          onChange={(e) => setStyle(e.target.value)}
          className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
        >
          <option value="casual">캐주얼 (친근한 어투)</option>
          <option value="formal">포멀 (격식있는 어투)</option>
          <option value="technical">테크니컬 (기술적인 어투)</option>
        </select>
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium text-gray-600">
          배경 이야기
        </label>
        <textarea
          value={backstory}
          onChange={(e) => setBackstory(e.target.value)}
          rows={3}
          className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
          placeholder="봇의 배경 이야기... (선택사항)"
        />
      </div>

      <button
        onClick={handleSave}
        disabled={saving}
        className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {saving ? '저장 중...' : saved ? '저장됨!' : '저장'}
      </button>
    </div>
  )
}
