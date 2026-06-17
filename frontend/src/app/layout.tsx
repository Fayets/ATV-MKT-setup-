import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import Script from 'next/script'
import { DbBootstrapProvider } from '@/features/setup/db-bootstrap-provider'
import { fetchCompanyConfig } from '@/shared/lib/company-config.server'
import { resolveMediaUrl } from '@/shared/lib/backend-public-url'
import { ThemeProvider } from '@/shared/components/theme-provider'
import { ToastProvider } from '@/shared/components/toast'
import './globals.css'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
})

export async function generateMetadata(): Promise<Metadata> {
  try {
    const config = await fetchCompanyConfig()
    const title = config.company_name || 'ATV'
    const icons: Metadata['icons'] = {}
    const logo = resolveMediaUrl(config.logo_url)
    if (logo) icons.icon = logo
    return {
      title,
      description: 'Plataforma integral de gestion de contenido y ventas para creadores high-ticket',
      icons: Object.keys(icons).length ? icons : undefined,
    }
  } catch {
    return {
      title: 'ATV',
      description: 'Plataforma integral de gestion de contenido y ventas para creadores high-ticket',
    }
  }
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const themeScript = `(function(){try{var t=localStorage.getItem('atvmkt-theme');if(t==='light')document.documentElement.setAttribute('data-theme','light');else document.documentElement.removeAttribute('data-theme');}catch(e){}})();`

  return (
    <html lang="es" className={inter.variable} suppressHydrationWarning>
      <body>
        <Script id="atvmkt-theme-init" strategy="beforeInteractive">
          {themeScript}
        </Script>
        <ThemeProvider>
          <ToastProvider>
            <DbBootstrapProvider>{children}</DbBootstrapProvider>
          </ToastProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}
