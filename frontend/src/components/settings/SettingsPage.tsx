import { useState, useEffect } from 'react'
import { useConfig } from '@/hooks/useConfig'
import { BotSettings } from './BotSettings'
import { PlatformSettings } from './PlatformSettings'
import { BehaviorSettings } from './BehaviorSettings'
import { VoiceSettings } from './VoiceSettings'
import { SecuritySettings } from './SecuritySettings'
import { DataManagement } from './DataManagement'
import { PersonalitySettings } from './PersonalitySettings'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import clsx from 'clsx'

interface Section {
  id: string
  title: string
  component: React.FC
}

const SECTIONS: Section[] = [
  { id: 'bot', title: '봇 설정', component: BotSettings },
  { id: 'personality', title: '성격', component: PersonalitySettings },
  { id: 'platforms', title: '플랫폼', component: PlatformSettings },
  { id: 'behavior', title: '행동 설정', component: BehaviorSettings },
  { id: 'voice', title: '음성', component: VoiceSettings },
  { id: 'security', title: '보안', component: SecuritySettings },
  { id: 'data', title: '데이터 관리', component: DataManagement },
]

export function SettingsPage() {
  const { config, loading, fetchConfig } = useConfig()
  const [openSection, setOpenSection] = useState<string | null>('bot')

  useEffect(() => {
    void fetchConfig()
  }, [fetchConfig])

  if (loading && !config) {
    return (
      <div className="flex h-full items-center justify-center">
        <LoadingSpinner />
      </div>
    )
  }

  if (!config) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-gray-400">설정을 불러올 수 없습니다</p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl p-4">
      <div className="space-y-2">
        {SECTIONS.map((section) => {
          const isOpen = openSection === section.id
          const SectionComponent = section.component

          return (
            <div
              key={section.id}
              className="rounded-lg border border-gray-200 bg-white"
            >
              <button
                onClick={() =>
                  setOpenSection(isOpen ? null : section.id)
                }
                className="flex w-full items-center justify-between px-4 py-3 text-left"
              >
                <span className="text-sm font-medium text-gray-900">
                  {section.title}
                </span>
                <svg
                  className={clsx(
                    'h-5 w-5 text-gray-400 transition-transform',
                    isOpen && 'rotate-180',
                  )}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M19 9l-7 7-7-7"
                  />
                </svg>
              </button>

              {isOpen && (
                <div className="border-t border-gray-100 px-4 py-4">
                  <SectionComponent />
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
