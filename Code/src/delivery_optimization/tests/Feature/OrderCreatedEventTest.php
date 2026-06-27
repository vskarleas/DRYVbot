<?php

use App\Enums\OrderStatus;
use App\Events\OrderCreated;
use App\Models\Order;
use App\Models\Room;
use App\Models\User;

it('broadcasts arrival room as object in OrderCreated payload', function () {
    $pharmacist = User::factory()->pharmacist()->create();

    $arrivalRoom = Room::factory()->create([
        'name' => 'Salle 201',
        'code' => 'salle_201',
    ]);

    $order = Order::factory()->create([
        'created_by' => $pharmacist->id,
        'arrival_room_id' => $arrivalRoom->id,
        'status' => OrderStatus::Pending,
    ])->fresh(['arrivalRoom']);

    $event = new OrderCreated($order);
    $payload = $event->broadcastWith();

    expect($payload['order']['arrival_room'])->toBeArray()
        ->and($payload['order']['arrival_room']['id'])->toBe($arrivalRoom->id)
        ->and($payload['order']['arrival_room']['name'])->toBe('Salle 201')
        ->and($payload['order']['arrival_room']['code'])->toBe('salle_201');
});
