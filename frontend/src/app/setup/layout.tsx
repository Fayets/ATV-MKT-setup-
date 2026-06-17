import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'ATV Setup',
}

export default function SetupRootLayout({ children }: { children: React.ReactNode }) {
  return children
}
