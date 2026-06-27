<?php

namespace App\Services;

use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Log;

class DtOutboundQueueService
{
    private const CACHE_KEY = 'dt:outbound_room_commands_queue';

    /**
     * @return array<int, array{type: string, room: string}>
     */
    public function all(): array
    {
        $queue = Cache::get(self::CACHE_KEY);

        if (! is_array($queue)) {
            return [];
        }

        return array_values(array_filter($queue, static fn (mixed $item): bool => is_array($item)));
    }

    /**
     * @param  array{type: string, room: string}  $message
     */
    public function push(array $message): void
    {
        $queue = $this->all();
        $queue[] = $message;

        Cache::forever(self::CACHE_KEY, $queue);

        Log::info('DT outbound queue message pushed', [
            'queue_size' => count($queue),
            'message_type' => $message['type'] ?? null,
            'message_room' => $message['room'] ?? null,
            'process' => 'dt:sync-local-socket',
        ]);
    }

    /**
     * @return array{type: string, room: string}|null
     */
    public function pop(): ?array
    {
        $queue = $this->all();

        if ($queue === []) {
            return null;
        }

        $next = array_shift($queue);
        Cache::forever(self::CACHE_KEY, $queue);

        if (is_array($next)) {
            Log::info('DT outbound queue message popped', [
                'queue_size' => count($queue),
                'message_type' => $next['type'] ?? null,
                'message_room' => $next['room'] ?? null,
                'process' => 'dt:dispatch-remote-socket',
            ]);
        }

        return is_array($next) ? $next : null;
    }
}
