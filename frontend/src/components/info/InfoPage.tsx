import { useEffect, useState, useCallback } from 'react'
import * as infoApi from '@/services/info.api'
import { InfoFilters } from './InfoFilters'
import { InfoList } from './InfoList'
import { InfoDetail } from './InfoDetail'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import type { CollectedInfo, CollectedInfoFilters } from '@/types'

export function InfoPage() {
  const [items, setItems] = useState<CollectedInfo[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedInfo, setSelectedInfo] = useState<CollectedInfo | null>(null)

  const fetchItems = useCallback(async (filters: CollectedInfoFilters = {}) => {
    setLoading(true)
    try {
      const res = await infoApi.getCollectedInfo(filters)
      setItems(res.items)
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchCategories = useCallback(async () => {
    try {
      const res = await infoApi.getCategories()
      setCategories(res.categories)
    } catch {
      // silent
    }
  }, [])

  useEffect(() => {
    void fetchItems()
    void fetchCategories()
  }, [fetchItems, fetchCategories])

  const handleFilter = useCallback(
    (filters: CollectedInfoFilters) => {
      void fetchItems(filters)
    },
    [fetchItems],
  )

  const handleToggleBookmark = useCallback(
    async (id: number) => {
      try {
        const res = await infoApi.toggleBookmark(id)
        setItems((prev) =>
          prev.map((item) =>
            item.id === id ? { ...item, bookmarked: res.bookmarked } : item,
          ),
        )
      } catch {
        // silent
      }
    },
    [],
  )

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <InfoFilters categories={categories} onFilter={handleFilter} />

      {loading ? (
        <div className="flex flex-1 items-center justify-center">
          <LoadingSpinner />
        </div>
      ) : (
        <InfoList
          items={items}
          onSelect={setSelectedInfo}
          onToggleBookmark={(id) => void handleToggleBookmark(id)}
        />
      )}

      <InfoDetail
        info={selectedInfo}
        onClose={() => setSelectedInfo(null)}
      />
    </div>
  )
}
