export type ConnectionField = {
  key: string
  label: string
  placeholder?: string
  type?: string
  span?: 2
}

export type ConnectionPlatform = {
  key: string
  label: string
  icon: string
  subtitle: string
  fields: ConnectionField[]
  guide: { title: string; steps: string[] }
  infoOnly?: boolean
}

const PLATFORMS: ConnectionPlatform[] = [
  {
    key: 'calendly',
    label: 'Calendly',
    icon: '📅',
    subtitle: 'Creá leads cuando alguien agenda una sesión',
    fields: [
      { key: 'api_key', label: 'Personal Access Token', placeholder: 'eyJraWQ...', type: 'password' },
      { key: 'signing_key', label: 'Webhook Signing Key', placeholder: 'whsec_...', type: 'password' },
    ],
    guide: {
      title: 'Cómo configurar Calendly',
      steps: [
        'Andá a calendly.com → Integraciones → API & Webhooks',
        'Generá un Personal Access Token y pegalo acá',
        'Creá un webhook en Calendly con la URL de abajo y el evento invitee.created',
        'Copiá el Signing Key del webhook y pegalo en el campo correspondiente',
      ],
    },
  },
  {
    key: 'manychat',
    label: 'ManyChat',
    icon: '💬',
    subtitle: 'Conectá tu keyword de bio para trackear chats',
    fields: [
      { key: 'api_key', label: 'API Key de ManyChat', placeholder: 'Settings → API', type: 'password' },
      { key: 'bio_keyword', label: 'Keyword de bio', placeholder: 'Ej: info, value, hola', type: 'text' },
    ],
    guide: {
      title: 'Cómo configurar ManyChat',
      steps: [
        'Copiá la API Key desde Settings → API',
        'Conectá y usá la URL del webhook en un External Request POST',
        'Incluí webhook_token en el body del request',
      ],
    },
  },
  {
    key: 'instagram',
    label: 'Instagram',
    icon: '📸',
    subtitle: 'Sincronizá insights de stories con Instagram Graph API',
    fields: [
      { key: 'access_token', label: 'Access Token', placeholder: 'EAAG...', type: 'password' },
      { key: 'instagram_user_id', label: 'Instagram User ID', placeholder: '1784...' },
    ],
    guide: {
      title: 'Cómo configurar Instagram',
      steps: [
        'Conectá tu app en Meta for Developers',
        'Generá un Access Token con permisos para stories e insights',
        'Pegá token e Instagram User ID y guardá',
      ],
    },
  },
  {
    key: 'youtube',
    label: 'YouTube',
    icon: '▶️',
    subtitle: 'Importá videos con YouTube Data API v3',
    fields: [
      { key: 'api_key', label: 'API Key de Google', placeholder: 'AIzaSy...', type: 'password' },
      { key: 'channel_id', label: 'Channel ID', placeholder: 'UCxxxxxxxxxx' },
    ],
    guide: {
      title: 'Cómo configurar YouTube',
      steps: [
        'Habilitá YouTube Data API v3 en Google Cloud',
        'Creá una API Key y pegala acá',
        'Copiá el Channel ID de tu canal',
      ],
    },
  },
]

const SETUP_ORDER = ['instagram', 'manychat', 'calendly', 'youtube'] as const
const APP_ORDER = ['calendly', 'manychat', 'instagram', 'youtube'] as const

function pick(order: readonly string[]): ConnectionPlatform[] {
  const map = new Map(PLATFORMS.map((p) => [p.key, p]))
  return order.map((key) => map.get(key)).filter(Boolean) as ConnectionPlatform[]
}

export function platformsForSetup(): ConnectionPlatform[] {
  return pick(SETUP_ORDER)
}

export function platformsForApp(): ConnectionPlatform[] {
  return pick(APP_ORDER)
}
