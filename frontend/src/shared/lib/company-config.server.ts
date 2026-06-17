import { getBackendInternalUrl } from './backend-internal-url'

export type CompanyConfigPublic = {
  company_name: string
  logo_url: string
}

const DEFAULTS: CompanyConfigPublic = {
  company_name: 'ATV',
  logo_url: '',
}

export async function fetchCompanyConfig(): Promise<CompanyConfigPublic> {
  const base = getBackendInternalUrl()
  try {
    const res = await fetch(`${base}/api/setup/config`, {
      next: { revalidate: 0 },
      signal: AbortSignal.timeout(2000),
    })
    if (!res.ok) return DEFAULTS
    const data = (await res.json()) as Partial<CompanyConfigPublic> & { company_tagline?: string }
    return {
      company_name: (data.company_name || DEFAULTS.company_name).trim() || DEFAULTS.company_name,
      logo_url: (data.logo_url || '').trim(),
    }
  } catch {
    return DEFAULTS
  }
}
