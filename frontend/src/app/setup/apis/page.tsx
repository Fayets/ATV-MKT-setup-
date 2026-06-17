'use client'

import { ConnectionCard } from '@/features/conexiones/connection-card'
import { platformsForSetup } from '@/features/conexiones/connection-platforms'
import { API_BASE } from '@/shared/lib/backend-public-url'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useCallback, useEffect, useState } from 'react'

type ConnectionRow = {
  platform: string
  credentials: Record<string, string>
  last_sync_at: string | null
}

export default function SetupApisPage() {
  const router = useRouter()
  const [connections, setConnections] = useState<Record<string, ConnectionRow>>({})
  const [loading, setLoading] = useState(true)

  const fetchConnections = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/connections`)
      if (!res.ok) return
      const rows = (await res.json()) as Array<{
        platform: string
        credentials: Record<string, unknown>
        last_sync_at: string | null
      }>
      const map: Record<string, ConnectionRow> = {}
      rows.forEach((row) => {
        const creds: Record<string, string> = {}
        Object.entries(row.credentials || {}).forEach(([k, v]) => {
          creds[k] = v == null ? '' : String(v)
        })
        map[row.platform] = {
          platform: row.platform,
          credentials: creds,
          last_sync_at: row.last_sync_at,
        }
      })
      setConnections(map)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetch(`${API_BASE}/api/setup/status`)
      .then((r) => r.json())
      .then((data: { configured?: boolean }) => {
        if (!data.configured) router.replace('/onboarding')
        else fetchConnections()
      })
      .catch(() => router.replace('/onboarding'))
  }, [router, fetchConnections])

  const saveConnection = async (platform: string, credentials: Record<string, string>) => {
    const res = await fetch(`${API_BASE}/api/connections/${encodeURIComponent(platform)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ credentials }),
    })
    const raw = await res.json().catch(() => ({}))
    if (!res.ok) {
      const detail =
        typeof raw === 'object' && raw && 'detail' in raw
          ? String((raw as { detail: unknown }).detail)
          : res.statusText
      throw new Error(detail)
    }
    await fetchConnections()
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--bg)] text-[var(--text3)]">
        Cargando…
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[var(--bg)] px-4 py-10 sm:px-8">
      <div className="mx-auto max-w-7xl">
        <h1 className="text-xl font-semibold tracking-tight text-[var(--text)]">Configurar APIs</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--text2)]">
          Podés conectar ahora o más tarde desde Conexiones API. No es obligatorio completar todo.
        </p>

        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {platformsForSetup().map((p) => (
            <ConnectionCard
              key={p.key}
              platform={p}
              connection={connections[p.key]}
              cardLayout="setup"
              apiBase={API_BASE}
              onSave={(creds) => saveConnection(p.key, creds)}
            />
          ))}
        </div>

        <div className="mt-10 flex justify-end">
          <Link
            href="/login"
            className="rounded-lg bg-[var(--auth-cta-bg)] px-6 py-3 text-sm font-semibold uppercase tracking-wider text-[var(--auth-cta-text)] hover:opacity-90"
          >
            Ir al sistema
          </Link>
        </div>
      </div>
    </div>
  )
}
