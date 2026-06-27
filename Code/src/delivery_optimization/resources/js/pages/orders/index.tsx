import { Head, router, useForm } from '@inertiajs/react';
import { AlertTriangle, Plus, Search, Filter, Eye, FileSpreadsheet, FileScan, Package, Send } from 'lucide-react';
import type { ReactNode } from 'react';
import { useState } from 'react';
import * as ordersRoute from '@/actions/App/Http/Controllers/OrderController';
import { OrderStatusBadge } from '@/components/order-status-badge';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useEchoChannel } from '@/hooks/use-echo';
import { useFlashToast } from '@/hooks/use-flash-toast';
import type { Auth, Medication, Order, Room, PageProps, PaginatedData } from '@/types';
import { toast } from 'sonner';

type LegacyOrderRelations = {
    departure_room?: Room;
    arrival_room?: Room;
};

function getDepartureRoomName(order: Order): string {
    const legacyOrder = order as Order & LegacyOrderRelations;

    return order.departure_room?.name ?? legacyOrder.departure_room?.name ?? '—';
}

function getArrivalRoomName(order: Order): string {
    const legacyOrder = order as Order & LegacyOrderRelations;

    return order.arrival_room?.name ?? legacyOrder.arrival_room?.name ?? '—';
}

type Props = PageProps & {
    auth: Auth;
    orders: PaginatedData<Order>;
    rooms: Room[];
    medications: Medication[];
    filters: {
        status?: string;
        departure_room_id?: string;
    };
};

type OrderFormData = {
    arrival_room_id: string;
    expected_delivery_at: string;
    is_critical: boolean;
    medication_ids: number[];
    notes: string;
};

