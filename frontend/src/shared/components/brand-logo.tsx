import Image from 'next/image'
import atvLogo from '@/assets/atv-logo.png'
import { resolveMediaUrl } from '@/shared/lib/backend-public-url'

type BrandLogoProps = {
  className?: string
  /** Logo subido en onboarding (`CompanyConfig.logo_url`). Si falta, usa el PNG por defecto. */
  logoUrl?: string | null
  alt?: string
}

/** Logo de marca: configurado en setup o fallback ATV (PNG importado). */
export function BrandLogo({
  className = 'h-10 w-auto max-w-[56px] flex-shrink-0 object-contain',
  logoUrl,
  alt = 'ATV',
}: BrandLogoProps) {
  const customSrc = resolveMediaUrl(logoUrl)
  if (customSrc) {
    return (
      <Image
        src={customSrc}
        alt={alt}
        width={72}
        height={72}
        className={className}
        sizes="120px"
        priority
        unoptimized
      />
    )
  }
  return (
    <Image
      src={atvLogo}
      alt={alt}
      width={atvLogo.width}
      height={atvLogo.height}
      className={className}
      sizes="120px"
      priority
    />
  )
}
