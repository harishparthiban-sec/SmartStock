import * as React from 'react';
import { Activity, AlertTriangle, Inbox } from 'lucide-react';
import { cn } from '../../utils/cn';

interface StateProps {
  title?: string;
  message?: string;
  className?: string;
}

export function LoadingState({ title = "Loading...", message = "Please wait while we fetch the data.", className }: StateProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center min-h-[300px] text-gray-500 space-y-4 p-8 text-center", className)} role="status" aria-live="polite">
      <Activity className="h-8 w-8 animate-pulse text-indigo-400" aria-hidden="true" />
      <div>
        <h3 className="text-lg font-medium text-gray-900">{title}</h3>
        <p className="text-sm mt-1">{message}</p>
      </div>
      <span className="sr-only">Loading</span>
    </div>
  );
}

interface ErrorStateProps extends StateProps {
  onRetry?: () => void;
}

export function ErrorState({ title = "Error Loading Data", message = "We encountered a problem while fetching this information.", onRetry, className }: ErrorStateProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center min-h-[300px] text-gray-500 space-y-4 p-8 text-center", className)} role="alert" aria-live="assertive">
      <AlertTriangle className="h-8 w-8 text-red-500" aria-hidden="true" />
      <div>
        <h3 className="text-lg font-medium text-red-900">{title}</h3>
        <p className="text-sm text-red-700 mt-1 max-w-md">{message}</p>
      </div>
      {onRetry && (
        <button 
          onClick={onRetry}
          className="mt-4 px-4 py-2 bg-red-100 hover:bg-red-200 text-red-800 rounded-md text-sm font-medium transition-colors focus:ring-2 focus:ring-red-500 focus:outline-none"
          aria-label="Retry loading data"
        >
          Retry
        </button>
      )}
    </div>
  );
}

interface EmptyStateProps extends StateProps {
  icon?: React.ReactNode;
}

export function EmptyState({ title = "No Data Available", message = "There is currently no information to display here.", icon, className }: EmptyStateProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center min-h-[300px] text-gray-500 space-y-4 p-8 text-center", className)}>
      {icon ? icon : <Inbox className="h-8 w-8 text-gray-400" aria-hidden="true" />}
      <div>
        <h3 className="text-lg font-medium text-gray-900">{title}</h3>
        <p className="text-sm mt-1 max-w-md">{message}</p>
      </div>
    </div>
  );
}
