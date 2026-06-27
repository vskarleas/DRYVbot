import { Head, Link, router } from '@inertiajs/react';
import { useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { AlertTriangle, CheckCircle, Clock, Package, XCircle } from 'lucide-react';
import { OrderStatusBadge } from '@/components/order-status-badge';
import { useOrderNotifications } from '@/hooks/use-order-notifications';
import { useEchoChannel } from '@/hooks/use-echo';
import { dashboard } from '@/routes';
import type { DeliveryPlan, Order, PageProps, Room } from '@/types';

type Stats = {
    pending: number;
    pending_critical: number;
    pending_non_critical: number;
    in_transit: number;
    delivered: number;
    cancelled: number;
};

type Props = PageProps & {
    stats: Stats;
    myOrders: Order[];
    activePlan: DeliveryPlan | null;
    queuedPlans: DeliveryPlan[];
    rooms: Room[];
};

export default function PharmacyDashboard({ stats: initialStats, myOrders: initialOrders, activePlan, queuedPlans }: Props) {
    const [orders] = useState(initialOrders);

    useOrderNotifications();

    useEchoChannel<{ order: Order }>('orders', 'OrderStatusUpdated', () => {
        router.reload({ only: ['stats', 'myOrders', 'activePlan', 'queuedPlans'] });
    });

    useEchoChannel<{ order: Order }>('orders', 'OrderCreated', () => {
        router.reload({ only: ['stats', 'myOrders', 'activePlan', 'queuedPlans'] });
    });

    const chartData = [
        { name: 'En attente', value: initialStats.pending },
        { name: 'En transit', value: initialStats.in_transit },
        { name: 'Livrées', value: initialStats.delivered },
        { name: 'Annulées', value: initialStats.cancelled },
    ];

    return (
        <>
            <Head title="Tableau de bord Pharmacie" />
            <div className="flex flex-col gap-6 p-6">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Mes commissions</h1>
                        <p className="text-sm text-gray-500">Suivez les commissions en temps réel</p>
                    </div>
                </div>

                {/* Stats Cards */}
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    <StatCard icon={<Clock className="text-yellow-500" />} label="En attente" value={initialStats.pending} />
                    <StatCard icon={<AlertTriangle className="text-red-500" />} label="En attente critiques" value={initialStats.pending_critical} />
                    <StatCard icon={<Package className="text-slate-500" />} label="En attente standards" value={initialStats.pending_non_critical} />
                    <StatCard icon={<Package className="text-blue-500" />} label="En transit" value={initialStats.in_transit} />
                    <StatCard icon={<CheckCircle className="text-green-500" />} label="Livrées" value={initialStats.delivered} />
                    <StatCard icon={<XCircle className="text-red-500" />} label="Annulées" value={initialStats.cancelled} />
                </div>

                <div className="rounded-xl border border-sidebar-border/70 bg-white p-4 dark:bg-sidebar dark:border-sidebar-border">
                    <h2 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">Etat de la planification</h2>
                    <div className="space-y-2 text-sm">
                        <p>
                            Plan actif: {activePlan ? `#${activePlan.id} (${activePlan.is_critical ? 'Critique' : 'Standard'})` : 'Aucun'}
                        </p>
                        <p>
                            Plans en attente: {queuedPlans.length}
                        </p>
                    </div>
                </div>

                {/* Chart */}
                <div className="rounded-xl border border-sidebar-border/70 bg-white p-4 dark:bg-sidebar dark:border-sidebar-border">
                    <h2 className="mb-4 text-sm font-semibold text-gray-700 dark:text-gray-300">Aperçu des commissions</h2>
                    <ResponsiveContainer width="100%" height={200}>
                        <LineChart data={chartData}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                            <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                            <YAxis tick={{ fontSize: 11 }} />
                            <Tooltip />
                            <Line type="monotone" dataKey="value" stroke="#3b82f6" strokeWidth={2} dot={{ r: 4 }} />
                        </LineChart>
                    </ResponsiveContainer>
                </div>

                {/* Orders Table */}
                <div className="rounded-xl border border-sidebar-border/70 bg-white dark:bg-sidebar dark:border-sidebar-border">
                    <div className="flex items-center justify-between border-b border-sidebar-border/70 px-4 py-3 dark:border-sidebar-border">
                        <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Commissions récentes</h2>
                        <Link href="/orders" className="text-xs text-blue-600 hover:underline dark:text-blue-400">
                            Voir tout →
                        </Link>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead className="bg-gray-50 dark:bg-sidebar-accent/30">
                                <tr>
                                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Référence</th>
                                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Départ → Arrivée</th>
                                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Livraison prévue</th>
                                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Statut</th>
                                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Priorité</th>
                                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Séquence</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100 dark:divide-sidebar-border/50">
                                {orders.length === 0 ? (
                                    <tr>
                                        <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                                            Aucune commission.
                                        </td>
                                    </tr>
                                ) : orders.map(order => (
                                    <tr key={order.id} className="hover:bg-gray-50 dark:hover:bg-sidebar-accent/20 cursor-pointer" onClick={() => router.visit(`/orders/${order.id}`)}>
                                        <td className="px-4 py-3 font-mono text-xs">{order.reference}</td>
                                        <td className="px-4 py-3">
                                            {order.departure_room?.name} → {order.arrival_room?.name}
                                        </td>
                                        <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                                            {new Date(order.expected_delivery_at).toLocaleString('fr-FR')}
                                        </td>
                                        <td className="px-4 py-3">
                                            <OrderStatusBadge status={order.status} />
                                        </td>
                                        <td className="px-4 py-3 text-xs text-gray-500">
                                            {order.is_critical ? 'Critique' : 'Standard'}
                                        </td>
                                        <td className="px-4 py-3 text-center">
                                            {order.planned_sequence ? (
                                                <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-blue-100 text-xs font-bold text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                                                    {order.planned_sequence}
                                                </span>
                                            ) : '—'}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </>
    );
}

function StatCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: number }) {
    return (
        <div className="flex items-center gap-4 rounded-xl border border-sidebar-border/70 bg-white p-4 dark:bg-sidebar dark:border-sidebar-border">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gray-50 dark:bg-sidebar-accent/30">
                {icon}
            </div>
            <div>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">{value}</p>
                <p className="text-xs text-gray-500">{label}</p>
            </div>
        </div>
    );
}

PharmacyDashboard.layout = {
    breadcrumbs: [{ title: 'Tableau de bord', href: dashboard() }],
};
