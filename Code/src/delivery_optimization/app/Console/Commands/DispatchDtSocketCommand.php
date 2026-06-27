<?php

namespace App\Console\Commands;

use App\Services\DtConnectionSettings;
use App\Services\DtOutboundQueueService;
use App\Services\DtStatusService;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Log;

class DispatchDtSocketCommand extends Command
{
    protected $signature = 'dt:dispatch-remote-socket';

    protected $description = 'Dispatch queued delivery room commands to remote DT socket';

    public function handle(
        DtOutboundQueueService $outboundQueue,
        DtStatusService $statusService,
        DtConnectionSettings $connectionSettings
    ): int {
        $connectTimeout = (float) config('dt.socket.connect_timeout', 5);
        $readTimeout = (int) config('dt.socket.read_timeout', 60);
        $reconnectDelayMs = (int) config('dt.socket.reconnect_delay_ms', 1000);
        $idlePollDelayMs = (int) config('dt.socket.idle_poll_delay_ms', 300);

        $announcedAddress = null;

        while (true) {
            // Re-read the address every cycle so a change made in the settings
            // UI is picked up on the next (re)connection without a restart.
            $address = $connectionSettings->address();

            if ($address === '') {
                if ($announcedAddress !== '') {
                    $this->warn('DT socket address is not configured. Set it in Settings → Connection. Waiting...');
                    $announcedAddress = '';
                }

                usleep($reconnectDelayMs * 1000);

                continue;
            }

            if ($address !== $announcedAddress) {
                $this->info("Connecting to remote DT dispatch socket at {$address}...");
                $announcedAddress = $address;
            }

            [$socket, $transport] = $this->connectToRemoteSocket($address, $connectTimeout, $readTimeout);

            if (! is_resource($socket)) {
                usleep($reconnectDelayMs * 1000);
                continue;
            }

            stream_set_timeout($socket, $readTimeout);
            $this->info('Remote DT socket connected. Dispatching delivery commands...');
            if ($transport === 'websocket') {
                $this->sendWebSocketJson($socket, ['type' => 'get_status']);
            }

            while (! feof($socket)) {
                // Drop the connection if the configured address changed, so we
                // reconnect to the new ROS machine on the next loop iteration.
                if ($connectionSettings->address() !== $address) {
                    $this->info('DT socket address changed; reconnecting to the new target...');
                    break;
                }

                if ($transport === 'websocket' && ! $this->drainWebSocketMessages($socket, $statusService, $outboundQueue)) {
                    break;
                }

                $nextMessage = $outboundQueue->pop();

                if ($nextMessage === null) {
                    usleep($idlePollDelayMs * 1000);

                    continue;
                }

                $encodedMessage = json_encode($nextMessage, JSON_UNESCAPED_SLASHES);

                if ($encodedMessage === false) {
                    continue;
                }

                $result = $transport === 'websocket'
                    ? @fwrite($socket, $this->encodeWebSocketFrame($encodedMessage))
                    : @fwrite($socket, $encodedMessage.PHP_EOL);

                if ($result === false) {
                    // Push the message back if sending failed, then reconnect.
                    $outboundQueue->push($nextMessage);
                    break;
                }

                Log::info('Remote DT command dispatched', [
                    'payload' => $nextMessage,
                    'process' => 'dt:dispatch-remote-socket',
                ]);

                if ($transport === 'websocket' && ! $this->drainWebSocketMessages($socket, $statusService, $outboundQueue)) {
                    break;
                }
            }

            fclose($socket);
            usleep($reconnectDelayMs * 1000);
        }
    }

