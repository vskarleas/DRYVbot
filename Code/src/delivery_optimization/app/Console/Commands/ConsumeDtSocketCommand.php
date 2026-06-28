<?php

namespace App\Console\Commands;

use App\Services\DtStatusService;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Log;

class ConsumeDtSocketCommand extends Command
{
    protected $signature = 'dt:socket-consume';

    protected $description = 'Consume DT socket events and publish room commands back to the same socket';

    public function handle(DtStatusService $statusService): int
    {
        $address = (string) config('dt.socket.address', '');

        if ($address === '') {
            $this->error('DT_SOCKET_ADDRESS is not configured.');

            return self::FAILURE;
        }

        $connectTimeout = (float) config('dt.socket.connect_timeout', 5);
        $readTimeout = (int) config('dt.socket.read_timeout', 60);
        $reconnectDelayMs = (int) config('dt.socket.reconnect_delay_ms', 1000);

        $this->info("Connecting to DT socket at {$address}...");

        while (true) {
            $socket = @stream_socket_client($address, $errorNumber, $errorMessage, $connectTimeout);

            if (! is_resource($socket)) {
                Log::warning('Unable to connect to DT socket', [
                    'address' => $address,
                    'error_number' => $errorNumber,
                    'error_message' => $errorMessage,
                ]);

                usleep($reconnectDelayMs * 1000);

                continue;
            }

            stream_set_timeout($socket, $readTimeout);
            $this->info('DT socket connected. Listening for status events...');

            while (! feof($socket)) {
                $rawLine = fgets($socket);

                if ($rawLine === false) {
                    $metadata = stream_get_meta_data($socket);

                    if (($metadata['timed_out'] ?? false) === true) {
                        continue;
                    }

                    break;
                }

                $line = trim($rawLine);
                if ($line === '') {
                    continue;
                }

                $payload = json_decode($line, true);

                if (! is_array($payload)) {
                    Log::warning('Invalid JSON received from DT socket', ['payload' => $line]);

                    continue;
                }

                $messagesToPublish = $statusService->handleStatusEvent($payload);

                foreach ($messagesToPublish as $outgoingMessage) {
                    $encodedMessage = json_encode($outgoingMessage, JSON_UNESCAPED_SLASHES);

                    if ($encodedMessage === false) {
                        Log::warning('Unable to encode outgoing DT message', ['message' => $outgoingMessage]);

                        continue;
                    }

                    fwrite($socket, $encodedMessage . PHP_EOL);
                }
            }

            fclose($socket);
            Log::warning('DT socket disconnected. Reconnecting...');
            usleep($reconnectDelayMs * 1000);
        }
    }
}
