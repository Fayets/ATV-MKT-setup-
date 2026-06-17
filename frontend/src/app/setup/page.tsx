'use client'

import { API_BASE } from '@/shared/lib/backend-public-url'
import { useRouter } from 'next/navigation'
import { FormEvent, useState } from 'react'

const INPUT_CLASS =
  'w-full rounded-lg border border-[var(--border2)] bg-[var(--bg3)] px-4 py-3 font-mono text-sm text-[var(--auth-detail)] outline-none transition-all placeholder:text-[var(--text3)] focus:border-[var(--auth-detail)] focus:shadow-[0_0_0_3px_var(--auth-focus-ring)]'

const CTA_CLASS =
  'w-full rounded-lg bg-[var(--auth-cta-bg)] px-4 py-3 text-sm font-semibold uppercase tracking-wider text-[var(--auth-cta-text)] transition-all hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50'

export default function SetupDatabasePage() {
  const router = useRouter()
  const [connectionString, setConnectionString] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState('')

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setStatus('loading')
    setMessage('')

    const res = await fetch(`${API_BASE}/api/setup/db-connect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ connection_string: connectionString.trim() }),
    })
    const data = (await res.json().catch(() => ({}))) as { success?: boolean; error?: string }

    if (!data.success) {
      setStatus('error')
      setMessage(data.error || 'No se pudo conectar a la base de datos.')
      return
    }

    setStatus('success')
    setMessage('Base de datos conectada. Redirigiendo…')
    if (typeof window !== 'undefined') {
      sessionStorage.removeItem('atvmkt-db-bootstrap-checked')
    }
    setTimeout(() => router.replace('/onboarding'), 600)
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--bg)] px-4">
      <div className="w-full max-w-lg rounded-xl border border-[var(--border)] bg-[var(--bg2)] p-8 shadow-[var(--shadow-sm)]">
        <h1 className="text-xl font-semibold tracking-tight text-[var(--text)]">ATV Setup</h1>
        <p className="mt-2 text-sm text-[var(--text2)]">
          Configurá la base de datos. Pegá la cadena de conexión PostgreSQL (por ejemplo la de Neon) y probá la conexión.
        </p>

        <form onSubmit={onSubmit} className="mt-8 space-y-6">
          <div>
            <label
              htmlFor="connection_string"
              className="mb-2 block text-[10px] font-semibold uppercase tracking-wider text-[var(--text3)]"
            >
              Connection string
            </label>
            <textarea
              id="connection_string"
              rows={4}
              required
              value={connectionString}
              onChange={(e) => setConnectionString(e.target.value)}
              placeholder="postgresql://usuario:contraseña@host...?sslmode=require"
              className={INPUT_CLASS}
            />
          </div>

          {message && (
            <p className={`text-sm ${status === 'success' ? 'text-[var(--green)]' : 'text-[var(--text2)]'}`}>
              {message}
            </p>
          )}

          <button type="submit" disabled={status === 'loading'} className={CTA_CLASS}>
            {status === 'loading' ? 'Conectando…' : 'Conectar'}
          </button>
        </form>
      </div>
    </div>
  )
}
