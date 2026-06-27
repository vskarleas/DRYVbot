<?php

use App\Models\Order;
use App\Models\Room;
use App\Models\User;
use App\Services\DtOutboundQueueService;
use Illuminate\Support\Facades\Cache;

it('queues a remote DT room command from the orders listing action', function () {
    Cache::forget('dt:outbound_room_commands_queue');

    $manager = User::factory()->manager()->create();
    $arrivalRoom = Room::factory()->create([
        'code' => 'salle_102',
    ]);

    $order = Order::factory()->create([
        'created_by' => $manager->id,
        'arrival_room_id' => $arrivalRoom->id,
    ]);

    $response = $this
        ->from(route('orders.index'))
        ->actingAs($manager)
        ->post(route('orders.dispatch-remote-socket', ['order' => $order->id]));

    $response->assertRedirect(route('orders.index'));

    /** @var DtOutboundQueueService $outboundQueue */
    $outboundQueue = app(DtOutboundQueueService::class);

    expect($outboundQueue->all())->toBe([
        [
            'type' => 'room_command',
            'room' => 'salle_102',
        ],
    ]);
});