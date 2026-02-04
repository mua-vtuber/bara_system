import type { Activity } from '@/types'

interface DailySummaryProps {
  activities: Activity[]
}

export function DailySummary({ activities }: DailySummaryProps) {
  const today = new Date().toISOString().slice(0, 10)
  const todayActivities = activities.filter(
    (a) => a.timestamp.slice(0, 10) === today,
  )

  const commentCount = todayActivities.filter((a) => a.type === 'comment' || a.type === 'reply').length
  const postCount = todayActivities.filter((a) => a.type === 'post').length
  const upvoteCount = todayActivities.filter((a) => a.type === 'upvote').length
  const followCount = todayActivities.filter((a) => a.type === 'follow').length

  const parts: string[] = []
  if (commentCount > 0) parts.push(`댓글 ${commentCount}개`)
  if (postCount > 0) parts.push(`글 ${postCount}개`)
  if (upvoteCount > 0) parts.push(`추천 ${upvoteCount}개`)
  if (followCount > 0) parts.push(`팔로우 ${followCount}개`)

  const summary = parts.length > 0 ? parts.join(', ') : '활동 없음'

  return (
    <div className="rounded-lg bg-blue-50 px-4 py-3">
      <span className="text-sm font-medium text-blue-800">
        오늘: {summary}
      </span>
    </div>
  )
}
