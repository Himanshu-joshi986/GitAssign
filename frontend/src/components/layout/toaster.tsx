import { AnimatePresence, motion } from 'motion/react'
import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react'
import { Button } from '../ui/button'
import { cn } from '../../lib/utils'

export interface ToastNotification {
  message: string
  type: 'success' | 'error' | 'info'
}

const TOAST_META = {
  success: { icon: CheckCircle2, className: 'border-emerald-500/25 bg-emerald-500/10 text-emerald-300' },
  error: { icon: AlertCircle, className: 'border-rose-500/25 bg-rose-500/10 text-rose-300' },
  info: { icon: Info, className: 'border-sky-500/25 bg-sky-500/10 text-sky-300' },
}

export function Toaster({
  notification,
  onClose,
}: {
  notification: ToastNotification | null
  onClose: () => void
}) {
  const ToastIcon = notification ? TOAST_META[notification.type].icon : Info
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[60] w-[calc(100vw-2rem)] max-w-sm" aria-live="polite" aria-atomic="true">
      <AnimatePresence>
        {notification && (
          <motion.div
            key={`${notification.type}-${notification.message}`}
            initial={{ opacity: 0, y: 16, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.97 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            className={cn(
              'pointer-events-auto relative overflow-hidden rounded-xl border bg-card/95 p-3.5 shadow-panel backdrop-blur-xl',
              TOAST_META[notification.type].className,
            )}
          >
            <div className="flex items-start gap-2.5">
              <ToastIcon className="mt-0.5 size-4 shrink-0" />
              <p className="flex-1 text-xs leading-relaxed">{notification.message}</p>
              <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Dismiss notification">
                <X className="size-3.5" />
              </Button>
            </div>
            <motion.div
              initial={{ width: '100%' }}
              animate={{ width: '0%' }}
              transition={{ duration: 4, ease: 'linear' }}
              className="absolute inset-x-0 bottom-0 h-px bg-current opacity-40"
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
