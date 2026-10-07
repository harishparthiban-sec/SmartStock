import * as React from 'react';
import { cn } from '../../utils/cn';

interface StatusIndicatorProps extends React.HTMLAttributes<HTMLDivElement> {
  status: "CRITICAL" | "WARNING" | "HEALTHY" | "OVERSTOCKED";
}

export function StatusIndicator({ status, className, ...props }: StatusIndicatorProps) {
  const statusConfig = {
    CRITICAL: { bg: 'bg-red-500', text: 'ORDER NOW', ring: 'ring-red-100' },
    WARNING: { bg: 'bg-amber-500', text: 'ORDER SOON', ring: 'ring-amber-100' },
    HEALTHY: { bg: 'bg-emerald-500', text: 'OK', ring: 'ring-emerald-100' },
    OVERSTOCKED: { bg: 'bg-blue-500', text: 'OVERSTOCK', ring: 'ring-blue-100' },
  };

  const config = statusConfig[status];

  return (
    <div className={cn("flex items-center space-x-2", className)} {...props}>
      <span className={cn("relative flex h-3 w-3", config.ring, "ring-4 rounded-full")} aria-hidden="true">
        <span className={cn("animate-ping absolute inline-flex h-full w-full rounded-full opacity-20", config.bg)}></span>
        <span className={cn("relative inline-flex rounded-full h-3 w-3", config.bg)}></span>
      </span>
      <span className="text-sm font-bold tracking-tight text-gray-700">{config.text}</span>
    </div>
  );
}
