'use client'

import { API_BASE } from '@/shared/lib/backend-public-url'
import { usePathname, useRouter } from 'next/navigation'
import { useEffect, useRef } from 'react'

const SETUP_DB_PATH = '/setup'
const ONBOARDING_PATH = '/onboarding'
const LOGIN_PATH = '/login'
const TIMEOUT_MS = 4000

/** Rutas del wizard que no deben redirigirse a /setup si falta la DB. */
const PUBLIC_WIZARD_PATHS = new Set([SETUP_DB_PATH, ONBOARDING_PATH, LOGIN_PATH])

function isWizardPath(pathname: string | null): boolean {
  if (!pathname) return false
  if (PUBLIC_WIZARD_PATHS.has(pathname)) return true
  return pathname.startsWith('/setup/')
}

export function DbBootstrapProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const pathnameRef = useRef(pathname)
  pathnameRef.current = pathname

  useEffect(() => {
    const controller = new AbortController()
    const timer = window.setTimeout(() => controller.abort(), TIMEOUT_MS)

    void (async () => {
      try {
        const dbRes = await fetch(`${API_BASE}/api/setup/db-status`, {
          cache: 'no-store',
          signal: controller.signal,
        })
        const dbData = (await dbRes.json().catch(() => ({}))) as { configured?: boolean }
        const dbConfigured = Boolean(dbData?.configured)
        const current = pathnameRef.current
        const onWizard = isWizardPath(current)

        if (!dbConfigured) {
          if (!onWizard) router.replace(SETUP_DB_PATH)
          return
        }

        const statusRes = await fetch(`${API_BASE}/api/setup/status`, {
          cache: 'no-store',
          signal: controller.signal,
        })
        const statusData = (await statusRes.json().catch(() => ({}))) as { configured?: boolean }
        const systemReady = Boolean(statusData?.configured)

        if (!systemReady) {
          if (current === SETUP_DB_PATH) {
            router.replace(ONBOARDING_PATH)
          } else if (!onWizard) {
            router.replace(ONBOARDING_PATH)
          }
          return
        }

        if (current === SETUP_DB_PATH || current === ONBOARDING_PATH) {
          router.replace(LOGIN_PATH)
        }
      } catch {
        /* Backend caído: no bloquear la UI */
      } finally {
        window.clearTimeout(timer)
      }
    })()

    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [router, pathname])

  return <>{children}</>
}
