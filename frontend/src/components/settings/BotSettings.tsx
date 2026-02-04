import { useState, useEffect } from 'react'
import { useConfig } from '@/hooks/useConfig'
import { Button } from '@/components/common/Button'
import { Input } from '@/components/common/Input'
import { useToast } from '@/components/common/Toast'

export function BotSettings() {
  const { config, updateConfig, loading } = useConfig()
  const { addToast } = useToast()
  const [name, setName] = useState('')
  const [model, setModel] = useState('')

  useEffect(() => {
    if (config) {
      setName(config.bot.name)
      setModel(config.bot.model)
    }
  }, [config])

  const handleSave = async () => {
    try {
      await updateConfig('bot', {
        bot: { ...config!.bot, name, model },
      } as never)
      addToast('success', '봇 설정이 저장되었습니다')
    } catch {
      addToast('error', '설정 저장에 실패했습니다')
    }
  }

  return (
    <div className="space-y-4">
      <Input
        label="봇 이름"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="봇 이름"
      />
      <Input
        label="모델"
        value={model}
        onChange={(e) => setModel(e.target.value)}
        placeholder="모델 이름 (예: llama3)"
      />
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
