<?php

namespace App\Services;

use App\Enums\OrderStatus;
use App\Events\OrderStatusUpdated;
use App\Models\DeliveryPlan;
use App\Models\Order;
use App\Models\Room;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Str;

class DtStatusService
{
    public function __construct(
        private readonly DeliveryPlannerService $planner,
        private readonly DtTaskQueueService $taskQueue,
    ) {}

    private const PLAN_PHASE_AWAITING_START = 'awaiting_start';

    private const PLAN_PHASE_DELIVERING = 'delivering';

    private const PLAN_PHASE_RETURNING_TO_START = 'returning_to_start';

    private const NEXT_ORDER_DISPATCH_DELAY_MICROSECONDS = 2500000;

    /**
     * @param  array<string, mixed>  $payload
     * @return array<int, array{type: string, room: string}>
     */
    public function handleStatusEvent(array $payload, string $source = 'dt:socket-consume'): array
    {
        if (($payload['type'] ?? null) !== 'status') {
            return [];
        }

        $state = Str::lower((string) ($payload['state'] ?? ''));
        if (! in_array($state, ['arrived', 'navigating', 'aborted', 'idle'], true)) {
            return [];
        }

        Cache::put('dt:last_status_payload', $payload, now()->addDay());

        $targetRoom = isset($payload['target']) ? trim((string) $payload['target']) : null;
        $activePlan = $this->planner->getActivePlan();

        if ($activePlan !== null) {
            return $this->handleStatusForActiveBatchPlan($activePlan, $state, $targetRoom, $source);
        }

        $currentOrder = $this->resolveCurrentOrder($targetRoom);

        if ($state === 'navigating' && $currentOrder !== null) {
            $this->markOrderInTransit($currentOrder);
        }

        if ($state === 'arrived' && $currentOrder !== null) {
            $this->markOrderDelivered($currentOrder);
            $this->taskQueue->markRoomAsCompleted($targetRoom ?? $currentOrder->arrivalRoom?->code);
            $this->waitBeforeNextOrderDispatch();
        }

        if ($state === 'aborted' && $currentOrder !== null) {
            $this->markOrderPending($currentOrder);
        }

        if (! in_array($state, ['arrived', 'idle'], true)) {
            return [];
        }

        $nextRoom = $this->taskQueue->popNextRoom();

        if ($nextRoom === null) {
            return [];
        }

        return [[
            'type' => 'room_command',
            'room' => $nextRoom,
        ]];
    }

    /**
     * @return array<int, array{type: string, room: string}>
     */
    private function handleStatusForActiveBatchPlan(DeliveryPlan $activePlan, string $state, ?string $targetRoom, string $source): array
    {
        $startRoom = $this->planner->getStartRoom();

        if ($startRoom === null) {
            return [];
        }

        $phase = $this->getPlanPhase($activePlan);

        if ($state === 'navigating') {
            $currentOrder = $this->resolveCurrentOrderWithinPlan($activePlan, $targetRoom);

            if ($currentOrder !== null) {
                $this->markOrderInTransit($currentOrder);
            }

            return [];
        }

        if ($state === 'aborted') {
            $currentOrder = $this->resolveCurrentOrderWithinPlan($activePlan, $targetRoom);

            if ($currentOrder !== null) {
                $this->markOrderPending($currentOrder);
            }

            return [];
        }

        if (! in_array($state, ['arrived', 'idle'], true)) {
            return [];
        }

        if ($state === 'arrived') {
            $currentOrder = $this->resolveCurrentOrderWithinPlan($activePlan, $targetRoom);

            if ($currentOrder !== null) {
                $this->markOrderDelivered($currentOrder);
                $activePlan = $activePlan->fresh() ?? $activePlan;
            } elseif (
                $phase === self::PLAN_PHASE_RETURNING_TO_START
                && $this->isStartRoomCode($targetRoom, $startRoom)
            ) {
                return $this->completePlanAndActivateNext($activePlan, $startRoom, $source);
            }
        }

        if (! $this->planner->hasRemainingOrders($activePlan)) {
            if ($state === 'arrived' && $this->isStartRoomCode($targetRoom, $startRoom)) {
                return $this->completePlanAndActivateNext($activePlan, $startRoom, $source);
            }

            $this->setPlanPhase($activePlan, self::PLAN_PHASE_RETURNING_TO_START);

            return [[
                'type' => 'room_command',
                'room' => $startRoom->code,
            ]];
        }

        if ($this->planner->hasInTransitOrder($activePlan)) {
            return [];
        }

        if ($phase === self::PLAN_PHASE_AWAITING_START) {
            if ($state === 'idle' && ! $this->isStartRoomCode($targetRoom, $startRoom)) {
                \Log::info('DT batch plan: sending robot to start room', [
                    'plan_id' => $activePlan->id,
                    'state' => $state,
                    'target_room' => $targetRoom,
                    'source' => $source,
                ]);

                return [[
                    'type' => 'room_command',
                    'room' => $startRoom->code,
                ]];
            }

            if (
                ($state === 'arrived' && $this->isStartRoomCode($targetRoom, $startRoom))
                || ($state === 'idle' && $this->isStartRoomCode($targetRoom, $startRoom))
            ) {
                $nextOrder = $this->planner->findNextPendingOrderFromRoom($activePlan, $startRoom);

                if ($nextOrder === null || $nextOrder->arrivalRoom?->code === null) {
                    return [];
                }

                if ($state === 'arrived') {
                    $this->waitBeforeNextOrderDispatch();
                }

                $this->markOrderInTransit($nextOrder);
                $this->setPlanPhase($activePlan, self::PLAN_PHASE_DELIVERING);

                \Log::info('DT batch plan: dispatching first order from start room', [
                    'plan_id' => $activePlan->id,
                    'order_id' => $nextOrder->id,
                    'departure_room_id' => $nextOrder->departure_room_id,
                    'arrival_room' => $nextOrder->arrivalRoom->code,
                    'source' => $source,
                ]);

                return [[
                    'type' => 'room_command',
                    'room' => $nextOrder->arrivalRoom->code,
                ]];
            }

            return [];
        }

        $currentRoom = $this->resolveCurrentRoom($targetRoom, $startRoom);

        if ($currentRoom === null) {
            return [];
        }

        $nextOrder = $this->planner->findNextPendingOrderFromRoom($activePlan, $currentRoom);

        if ($nextOrder === null || $nextOrder->arrivalRoom?->code === null) {
            $this->setPlanPhase($activePlan, self::PLAN_PHASE_RETURNING_TO_START);

            return [[
                'type' => 'room_command',
                'room' => $startRoom->code,
            ]];
        }

        if ($state === 'arrived') {
            $this->waitBeforeNextOrderDispatch();
        }

        $this->markOrderInTransit($nextOrder);
        $this->setPlanPhase($activePlan, self::PLAN_PHASE_DELIVERING);

        \Log::info('DT batch plan: dispatching next order', [
            'plan_id' => $activePlan->id,
            'order_id' => $nextOrder->id,
            'departure_room_id' => $nextOrder->departure_room_id,
            'arrival_room' => $nextOrder->arrivalRoom->code,
            'state' => $state,
            'target_room' => $targetRoom,
            'source' => $source,
        ]);

        return [[
            'type' => 'room_command',
            'room' => $nextOrder->arrivalRoom->code,
        ]];
    }