export default function OrdersIndex({ orders, rooms, medications, filters, auth }: Props) {
    const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [ocrLoading, setOcrLoading] = useState(false);
    const [dispatchingOrderId, setDispatchingOrderId] = useState<number | null>(null);
    const [initializingPlanning, setInitializingPlanning] = useState(false);
    const [excelInputId] = useState('bulk-excel-import');
    const [ocrInputId] = useState('bulk-ocr-import');
    const {
        data: createData,
        setData: setCreateData,
        post: postCreateOrder,
        processing: createProcessing,
        errors: createErrors,
        reset: resetCreateForm,
    } = useForm<OrderFormData>({
        arrival_room_id: '',
        expected_delivery_at: '',
        is_critical: false,
        medication_ids: [],
        notes: '',
    });

    useFlashToast();

    // Real-time updates: listen for new orders and status changes
    useEchoChannel('orders', {
        OrderCreated: (evt: any) => {
            toast.success(`Nouvelle commission créée: ${evt.order.reference}`);
            router.reload({
                only: ['orders'],
            });
        },
        OrderStatusUpdated: (evt: any) => {
            toast.success(`Statut de la commission mise à jour: ${evt.order.reference}`);
            router.reload({
                only: ['orders'],
            });
        },
    });

    function applyFilters(e: React.FormEvent<HTMLFormElement>) {
        e.preventDefault();
        const form = e.currentTarget;
        const data = new FormData(form);
        router.get(
            ordersRoute.index.url(),
            Object.fromEntries(data.entries()),
            { preserveState: true, replace: true },
        );
    }

    function clearFilters() {
        router.get(ordersRoute.index.url(), {}, { preserveState: false, replace: true });
    }

    function toggleMedication(id: number) {
        if (createData.medication_ids.includes(id)) {
            setCreateData('medication_ids', createData.medication_ids.filter((item) => item !== id));

            return;
        }

        setCreateData('medication_ids', [...createData.medication_ids, id]);
    }

    function handleCreateSubmit(e: React.FormEvent<HTMLFormElement>) {
        e.preventDefault();

        postCreateOrder(ordersRoute.store.url(), {
            preserveScroll: true,
            onSuccess: () => {
                resetCreateForm();
                setShowCreateModal(false);
            },
        });
    }

    function handleDispatchToDt(orderId: number) {
        setDispatchingOrderId(orderId);

        router.post(ordersRoute.dispatchRemoteSocket.url({ order: orderId }), {}, {
            preserveScroll: true,
            onFinish: () => setDispatchingOrderId(null),
        });
    }

    function handleInitializePlanning() {
        setInitializingPlanning(true);

        router.post(ordersRoute.initializePlanning.url(), {}, {
            preserveScroll: true,
            onFinish: () => setInitializingPlanning(false),
        });
    }

    async function handleExcelImport(e: React.ChangeEvent<HTMLInputElement>) {
        const input = e.currentTarget;
        const file = input.files?.[0];

        if (!file) {
            return;
        }

        const formData = new FormData();
        formData.append('file', file);
        const csrfToken = document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content;

        const response = await fetch(ordersRoute.importExcel.url(), {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                ...(csrfToken ? { 'X-CSRF-TOKEN': csrfToken } : {}),
            },
            credentials: 'same-origin',
        });

        if (response.ok) {
            await router.reload({
                only: ['orders'],
            });
        }

        input.value = '';
    }

    async function handleOcrImport(e: React.ChangeEvent<HTMLInputElement>) {
        const input = e.currentTarget;
        const file = input.files?.[0];

        if (!file) {
            return;
        }

        setOcrLoading(true);

        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch(ordersRoute.importOcr.url(), {
                method: 'POST',
                body: formData,
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });

            if (response.ok) {
                router.reload({ only: ['orders'] });
            }
        } finally {
            setOcrLoading(false);
            input.value = '';
        }
    }

    const isManager = auth.user.role === 'manager';

    return (
        <>
            <Head title="Commissions" />

            <div className="flex h-full flex-1 flex-col gap-6 p-4 md:p-6">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold tracking-tight">Commissions</h1>
                        <p className="text-muted-foreground">Gérez les commissions</p>
                    </div>
                    <div className="flex items-center gap-2">
                        {!isManager && (
                            <>
                                <Button
                                    type="button"
                                    variant="default"
                                    disabled={initializingPlanning}
                                    onClick={handleInitializePlanning}
                                >
                                    <Send className="mr-2 h-4 w-4" />
                                    {initializingPlanning ? 'Initialisation...' : 'Planifier'}
                                </Button>

                                <input
                                    id={excelInputId}
                                    type="file"
                                    className="hidden"
                                    accept=".xlsx,.xls,.csv"
                                    onChange={handleExcelImport}
                                />
                                <Button
                                    type="button"
                                    variant="outline"
                                    onClick={() => document.getElementById(excelInputId)?.click()}
                                >
                                    <FileSpreadsheet className="mr-2 h-4 w-4" />
                                    Import Excel
                                </Button>

                                <input
                                    id={ocrInputId}
                                    type="file"
                                    className="hidden"
                                    accept=".pdf,image/*"
                                    onChange={handleOcrImport}
                                />
                                {/* <Button
                                    type="button"
                                    variant="outline"
                                    disabled={ocrLoading}
                                    onClick={() => document.getElementById(ocrInputId)?.click()}
                                >
                                    <FileScan className="mr-2 h-4 w-4" />
                                    {ocrLoading ? 'OCR...' : 'Import OCR'}
                                </Button> */}
                            </>
                        )}

                        {!isManager && (
                            <Button type="button" onClick={() => setShowCreateModal(true)}>
                                <Plus className="mr-2 h-4 w-4" />
                                Commission
                            </Button>
                        )}
                    </div>
                </div>

                {/* Filters */}
                <Card>
                    <CardHeader className="pb-3">
                        <CardTitle className="flex items-center gap-2 text-base">
                            <Filter className="h-4 w-4" />
                            Filtres
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <form onSubmit={applyFilters} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                            <select
                                name="status"
                                defaultValue={filters.status ?? ''}
                                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
                            >
                                <option value="">Tous les statuts</option>
                                <option value="pending">En attente</option>
                                <option value="in_transit">En cours</option>
                                <option value="delivered">Livré</option>
                                <option value="cancelled">Annulé</option>
                            </select>

                            <select
                                name="departure_room_id"
                                defaultValue={filters.departure_room_id ?? ''}
                                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
                            >
                                <option value="">Toutes les salles de départ</option>
                                {rooms.map((r) => (
                                    <option key={r.id} value={r.id}>{r.name}</option>
                                ))}
                            </select>

                            <div className="flex gap-2 sm:col-span-2 lg:col-span-3">
                                <Button type="submit" size="sm">
                                    <Search className="mr-1 h-3 w-3" />
                                    Filtrer
                                </Button>
                                <Button type="button" variant="outline" size="sm" onClick={clearFilters}>
                                    Réinitialiser
                                </Button>
                            </div>
                        </form>
                    </CardContent>
                </Card>

                {/* Orders table */}
                <Card>
                    <CardContent className="p-0">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Référence</TableHead>
                                    <TableHead>Départ</TableHead>
                                    <TableHead>Arrivée</TableHead>
                                    <TableHead>Date prévue</TableHead>
                                    <TableHead>Priorité</TableHead>
                                    <TableHead>Statut</TableHead>
                                    {isManager && <TableHead>Pharmacien</TableHead>}
                                    <TableHead className="text-right">Actions</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {orders.data.length === 0 ? (
                                    <TableRow>
                                        <TableCell colSpan={isManager ? 8 : 7} className="py-12 text-center text-muted-foreground">
                                            <Package className="mx-auto mb-3 h-10 w-10 opacity-30" />
                                            Aucune commission trouvée
                                        </TableCell>
                                    </TableRow>
                                ) : (
                                    orders.data.map((order) => (
                                        <TableRow key={order.id}>
                                            <TableCell className="font-mono text-sm font-medium">
                                                {order.reference}
                                                {order.planned_sequence && (
                                                    <Badge variant="outline" className="ml-2 text-xs">
                                                        #{order.planned_sequence}
                                                    </Badge>
                                                )}
                                            </TableCell>
                                            <TableCell>{getDepartureRoomName(order)}</TableCell>
                                            <TableCell>{getArrivalRoomName(order)}</TableCell>
                                            <TableCell>
                                                {order.expected_delivery_at
                                                    ? new Date(order.expected_delivery_at).toLocaleString('fr-FR', {
                                                        dateStyle: 'short',
                                                        timeStyle: 'short',
                                                    })
                                                    : '—'}
                                            </TableCell>
                                            <TableCell>
                                                {order.is_critical ? (
                                                    <Badge variant="destructive" className="gap-1">
                                                        <AlertTriangle className="h-3.5 w-3.5" />
                                                        Critique
                                                    </Badge>
                                                ) : (
                                                    <Badge variant="secondary">Standard</Badge>
                                                )}
                                            </TableCell>
                                            <TableCell>
                                                <OrderStatusBadge status={order.status} />
                                            </TableCell>
                                            {isManager && (
                                                <TableCell className="text-sm text-muted-foreground">
                                                    {order.creator?.name ?? '—'}
                                                </TableCell>
                                            )}
                                            <TableCell className="text-right">
                                                <div className="flex items-center justify-end gap-2">
                                                    {isManager && (
                                                        <Button
                                                            type="button"
                                                            variant="outline"
                                                            size="sm"
                                                            disabled={dispatchingOrderId === order.id}
                                                            onClick={() => handleDispatchToDt(order.id)}
                                                        >
                                                            <Send className="mr-1.5 h-4 w-4" />
                                                            {dispatchingOrderId === order.id ? 'Envoi...' : 'Envoyer au DT'}
                                                        </Button>
                                                    )}
                                                    <Button variant="ghost" size="sm" onClick={() => setSelectedOrder(order)}>
                                                        <Eye className="h-4 w-4" />
                                                    </Button>
                                                </div>
                                            </TableCell>
                                        </TableRow>
                                    ))
                                )}
                            </TableBody>
                        </Table>
                    </CardContent>
                </Card>

                {/* Pagination */}
                {orders.last_page > 1 && (
                    <div className="flex justify-center gap-2">
                        {orders.links.map((link) => (
                            <Button
                                key={link.label}
                                variant={link.active ? 'default' : 'outline'}
                                size="sm"
                                disabled={!link.url}
                                onClick={() => link.url && router.visit(link.url, { preserveState: true })}
                                dangerouslySetInnerHTML={{ __html: link.label }}
                            />
                        ))}
                    </div>
                )}

                <Dialog open={selectedOrder !== null} onOpenChange={(open) => !open && setSelectedOrder(null)}>
                    <DialogContent className="max-w-2xl">
                        {selectedOrder && (
                            <>
                                <DialogHeader>
                                    <DialogTitle className="font-mono">{selectedOrder.reference}</DialogTitle>
                                    <DialogDescription>Détails de la commission</DialogDescription>
                                </DialogHeader>

                                <div className="grid gap-4 sm:grid-cols-2">
                                    <Info label="Statut" value={<OrderStatusBadge status={selectedOrder.status} />} />
                                    <Info
                                        label="Priorité"
                                        value={selectedOrder.is_critical
                                            ? <Badge variant="destructive">Critique</Badge>
                                            : <Badge variant="secondary">Standard</Badge>}
                                    />
                                    <Info label="Séquence" value={selectedOrder.planned_sequence ? `#${selectedOrder.planned_sequence}` : '—'} />
                                    <Info label="Salle de départ" value={getDepartureRoomName(selectedOrder)} />
                                    <Info label="Salle d'arrivée" value={getArrivalRoomName(selectedOrder)} />
                                    <Info
                                        label="Livraison prévue"
                                        value={selectedOrder.expected_delivery_at
                                            ? new Date(selectedOrder.expected_delivery_at).toLocaleString('fr-FR')
                                            : '—'}
                                    />
                                    <Info
                                        label="Créée le"
                                        value={selectedOrder.created_at
                                            ? new Date(selectedOrder.created_at).toLocaleString('fr-FR')
                                            : '—'}
                                    />
                                </div>

                                {selectedOrder.content && (
                                    <div className="rounded-lg border bg-muted/30 p-3">
                                        <p className="mb-1 text-xs font-semibold text-muted-foreground">Contenu</p>
                                        <p className="text-sm">{selectedOrder.content}</p>
                                    </div>
                                )}
                            </>
                        )}
                    </DialogContent>
                </Dialog>

                <Dialog
                    open={showCreateModal}
                    onOpenChange={(open) => {
                        setShowCreateModal(open);

                        if (!open) {
                            resetCreateForm();
                        }
                    }}
                >
                    <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
                        <DialogHeader>
                            <DialogTitle>Nouvelle commission</DialogTitle>
                            <DialogDescription>Créer un ordre de livraison (départ ajouté automatiquement)</DialogDescription>
                        </DialogHeader>

                        <form onSubmit={handleCreateSubmit} className="space-y-5">
                            <div className="space-y-1.5">
                                <label htmlFor="arrival_room_id" className="text-sm font-medium">
                                    Salle <span className="text-destructive">*</span>
                                </label>
                                <select
                                    id="arrival_room_id"
                                    value={createData.arrival_room_id}
                                    onChange={(e) => setCreateData('arrival_room_id', e.target.value)}
                                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
                                >
                                    <option value="">Sélectionner une salle</option>
                                    {rooms.map((room) => (
                                        <option key={room.id} value={room.id}>
                                            {room.name}
                                        </option>
                                    ))}
                                </select>
                                {createErrors.arrival_room_id && (
                                    <p className="text-sm text-destructive">{createErrors.arrival_room_id}</p>
                                )}
                            </div>

                            <div className="space-y-1.5">
                                <label htmlFor="expected_delivery_at" className="text-sm font-medium">
                                    Date <span className="text-destructive">*</span>
                                </label>
                                <input
                                    id="expected_delivery_at"
                                    type="datetime-local"
                                    value={createData.expected_delivery_at}
                                    onChange={(e) => setCreateData('expected_delivery_at', e.target.value)}
                                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
                                />
                                {createErrors.expected_delivery_at && (
                                    <p className="text-sm text-destructive">{createErrors.expected_delivery_at}</p>
                                )}
                            </div>

                            <label className="flex items-center gap-2 rounded-md border p-3 text-sm">
                                <input
                                    type="checkbox"
                                    checked={createData.is_critical}
                                    onChange={(e) => setCreateData('is_critical', e.target.checked)}
                                    className="h-4 w-4"
                                />
                                <span className="font-medium">Commission critique</span>
                            </label>

                            <div className="space-y-2">
                                <p className="text-sm font-medium">
                                    Médicaments <span className="text-destructive">*</span>
                                </p>
                                <div className="flex flex-wrap gap-2 rounded-lg border bg-muted/20 p-3">
                                    {medications.map((medication) => {
                                        const selected = createData.medication_ids.includes(medication.id);

                                        return (
                                            <button
                                                key={medication.id}
                                                type="button"
                                                onClick={() => toggleMedication(medication.id)}
                                                className={`rounded-full border px-3 py-1.5 text-sm transition ${
                                                    selected
                                                        ? 'border-primary bg-primary text-primary-foreground'
                                                        : 'border-border bg-background hover:border-primary/50'
                                                }`}
                                            >
                                                {medication.name}
                                            </button>
                                        );
                                    })}
                                </div>
                                {createData.medication_ids.length > 0 && (
                                    <div className="flex flex-wrap gap-2">
                                        {medications
                                            .filter((medication) => createData.medication_ids.includes(medication.id))
                                            .map((medication) => (
                                                <Badge key={medication.id} variant="secondary">
                                                    {medication.code}
                                                </Badge>
                                            ))}
                                    </div>
                                )}
                                {createErrors.medication_ids && (
                                    <p className="text-sm text-destructive">{createErrors.medication_ids}</p>
                                )}
                            </div>

                            <div className="space-y-1.5">
                                <label htmlFor="notes" className="text-sm font-medium">Notes</label>
                                <textarea
                                    id="notes"
                                    value={createData.notes}
                                    onChange={(e) => setCreateData('notes', e.target.value)}
                                    rows={3}
                                    className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm"
                                    placeholder="Commentaire optionnel"
                                />
                                {createErrors.notes && (
                                    <p className="text-sm text-destructive">{createErrors.notes}</p>
                                )}
                            </div>

                            <div className="flex justify-end gap-3">
                                <Button type="button" variant="outline" onClick={() => setShowCreateModal(false)}>
                                    Annuler
                                </Button>
                                <Button type="submit" disabled={createProcessing}>
                                    {createProcessing ? 'Envoi...' : 'Créer la commission'}
                                </Button>
                            </div>
                        </form>
                    </DialogContent>
                </Dialog>
            </div>
        </>
    );
}

function Info({ label, value }: { label: string; value: ReactNode }) {
    return (
        <div className="rounded-md border p-3">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
            <div className="mt-1 text-sm">{value}</div>
        </div>
    );
}