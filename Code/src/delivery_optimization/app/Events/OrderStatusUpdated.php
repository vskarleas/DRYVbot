<?php

namespace App\Events;

use App\Models\Order;
use Illuminate\Broadcasting\Channel;
use Illuminate\Broadcasting\InteractsWithSockets;
use Illuminate\Contracts\Broadcasting\ShouldBroadcastNow;
use Illuminate\Foundation\Events\Dispatchable;
use Illuminate\Queue\SerializesModels;

class OrderStatusUpdated implements ShouldBroadcastNow
{
    use Dispatchable, InteractsWithSockets, SerializesModels;

    public function __construct(public readonly Order $order) {}

    /** @return array<int, Channel> */
    public function broadcastOn(): array
    {
        return [
            new Channel('orders'),
        ];
    }

    /** @return array<string, mixed> */
    public function broadcastWith(): array
    {
        return [
            'order' => [
                'id' => $this->order->id,
                'reference' => $this->order->reference,
                'status' => $this->order->status->value,
                'status_label' => $this->order->status->label(),
                'status_color' => $this->order->status->color(),
                'delivered_at' => $this->order->delivered_at?->toIso8601String(),
                'cancelled_at' => $this->order->cancelled_at?->toIso8601String(),
                'dt_date_depart' => $this->order->dt_date_depart?->toIso8601String(),
                'dt_date_arrivee' => $this->order->dt_date_arrivee?->toIso8601String(),
                'dt_duree' => $this->order->dt_duree,
            ],
        ];
    }
}
