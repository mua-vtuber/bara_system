import { TimelineItem } from './TimelineItem'
import type { Activity } from '@/types'

interface TimelineProps {
  activities: Activity[]
  onSelect: (activity: Activity) => void
}

export function Timeline({ activities, onSelect }: TimelineProps) {
  if (activities.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-sm text-gray-400">활동 기록이 없습니다</p>
      </div>
    )
  }

  return (
    <div className="pl-2">
      {activities.map((activity) => (
        <TimelineItem
          key={activity.id}
          activity={activity}
          onSelect={onSelect}
        />
      ))}
    </div>
  )
}
