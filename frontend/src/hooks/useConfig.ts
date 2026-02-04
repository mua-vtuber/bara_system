import { useConfigStore } from '@/stores/configStore'

/**
 * Config hook wrapping the config store.
 */
export function useConfig() {
  const config = useConfigStore((s) => s.config)
  const loading = useConfigStore((s) => s.loading)
  const error = useConfigStore((s) => s.error)
  const fetchConfig = useConfigStore((s) => s.fetchConfig)
  const updateConfig = useConfigStore((s) => s.updateConfig)

  return { config, loading, error, fetchConfig, updateConfig }
}
