import { AppProviders } from '@/shared/components/app-providers'
import { AuthGuard } from '@/shared/components/auth-guard'
import { MainLayoutShell } from '@/shared/components/main-layout-shell'
import { fetchCompanyConfig } from '@/shared/lib/company-config.server'

export default async function MainLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const companyConfig = await fetchCompanyConfig()
  return (
    <AppProviders>
      <AuthGuard>
        <MainLayoutShell companyConfig={companyConfig}>{children}</MainLayoutShell>
      </AuthGuard>
    </AppProviders>
  )
}
