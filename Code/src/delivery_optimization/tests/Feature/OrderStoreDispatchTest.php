<?php

use App\Events\OrderCreated;
use App\Models\Medication;
use App\Models\Room;
use App\Models\User;
use App\Services\DtOutboundQueueService;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\Event;

it('does not queue DT room command when a pharmacist creates an order', function () {
    Event::fake([OrderCreated::class]);

    $pharmacist = User::factory()->pharmacist()->create();

    $departureRoom = Room::query()->create([
        'name' => 'Pharmacie',
        'code' => 'salle_pharmacie',
        'is_active' => true,
        'x' => 0,
        'y' => 0,
        'orientation_w' => 1,
        'aliases' => [],
    ]);

    $arrivalRoom = Room::query()->create([
        'name' => 'Salle 101',
        'code' => 'salle_101',
        'is_active' => true,
        'x' => 1,
        'y' => 1,
        'orientation_w' => 1,
        'aliases' => [],
    ]);

    $medication = Medication::query()->create([
        'name' => 'Paracetamol',
        'code' => 'paracetamol',
        'is_active' => true,
    ]);

    $response = $this
        ->actingAs($pharmacist)
        ->post(route('orders.store'), [
            'arrival_room_id' => $arrivalRoom->id,
            'expected_delivery_at' => Carbon::now()->addHour()->toIso8601String(),
            'medication_ids' => [$medication->id],
            'notes' => 'Test dispatch immediate',
        ]);

    $response->assertRedirect(route('orders.index'));

    Event::assertDispatched(OrderCreated::class);

    /** @var DtOutboundQueueService $outboundQueue */
    $outboundQueue = app(DtOutboundQueueService::class);
    $messages = $outboundQueue->all();

    expect($messages)->toBe([]);
});
