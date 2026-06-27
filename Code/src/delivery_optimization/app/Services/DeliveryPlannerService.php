<?php

namespace App\Services;

use App\Enums\OrderStatus;
use App\Events\DeliveryPlanUpdated;
use App\Models\DeliveryPlan;
use App\Models\Order;
use App\Models\Room;
use DateTimeInterface;
use Illuminate\Support\Carbon;
use Illuminate\Support\Collection;

class DeliveryPlannerService
{
    public function __construct(
        private readonly PredictionService $predictionService,
        private readonly DtTaskQueueService $dtTaskQueue,
    ) {}

    public const START_ROOM_CODE = 'salle_pharmacie';

    public const BATCH_WINDOW_MINUTES = 15;

    public function getActivePlan(): ?DeliveryPlan
    {
        return DeliveryPlan::query()
            ->where('status', 'active')
            ->latest('id')
            ->first();
    }

    public function getStartRoom(): ?Room
    {
        return Room::query()
            ->where('code', self::START_ROOM_CODE)
            ->first();
    }

    public function hasRemainingOrders(DeliveryPlan $plan): bool
    {
        $orderIds = $this->sequenceOrderIds($plan);

        if ($orderIds === []) {
            return false;
        }

        return Order::query()
            ->whereIn('id', $orderIds)
            ->whereIn('status', [OrderStatus::Pending->value, OrderStatus::InTransit->value])
            ->exists();
    }

    public function hasInTransitOrder(DeliveryPlan $plan): bool
    {
        $orderIds = $this->sequenceOrderIds($plan);

        if ($orderIds === []) {
            return false;
        }

        return Order::query()
            ->whereIn('id', $orderIds)
            ->where('status', OrderStatus::InTransit->value)
            ->exists();
    }

    public function initializeBatchPlan(?DateTimeInterface $referenceTime = null, int $windowMinutes = self::BATCH_WINDOW_MINUTES): ?DeliveryPlan
    {
        $activePlan = $this->getActivePlan();

        if ($activePlan !== null && $this->hasRemainingOrders($activePlan)) {
            return null;
        }

        if ($activePlan !== null) {
            $this->completePlan($activePlan, null);
        }

        // Any stale queued plans belong to a previous planning cycle.
        DeliveryPlan::query()
            ->where('status', 'queued')
            ->update(['status' => 'completed']);

        $startRoom = $this->getStartRoom();

        if ($startRoom === null) {
            return null;
        }

        $now = $referenceTime !== null ? Carbon::instance($referenceTime) : Carbon::now();
        $from = $now->copy()->subMinutes($windowMinutes);
        $to = $now->copy()->addMinutes($windowMinutes);

        /** @var Collection<int, Order> $pendingOrders */
        $pendingOrders = Order::query()
            ->where('status', OrderStatus::Pending->value)
            //->whereBetween('expected_delivery_at', [$from, $to])
            ->with(['departureRoom', 'arrivalRoom'])
            ->orderByDesc('is_critical')
            ->orderBy('expected_delivery_at')
            ->get();

        if ($pendingOrders->isEmpty()) {
            return null;
        }

        /** @var Collection<int, Order> $criticalOrders */
        $criticalOrders = $pendingOrders
            ->filter(static fn (Order $order): bool => $order->is_critical)
            ->values();

        /** @var Collection<int, Order> $nonCriticalOrders */
        $nonCriticalOrders = $pendingOrders
            ->filter(static fn (Order $order): bool => ! $order->is_critical)
            ->values();

        $criticalPlan = $this->createPlanFromOrders(
            orders: $criticalOrders,
            startRoom: $startRoom,
            status: 'active',
            isCritical: true,
            sequenceOffset: 0,
        );

        $criticalCount = $criticalPlan !== null
            ? count($this->sequenceOrderIds($criticalPlan))
            : 0;

        $nonCriticalPlan = $this->createPlanFromOrders(
            orders: $nonCriticalOrders,
            startRoom: $startRoom,
            status: $criticalPlan !== null ? 'queued' : 'active',
            isCritical: false,
            sequenceOffset: $criticalCount,
        );

        $plan = $criticalPlan ?? $nonCriticalPlan;

        if ($plan === null) {
            return null;
        }

        DeliveryPlanUpdated::dispatch($plan->fresh());
        $this->dtTaskQueue->refreshFromActivePlan();

        return $plan;
    }

