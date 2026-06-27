import { Head, router } from '@inertiajs/react';
import { useState } from 'react';
import { RefreshCw, ListOrdered, Clock, MapPin } from 'lucide-react';
import { OrderStatusBadge } from '@/components/order-status-badge';
import { useEchoChannel } from '@/hooks/use-echo';
import { useFlashToast } from '@/hooks/use-flash-toast';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import * as planRoute from '@/actions/App/Http/Controllers/DeliveryPlanController';
import type { DeliveryPlan, Order, PageProps, Room } from '@/types';

type LegacyOrderRelations = {
    departure_room?: Room;
    arrival_room?: Room;
};

type DeliveryPlanWithCurrentRoom = DeliveryPlan & {
    current_room?: Room;
    currentRoom?: Room;
};

function getCurrentRoom(plan: DeliveryPlan | null): Room | undefined {
    if (!plan) {
        return undefined;
    }

    const typedPlan = plan as DeliveryPlanWithCurrentRoom;

    return typedPlan.currentRoom ?? typedPlan.current_room;
}

function getDepartureRoomName(order: Order): string {
    const legacyOrder = order as Order & LegacyOrderRelations;

    return order.departure_room?.name ?? legacyOrder.departure_room?.name ?? '?';
}

function getArrivalRoomName(order: Order): string {
    const legacyOrder = order as Order & LegacyOrderRelations;

    return order.arrival_room?.name ?? legacyOrder.arrival_room?.name ?? '?';
}

type Props = PageProps & {
    plan: DeliveryPlan | null;
    orders: Order[];
    queuedPlans: DeliveryPlan[];
};

export default function DeliveryPlanIndex({ plan: initialPlan, orders: initialOrders, queuedPlans }: Props) {
    const [plan] = useState(initialPlan);
    const [orders] = useState(initialOrders);
    const [replanning, setReplanning] = useState(false);

    useFlashToast();

    useEchoChannel('delivery-plan', {
        DeliveryPlanUpdated: () => {
            router.reload({
                only: ['plan', 'orders', 'queuedPlans'],
            });
        },
    });

    useEchoChannel('orders', {
        OrderStatusUpdated: () => {
            router.reload({
                only: ['plan', 'orders', 'queuedPlans'],
            });
        },
    });

    const currentRoom = getCurrentRoom(plan);

    function handleReplan() {
        setReplanning(true);
        router.post(planRoute.replan.url(), {}, {
            onFinish: () => setReplanning(false),
        });
    }

    // Build ordered list from plan sequence
    const orderedItems: Array<{ order: Order; sequence: number; predictedMinutes?: number }> = [];

    if (plan?.sequence) {
        for (const orderId of plan.sequence) {
            const order = orders.find((o) => o.id === orderId);
            if (order) {
                const estimated = plan.estimated_times?.[String(orderId)];
                orderedItems.push({
                    order,
                    sequence: estimated?.sequence ?? 0,
                    predictedMinutes: estimated?.predicted_minutes,
                });
            }
        }
    }

    return (
        <>
            <Head title="Plan de livraison" />

            <div className="flex h-full flex-1 flex-col gap-6 p-4 md:p-6">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold tracking-tight">Plan de livraison</h1>
                        <p className="text-muted-foreground">
                            Séquence optimisée des livraisons en cours
                        </p>
                        {plan && (
                            <div className="mt-2">
                                <Badge variant={plan.is_critical ? 'destructive' : 'secondary'}>
                                    {plan.is_critical ? 'Plan critique' : 'Plan standard'}
                                </Badge>
                            </div>
                        )}
                    </div>
                    <Button onClick={handleReplan} disabled={replanning} variant="outline">
                        <RefreshCw className={`mr-2 h-4 w-4 ${replanning ? 'animate-spin' : ''}`} />
                        Re-planifier
                    </Button>
                </div>

                {/* Current robot position */}
                {currentRoom && (
                    <Card className="border-primary/20 bg-primary/5">
                        <CardContent className="flex items-center gap-3 py-3">
                            <MapPin className="h-5 w-5 text-primary" />
                            <div>
                                <p className="text-sm font-medium">Position actuelle du robot</p>
                                <p className="text-xs text-muted-foreground">{currentRoom.name}</p>
                            </div>
                            {plan?.updated_at && (
                                <p className="ml-auto text-xs text-muted-foreground">
                                    Mis à jour le {new Date(plan.updated_at).toLocaleString('fr-FR')}
                                </p>
                            )}
                        </CardContent>
                    </Card>
                )}

                {queuedPlans.length > 0 && (
                    <Card>
                        <CardContent className="py-4">
                            <p className="mb-2 text-sm font-semibold">Plans en attente</p>
                            <ul className="space-y-1 text-sm text-muted-foreground">
                                {queuedPlans.map((queuedPlan) => (
                                    <li key={queuedPlan.id}>
                                        Plan #{queuedPlan.id} - {queuedPlan.is_critical ? 'Critique' : 'Standard'} ({queuedPlan.sequence.length} commissions)
                                    </li>
                                ))}
                            </ul>
                        </CardContent>
                    </Card>
                )}

                {orderedItems.length === 0 ? (
                    <Card>
                        <CardContent className="flex flex-col items-center justify-center py-16 text-center">
                            <ListOrdered className="mb-3 h-12 w-12 text-muted-foreground opacity-30" />
                            <p className="font-medium">Aucune livraison planifiée</p>
                            <p className="mt-1 text-sm text-muted-foreground">
                                Toutes les commissions ont été livrées ou annulées.
                            </p>
                        </CardContent>
                    </Card>
                ) : (
                    <div className="space-y-3">
                        {orderedItems.map(({ order, sequence, predictedMinutes }) => (
                            <Card key={order.id} className="transition-all hover:shadow-md">
                                <CardContent className="flex items-center gap-4 py-3">
                                    {/* Sequence number */}
                                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-bold">
                                        {sequence}
                                    </div>

                                    {/* Route */}
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 text-sm">
                                            <span className="font-medium truncate">
                                                {getDepartureRoomName(order)}
                                            </span>
                                            <span className="text-muted-foreground shrink-0">→</span>
                                            <span className="font-medium truncate">
                                                {getArrivalRoomName(order)}
                                            </span>
                                        </div>
                                        <p className="text-xs text-muted-foreground font-mono">
                                            {order.reference}
                                        </p>
                                    </div>

                                    {/* Predicted time */}
                                    {predictedMinutes && (
                                        <div className="flex items-center gap-1 text-sm text-muted-foreground">
                                            <Clock className="h-3.5 w-3.5" />
                                            <span>~{predictedMinutes} min</span>
                                        </div>
                                    )}

                                    {/* Status */}
                                    <OrderStatusBadge status={order.status} />
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                )}

                {/* Stats */}
                {orderedItems.length > 0 && (
                    <Card>
                        <CardContent className="flex gap-6 py-3 text-sm">
                            <div>
                                <span className="text-muted-foreground">Total commissions :</span>
                                <span className="ml-1.5 font-medium">{orderedItems.length}</span>
                            </div>
                            <div>
                                <span className="text-muted-foreground">Durée totale estimée :</span>
                                <span className="ml-1.5 font-medium">
                                    {orderedItems.reduce((acc, i) => acc + (i.predictedMinutes ?? 0), 0)} min
                                </span>
                            </div>
                        </CardContent>
                    </Card>
                )}
            </div>
        </>
    );
}
