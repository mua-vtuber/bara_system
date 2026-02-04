import { useState, type FormEvent } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { Button } from '@/components/common/Button'
import { Input } from '@/components/common/Input'

export function LoginPage() {
  const { login, loading } = useAuth()
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')

    if (!password.trim()) {
      setError('비밀번호를 입력해주세요')
      return
    }

    const success = await login(password)
    if (!success) {
      setError('비밀번호가 올바르지 않습니다')
      setPassword('')
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-100">
      <div className="w-full max-w-sm rounded-lg bg-white p-8 shadow-md">
        <div className="mb-6 text-center">
          <h1 className="text-2xl font-bold text-gray-900">BARA System</h1>
          <p className="mt-1 text-sm text-gray-500">관리자 로그인</p>
        </div>

        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
          <Input
            type="password"
            label="비밀번호"
            placeholder="비밀번호를 입력하세요"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={error}
            autoFocus
          />

          <Button
            type="submit"
            variant="primary"
            size="lg"
            loading={loading}
            className="w-full"
          >
            로그인
          </Button>
        </form>
      </div>
    </div>
  )
}
