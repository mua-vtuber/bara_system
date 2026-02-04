import { fetchApi } from './api'
import type { BackupExportResponse, BackupImportResponse } from '@/types'

/** Create a full backup of the database and config. */
export function exportBackup(): Promise<BackupExportResponse> {
  return fetchApi<BackupExportResponse>('/api/backup/export', {
    method: 'POST',
  })
}

/** Import a backup from a JSON object. */
export function importBackup(data: Record<string, unknown>): Promise<BackupImportResponse> {
  return fetchApi<BackupImportResponse>('/api/backup/import', {
    method: 'POST',
    body: data,
  })
}
