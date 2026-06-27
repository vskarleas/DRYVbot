<?php

namespace App\Http\Controllers\Api;

use App\Enums\OrderStatus;
use App\Events\DtDataReceived;
use App\Events\OrderStatusUpdated;
use App\Http\Controllers\Controller;
use App\Models\Order;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class DtWebhookController extends Controller
{
    /**
     * Receive data from the Digital Twin and update the corresponding order.
     * Expected payload: { order_id, salle_id_depart, salle_id_arrivee,
     *   date_depart, date_arrivee, duree: { annee, mois, jour, heure, minute },
     *   status (optional) }
     */
    public function receive(Request $request): JsonResponse
    {
        \Log::info('Received DT webhook data', ['payload' => $request->all()]);
        $data = $request->validate([
            'order_id' => ['required', 'exists:orders,id'],
            'salle_id_depart' => ['required', 'string'],
            'salle_id_arrivee' => ['required', 'string'],
            'date_depart' => ['required', 'date'],
            'date_arrivee' => ['required', 'date'],
            'duree' => ['required', 'array'],
            'duree.annee' => ['required', 'integer', 'min:0'],
            'duree.mois' => ['required', 'integer', 'min:0', 'max:11'],
            'duree.jour' => ['required', 'integer', 'min:0', 'max:30'],
            'duree.heure' => ['required', 'integer', 'min:0', 'max:23'],
            'duree.minute' => ['required', 'integer', 'min:0', 'max:59'],
            'status' => ['nullable', 'in:in_transit,delivered'],
        ]);

        $order = Order::findOrFail($data['order_id']);

        $order->update([
            'dt_salle_id_depart' => $data['salle_id_depart'],
            'dt_salle_id_arrivee' => $data['salle_id_arrivee'],
            'dt_date_depart' => $data['date_depart'],
            'dt_date_arrivee' => $data['date_arrivee'],
            'dt_duree_annee' => $data['duree']['annee'],
            'dt_duree_mois' => $data['duree']['mois'],
            'dt_duree_jour' => $data['duree']['jour'],
            'dt_duree_heure' => $data['duree']['heure'],
            'dt_duree_minute' => $data['duree']['minute'],
        ]);

        // If the DT says delivered, mark the order without creating a new global plan.
        if (isset($data['status']) && $data['status'] === 'delivered') {
            $order->update(['status' => OrderStatus::Delivered, 'delivered_at' => now()]);
            OrderStatusUpdated::dispatch($order->fresh());
        } elseif ($order->status === OrderStatus::Pending) {
            $order->update(['status' => OrderStatus::InTransit]);
            OrderStatusUpdated::dispatch($order->fresh());
        }

        DtDataReceived::dispatch($order->fresh());

        return response()->json(['message' => 'Data received', 'order_id' => $order->id]);
    }
}
