import { useState, type FormEvent } from 'react'
import { Button } from '@/components/common/Button'
import type { ActivityFilters as ActivityFiltersType } from '@/types'

interface ActivityFiltersProps {
  onFilter: (filters: ActivityFiltersType) => void
}

export function ActivityFilters({ onFilter }: ActivityFiltersProps) {
  const [platform, setPlatform] = useState('')
  const [type, setType] = useState('')
  const [status, setStatus] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    const filters: ActivityFiltersType = {}
    if (platform) filters.platform = platform
    if (type) filters.type = type
    if (status) filters.status = status
    if (startDate) filters.start = startDate
    if (endDate) filters.end = endDate
    onFilter(filters)
  }

  const handleReset = () => {
    setPlatform('')
    setType('')
    setStatus('')
    setStartDate('')
    setEndDate('')
    onFilter({})
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-wrap items-end gap-3 rounded-lg bg-white p-4 shadow-sm"
    >
      <div>
        <label className="mb-1 block text-xs font-medium text-gray-500">
          플랫폼
        </label>
        <select
          value={platform}
          onChange={(e) => setPlatform(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="">전체</option>
          <option value="botmadang">봇마당</option>
          <option value="moltbook">몰트북</option>
        </select>
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium text-gray-500">
          유형
        </label>
        <select
          value={type}
          onChange={(e) => setType(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="">전체</option>
          <option value="comment">댓글</option>
          <option value="post">글</option>
          <option value="reply">답글</option>
          <option value="upvote">추천</option>
          <option value="downvote">비추천</option>
          <option value="follow">팔로우</option>
        </select>
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium text-gray-500">
          상태
        </label>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="">전체</option>
          <option value="pending">대기</option>
          <option value="approved">승인</option>
          <option value="posted">완료</option>
          <option value="rejected">거부</option>
          <option value="failed">실패</option>
        </select>
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium text-gray-500">
          시작일
        </label>
        <input
          type="date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium text-gray-500">
          종료일
        </label>
        <input
          type="date"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      </div>

      <div className="flex gap-2">
        <Button type="submit" variant="primary" size="sm">
          검색
        </Button>
        <Button type="button" variant="secondary" size="sm" onClick={handleReset}>
          초기화
        </Button>
      </div>
    </form>
  )
}
