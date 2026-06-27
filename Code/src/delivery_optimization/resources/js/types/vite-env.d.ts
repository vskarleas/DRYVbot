/// <reference types="vite/client" />

interface ImportMetaEnv {
	readonly VITE_DT_REMOTE_SOCKET_URL?: string;
}

interface ImportMeta {
	readonly env: ImportMetaEnv;
}
