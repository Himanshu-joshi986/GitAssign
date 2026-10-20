import type { ReactNode } from 'react'
import {
  LayoutDashboard,
  Inbox,
  Zap,
  Users,
  BarChart3,
  FlaskConical,
  type LucideIcon,
} from 'lucide-react'

export type TabId = 'overview' | 'issues' | 'assign' | 'metrics' | 'developers' | 'demo'

export interface TabDefinition {
  id: TabId
  label: string
  shortLabel: string
  description: string
  icon: LucideIcon
}

export const TABS: TabDefinition[] = [
  {
    id: 'overview',
    label: 'Overview',
    shortLabel: 'Overview',
    description: 'Repository health, priorities, and coverage at a glance',
    icon: LayoutDashboard,
  },
  {
    id: 'issues',
    label: 'Issue Queue',
    shortLabel: 'Issues',
    description: 'Triage issues and inspect developer recommendations',
    icon: Inbox,
  },
  {
    id: 'assign',
    label: 'Batch Assign',
    shortLabel: 'Assign',
    description: 'Capacity-aware assignment preview and apply',
    icon: Zap,
  },
  {
    id: 'developers',
    label: 'Developers',
    shortLabel: 'Developers',
    description: 'Expertise profiles built from repository history',
    icon: Users,
  },
  {
    id: 'metrics',
    label: 'Evaluation',
    shortLabel: 'Metrics',
    description: 'Replay metrics and ablation study results',
    icon: BarChart3,
  },
  {
    id: 'demo',
    label: 'Demo Scan',
    shortLabel: 'Demo',
    description: 'Scan a marked file and route its defects',
    icon: FlaskConical,
  },
]

export function tabDefinition(id: TabId): TabDefinition {
  return TABS.find(tab => tab.id === id) ?? TABS[0]
}

export function TabIcon({ tab, className }: { tab: TabId; className?: string }): ReactNode {
  const Icon = tabDefinition(tab).icon
  return <Icon className={className} />
}
