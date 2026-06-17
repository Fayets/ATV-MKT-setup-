'use client'

import { API_BASE } from '@/shared/lib/backend-public-url'
import Image from 'next/image'
import { useRouter } from 'next/navigation'
import { FormEvent, useEffect, useState } from 'react'

const LABEL_CLASS = 'mb-2 block text-[10px] font-semibold uppercase tracking-wider text-[var(--text3)]'
const INPUT_CLASS =
  'w-full rounded-lg border border-[var(--border2)] bg-[var(--bg3)] px-4 py-3 text-sm text-[var(--auth-detail)] outline-none transition-all placeholder:text-[var(--text3)] focus:border-[var(--auth-detail)] focus:shadow-[0_0_0_3px_var(--auth-focus-ring)]'
const CTA_CLASS =
  'w-full rounded-lg bg-[var(--auth-cta-bg)] px-4 py-3 text-sm font-semibold uppercase tracking-wider text-[var(--auth-cta-text)] transition-all hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50'

export default function OnboardingPage() {
  const router = useRouter()
  const [companyName, setCompanyName] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [logoFile, setLogoFile] = useState<File | null>(null)
  const [logoPreview, setLogoPreview] = useState<string | null>(null)
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState('')

  useEffect(() => {
    fetch(`${API_BASE}/api/setup/db-status`)
      .then((r) => r.json())
      .then((data: { configured?: boolean }) => {
        if (!data.configured) router.replace('/setup')
      })
      .catch(() => {})

    fetch(`${API_BASE}/api/setup/status`)
      .then((r) => r.json())
      .then((data: { configured?: boolean }) => {
        if (data.configured) router.replace('/login')
      })
      .catch(() => {})
  }, [router])

  useEffect(() => {
    if (!logoFile) {
      setLogoPreview(null)
      return
    }
    const url = URL.createObjectURL(logoFile)
    setLogoPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [logoFile])

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setStatus('loading')
    setMessage('')

    let logoUrl = ''
    if (logoFile) {
      const fd = new FormData()
      fd.append('file', logoFile)
      const up = await fetch(`${API_BASE}/api/setup/upload-logo`, { method: 'POST', body: fd })
      const upData = (await up.json().catch(() => ({}))) as { url?: string; detail?: string }
      if (!up.ok) {
        setStatus('error')
        setMessage(typeof upData.detail === 'string' ? upData.detail : 'Error al subir el logo.')
        return
      }
      logoUrl = upData.url || ''
    }

    const res = await fetch(`${API_BASE}/api/setup/init`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company_name: companyName.trim(),
        logo_url: logoUrl,
        username: username.trim(),
        password,
      }),
    })

    if (!res.ok) {
      const err = (await res.json().catch(() => ({}))) as { detail?: string }
      setStatus('error')
      setMessage(err.detail || 'No se pudo crear el sistema.')
      return
    }

    setStatus('success')
    setMessage('Listo. Continuando con la configuración de APIs…')
    setTimeout(() => {
      window.location.href = '/setup/apis'
    }, 600)
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--bg)] px-4">
      <div className="w-full max-w-lg rounded-xl border border-[var(--border)] bg-[var(--bg2)] p-8 shadow-[var(--shadow-sm)]">
        <h1 className="text-xl font-semibold tracking-tight text-[var(--text)]">ATV Setup</h1>
        <p className="mt-2 text-sm text-[var(--text2)]">
          Configurá tu empresa: primer usuario administrador y datos públicos de tu marca.
        </p>

        <form onSubmit={onSubmit} className="mt-8 space-y-5">
          <div>
            <label htmlFor="company_name" className={LABEL_CLASS}>
              Nombre de la empresa
            </label>
            <input
              id="company_name"
              required
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              className={INPUT_CLASS}
            />
          </div>

          <div>
            <label htmlFor="logo" className={LABEL_CLASS}>
              Logo (opcional)
            </label>
            <input
              id="logo"
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif"
              onChange={(e) => setLogoFile(e.target.files?.[0] ?? null)}
              className="block w-full text-sm text-[var(--text2)]"
            />
            {logoPreview && (
              <div className="relative mt-3 h-16 w-16 overflow-hidden rounded-lg border border-[var(--border2)]">
                <Image src={logoPreview} alt="Vista previa" fill className="object-contain" unoptimized />
              </div>
            )}
          </div>

          <div>
            <label htmlFor="username" className={LABEL_CLASS}>
              Usuario
            </label>
            <input
              id="username"
              required
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className={INPUT_CLASS}
            />
          </div>

          <div>
            <label htmlFor="password" className={LABEL_CLASS}>
              Contraseña
            </label>
            <input
              id="password"
              type="password"
              required
              minLength={6}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={INPUT_CLASS}
            />
          </div>

          {message && (
            <p className={`text-sm ${status === 'success' ? 'text-[var(--green)]' : 'text-[var(--text2)]'}`}>
              {message}
            </p>
          )}

          <button type="submit" disabled={status === 'loading'} className={CTA_CLASS}>
            {status === 'loading' ? 'Creando…' : 'Crear sistema'}
          </button>
        </form>
      </div>
    </div>
  )
}