    /**
     * Re-plan deliveries from the given current room position.
     * Uses a greedy nearest-neighbor algorithm based on predicted delivery times.
     */
    public function plan(Room $currentRoom): DeliveryPlan
    {
        $activePlan = $this->getActivePlan();

        if ($activePlan !== null) {
            $activeOrderIds = $this->sequenceOrderIds($activePlan);

            /** @var Collection<int, Order> $pendingOrders */
            $pendingOrders = Order::query()
                ->whereIn('id', $activeOrderIds)
                ->whereIn('status', [OrderStatus::Pending->value, OrderStatus::InTransit->value])
                ->with(['departureRoom', 'arrivalRoom'])
                ->orderBy('planned_sequence')
                ->orderBy('expected_delivery_at')
                ->get();

            if ($pendingOrders->isEmpty()) {
                return $activePlan;
            }

            $sequence = $this->computeSequence($pendingOrders, $currentRoom);
            $estimatedTimes = $this->computeEstimatedTimesFromRoom($sequence, $pendingOrders, $currentRoom);

            $activePlan->update([
                'current_room_id' => $currentRoom->id,
                'sequence' => $sequence,
                'estimated_times' => $estimatedTimes,
            ]);

            $this->syncOrderSequence($sequence, $pendingOrders, $currentRoom);

            DeliveryPlanUpdated::dispatch($activePlan->fresh());
            $this->dtTaskQueue->refreshFromActivePlan();

            return $activePlan->fresh();
        }

        /** @var Collection<int, Order> $pendingOrders */
        $pendingOrders = Order::query()
            ->whereIn('status', [OrderStatus::Pending->value, OrderStatus::InTransit->value])
            ->with(['departureRoom', 'arrivalRoom'])
            ->orderByDesc('is_critical')
            ->orderBy('expected_delivery_at')
            ->get();

        $sequence = $this->computeSequence($pendingOrders, $currentRoom);
        $estimatedTimes = $this->computeEstimatedTimesFromRoom($sequence, $pendingOrders, $currentRoom);

        // Deactivate the previous active plan
        DeliveryPlan::query()->where('status', 'active')->update(['status' => 'completed']);

        $plan = DeliveryPlan::create([
            'current_room_id' => $currentRoom->id,
            'status' => 'active',
            'is_critical' => (bool) $pendingOrders->first()?->is_critical,
            'sequence' => $sequence,
            'estimated_times' => $estimatedTimes,
        ]);

        $this->syncOrderSequence($sequence, $pendingOrders, $currentRoom);

        DeliveryPlanUpdated::dispatch($plan);
        $this->dtTaskQueue->refreshFromActivePlan();

        return $plan;
    }

    public function getNextQueuedPlan(): ?DeliveryPlan
    {
        return DeliveryPlan::query()
            ->where('status', 'queued')
            ->orderByDesc('is_critical')
            ->oldest('id')
            ->first();
    }

    public function activateNextQueuedPlan(Room $currentRoom): ?DeliveryPlan
    {
        $nextPlan = $this->getNextQueuedPlan();

        if ($nextPlan === null) {
            return null;
        }

        $nextPlan->update([
            'status' => 'active',
            'current_room_id' => $currentRoom->id,
        ]);

        $freshPlan = $nextPlan->fresh();

        DeliveryPlanUpdated::dispatch($freshPlan);
        $this->dtTaskQueue->refreshFromActivePlan();

        return $freshPlan;
    }

