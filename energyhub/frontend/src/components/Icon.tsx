import {
  Car,
  CookingPot,
  Droplets,
  Flame,
  Gamepad2,
  Laptop,
  Lightbulb,
  Microwave,
  Plug,
  Refrigerator,
  Router,
  Shirt,
  ShowerHead,
  Snowflake,
  Tv,
  WashingMachine,
  Wind,
  Zap,
  type LucideIcon,
} from 'lucide-react'

const ICONS: Record<string, LucideIcon> = {
  refrigerator: Refrigerator,
  snowflake: Snowflake,
  router: Router,
  tv: Tv,
  laptop: Laptop,
  gamepad: Gamepad2,
  'washing-machine': WashingMachine,
  wind: Wind,
  droplets: Droplets,
  oven: Flame,
  'cooking-pot': CookingPot,
  microwave: Microwave,
  'shower-head': ShowerHead,
  flame: Flame,
  lightbulb: Lightbulb,
  car: Car,
  shirt: Shirt,
  plug: Plug,
  zap: Zap,
}

export function DeviceIcon({
  name,
  size = 19,
  strokeWidth = 1.8,
}: {
  name?: string | null
  size?: number
  strokeWidth?: number
}) {
  const Icon = ICONS[name ?? 'zap'] ?? Zap
  return <Icon size={size} strokeWidth={strokeWidth} />
}

export function BoltIcon({ size = 21 }: { size?: number }) {
  return <Zap size={size} strokeWidth={2.4} fill="currentColor" />
}