    /**
     * @return array{0: resource|null, 1: 'tcp'|'websocket'}
     */
    private function connectToRemoteSocket(string $address, float $connectTimeout, int $readTimeout): array
    {
        if (str_starts_with($address, 'ws://') || str_starts_with($address, 'wss://')) {
            return $this->connectToWebSocket($address, $connectTimeout, $readTimeout);
        }

        $errorNumber = 0;
        $errorMessage = '';
        $socket = @stream_socket_client($address, $errorNumber, $errorMessage, $connectTimeout);

        if (! is_resource($socket)) {
            Log::warning('Unable to connect to remote DT TCP socket', [
                'address' => $address,
                'error_number' => $errorNumber,
                'error_message' => $errorMessage,
                'process' => 'dt:dispatch-remote-socket',
            ]);

            return [null, 'tcp'];
        }

        stream_set_timeout($socket, $readTimeout);

        return [$socket, 'tcp'];
    }

    /**
     * @return array{0: resource|null, 1: 'websocket'}
     */
    private function connectToWebSocket(string $address, float $connectTimeout, int $readTimeout): array
    {
        $parts = parse_url($address);

        if (! is_array($parts) || ! isset($parts['scheme'], $parts['host'])) {
            Log::warning('Invalid remote WebSocket address', [
                'address' => $address,
                'process' => 'dt:dispatch-remote-socket',
            ]);

            return [null, 'websocket'];
        }

        $scheme = strtolower((string) $parts['scheme']);
        $host = (string) $parts['host'];
        $port = isset($parts['port']) ? (int) $parts['port'] : ($scheme === 'wss' ? 443 : 80);
        $path = ($parts['path'] ?? '/').(isset($parts['query']) ? '?'.$parts['query'] : '');
        $transport = $scheme === 'wss' ? 'ssl' : 'tcp';
        $endpoint = sprintf('%s://%s:%d', $transport, $host, $port);

        $errorNumber = 0;
        $errorMessage = '';
        $socket = @stream_socket_client($endpoint, $errorNumber, $errorMessage, $connectTimeout);

        if (! is_resource($socket)) {

            return [null, 'websocket'];
        }

        stream_set_timeout($socket, $readTimeout);

        $webSocketKey = base64_encode(random_bytes(16));
        $hostHeader = ($scheme === 'ws' && $port === 80) || ($scheme === 'wss' && $port === 443)
            ? $host
            : sprintf('%s:%d', $host, $port);
        $headers = [
            sprintf('GET %s HTTP/1.1', $path),
            sprintf('Host: %s', $hostHeader),
            'Upgrade: websocket',
            'Connection: Upgrade',
            sprintf('Sec-WebSocket-Key: %s', $webSocketKey),
            'Sec-WebSocket-Version: 13',
            'User-Agent: DRYV-BOT-DT-Dispatcher/1.0',
            "\r\n",
        ];

        $result = @fwrite($socket, implode("\r\n", $headers));

        if ($result === false) {
            fclose($socket);
            Log::warning('Unable to send WebSocket handshake request', [
                'address' => $address,
                'process' => 'dt:dispatch-remote-socket',
            ]);

            return [null, 'websocket'];
        }

        $responseHeaders = '';

        while (! str_contains($responseHeaders, "\r\n\r\n")) {
            $line = fgets($socket);

            if ($line === false) {
                fclose($socket);
                Log::warning('Remote WebSocket handshake response was empty', [
                    'address' => $address,
                    'process' => 'dt:dispatch-remote-socket',
                ]);

                return [null, 'websocket'];
            }

            $responseHeaders .= $line;
        }

        $expectedAccept = base64_encode(sha1($webSocketKey.'258EAFA5-E914-47DA-95CA-C5AB0DC85B11', true));
        $isStatusSwitchingProtocol = preg_match('/^HTTP\/1\.[01] 101 /i', $responseHeaders) === 1;
        $hasUpgradeHeader = preg_match('/\r\nUpgrade:\s*websocket\r\n/i', $responseHeaders) === 1;
        $hasConnectionUpgrade = preg_match('/\r\nConnection:\s*Upgrade\r\n/i', $responseHeaders) === 1;
        $hasExpectedAccept = preg_match('/\r\nSec-WebSocket-Accept:\s*'.preg_quote($expectedAccept, '/').'\r\n/i', $responseHeaders) === 1;

        if (! $isStatusSwitchingProtocol || ! $hasUpgradeHeader || ! $hasConnectionUpgrade || ! $hasExpectedAccept) {
            fclose($socket);
            Log::warning('Remote WebSocket handshake failed', [
                'address' => $address,
                'response_headers' => $responseHeaders,
                'process' => 'dt:dispatch-remote-socket',
            ]);

            return [null, 'websocket'];
        }

        Log::info('Remote WebSocket handshake succeeded', [
            'address' => $address,
            'endpoint' => $endpoint,
            'path' => $path,
            'process' => 'dt:dispatch-remote-socket',
        ]);

        return [$socket, 'websocket'];
    }

