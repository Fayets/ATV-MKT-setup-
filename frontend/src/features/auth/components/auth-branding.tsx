import Image from 'next/image'
import { resolveMediaUrl } from '@/shared/lib/backend-public-url'
import type { CompanyConfigPublic } from '@/shared/lib/company-config.server'

type Props = {
  config: CompanyConfigPublic
}

export function AuthBranding({ config }: Props) {
  const logoSrc = resolveMediaUrl(config.logo_url)

  return (
    <div className="mb-8 text-center">
      {logoSrc ? (
        <div className="relative mx-auto h-20 w-20 overflow-hidden rounded-xl">
          <Image
            src={logoSrc}
            alt={config.company_name}
            fill
            className="object-contain p-2"
            unoptimized
          />
        </div>
      ) : null}
    </div>
  )
}