    public function recalculateRemainingSequence(DeliveryPlan $plan, Room $currentRoom): DeliveryPlan
    {
        $sequence = $this->sequenceOrderIds($plan);

        if ($sequence === []) {
            return $plan;
        }

        $orders = Order::query()
            ->whereIn('id', $sequence)
            ->with(['arrivalRoom', 'departureRoom'])
            ->get()
            ->keyBy('id');

        $completedOrderIds = [];
        $remainingOrders = collect();

        foreach ($sequence as $orderId) {
            /** @var Order|null $order */
            $order = $orders->get($orderId);

            if ($order === null) {
                continue;
            }

            if (in_array($order->status, [OrderStatus::Delivered, OrderStatus::Cancelled], true)) {
                $completedOrderIds[] = $orderId;

                continue;
            }

            $remainingOrders->put($orderId, $order);
        }

        if ($remainingOrders->isEmpty()) {
            $plan->update([
                'sequence' => $completedOrderIds,
                'estimated_times' => [],
                'current_room_id' => $currentRoom->id,
            ]);

            DeliveryPlanUpdated::dispatch($plan->fresh());
            $this->dtTaskQueue->refreshFromActivePlan();

            return $plan->fresh();
        }

        $remainingSequence = $this->computeSequence($remainingOrders->values(), $currentRoom);
        $newSequence = array_merge($completedOrderIds, $remainingSequence);
        $estimatedTimes = $this->computeEstimatedTimesFromRoom($remainingSequence, $remainingOrders->values(), $currentRoom);

        $plan->update([
            'sequence' => $newSequence,
            'estimated_times' => $estimatedTimes,
            'current_room_id' => $currentRoom->id,
        ]);

        $this->syncOrderSequence($newSequence, $orders->values(), null);

        DeliveryPlanUpdated::dispatch($plan->fresh());
        $this->dtTaskQueue->refreshFromActivePlan();

        return $plan->fresh();
    }

    public function findNextPendingOrderFromRoom(DeliveryPlan $plan, Room $currentRoom): ?Order
    {
        $refreshedPlan = $this->recalculateRemainingSequence($plan, $currentRoom);
        $sequence = $this->sequenceOrderIds($refreshedPlan);

        if ($sequence === []) {
            return null;
        }

        $ordersById = Order::query()
            ->whereIn('id', $sequence)
            ->where('status', OrderStatus::Pending->value)
            ->with(['arrivalRoom'])
            ->get()
            ->keyBy('id');

        foreach ($sequence as $orderId) {
            /** @var Order|null $order */
            $order = $ordersById->get($orderId);

            if ($order !== null) {
                if ($order->departure_room_id !== $currentRoom->id) {
                    $order->update(['departure_room_id' => $currentRoom->id]);
                }

                return $order->fresh(['arrivalRoom']);
            }
        }

        return null;
    }

    public function completePlan(DeliveryPlan $plan, ?Room $currentRoom): void
    {
        $payload = ['status' => 'completed'];

        if ($currentRoom !== null) {
            $payload['current_room_id'] = $currentRoom->id;
        }

        $plan->update($payload);
        DeliveryPlanUpdated::dispatch($plan->fresh());
        $this->dtTaskQueue->refreshFromActivePlan();
    }

    /**
     * @param  Collection<int, Order>  $orders
     * @return array<int>
     */
    private function computeSequence(Collection $orders, Room $currentRoom): array
    {
        if ($orders->isEmpty()) {
            return [];
        }

        $remaining = $orders->keyBy('id');
        $sequence = [];
        $currentRoomId = $currentRoom->id;

        while ($remaining->isNotEmpty()) {
            $bestOrderId = null;
            $bestTime = PHP_INT_MAX;

            $localStartRoom = Room::query()->find($currentRoomId);
            foreach ($remaining as $order) {

                $predicted = $this->predictionService->predict(
                    (string) $localStartRoom->code,
                    (string) $order->arrivalRoom?->code,
                    $order->expected_delivery_at
                );

                if ($predicted < $bestTime) {
                    $bestTime = $predicted;
                    $bestOrderId = $order->id;
                }
            }

            if ($bestOrderId === null) {
                break;
            }

            $sequence[] = $bestOrderId;
            $bestOrder = $remaining->get($bestOrderId);
            $currentRoomId = $bestOrder->arrival_room_id;
            $remaining->forget($bestOrderId);
        }

        return $sequence;
    }

