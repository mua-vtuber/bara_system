import { useState, useEffect } from 'react'
import { useConfig } from '@/hooks/useConfig'
import { Button } from '@/components/common/Button'
import { useToast } from '@/components/common/Toast'

interface PlatformToggle {
  name: string
  label: string
  enabled: boolean
}

export function PlatformSettings() {
  const { config, updateConfig, loading } = useConfig()
  const { addToast } = useToast()
  const [platforms, setPlatforms] = useState<PlatformToggle[]>([])

  useEffect(() => {
    if (config) {
      setPlatforms([
        { name: 'moltbook', label: '몰트북', enabled: config.platforms.moltbook.enabled },
        { name: 'botmadang', label: '봇마당', enabled: config.platforms.botmadang.enabled },
      ])
    }
  }, [config])

  const toggle = (name: string) => {
    setPlatforms((prev) =>
      prev.map((p) => (p.name === name ? { ...p, enabled: !p.enabled } : p)),
    )
  }

  const handleSave = async () => {
    if (!config) return
    try {
      const updated = { ...config.platforms }
      for (const p of platforms) {
        if (p.name in updated) {
          (updated as Record<string, { enabled: boolean; base_url: string }>)[p.name] = {
            ...(updated as Record<string, { enabled: boolean; base_url: string }>)[p.name],
            enabled: p.enabled,
          }
        }
      }
      await updateConfig('platforms', { platforms: updated } as never)
      addToast('success', '플랫폼 설정이 저장되었습니다')
    } catch {
      addToast('error', '설정 저장에 실패했습니다')
    }
  }

  return (
    <div className="space-y-4">
      {platforms.map((platform) => (
        <label
          key={platform.name}
          className="flex items-center justify-between rounded-lg border border-gray-200 p-3"
        >
          <span className="text-sm font-medium text-gray-700">
            {platform.label}
          </span>
          <button
            type="button"
            onClick={() => toggle(platform.name)}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              platform.enabled ? 'bg-blue-600' : 'bg-gray-300'
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                platform.enabled ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </label>
      ))}
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
