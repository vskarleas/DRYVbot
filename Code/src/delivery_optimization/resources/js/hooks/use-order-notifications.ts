import { toast } from 'sonner';
import { useEchoChannel } from '@/hooks/use-echo';
import type { Order } from '@/types';

type RoomPayload = { name?: string } | string | null | undefined;

function roomLabel(room: RoomPayload): string {
    if (typeof room === 'string') {
        return room;
    }

    return room?.name ?? '—';
}

/**
 * Subscribe to real-time order updates and show toast notifications.
 */
export function useOrderNotifications() {
    useEchoChannel<{ order: Order }>('orders', 'OrderCreated', ({ order }) => {
        toast.info(`Nouvelle commission ${order.reference}`, {
            description: `${roomLabel(order.departure_room)} → ${roomLabel(order.arrival_room)}`,
        });
    });

    useEchoChannel<{ order: Order }>('orders', 'OrderStatusUpdated', ({ order }) => {
        const messages: Record<string, string> = {
            delivered: `✅ Commission ${order.reference} livrée`,
            cancelled: `❌ Commission ${order.reference} annulée`,
            in_transit: `🚀 Commission ${order.reference} en transit`,
        };
        const msg = messages[order.status] ?? `Commission ${order.reference} mise à jour`;
        toast(msg);
    });
}