    /**
     * @param  array<int>  $sequence
     * @param  Collection<int, Order>  $orders
     * @return array<string, mixed>
     */
    private function computeEstimatedTimesFromRoom(array $sequence, Collection $orders, Room $startRoom): array
    {
        $times = [];
        $currentRoomId = $startRoom->id;

        foreach ($sequence as $position => $orderId) {
            $localStartRoom = Room::query()->find($currentRoomId);
            $order = $orders->firstWhere('id', $orderId);
            if ($order === null) {
                continue;
            }

            $predictedMinutes = $this->predictionService->predict(
                (string) $localStartRoom->code,
                (string) $order->arrivalRoom?->code,
                $order->expected_delivery_at
            );

            $times[(string) $orderId] = [
                'sequence' => $position + 1,
                'predicted_minutes' => $predictedMinutes,
                'departure_room' => $localStartRoom?->name,
                'arrival_room' => $order->arrivalRoom?->name,
                'expected_delivery_at' => $order->expected_delivery_at,
            ];

            $currentRoomId = (int) $order->arrival_room_id;
        }

        return $times;
    }

    /**
     * @param  array<int>  $sequence
     * @param  Collection<int, Order>  $orders
     */
    private function syncOrderSequence(array $sequence, Collection $orders, ?Room $defaultDepartureRoom): void
    {
        $ordersById = $orders->keyBy('id');

        foreach ($sequence as $position => $orderId) {
            /** @var Order|null $order */
            $order = $ordersById->get($orderId);

            if ($order === null) {
                continue;
            }

            $updatePayload = ['planned_sequence' => $position + 1];

            // if ($defaultDepartureRoom !== null) {
            //     $updatePayload['departure_room_id'] = $defaultDepartureRoom->id;
            // }

            $order->update($updatePayload);
        }
    }

    /**
     * @param  Collection<int, Order>  $orders
     */
    private function createPlanFromOrders(Collection $orders, Room $startRoom, string $status, bool $isCritical, int $sequenceOffset = 0): ?DeliveryPlan
    {
        if ($orders->isEmpty()) {
            return null;
        }

        $sequence = $this->computeSequence($orders, $startRoom);

        if ($sequence === []) {
            return null;
        }

        $estimatedTimes = $this->computeEstimatedTimesFromRoom($sequence, $orders, $startRoom);

        $plan = DeliveryPlan::query()->create([
            'current_room_id' => $startRoom->id,
            'status' => $status,
            'is_critical' => $isCritical,
            'sequence' => $sequence,
            'estimated_times' => $estimatedTimes,
        ]);

        $this->syncOrderSequenceWithOffset($sequence, $orders, $sequenceOffset);

        return $plan;
    }

    /**
     * @param  array<int>  $sequence
     * @param  Collection<int, Order>  $orders
     */
    private function syncOrderSequenceWithOffset(array $sequence, Collection $orders, int $sequenceOffset): void
    {
        $ordersById = $orders->keyBy('id');

        foreach ($sequence as $position => $orderId) {
            /** @var Order|null $order */
            $order = $ordersById->get($orderId);

            if ($order === null) {
                continue;
            }

            $order->update([
                'planned_sequence' => $position + 1 + $sequenceOffset,
            ]);
        }
    }

    /**
     * @return array<int>
     */
    private function sequenceOrderIds(DeliveryPlan $plan): array
    {
        if (! is_array($plan->sequence)) {
            return [];
        }

        return collect($plan->sequence)
            ->map(static fn (mixed $value): int => (int) $value)
            ->filter(static fn (int $value): bool => $value > 0)
            ->values()
            ->all();
    }
}