    /**
     * @return array<int, array{type: string, room: string}>
     */
    private function completePlanAndActivateNext(DeliveryPlan $activePlan, Room $startRoom, string $source): array
    {
        $this->planner->completePlan($activePlan, $startRoom);
        $this->forgetPlanPhase($activePlan);

        $nextPlan = $this->planner->activateNextQueuedPlan($startRoom);

        if ($nextPlan === null) {
            $nextPlan = $this->planner->initializeBatchPlan(now(), DeliveryPlannerService::BATCH_WINDOW_MINUTES);
        }

        if ($nextPlan === null) {
            return [];
        }

        $nextOrder = $this->planner->findNextPendingOrderFromRoom($nextPlan, $startRoom);

        if ($nextOrder === null || $nextOrder->arrivalRoom?->code === null) {
            return [];
        }

        $this->waitBeforeNextOrderDispatch();
        $this->markOrderInTransit($nextOrder);
        $this->setPlanPhase($nextPlan, self::PLAN_PHASE_DELIVERING);

        \Log::info('DT batch plan: activating queued plan', [
            'plan_id' => $nextPlan->id,
            'is_critical' => $nextPlan->is_critical,
            'order_id' => $nextOrder->id,
            'arrival_room' => $nextOrder->arrivalRoom->code,
            'source' => $source,
        ]);

        return [[
            'type' => 'room_command',
            'room' => $nextOrder->arrivalRoom->code,
        ]];
    }

    private function markOrderInTransit(Order $order): void
    {
        if ($order->status !== OrderStatus::Pending) {
            return;
        }

        $order->update(['status' => OrderStatus::InTransit]);
        OrderStatusUpdated::dispatch($order->fresh());
    }

    private function markOrderDelivered(Order $order): void
    {
        if (in_array($order->status, [OrderStatus::Delivered, OrderStatus::Cancelled], true)) {
            return;
        }

        $order->update([
            'status' => OrderStatus::Delivered,
            'delivered_at' => now(),
        ]);

        $freshOrder = $order->fresh(['arrivalRoom']);

        if ($freshOrder !== null) {
            OrderStatusUpdated::dispatch($freshOrder);
        }
    }

    private function markOrderPending(Order $order): void
    {
        if ($order->status !== OrderStatus::InTransit) {
            return;
        }

        $order->update(['status' => OrderStatus::Pending]);
        OrderStatusUpdated::dispatch($order->fresh());
    }

