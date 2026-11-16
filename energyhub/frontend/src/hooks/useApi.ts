import { useCallback, useEffect, useRef, useState } from 'react'

export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(Boolean(path))
  const [error, setError] = useState<string | null>(null)
  const requestId = useRef(0)

  const load = useCallback(async () => {
    if (!path) {
      setData(null)
      setLoading(false)
      setError(null)
      return
    }
    const id = ++requestId.current
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE ?? 'api'}${path}`)
      if (!response.ok) {
        let message = `Error ${response.status}`
        try {
          const body = await response.json()
          if (typeof body?.detail === 'string') message = body.detail
        } catch {
          // no-op
        }
        throw new Error(message)
      }
      const body = (await response.json()) as T
      if (id === requestId.current) setData(body)
    } catch (err) {
      if (id === requestId.current) setError(err instanceof Error ? err.message : 'Error desconocido')
    } finally {
      if (id === requestId.current) setLoading(false)
    }
  }, [path])

  useEffect(() => {
    void load()
  }, [load])

  return { data, loading, error, reload: load, setData }
}
