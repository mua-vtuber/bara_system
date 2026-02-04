import { useState, useRef } from 'react'
import * as backupApi from '@/services/backup.api'
import { Button } from '@/components/common/Button'
import { useToast } from '@/components/common/Toast'

export function DataManagement() {
  const { addToast } = useToast()
  const [exporting, setExporting] = useState(false)
  const [importing, setImporting] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleExport = async () => {
    setExporting(true)
    try {
      const res = await backupApi.exportBackup()
      const blob = new Blob([JSON.stringify(res.data, null, 2)], {
        type: 'application/json',
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = res.filename || 'bara-backup.json'
      a.click()
      URL.revokeObjectURL(url)
      addToast('success', '백업 파일이 다운로드되었습니다')
    } catch {
      addToast('error', '백업 내보내기에 실패했습니다')
    } finally {
      setExporting(false)
    }
  }

  const handleImport = async (file: File) => {
    setImporting(true)
    try {
      const text = await file.text()
      const data = JSON.parse(text) as Record<string, unknown>
      await backupApi.importBackup(data)
      addToast('success', '백업이 복구되었습니다')
    } catch {
      addToast('error', '백업 가져오기에 실패했습니다')
    } finally {
      setImporting(false)
    }
  }

  const handleFileSelect = () => {
    fileInputRef.current?.click()
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      void handleImport(file)
    }
    // Reset so the same file can be selected again
    e.target.value = ''
  }

  const handleEmergencyStop = () => {
    // This will be connected to a bot stop endpoint
    addToast('warning', '긴급 정지가 요청되었습니다')
  }

  return (
    <div className="space-y-6">
      {/* Backup / Restore */}
      <div>
        <h4 className="mb-3 text-sm font-medium text-gray-700">
          백업 / 복구
        </h4>
        <div className="flex gap-3">
          <Button
            variant="secondary"
            size="sm"
            loading={exporting}
            onClick={() => void handleExport()}
          >
            백업 내보내기
          </Button>
          <Button
            variant="secondary"
            size="sm"
            loading={importing}
            onClick={handleFileSelect}
          >
            백업 가져오기
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            onChange={handleFileChange}
            className="hidden"
          />
        </div>
      </div>

      {/* Emergency stop */}
      <div>
        <h4 className="mb-3 text-sm font-medium text-gray-700">긴급 제어</h4>
        <Button variant="danger" size="sm" onClick={handleEmergencyStop}>
          긴급 정지
        </Button>
        <p className="mt-1 text-xs text-gray-400">
          모든 봇 활동을 즉시 중지합니다
        </p>
      </div>
    </div>
  )
}
