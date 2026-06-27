import { cn } from '@/lib/utils';
import type { OrderStatus } from '@/types';

const statusConfig: Record<OrderStatus, { label: string; className: string }> = {
    pending: { label: 'En attente', className: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400' },
    in_transit: { label: 'En transit', className: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400' },
    delivered: { label: 'Livré', className: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400' },
    cancelled: { label: 'Annulé', className: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400' },
};

export function OrderStatusBadge({ status }: { status: OrderStatus }) {
    const config = statusConfig[status];
    return (
        <span className={cn('inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium', config.className)}>
            {config.label}
        </span>
    );
}
