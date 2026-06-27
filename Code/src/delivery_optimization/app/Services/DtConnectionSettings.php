<?php

namespace App\Services;

use App\Models\AppSetting;

/**
 * Resolves the digital twin (ROS machine) socket address.
 *
 * The address can be set at runtime from the settings UI; when no value has
 * been saved it falls back to the `DT_SOCKET_ADDRESS` config/env value. Both
 * long-running socket workers read the address through this service so a change
 * made in the UI is picked up on their next reconnect cycle.
 */
class DtConnectionSettings
{
    public const SETTING_KEY = 'dt_socket_address';

    public const ALLOWED_SCHEMES = ['ws', 'wss', 'tcp'];

    /**
     * The full DT socket address, e.g. "ws://192.168.1.42:9090".
     */
    public function address(): string
    {
        $stored = AppSetting::get(self::SETTING_KEY);

        if (is_string($stored) && $stored !== '') {
            return $stored;
        }

        return (string) config('dt.socket.address', '');
    }

    /**
     * The current address broken into UI-editable parts.
     *
     * @return array{scheme: string, host: string, port: int|null}
     */
    public function current(): array
    {
        $parts = parse_url($this->address());

        $scheme = is_array($parts) && isset($parts['scheme']) ? strtolower((string) $parts['scheme']) : 'ws';
        if (! in_array($scheme, self::ALLOWED_SCHEMES, true)) {
            $scheme = 'ws';
        }

        return [
            'scheme' => $scheme,
            'host' => is_array($parts) && isset($parts['host']) ? (string) $parts['host'] : '',
            'port' => is_array($parts) && isset($parts['port']) ? (int) $parts['port'] : null,
        ];
    }

    /**
     * Compose and persist a new address from its parts. Returns the saved value.
     */
    public function update(string $scheme, string $host, int $port): string
    {
        if (! in_array($scheme, self::ALLOWED_SCHEMES, true)) {
            $scheme = 'ws';
        }

        $address = sprintf('%s://%s:%d', $scheme, $host, $port);

        AppSetting::put(self::SETTING_KEY, $address);

        return $address;
    }
}
