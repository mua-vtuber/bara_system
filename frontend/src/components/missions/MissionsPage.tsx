import { useState, useEffect, useCallback } from 'react'
import {
  listMissions,
  createMission,
  cancelMission,
  completeMission,
  type MissionResponse,
  type MissionCreateRequest,
} from '@/services/missions.api'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'

const STATUS_LABELS: Record<string, string> = {
  pending: '대기',
  warmup: '워밍업',
  active: '준비됨',
  posted: '게시됨',
  collecting: '수집 중',
  complete: '완료',
  cancelled: '취소',
}

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-gray-100 text-gray-800',
  warmup: 'bg-yellow-100 text-yellow-800',
  active: 'bg-blue-100 text-blue-800',
  posted: 'bg-indigo-100 text-indigo-800',
  collecting: 'bg-purple-100 text-purple-800',
  complete: 'bg-green-100 text-green-800',
  cancelled: 'bg-red-100 text-red-800',
}

export function MissionsPage() {
  const [missions, setMissions] = useState<MissionResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [filter, setFilter] = useState<string>('')

  const fetchMissions = useCallback(async () => {
    try {
      const res = await listMissions(50, 0, filter || undefined)
      setMissions(res.missions)
    } catch (err) {
      console.error('Failed to load missions:', err)
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => {
    void fetchMissions()
  }, [fetchMissions])

  const selected = missions.find((m) => m.id === selectedId) ?? null

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <LoadingSpinner />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl p-4">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">미션 관리</h2>
        <button
          onClick={() => setShowCreate(true)}
          className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700"
        >
          + 새 미션
        </button>
      </div>

      {/* Filter */}
      <div className="mb-4 flex gap-2">
        {['', 'pending', 'warmup', 'active', 'collecting', 'complete', 'cancelled'].map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`rounded-full px-3 py-1 text-xs ${
              filter === s
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {s ? STATUS_LABELS[s] || s : '전체'}
          </button>
        ))}
      </div>

      {/* Mission list */}
      {missions.length === 0 ? (
        <div className="py-12 text-center text-sm text-gray-400">
          미션이 없습니다
        </div>
      ) : (
        <div className="space-y-2">
          {missions.map((m) => (
            <MissionCard
              key={m.id}
              mission={m}
              isSelected={m.id === selectedId}
              onSelect={() => setSelectedId(m.id === selectedId ? null : m.id)}
              onCancel={async () => {
                await cancelMission(m.id)
                void fetchMissions()
              }}
              onComplete={async () => {
                await completeMission(m.id)
                void fetchMissions()
              }}
            />
          ))}
        </div>
      )}

      {/* Detail panel */}
      {selected && (
        <MissionDetail mission={selected} onClose={() => setSelectedId(null)} />
      )}

      {/* Create modal */}
      {showCreate && (
        <CreateMissionModal
          onClose={() => setShowCreate(false)}
          onCreate={async (data) => {
            await createMission(data)
            setShowCreate(false)
            void fetchMissions()
          }}
        />
      )}
    </div>
  )
}

// -- Sub-components -------------------------------------------------------

function MissionCard({
  mission: m,
  isSelected,
  onSelect,
  onCancel,
  onComplete,
}: {
  mission: MissionResponse
  isSelected: boolean
  onSelect: () => void
  onCancel: () => void
  onComplete: () => void
}) {
  const isTerminal = m.status === 'complete' || m.status === 'cancelled'

  return (
    <div
      className={`cursor-pointer rounded-lg border bg-white p-4 transition ${
        isSelected ? 'border-blue-400 ring-1 ring-blue-200' : 'border-gray-200 hover:border-gray-300'
      }`}
      onClick={onSelect}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[m.status] || 'bg-gray-100'}`}>
              {STATUS_LABELS[m.status] || m.status}
            </span>
            <span className="text-xs text-gray-400">#{m.id}</span>
            {m.urgency === 'immediate' && (
              <span className="text-xs text-red-500">긴급</span>
            )}
          </div>
          <h3 className="mt-1 text-sm font-medium text-gray-900">{m.topic}</h3>
          {m.question_hint && (
            <p className="mt-0.5 text-xs text-gray-500">{m.question_hint}</p>
          )}
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-500">
          {m.status === 'warmup' && (
            <span>워밍업 {m.warmup_count}/{m.warmup_target}</span>
          )}
          {(m.status === 'collecting' || m.status === 'complete') && (
            <span>응답 {m.collected_responses.length}개</span>
          )}
        </div>
      </div>
      {!isTerminal && (
        <div className="mt-2 flex gap-2" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={onCancel}
            className="rounded px-2 py-1 text-xs text-red-600 hover:bg-red-50"
          >
            취소
          </button>
          {(m.status === 'collecting' || m.status === 'posted') && (
            <button
              onClick={onComplete}
              className="rounded px-2 py-1 text-xs text-blue-600 hover:bg-blue-50"
            >
              수동 완료
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function MissionDetail({
  mission: m,
  onClose,
}: {
  mission: MissionResponse
  onClose: () => void
}) {
  return (
    <div className="mt-4 rounded-lg border border-gray-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-medium text-gray-900">미션 상세</h3>
        <button onClick={onClose} className="text-sm text-gray-400 hover:text-gray-600">
          닫기
        </button>
      </div>

      <dl className="space-y-2 text-sm">
        <div className="flex gap-2">
          <dt className="w-20 shrink-0 text-gray-500">주제</dt>
          <dd className="text-gray-900">{m.topic}</dd>
        </div>
        {m.question_hint && (
          <div className="flex gap-2">
            <dt className="w-20 shrink-0 text-gray-500">힌트</dt>
            <dd className="text-gray-900">{m.question_hint}</dd>
          </div>
        )}
        {m.post_platform && (
          <div className="flex gap-2">
            <dt className="w-20 shrink-0 text-gray-500">게시 위치</dt>
            <dd className="text-gray-900">{m.post_platform} / {m.post_id}</dd>
          </div>
        )}
      </dl>

      {/* Collected responses */}
      {m.collected_responses.length > 0 && (
        <div className="mt-4">
          <h4 className="mb-2 text-sm font-medium text-gray-700">
            수집된 응답 ({m.collected_responses.length}개)
          </h4>
          <div className="space-y-2">
            {m.collected_responses.map((r, i) => (
              <div key={i} className="rounded bg-gray-50 p-2 text-xs">
                <span className="font-medium text-gray-700">{r.author}</span>
                <p className="mt-0.5 text-gray-600">{r.content}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Summary */}
      {m.summary && (
        <div className="mt-4">
          <h4 className="mb-1 text-sm font-medium text-gray-700">AI 요약</h4>
          <div className="rounded bg-blue-50 p-3 text-sm text-gray-800 whitespace-pre-wrap">
            {m.summary}
          </div>
        </div>
      )}
    </div>
  )
}

function CreateMissionModal({
  onClose,
  onCreate,
}: {
  onClose: () => void
  onCreate: (data: MissionCreateRequest) => Promise<void>
}) {
  const [topic, setTopic] = useState('')
  const [hint, setHint] = useState('')
  const [urgency, setUrgency] = useState('normal')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async () => {
    if (!topic.trim()) return
    setSubmitting(true)
    try {
      await onCreate({ topic: topic.trim(), question_hint: hint.trim(), urgency })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-lg">
        <h3 className="mb-4 text-lg font-semibold">새 미션 만들기</h3>

        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">주제 *</label>
            <input
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
              placeholder="알아보고 싶은 주제"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">질문 힌트</label>
            <input
              value={hint}
              onChange={(e) => setHint(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
              placeholder="구체적인 질문 방향 (선택)"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">긴급도</label>
            <select
              value={urgency}
              onChange={(e) => setUrgency(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
            >
              <option value="patient">여유있게 (워밍업 길게)</option>
              <option value="normal">보통</option>
              <option value="immediate">즉시 (워밍업 없이)</option>
            </select>
          </div>
        </div>

        <div className="mt-4 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded px-4 py-2 text-sm text-gray-600 hover:bg-gray-100"
          >
            취소
          </button>
          <button
            onClick={handleSubmit}
            disabled={!topic.trim() || submitting}
            className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {submitting ? '생성 중...' : '미션 생성'}
          </button>
        </div>
      </div>
    </div>
  )
}
