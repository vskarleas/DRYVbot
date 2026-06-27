export type OrderStatus = 'pending' | 'in_transit' | 'delivered' | 'cancelled';

export type Room = {
    id: number;
    name: string;
    code: string;
    building: string | null;
    floor: string | null;
    description: string | null;
    is_active: boolean;
    created_at: string;
    updated_at: string;
};

export type Order = {
    id: number;
    reference: string;
    created_by: number;
    departure_room_id: number;
    arrival_room_id: number;
    expected_delivery_at: string;
    status: OrderStatus;
    is_critical: boolean;
    planned_sequence: number | null;
    content: string | null;
    attachment_path: string | null;
    notes: string | null;
    // Digital Twin data
    dt_salle_id_depart: string | null;
    dt_salle_id_arrivee: string | null;
    dt_date_depart: string | null;
    dt_date_arrivee: string | null;
    dt_duree: {
        annee: number | null;
        mois: number | null;
        jour: number | null;
        heure: number | null;
        minute: number | null;
    } | null;
    cancelled_by: number | null;
    cancellation_reason: string | null;
    cancelled_at: string | null;
    delivered_at: string | null;
    created_at: string;
    updated_at: string;
    // Relations
    departure_room?: Room;
    arrival_room?: Room;
    arrivalRoom?: Room;
    creator?: { id: number; name: string; email: string };
    cancelled_by_user?: { id: number; name: string };
};

export type DeliveryPlan = {
    id: number;
    current_room_id: number | null;
    status: 'queued' | 'active' | 'completed';
    is_critical: boolean;
    sequence: number[];
    estimated_times: Record<string, {
        sequence: number;
        predicted_minutes: number;
        departure_room: string;
        arrival_room: string;
    }> | null;
    created_at: string;
    updated_at: string;
    current_room?: Room;
};

export type PaginatedData<T> = {
    data: T[];
    current_page: number;
    last_page: number;
    per_page: number;
    total: number;
    links: { url: string | null; label: string; active: boolean }[];
};

export type PageProps = {
    flash: {
        success?: string;
        error?: string;
    };
};
