<?php

namespace App\Services;

use App\Enums\OrderStatus;
use App\Models\DeliveryPlan;
use App\Models\Order;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Str;

class DtTaskQueueService
{
    private const CACHE_KEY = 'dt:planned_rooms_queue';

    public function popNextRoom(): ?string
    {
        $queue = $this->ensureQueue();

        if ($queue === []) {
            return null;
        }

        $nextRoom = array_shift($queue);
        Cache::forever(self::CACHE_KEY, $queue);

        return $nextRoom !== null ? (string) $nextRoom : null;
    }

    public function markRoomAsCompleted(?string $roomCode): void
    {
        if ($roomCode === null || trim($roomCode) === '') {
            return;
        }

        $queue = $this->ensureQueue();
        if ($queue === []) {
            return;
        }

        $normalizedTarget = $this->normalizeRoomCode($roomCode);
        $updatedQueue = [];
        $removed = false;

        foreach ($queue as $queuedRoom) {
            if (! $removed && $this->normalizeRoomCode($queuedRoom) === $normalizedTarget) {
                $removed = true;

                continue;
            }

            $updatedQueue[] = $queuedRoom;
        }

        Cache::forever(self::CACHE_KEY, $updatedQueue);
    }

    /**
     * @return array<int, string>
     */
    public function refreshFromActivePlan(): array
    {
        $activePlan = DeliveryPlan::query()
            ->where('status', 'active')
            ->latest('id')
            ->first();

        if ($activePlan === null || $activePlan->sequence === []) {
            Cache::forget(self::CACHE_KEY);

            return [];
        }

        $sequence = collect($activePlan->sequence)
            ->map(static fn (mixed $id): int => (int) $id)
            ->values();

        $orders = Order::query()
            ->whereIn('id', $sequence)
            ->whereIn('status', [OrderStatus::Pending->value, OrderStatus::InTransit->value])
            ->with('arrivalRoom:id,code')
            ->get()
            ->keyBy('id');

        $roomQueue = [];

        foreach ($sequence as $orderId) {
            $roomCode = $orders->get($orderId)?->arrivalRoom?->code;

            if ($roomCode !== null && trim($roomCode) !== '') {
                $roomQueue[] = $roomCode;
            }
        }

        if ($roomQueue === []) {
            Cache::forget(self::CACHE_KEY);

            return [];
        }

        Cache::forever(self::CACHE_KEY, $roomQueue);

        return $roomQueue;
    }

    /**
     * @return array<int, string>
     */
    public function ensureQueue(): array
    {
        $cachedQueue = Cache::get(self::CACHE_KEY);

        if (is_array($cachedQueue) && $cachedQueue !== []) {
            return array_values(array_map(static fn (mixed $value): string => (string) $value, $cachedQueue));
        }

        return $this->refreshFromActivePlan();
    }

    private function normalizeRoomCode(string $roomCode): string
    {
        return (string) Str::of($roomCode)
            ->trim()
            ->lower()
            ->replace([' ', '-'], '_');
    }
}
