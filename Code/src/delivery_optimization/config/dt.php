<?php

return [
    'socket' => [
        'address' => env('DT_SOCKET_ADDRESS', ''),
        'connect_timeout' => (float) env('DT_SOCKET_CONNECT_TIMEOUT', 5),
        'read_timeout' => (int) env('DT_SOCKET_READ_TIMEOUT', 60),
        'reconnect_delay_ms' => (int) env('DT_SOCKET_RECONNECT_DELAY_MS', 1000),
        'idle_poll_delay_ms' => (int) env('DT_SOCKET_IDLE_POLL_DELAY_MS', 300),
    ],
];
