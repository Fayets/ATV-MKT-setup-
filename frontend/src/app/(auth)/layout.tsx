import { AuthBranding } from '@/features/auth/components/auth-branding'
import { fetchCompanyConfig } from '@/shared/lib/company-config.server'
import { ThemeToggle } from '@/shared/components/theme-toggle'

export default async function AuthLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const config = await fetchCompanyConfig()

  return (
    <div className="auth-shell relative flex min-h-screen items-center justify-center bg-[var(--bg)]">
      <div className="absolute right-4 top-4 z-10 sm:right-6 sm:top-6">
        <ThemeToggle />
      </div>
      <div className="w-full max-w-md px-6">
        <AuthBranding config={config} />
        <div className="auth-card p-8">
          {children}
        </div>
      </div>
    </div>
  )
}
