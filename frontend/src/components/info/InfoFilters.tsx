import { useState, type FormEvent } from 'react'
import { Button } from '@/components/common/Button'
import type { CollectedInfoFilters } from '@/types'

interface InfoFiltersProps {
  categories: string[]
  onFilter: (filters: CollectedInfoFilters) => void
}

export function InfoFilters({ categories, onFilter }: InfoFiltersProps) {
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [bookmarkedOnly, setBookmarkedOnly] = useState(false)

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    const filters: CollectedInfoFilters = {}
    if (query) filters.q = query
    if (category) filters.category = category
    if (bookmarkedOnly) filters.bookmarked = true
    onFilter(filters)
  }

  const handleReset = () => {
    setQuery('')
    setCategory('')
    setBookmarkedOnly(false)
    onFilter({})
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-wrap items-end gap-3 rounded-lg bg-white p-4 shadow-sm"
    >
      <div className="flex-1">
        <label className="mb-1 block text-xs font-medium text-gray-500">
          검색
        </label>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="키워드 검색..."
          className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium text-gray-500">
          카테고리
        </label>
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="">전체</option>
          {categories.map((cat) => (
            <option key={cat} value={cat}>
              {cat}
            </option>
          ))}
        </select>
      </div>

      <label className="flex items-center gap-2 pb-1">
        <input
          type="checkbox"
          checked={bookmarkedOnly}
          onChange={(e) => setBookmarkedOnly(e.target.checked)}
          className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
        />
        <span className="text-sm text-gray-600">북마크만</span>
      </label>

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
