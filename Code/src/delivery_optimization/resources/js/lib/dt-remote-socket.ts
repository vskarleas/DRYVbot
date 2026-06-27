import { toast } from "sonner";

type DtRemoteMessage = {
    type?: string;
    [key: string]: unknown;
};

const DEFAULT_RECONNECT_DELAY_MS = 1500;
const MAX_RECONNECT_DELAY_MS = 10000;
const START_ROOM_CODE = 'salle_pharmacie';
const DELIVERY_SOUND_URL = '/notification/sound.mp3';
const DELIVERY_FAULT_SOUND_URL = '/notification/fault.mp3';

let socket: WebSocket | null = null;
let hasStarted = false;
let reconnectAttempts = 0;
let reconnectTimer: number | null = null;
let notificationAudio: HTMLAudioElement | null = null;
let lastPlayedDeliveryTarget: string | null = null;
let lastPlayedAt = 0;

function getRemoteSocketUrl(): string {
    return (import.meta.env.VITE_DT_REMOTE_SOCKET_URL ?? '').trim();
}

function scheduleReconnect(): void {
    if (!hasStarted || reconnectTimer !== null) {
        return;
    }

    const delay = Math.min(DEFAULT_RECONNECT_DELAY_MS * (reconnectAttempts + 1), MAX_RECONNECT_DELAY_MS);

    reconnectTimer = window.setTimeout(() => {
        reconnectTimer = null;
        connect();
    }, delay);
}

function sendJson(payload: Record<string, unknown>): void {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
        return;
    }

    socket.send(JSON.stringify(payload));
}

function getNotificationAudio(): HTMLAudioElement {
    if (notificationAudio === null) {
        notificationAudio = new Audio(DELIVERY_SOUND_URL);
        notificationAudio.preload = 'auto';
    }

    return notificationAudio;
}

function getNotificationFaultAudio(): HTMLAudioElement {
    if (notificationAudio === null) {
        notificationAudio = new Audio(DELIVERY_FAULT_SOUND_URL);
        notificationAudio.preload = 'auto';
    }

    return notificationAudio;
}

function playDeliverySuccessSound(): void {
    const audio = getNotificationAudio();

    audio.currentTime = 0;

    void audio.play().catch(() => {
        console.warn('[DT-REMOTE] Unable to autoplay delivery notification sound');
    });
}

function playDeliveryFaultSound(): void {
    const audio = getNotificationFaultAudio();

    audio.currentTime = 0;

    void audio.play().catch(() => {
        console.warn('[DT-REMOTE] Unable to autoplay delivery fault sound');
    });
}

function normalizeRoomCode(room: unknown): string {
    if (typeof room !== 'string') {
        return '';
    }

    return room.trim().toLowerCase().replaceAll('-', '_').replaceAll(' ', '_');
}

function handleDeliverySuccessNotification(payload: DtRemoteMessage): void {
    const state = typeof payload.state === 'string' ? payload.state.toLowerCase() : '';

    const target = normalizeRoomCode(payload.target);
    if (state === 'aborted') {
        toast.error(`La livraison vers ${payload.target} a été interrompue`);
        setTimeout(() => {
            sendJson({ type: 'room_command', room: payload.target });
        }, 3000);

        playDeliveryFaultSound();
        toast.info(`La livraison vers ${payload.target} va etre relancee dans 3 secondes`);
        return;
    }

    if (state !== 'arrived') {
        return;
    }

    if (target === '' || target === START_ROOM_CODE) {
        return;
    }

    const now = Date.now();

    // Prevent duplicate sounds for repeated arrived status messages.
    if (lastPlayedDeliveryTarget === target && now - lastPlayedAt < 1200) {
        return;
    }

    lastPlayedDeliveryTarget = target;
    lastPlayedAt = now;
    playDeliverySuccessSound();
}

function handleMessage(rawData: unknown): void {
    if (typeof rawData !== 'string') {
        return;
    }

    try {
        const payload = JSON.parse(rawData) as DtRemoteMessage;
        console.log(payload);

        window.dispatchEvent(
            new CustomEvent<DtRemoteMessage>('dt:remote-message', {
                detail: payload,
            }),
        );

        if (payload.type === 'status') {
            handleDeliverySuccessNotification(payload);
            console.debug('[DT-REMOTE] status:', payload);
        }
    } catch {
        console.warn('[DT-REMOTE] Received non-JSON message from remote socket');
    }
}

function connect(): void {
    const url = getRemoteSocketUrl();

    if (url === '') {
        console.info('[DT-REMOTE] No VITE_DT_REMOTE_SOCKET_URL configured, skipping remote socket subscription');
        return;
    }

    socket = new WebSocket(url);

    socket.addEventListener('open', () => {
        reconnectAttempts = 0;
        console.info('[DT-REMOTE] Connected:', url);

        // Bootstrap queries expected by the remote DT server.
        sendJson({ type: 'list_rooms' });
        sendJson({ type: 'get_status' });
        // sendJson({ type: 'room_command', room: 'salle_pharmacie' });
    });

    socket.addEventListener('message', (event: MessageEvent) => {
        handleMessage(event.data);
    });

    socket.addEventListener('error', () => {
        console.error('[DT-REMOTE] Socket error');
    });

    socket.addEventListener('close', () => {
        reconnectAttempts += 1;
        console.warn('[DT-REMOTE] Disconnected, reconnecting...');
        scheduleReconnect();
    });
}

export function startRemoteDtSocketSubscription(): void {
    if (typeof window === 'undefined' || hasStarted) {
        return;
    }

    hasStarted = true;
    connect();
}