    private function resolveCurrentOrder(?string $targetRoom): ?Order
    {
        $activePlan = DeliveryPlan::query()
            ->where('status', 'active')
            ->latest('id')
            ->first();

        if ($activePlan === null || $activePlan->sequence === []) {
            return Order::query()
                ->whereIn('status', [OrderStatus::InTransit->value, OrderStatus::Pending->value])
                ->with('arrivalRoom:id,code')
                ->orderByRaw("CASE WHEN status = 'in_transit' THEN 0 ELSE 1 END")
                ->orderBy('planned_sequence')
                ->orderBy('id')
                ->first();
        }

        $sequence = collect($activePlan->sequence)
            ->map(static fn (mixed $id): int => (int) $id)
            ->values();

        $ordersById = Order::query()
            ->whereIn('id', $sequence)
            ->whereIn('status', [OrderStatus::Pending->value, OrderStatus::InTransit->value])
            ->with('arrivalRoom:id,code')
            ->get()
            ->keyBy('id');

        $sortedOrders = $sequence
            ->map(static fn (int $orderId): ?Order => $ordersById->get($orderId))
            ->filter()
            ->values();

        if ($sortedOrders->isEmpty()) {
            return null;
        }

        if ($targetRoom !== null && trim($targetRoom) !== '') {
            $normalizedTarget = $this->normalizeRoomCode($targetRoom);

            /** @var Order|null $matchingOrder */
            $matchingOrder = $sortedOrders->first(function (Order $order) use ($normalizedTarget): bool {
                $arrivalCode = $order->arrivalRoom?->code;

                return $arrivalCode !== null && $this->normalizeRoomCode($arrivalCode) === $normalizedTarget;
            });

            if ($matchingOrder !== null) {
                return $matchingOrder;
            }
        }

        /** @var Order|null $inTransitOrder */
        $inTransitOrder = $sortedOrders->first(
            static fn (Order $order): bool => $order->status === OrderStatus::InTransit
        );

        return $inTransitOrder ?? $sortedOrders->first();
    }

    private function resolveCurrentOrderWithinPlan(DeliveryPlan $plan, ?string $targetRoom): ?Order
    {
        $sequence = collect($plan->sequence)
            ->map(static fn (mixed $id): int => (int) $id)
            ->values();

        if ($sequence->isEmpty()) {
            return null;
        }

        $ordersById = Order::query()
            ->whereIn('id', $sequence)
            ->whereIn('status', [OrderStatus::Pending->value, OrderStatus::InTransit->value])
            ->with('arrivalRoom:id,code')
            ->get()
            ->keyBy('id');

        $sortedOrders = $sequence
            ->map(static fn (int $orderId): ?Order => $ordersById->get($orderId))
            ->filter()
            ->values();

        if ($sortedOrders->isEmpty()) {
            return null;
        }

        if ($targetRoom !== null && trim($targetRoom) !== '') {
            $normalizedTarget = $this->normalizeRoomCode($targetRoom);

            /** @var Order|null $matchingOrder */
            $matchingOrder = $sortedOrders->first(function (Order $order) use ($normalizedTarget): bool {
                $arrivalCode = $order->arrivalRoom?->code;

                return $arrivalCode !== null && $this->normalizeRoomCode($arrivalCode) === $normalizedTarget;
            });

            if ($matchingOrder !== null) {
                return $matchingOrder;
            }
        }

        /** @var Order|null $inTransitOrder */
        $inTransitOrder = $sortedOrders->first(
            static fn (Order $order): bool => $order->status === OrderStatus::InTransit
        );

        return $inTransitOrder;
    }

    private function resolveCurrentRoom(?string $targetRoom, Room $startRoom): ?Room
    {
        if ($targetRoom === null || trim($targetRoom) === '') {
            return $startRoom;
        }

        $room = Room::query()->where('code', $targetRoom)->first();

        return $room ?? $startRoom;
    }

    private function isStartRoomCode(?string $roomCode, Room $startRoom): bool
    {
        if ($roomCode === null || trim($roomCode) === '') {
            return false;
        }

        return $this->normalizeRoomCode($roomCode) === $this->normalizeRoomCode($startRoom->code);
    }

    private function getPlanPhase(DeliveryPlan $plan): string
    {
        $phase = Cache::get($this->planPhaseCacheKey($plan));

        if (! is_string($phase) || trim($phase) === '') {
            return self::PLAN_PHASE_AWAITING_START;
        }

        if (! in_array($phase, [self::PLAN_PHASE_AWAITING_START, self::PLAN_PHASE_DELIVERING, self::PLAN_PHASE_RETURNING_TO_START], true)) {
            return self::PLAN_PHASE_AWAITING_START;
        }

        return $phase;
    }

    private function setPlanPhase(DeliveryPlan $plan, string $phase): void
    {
        Cache::put($this->planPhaseCacheKey($plan), $phase, now()->addDay());
    }

    private function forgetPlanPhase(DeliveryPlan $plan): void
    {
        Cache::forget($this->planPhaseCacheKey($plan));
    }

    private function planPhaseCacheKey(DeliveryPlan $plan): string
    {
        return "delivery-plan:{$plan->id}:phase";
    }

    private function normalizeRoomCode(string $roomCode): string
    {
        return (string) Str::of($roomCode)
            ->trim()
            ->lower()
            ->replace([' ', '-'], '_');
    }

    private function waitBeforeNextOrderDispatch(): void
    {
        usleep(self::NEXT_ORDER_DISPATCH_DELAY_MICROSECONDS);
    }
}
