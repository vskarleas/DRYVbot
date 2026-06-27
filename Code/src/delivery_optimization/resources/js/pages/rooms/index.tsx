import { Head, router, useForm } from '@inertiajs/react';
import { useState } from 'react';
import { Plus, Pencil, Trash2, Building } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { useFlashToast } from '@/hooks/use-flash-toast';
import * as roomsRoute from '@/actions/App/Http/Controllers/RoomController';
import type { Room, PageProps, PaginatedData } from '@/types';

type Props = PageProps & {
    rooms: PaginatedData<Room>;
};

type RoomFormData = {
    name: string;
    code: string;
    building: string;
    floor: string;
    description: string;
};

export default function RoomsIndex({ rooms }: Props) {
    useFlashToast();

    const [editingRoom, setEditingRoom] = useState<Room | null>(null);
    const [showCreateForm, setShowCreateForm] = useState(false);

    const { data, setData, post, put, processing, errors, reset } = useForm<RoomFormData>({
        name: '',
        code: '',
        building: '',
        floor: '',
        description: '',
    });

    function startEdit(room: Room) {
        setEditingRoom(room);
        setShowCreateForm(false);
        setData({
            name: room.name,
            code: room.code,
            building: room.building ?? '',
            floor: room.floor ?? '',
            description: '',
        });
    }

    function handleCreate(e: React.FormEvent) {
        e.preventDefault();
        post(roomsRoute.store.url(), {
            onSuccess: () => {
                reset();
                setShowCreateForm(false);
            },
        });
    }

    function handleUpdate(e: React.FormEvent) {
        e.preventDefault();
        if (!editingRoom) return;
        router.put(roomsRoute.update.url({ room: editingRoom.id }), data as Record<string, string>, {
            onSuccess: () => {
                reset();
                setEditingRoom(null);
            },
        });
    }

    function handleDelete(room: Room) {
        if (!confirm(`Supprimer la salle "${room.name}" ?`)) return;
        router.delete(roomsRoute.destroy.url({ room: room.id }), { preserveState: true });
    }

    return (
        <>
            <Head title="Salles" />

            <div className="flex h-full flex-1 flex-col gap-6 p-4 md:p-6">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold tracking-tight">Salles</h1>
                        <p className="text-muted-foreground">Gérez les salles de départ et d'arrivée</p>
                    </div>
                    <Button onClick={() => { setShowCreateForm(true); setEditingRoom(null); reset(); }}>
                        <Plus className="mr-2 h-4 w-4" />
                        Ajouter une salle
                    </Button>
                </div>

                {/* Create / Edit form */}
                {(showCreateForm || editingRoom) && (
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base">
                                {editingRoom ? `Modifier "${editingRoom.name}"` : 'Nouvelle salle'}
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <form onSubmit={editingRoom ? handleUpdate : handleCreate}
                                className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                                <div className="space-y-1.5">
                                    <Label htmlFor="name">Nom <span className="text-destructive">*</span></Label>
                                    <Input
                                        id="name"
                                        value={data.name}
                                        onChange={(e) => setData('name', e.target.value)}
                                        placeholder="Pharmacie centrale"
                                    />
                                    {errors.name && <p className="text-xs text-destructive">{errors.name}</p>}
                                </div>
                                <div className="space-y-1.5">
                                    <Label htmlFor="code">Code <span className="text-destructive">*</span></Label>
                                    <Input
                                        id="code"
                                        value={data.code}
                                        onChange={(e) => setData('code', e.target.value.toUpperCase())}
                                        placeholder="PHARMA-01"
                                    />
                                    {errors.code && <p className="text-xs text-destructive">{errors.code}</p>}
                                </div>
                                <div className="space-y-1.5">
                                    <Label htmlFor="building">Bâtiment</Label>
                                    <Input
                                        id="building"
                                        value={data.building}
                                        onChange={(e) => setData('building', e.target.value)}
                                        placeholder="Bâtiment A"
                                    />
                                </div>
                                <div className="space-y-1.5">
                                    <Label htmlFor="floor">Étage</Label>
                                    <Input
                                        id="floor"
                                        value={data.floor}
                                        onChange={(e) => setData('floor', e.target.value)}
                                        placeholder="2ème étage"
                                    />
                                </div>
                                <div className="sm:col-span-2 space-y-1.5">
                                    <Label htmlFor="description">Description</Label>
                                    <Input
                                        id="description"
                                        value={data.description}
                                        onChange={(e) => setData('description', e.target.value)}
                                    />
                                </div>
                                <div className="sm:col-span-2 lg:col-span-3 flex gap-2">
                                    <Button type="submit" size="sm" disabled={processing}>
                                        {editingRoom ? 'Mettre à jour' : 'Créer'}
                                    </Button>
                                    <Button
                                        type="button"
                                        variant="outline"
                                        size="sm"
                                        onClick={() => { setShowCreateForm(false); setEditingRoom(null); reset(); }}
                                    >
                                        Annuler
                                    </Button>
                                </div>
                            </form>
                        </CardContent>
                    </Card>
                )}

                {/* Rooms table */}
                <Card>
                    <CardContent className="p-0">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Nom</TableHead>
                                    <TableHead>Code</TableHead>
                                    <TableHead>Bâtiment</TableHead>
                                    <TableHead>Étage</TableHead>
                                    <TableHead>Statut</TableHead>
                                    <TableHead className="text-right">Actions</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {rooms.data.length === 0 ? (
                                    <TableRow>
                                        <TableCell colSpan={6} className="py-12 text-center text-muted-foreground">
                                            <Building className="mx-auto mb-3 h-10 w-10 opacity-30" />
                                            Aucune salle enregistrée
                                        </TableCell>
                                    </TableRow>
                                ) : (
                                    rooms.data.map((room) => (
                                        <TableRow key={room.id}>
                                            <TableCell className="font-medium">{room.name}</TableCell>
                                            <TableCell className="font-mono text-sm">{room.code}</TableCell>
                                            <TableCell>{room.building ?? '—'}</TableCell>
                                            <TableCell>{room.floor ?? '—'}</TableCell>
                                            <TableCell>
                                                <Badge variant={room.is_active ? 'default' : 'secondary'}>
                                                    {room.is_active ? 'Active' : 'Inactive'}
                                                </Badge>
                                            </TableCell>
                                            <TableCell className="text-right">
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={() => startEdit(room)}
                                                >
                                                    <Pencil className="h-3.5 w-3.5" />
                                                </Button>
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    className="text-destructive hover:text-destructive"
                                                    onClick={() => handleDelete(room)}
                                                >
                                                    <Trash2 className="h-3.5 w-3.5" />
                                                </Button>
                                            </TableCell>
                                        </TableRow>
                                    ))
                                )}
                            </TableBody>
                        </Table>
                    </CardContent>
                </Card>
            </div>
        </>
    );
}
