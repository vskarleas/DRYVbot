<?php

namespace App\Events;

use App\Models\Order;
use Illuminate\Broadcasting\Channel;
use Illuminate\Broadcasting\InteractsWithSockets;
use Illuminate\Contracts\Broadcasting\ShouldBroadcastNow;
use Illuminate\Foundation\Events\Dispatchable;
use Illuminate\Queue\SerializesModels;

class OrderCreated implements ShouldBroadcastNow
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
        $departureRoom = $this->order->departureRoom;
        $arrivalRoom = $this->order->arrivalRoom;

        return [
            'order' => [
                'id' => $this->order->id,
                'reference' => $this->order->reference,
                'status' => $this->order->status->value,
                'status_label' => $this->order->status->label(),
                'departure_room' => $departureRoom !== null ? [
                    'id' => $departureRoom->id,
                    'name' => $departureRoom->name,
                    'code' => $departureRoom->code,
                ] : null,
                'arrival_room' => $arrivalRoom !== null ? [
                    'id' => $arrivalRoom->id,
                    'name' => $arrivalRoom->name,
                    'code' => $arrivalRoom->code,
                ] : null,
                'expected_delivery_at' => $this->order->expected_delivery_at?->toIso8601String(),
                'created_at' => $this->order->created_at?->toIso8601String(),
            ],
        ];
    }
}