    /**
     * @param  array<string, mixed>  $payload
     */
    private function sendWebSocketJson($socket, array $payload): void
    {
        $encoded = json_encode($payload, JSON_UNESCAPED_SLASHES);

        if ($encoded === false) {
            return;
        }

        @fwrite($socket, $this->encodeWebSocketFrame($encoded));

        Log::info('Remote WebSocket protocol message sent', [
            'payload' => $payload,
            'process' => 'dt:dispatch-remote-socket',
        ]);
    }

    private function drainWebSocketMessages($socket, DtStatusService $statusService, DtOutboundQueueService $outboundQueue): bool
    {
        while (true) {
            $read = [$socket];
            $write = null;
            $except = null;
            $changed = @stream_select($read, $write, $except, 0, 0);

            if ($changed === false) {
                Log::warning('Unable to poll remote WebSocket stream', [
                    'process' => 'dt:dispatch-remote-socket',
                ]);

                return false;
            }

            if ($changed === 0) {
                return true;
            }

            $frame = $this->decodeWebSocketFrame($socket);

            if ($frame === null) {
                Log::warning('Unable to decode remote WebSocket frame', [
                    'process' => 'dt:dispatch-remote-socket',
                ]);

                return false;
            }

            $opcode = $frame['opcode'];
            $payload = $frame['payload'];

            if ($opcode === 0x1) {
                $this->logRemoteWebSocketPayload($payload, $statusService, $outboundQueue);

                continue;
            }

            if ($opcode === 0x8) {
                Log::warning('Remote WebSocket close frame received', [
                    'process' => 'dt:dispatch-remote-socket',
                ]);

                return false;
            }

            if ($opcode === 0x9) {
                @fwrite($socket, $this->encodeWebSocketFrame($payload, 0xA));
                continue;
            }

            if ($opcode === 0xA) {
                Log::debug('Remote WebSocket pong received', [
                    'process' => 'dt:dispatch-remote-socket',
                ]);
            }
        }
    }

    /**
     * @return array{opcode: int, payload: string}|null
     */
    private function decodeWebSocketFrame($socket): ?array
    {
        $header = $this->readExactBytes($socket, 2);

        if ($header === null) {
            return null;
        }

        $firstByte = ord($header[0]);
        $secondByte = ord($header[1]);

        $opcode = $firstByte & 0x0F;
        $masked = ($secondByte & 0x80) === 0x80;
        $payloadLength = $secondByte & 0x7F;

        if ($payloadLength === 126) {
            $extendedLength = $this->readExactBytes($socket, 2);

            if ($extendedLength === null) {
                return null;
            }

            $payloadLength = unpack('nlength', $extendedLength)['length'];
        } elseif ($payloadLength === 127) {
            $extendedLength = $this->readExactBytes($socket, 8);

            if ($extendedLength === null) {
                return null;
            }

            $lengthParts = unpack('Nhigh/Nlow', $extendedLength);
            $payloadLength = ((int) $lengthParts['high'] * 4294967296) + (int) $lengthParts['low'];
        }

        $maskingKey = $masked ? $this->readExactBytes($socket, 4) : null;

        if ($masked && $maskingKey === null) {
            return null;
        }

        $payload = $payloadLength > 0 ? $this->readExactBytes($socket, $payloadLength) : '';

        if ($payload === null) {
            return null;
        }

        if ($masked && $maskingKey !== null) {
            $unmaskedPayload = '';

            for ($index = 0; $index < $payloadLength; $index++) {
                $unmaskedPayload .= $payload[$index] ^ $maskingKey[$index % 4];
            }

            $payload = $unmaskedPayload;
        }

        return [
            'opcode' => $opcode,
            'payload' => $payload,
        ];
    }

