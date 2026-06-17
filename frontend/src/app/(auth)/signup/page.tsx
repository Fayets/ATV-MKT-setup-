import { redirect } from 'next/navigation'

/** Registro vía onboarding del sistema; esta ruta evita pantalla rota. */
export default function SignupPage() {
  redirect('/onboarding')
}
