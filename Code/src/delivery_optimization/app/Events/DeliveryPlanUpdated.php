<?php

namespace App\Events;

use App\Models\DeliveryPlan;
use Illuminate\Broadcasting\Channel;
use Illuminate\Broadcasting\InteractsWithSockets;
use Illuminate\Contracts\Broadcasting\ShouldBroadcastNow;
use Illuminate\Foundation\Events\Dispatchable;
use Illuminate\Queue\SerializesModels;

class DeliveryPlanUpdated implements ShouldBroadcastNow
{
    use Dispatchable, InteractsWithSockets, SerializesModels;

    public function __construct(public readonly DeliveryPlan $plan) {}

    /** @return array<int, Channel> */
    public function broadcastOn(): array
    {
        return [
            new Channel('delivery-plan'),
        ];
    }

    /** @return array<string, mixed> */
    public function broadcastWith(): array
    {
        return [
            'plan' => [
                'id' => $this->plan->id,
                'sequence' => $this->plan->sequence,
                'estimated_times' => $this->plan->estimated_times,
                'current_room_id' => $this->plan->current_room_id,
                'updated_at' => $this->plan->updated_at?->toIso8601String(),
            ],
        ];
    }
}
