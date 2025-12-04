import { useState, useEffect } from 'react'

export function useApiHealth() {
  const [status, setStatus] = useState<'connected' | 'disconnected' | 'unknown'>('unknown')

  useEffect(() => {
    const checkHealth = async () => {
      const apiBase = import.meta.env.VITE_API_BASE || ''
      try {
        // Try health endpoint first
        const healthUrl = `${apiBase}/api/health`
        const response = await fetch(healthUrl, { 
          method: 'GET',
          signal: AbortSignal.timeout(3000)
        })
        if (response.ok) {
          setStatus('connected')
          return
        }
      } catch {
        // Fallback to OPTIONS on netlist endpoint
        try {
          const netlistUrl = `${apiBase || ''}/api/netlist`
          const response = await fetch(netlistUrl, {
            method: 'OPTIONS',
            signal: AbortSignal.timeout(3000)
          })
          setStatus(response.ok ? 'connected' : 'disconnected')
        } catch {
          setStatus('unknown')
        }
      }
    }

    checkHealth()
    const interval = setInterval(checkHealth, 30000) // Check every 30s
    return () => clearInterval(interval)
  }, [])

  return status
}

