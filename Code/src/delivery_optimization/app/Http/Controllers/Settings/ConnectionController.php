<?php

namespace App\Http\Controllers\Settings;

use App\Http\Controllers\Controller;
use App\Http\Requests\Settings\ConnectionUpdateRequest;
use Illuminate\Http\RedirectResponse;
use Inertia\Inertia;
use Inertia\Response;

class ConnectionController extends Controller
{
    /**
     * Show the digital-twin connection settings page.
     */
    public function edit(): Response
    {
        $address = (string) config('dt.socket.address', '');
        $parts = parse_url($address);

        return Inertia::render('settings/connection', [
            'connection' => [
                'scheme' => is_array($parts) && isset($parts['scheme']) ? strtolower((string) $parts['scheme']) : 'ws',
                'host' => is_array($parts) && isset($parts['host']) ? (string) $parts['host'] : '',
                'port' => is_array($parts) && isset($parts['port']) ? (int) $parts['port'] : null,
            ],
        ]);
    }

    /**
     * Update the digital-twin socket address (scheme, host/IP and port).
     */
    public function update(ConnectionUpdateRequest $request): RedirectResponse
    {
        $this->writeEnv('DT_SOCKET_ADDRESS', $request->socketAddress());

        Inertia::flash('toast', ['type' => 'success', 'message' => __('Connection settings updated.')]);

        return to_route('connection.edit');
    }

    /**
     * Persist (or replace) a single key in the application's .env file.
     */
    private function writeEnv(string $key, string $value): void
    {
        $path = app()->environmentFilePath();

        if (! is_file($path) || ! is_writable($path)) {
            return;
        }

        $contents = (string) file_get_contents($path);
        $line = $key.'='.$this->encodeEnvValue($value);
        $pattern = '/^'.preg_quote($key, '/').'=.*$/m';

        $contents = preg_match($pattern, $contents) === 1
            ? (string) preg_replace($pattern, $line, $contents)
            : rtrim($contents, "\n")."\n".$line."\n";

        file_put_contents($path, $contents);

        // Reflect the change immediately for the current request lifecycle.
        config(['dt.socket.address' => $value]);
    }

    /**
     * Quote an env value when it contains characters that require it.
     */
    private function encodeEnvValue(string $value): string
    {
        return preg_match('/\s|#|"|\'/', $value) === 1
            ? '"'.str_replace('"', '\"', $value).'"'
            : $value;
    }
}
