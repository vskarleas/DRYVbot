import { Head, router } from '@inertiajs/react';
import { Activity, AlertTriangle, CheckCircle, Clock, Package, XCircle } from 'lucide-react';
import { Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';
import { OrderStatusBadge } from '@/components/order-status-badge';
import { useEchoChannel } from '@/hooks/use-echo';
import { useOrderNotifications } from '@/hooks/use-order-notifications';
import { dashboard } from '@/routes';
import type { DeliveryPlan, Order, PageProps } from '@/types';

type Stats = {
    pending: number;
    pending_critical: number;
    pending_non_critical: number;
    in_transit: number;
    delivered_today: number;
    cancelled_today: number;
};

type Props = PageProps & {
    stats: Stats;
    activePlan: DeliveryPlan | null;
    queuedPlans: DeliveryPlan[];
    recentOrders: Order[];
};

const COLORS = ['#f59e0b', '#3b82f6', '#22c55e', '#ef4444'];

export default function ManagerDashboard({ stats: initialStats, activePlan: initialPlan, queuedPlans, recentOrders: initialOrders }: Props) {
    useOrderNotifications();

    // Listen for plan updates
    useEchoChannel<{ plan: DeliveryPlan }>('delivery-plan', 'DeliveryPlanUpdated', () => {
        router.reload({ only: ['activePlan', 'queuedPlans'] });
    });

    // Refresh order list when status changes
    useEchoChannel<{ order: Order }>('orders', 'OrderStatusUpdated', () => {
        router.reload({ only: ['stats', 'recentOrders', 'activePlan', 'queuedPlans'] });
    });

    useEchoChannel<{ order: Order }>('orders', 'OrderCreated', () => {
        router.reload({ only: ['stats', 'recentOrders', 'activePlan', 'queuedPlans'] });
    });

    const pieData = [
        { name: 'En attente', value: initialStats.pending },
        { name: 'En transit', value: initialStats.in_transit },
        { name: 'Livrées aujourd\'hui', value: initialStats.delivered_today },
        { name: 'Annulées aujourd\'hui', value: initialStats.cancelled_today },
    ].filter(d => d.value > 0);

    return (
        <>
            <Head title="Tableau de bord Manager" />
            <div className="flex flex-col gap-6 p-6">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Tableau de bord</h1>
                    <p className="text-sm text-gray-500">Suivi en temps réel des commissions du robot</p>
                </div>

                {/* Stats Cards */}
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
                    <StatCard icon={<Clock className="text-yellow-500" />} label="En attente" value={initialStats.pending} color="yellow" />
                    <StatCard icon={<AlertTriangle className="text-red-500" />} label="En attente critiques" value={initialStats.pending_critical} color="red" />
                    <StatCard icon={<Package className="text-slate-500" />} label="En attente standards" value={initialStats.pending_non_critical} color="slate" />
                    <StatCard icon={<Activity className="text-blue-500" />} label="En transit" value={initialStats.in_transit} color="blue" />
                    <StatCard icon={<CheckCircle className="text-green-500" />} label="Livrées aujourd'hui" value={initialStats.delivered_today} color="green" />
                    <StatCard icon={<XCircle className="text-red-500" />} label="Annulées aujourd'hui" value={initialStats.cancelled_today} color="red" />
                </div>

                <div className="grid gap-6 lg:grid-cols-2">
                    {/* Pie Chart */}
                    <div className="rounded-xl border border-sidebar-border/70 bg-white p-4 dark:bg-sidebar dark:border-sidebar-border">
                        <h2 className="mb-4 text-sm font-semibold text-gray-700 dark:text-gray-300">Répartition des commissions</h2>
                        {pieData.length > 0 ? (
                            <ResponsiveContainer width="100%" height={240}>
                                <PieChart>
                                    <Pie data={pieData} cx="50%" cy="50%" innerRadius={60} outerRadius={100} paddingAngle={4} dataKey="value" label>
                                        {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                                    </Pie>
                                    <Legend />
                                    <Tooltip />
                                </PieChart>
                            </ResponsiveContainer>
                        ) : (
                            <div className="flex h-[240px] items-center justify-center text-gray-400">Aucune donnée</div>
                        )}
                    </div>

                    {/* Active Delivery Plan */}
                    <div className="rounded-xl border border-sidebar-border/70 bg-white p-4 dark:bg-sidebar dark:border-sidebar-border">
                        <h2 className="mb-4 text-sm font-semibold text-gray-700 dark:text-gray-300">Plan de livraison actif</h2>
                        {initialPlan && (
                            <p className="mb-3 text-xs text-muted-foreground">
                                Priorité: {initialPlan.is_critical ? 'Critique' : 'Standard'}
                            </p>
                        )}
                        {initialPlan && initialPlan.sequence.length > 0 ? (
                            <ol className="space-y-2">
                                {initialPlan.sequence.map((orderId, i) => {
                                    const estimated = initialPlan.estimated_times?.[String(orderId)];

                                    return (
                                        <li key={orderId} className="flex items-center gap-3 text-sm">
                                            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-100 text-xs font-bold text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                                                {i + 1}
                                            </span>
                                            <span className="flex-1 font-medium">
                                                {estimated ? `${estimated.departure_room} → ${estimated.arrival_room}` : `Commission #${orderId}`}
                                            </span>
                                            {estimated && (
                                                <span className="text-xs text-gray-400">~{estimated.predicted_minutes} min</span>
                                            )}
                                        </li>
                                    );
                                })}
                            </ol>
                        ) : (
                            <div className="flex h-[200px] items-center justify-center text-gray-400">
                                <Package className="mr-2 h-5 w-5" /> Aucune livraison planifiée
                            </div>
                        )}

                        {queuedPlans.length > 0 && (
                            <div className="mt-4 border-t pt-3">
                                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Plans en attente</h3>
                                <ul className="space-y-1 text-sm">
                                    {queuedPlans.map((plan) => (
                                        <li key={plan.id} className="flex items-center justify-between">
                                            <span>Plan #{plan.id} ({plan.is_critical ? 'Critique' : 'Standard'})</span>
                                            <span className="text-xs text-muted-foreground">{plan.sequence.length} commissions</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </div>
                </div>

                {/* Recent Orders Table */}
                <div className="rounded-xl border border-sidebar-border/70 bg-white dark:bg-sidebar dark:border-sidebar-border">
                    <div className="border-b border-sidebar-border/70 px-4 py-3 dark:border-sidebar-border">
                        <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Commissions récentes</h2>
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
                                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">DT départ</th>
                                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">DT arrivée</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100 dark:divide-sidebar-border/50">
                                {initialOrders.length === 0 ? (
                                    <tr>
                                        <td colSpan={7} className="px-4 py-8 text-center text-gray-400">Aucune commission</td>
                                    </tr>
                                ) : initialOrders.map(order => (
                                    <tr key={order.id} className="hover:bg-gray-50 dark:hover:bg-sidebar-accent/20">
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
                                        <td className="px-4 py-3 text-xs text-gray-500">
                                            {order.dt_date_depart ? new Date(order.dt_date_depart).toLocaleString('fr-FR') : '—'}
                                        </td>
                                        <td className="px-4 py-3 text-xs text-gray-500">
                                            {order.dt_date_arrivee ? new Date(order.dt_date_arrivee).toLocaleString('fr-FR') : '—'}
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

function StatCard({ icon, label, value, color }: { icon: React.ReactNode; label: string; value: number; color: string }) {
    return (
        <div className="flex items-center gap-4 rounded-xl border border-sidebar-border/70 bg-white p-4 dark:bg-sidebar dark:border-sidebar-border">
            <div className={`flex h-10 w-10 items-center justify-center rounded-lg bg-${color}-50 dark:bg-${color}-900/20`}>
                {icon}
            </div>
            <div>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">{value}</p>
                <p className="text-xs text-gray-500">{label}</p>
            </div>
        </div>
    );
}

ManagerDashboard.layout = {
    breadcrumbs: [{ title: 'Tableau de bord', href: dashboard() }],
};
