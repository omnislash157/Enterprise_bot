import { writable } from 'svelte/store';
import { artifacts } from './artifacts';

interface WebSocketState {
	connected: boolean;
	sessionId: string | null;
	error: string | null;
}

// Build WebSocket URL from environment or current location
function getWebSocketUrl(sessionId: string): string {
	// Check for explicit API URL from environment
	const apiUrl = import.meta.env.VITE_API_URL;

	if (apiUrl) {
		// Convert http(s) to ws(s)
		const wsProtocol = apiUrl.startsWith('https') ? 'wss' : 'ws';
		const host = new URL(apiUrl).host;
		return `${wsProtocol}://${host}/ws/${sessionId}`;
	}

	// Fallback: use current page location (works for same-origin deploys)
	if (typeof window !== 'undefined') {
		const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
		return `${wsProtocol}://${window.location.host}/ws/${sessionId}`;
	}

	// Dev fallback
	return `ws://localhost:8000/ws/${sessionId}`;
}

function createWebSocketStore() {
	const { subscribe, set, update } = writable<WebSocketState>({
		connected: false,
		sessionId: null,
		error: null,
	});

	let ws: WebSocket | null = null;
	let messageHandlers: ((data: any) => void)[] = [];
	let reconnectAttempts = 0;
	const maxReconnectAttempts = 5;
	let currentSessionId: string | null = null;
	let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
	let intentionalClose = false;

	function attemptReconnect() {
		if (!currentSessionId || reconnectAttempts >= maxReconnectAttempts || intentionalClose) {
			if (reconnectAttempts >= maxReconnectAttempts) {
				console.log('[WS] Max reconnect attempts reached');
			}
			return;
		}

		reconnectAttempts++;
		const delay = Math.min(1000 * Math.pow(2, reconnectAttempts - 1), 10000); // Exponential backoff, max 10s
		console.log(`[WS] Attempting reconnect in ${delay}ms (attempt ${reconnectAttempts}/${maxReconnectAttempts})`);

		reconnectTimeout = setTimeout(() => {
			if (currentSessionId && !intentionalClose) {
				store.connect(currentSessionId);
			}
		}, delay);
	}

	const store = {
		subscribe,

		connect(sessionId: string) {
			// Clear any pending reconnect
			if (reconnectTimeout) {
				clearTimeout(reconnectTimeout);
				reconnectTimeout = null;
			}

			intentionalClose = false;
			currentSessionId = sessionId;
			const url = getWebSocketUrl(sessionId);

			try {
				ws = new WebSocket(url);

				ws.onopen = () => {
					reconnectAttempts = 0;
					update(s => ({ ...s, connected: true, sessionId, error: null }));
					console.log(`[WS] Connected to session ${sessionId}`);
				};

				ws.onmessage = (event) => {
					try {
						const data = JSON.parse(event.data);
						messageHandlers.forEach(handler => handler(data));

						// Auto-handle artifact emissions
						if (data.type === 'artifact_emit' && data.artifact) {
							artifacts.add(data.artifact, data.suggested || false);
						}
					} catch (e) {
						console.error('[WS] Failed to parse message:', e);
					}
				};

				ws.onerror = (error) => {
					console.error('[WS] Error:', error);
					update(s => ({ ...s, error: 'Connection error' }));
				};

				ws.onclose = (event) => {
					update(s => ({ ...s, connected: false }));
					console.log('[WS] Disconnected:', event.code, event.reason || '');

					// Auto-reconnect on abnormal close (not intentional)
					if (!event.wasClean && !intentionalClose && currentSessionId) {
						attemptReconnect();
					}
				};
			} catch (e) {
				update(s => ({ ...s, error: `Failed to connect: ${e}` }));
				attemptReconnect();
			}
		},

		disconnect() {
			intentionalClose = true;
			if (reconnectTimeout) {
				clearTimeout(reconnectTimeout);
				reconnectTimeout = null;
			}
			if (ws) {
				ws.close();
				ws = null;
			}
			currentSessionId = null;
			reconnectAttempts = 0;
			update(s => ({ ...s, connected: false, sessionId: null }));
		},

		send(data: any) {
			if (ws && ws.readyState === WebSocket.OPEN) {
				ws.send(JSON.stringify(data));
			} else {
				console.warn('[WS] Cannot send - not connected');
			}
		},

		onMessage(handler: (data: any) => void) {
			messageHandlers.push(handler);
			return () => {
				messageHandlers = messageHandlers.filter(h => h !== handler);
			};
		},

		async commitAndClose() {
			if (ws && ws.readyState === WebSocket.OPEN) {
				ws.send(JSON.stringify({ type: 'commit' }));
				await new Promise(resolve => setTimeout(resolve, 500));
				ws.close();
			}
		}
	};

	return store;
}

export const websocket = createWebSocketStore();