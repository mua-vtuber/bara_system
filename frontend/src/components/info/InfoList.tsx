import { InfoCard } from './InfoCard'
import type { CollectedInfo } from '@/types'

interface InfoListProps {
  items: CollectedInfo[]
  onSelect: (info: CollectedInfo) => void
  onToggleBookmark: (id: number) => void
}

export function InfoList({ items, onSelect, onToggleBookmark }: InfoListProps) {
  if (items.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-sm text-gray-400">수집된 정보가 없습니다</p>
      </div>
    )
  }

  return (
    <div className="grid gap-4">
      {items.map((info) => (
        <InfoCard
          key={info.id}
          info={info}
          onSelect={onSelect}
          onToggleBookmark={onToggleBookmark}
        />
      ))}
    </div>
  )
}
