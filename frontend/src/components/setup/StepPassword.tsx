import { useState, type FormEvent } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { Button } from '@/components/common/Button'
import { Input } from '@/components/common/Input'

interface StepPasswordProps {
  onNext: () => void
}

export function StepPassword({ onNext }: StepPasswordProps) {
  const { setupPassword, loading } = useAuth()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')

    if (password.length < 4) {
      setError('비밀번호는 4자 이상이어야 합니다')
      return
    }
    if (password !== confirm) {
      setError('비밀번호가 일치하지 않습니다')
      return
    }

    const success = await setupPassword(password)
    if (success) {
      onNext()
    } else {
      setError('비밀번호 설정에 실패했습니다')
    }
  }

  return (
    <div>
      <h2 className="mb-2 text-lg font-semibold text-gray-900">
        비밀번호 설정
      </h2>
      <p className="mb-6 text-sm text-gray-500">
        관리자 접근을 위한 비밀번호를 설정하세요
      </p>

      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
        <Input
          type="password"
          label="비밀번호"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="비밀번호 입력"
          autoFocus
        />
        <Input
          type="password"
          label="비밀번호 확인"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          placeholder="비밀번호 다시 입력"
          error={error}
        />
        <Button type="submit" variant="primary" loading={loading} className="w-full">
          다음
        </Button>
      </form>
    </div>
  )
}
