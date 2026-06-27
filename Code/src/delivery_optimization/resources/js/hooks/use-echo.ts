import Echo from 'laravel-echo';
import Pusher from 'pusher-js';
import { useEffect, useRef } from 'react';

// Make Pusher available globally for Laravel Echo
(window as unknown as Record<string, unknown>)['Pusher'] = Pusher;

let echoInstance: Echo<'reverb'> | null = null;

function getEcho(): Echo<'reverb'> {
    if (!echoInstance) {
        echoInstance = new Echo({
            broadcaster: 'reverb',
            key: import.meta.env.VITE_REVERB_APP_KEY ?? 'drivbot',
            wsHost: import.meta.env.VITE_REVERB_HOST ?? '127.0.0.1',
            wsPort: Number(import.meta.env.VITE_REVERB_PORT ?? 8080),
            wssPort: Number(import.meta.env.VITE_REVERB_PORT ?? 8080),
            forceTLS: (import.meta.env.VITE_REVERB_SCHEME ?? 'http') === 'https',
            enabledTransports: ['ws', 'wss'],
            disableStats: true,
        });
    }
    return echoInstance;
}

/**
 * Listen to a public channel event.
 */
export function useEchoChannel<T>(
    channel: string,
    event: string,
    callback: (data: T) => void,
): void;
export function useEchoChannel(
    channel: string,
    listeners: Record<string, (data: unknown) => void>,
): void;
export function useEchoChannel<T>(
    channel: string,
    eventOrListeners: string | Record<string, (data: unknown) => void>,
    callback?: (data: T) => void,
): void {
    const callbackRef = useRef(callback);
    callbackRef.current = callback;

    useEffect(() => {
        const echo = getEcho();
        const ch = echo.channel(channel);

        if (typeof eventOrListeners === 'string') {
            if (!callbackRef.current) {
                return () => {
                    echo.leaveChannel(channel);
                };
            }

            ch.listen(eventOrListeners, (data: T) => callbackRef.current?.(data));
        } else {
            for (const [event, listener] of Object.entries(eventOrListeners)) {
                ch.listen(event, listener);
            }
        }

        return () => {
            echo.leaveChannel(channel);
        };
    }, [channel, eventOrListeners]);
}