    private function readExactBytes($socket, int $length): ?string
    {
        $buffer = '';

        while (strlen($buffer) < $length) {
            $chunk = fread($socket, $length - strlen($buffer));

            if ($chunk === false || $chunk === '') {
                $meta = stream_get_meta_data($socket);

                if (($meta['timed_out'] ?? false) === true) {
                    return null;
                }

                if (feof($socket)) {
                    return null;
                }

                continue;
            }

            $buffer .= $chunk;
        }

        return $buffer;
    }

    private function logRemoteWebSocketPayload(
        string $payload,
        DtStatusService $statusService,
        DtOutboundQueueService $outboundQueue
    ): void {
        $decoded = json_decode($payload, true);

        if (! is_array($decoded)) {
            Log::info('Remote WebSocket text message received', [
                'raw' => $payload,
                'process' => 'dt:dispatch-remote-socket',
            ]);

            return;
        }

        $type = $decoded['type'] ?? 'unknown';

        if ($type === 'status') {
            $messagesToPublish = $statusService->handleStatusEvent($decoded, 'dt:dispatch-remote-socket');

            foreach ($messagesToPublish as $message) {
                $outboundQueue->push($message);
            }

            if ($messagesToPublish !== []) {
                Log::info('Outbound commands queued from remote status', [
                    'commands_count' => count($messagesToPublish),
                    'process' => 'dt:dispatch-remote-socket',
                ]);
            }

            return;
        }

        if ($type === 'ack') {
            Log::info('Remote room command acknowledged', [
                'room' => $decoded['room'] ?? null,
                'resolved_room_id' => $decoded['resolved_room_id'] ?? null,
                'target_position' => $decoded['target_position'] ?? null,
                'process' => 'dt:dispatch-remote-socket',
            ]);

            return;
        }

        if ($type === 'feedback') {
            Log::info('Remote feedback received', [
                'text' => $decoded['text'] ?? null,
                'process' => 'dt:dispatch-remote-socket',
            ]);

            return;
        }

        if ($type === 'rooms') {
            $rooms = $decoded['rooms'] ?? [];

            Log::info('Remote rooms list received', [
                'rooms_count' => is_array($rooms) ? count($rooms) : null,
                'process' => 'dt:dispatch-remote-socket',
            ]);

            return;
        }

        if ($type === 'error') {
            Log::warning('Remote WebSocket reported an error', [
                'message' => $decoded['message'] ?? 'unknown',
                'payload' => $decoded,
                'process' => 'dt:dispatch-remote-socket',
            ]);

            return;
        }

        Log::info('Remote WebSocket message received', [
            'payload' => $decoded,
            'process' => 'dt:dispatch-remote-socket',
        ]);
    }

    private function encodeWebSocketFrame(string $payload, int $opcode = 0x1): string
    {
        $payloadLength = strlen($payload);
        $firstByte = 0x80 | $opcode;
        $maskingKey = random_bytes(4);
        $secondByte = 0x80;
        $extendedPayloadLength = '';

        if ($payloadLength <= 125) {
            $secondByte |= $payloadLength;
        } elseif ($payloadLength <= 65535) {
            $secondByte |= 126;
            $extendedPayloadLength = pack('n', $payloadLength);
        } else {
            $secondByte |= 127;
            $extendedPayloadLength = pack('N2', 0, $payloadLength);
        }

        $maskedPayload = '';

        for ($index = 0; $index < $payloadLength; $index++) {
            $maskedPayload .= $payload[$index] ^ $maskingKey[$index % 4];
        }

        return chr($firstByte).chr($secondByte).$extendedPayloadLength.$maskingKey.$maskedPayload;
    }
}
