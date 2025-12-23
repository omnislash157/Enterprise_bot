import { writable, get } from 'svelte/store';
import { websocket } from './websocket';
import { auth } from './auth';

// Session state persistence keys
const SESSION_STORAGE_KEY = 'cogtwin_session';
const SESSION_TTL_MS = 60 * 60 * 1000; // 1 hour

interface Message {
	role: 'user' | 'assistant';
	content: string;
	timestamp: Date;
	traceId?: string;
}

interface PersistedSession {
	sessionId: string;
	department: string;
	messages: Message[];
	timestamp: number;
}

function saveSessionToStorage(sessionId: string, department: string, messages: Message[]): void {
	try {
		const data: PersistedSession = {
			sessionId,
			department,
			messages: messages.slice(-50), // Keep last 50 messages only
			timestamp: Date.now()
		};
		localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(data));
	} catch (e) {
		console.warn('[Session] Failed to save to localStorage:', e);
	}
}

function loadSessionFromStorage(sessionId: string): PersistedSession | null {
	try {
		const saved = localStorage.getItem(SESSION_STORAGE_KEY);
		if (!saved) return null;

		const data: PersistedSession = JSON.parse(saved);

		// Check if same session and not stale
		if (data.sessionId !== sessionId) {
			console.log('[Session] Different session ID, clearing storage');
			localStorage.removeItem(SESSION_STORAGE_KEY);
			return null;
		}

		if (Date.now() - data.timestamp > SESSION_TTL_MS) {
			console.log('[Session] Session expired, clearing storage');
			localStorage.removeItem(SESSION_STORAGE_KEY);
			return null;
		}

		return data;
	} catch (e) {
		console.warn('[Session] Failed to load from localStorage:', e);
		return null;
	}
}

function clearSessionStorage(): void {
	localStorage.removeItem(SESSION_STORAGE_KEY);
}

interface CognitiveState {
	phase: string;
	temperature: number;
	driftDetected: boolean;
	gapCount: number;
}

export interface SessionAnalytics {
	phase: string;
	phaseDescription: string;
	stability: number;
	temperature: number;
	focusScore: number;
	driftSignal: string | null;
	driftMagnitude: number;
	recurringPatterns: Array<{ topic: string; frequency: number; recency: number }>;
	hotspotTopics: Array<{ memory_id: string; temperature: number }>;
	emergingTopics: Array<{ memory_id: string; burst_intensity: number }>;
	sessionDurationMinutes: number;
	totalQueries: number;
	totalTokens: number;
	predictionAccuracy: number;
	suggestion: string;
	recentTransitions: Array<{ timestamp: string; from: string; to: string }>;
}

const DEFAULT_ANALYTICS: SessionAnalytics = {
	phase: 'idle',
	phaseDescription: 'Waiting for input',
	stability: 1.0,
	temperature: 0.5,
	focusScore: 0.0,
	driftSignal: null,
	driftMagnitude: 0.0,
	recurringPatterns: [],
	hotspotTopics: [],
	emergingTopics: [],
	sessionDurationMinutes: 0,
	totalQueries: 0,
	totalTokens: 0,
	predictionAccuracy: 0.0,
	suggestion: '',
	recentTransitions: [],
};

interface SessionState {
	messages: Message[];
	currentStream: string;
	inputValue: string;
	cognitiveState: CognitiveState;
	analytics: SessionAnalytics;
	isStreaming: boolean;
	currentDivision: string | null;  // Track the active division
	verified: boolean;               // Track if session is verified
	connectionState: 'connecting' | 'connected' | 'reconnecting' | 'disconnected';
	reconnectAttempts: number;
	sessionId: string | null;        // Track current session ID for persistence
}

function createSessionStore() {
	const store = writable<SessionState>({
		messages: [],
		currentStream: '',
		inputValue: '',
		cognitiveState: {
			phase: 'idle',
			temperature: 0.5,
			driftDetected: false,
			gapCount: 0,
		},
		analytics: { ...DEFAULT_ANALYTICS },
		isStreaming: false,
		currentDivision: null,
		verified: false,
		connectionState: 'disconnected',
		reconnectAttempts: 0,
		sessionId: null,
	});

	const { subscribe, set, update } = store;

	// Set up WebSocket message handler
	let unsubscribe: (() => void) | null = null;
	let wsUnsubscribe: (() => void) | null = null;
	let pendingDivision: string | null = null;  // Division we want after verify

	function initMessageHandler() {
		// Subscribe to WebSocket connection state
		wsUnsubscribe = websocket.subscribe((wsState) => {
			const sessionState = get(store);

			// Update connection state based on WebSocket state
			if (wsState.connected && sessionState.verified) {
				// Fully connected and verified
				update(s => ({ ...s, connectionState: 'connected', reconnectAttempts: 0 }));
			} else if (!wsState.connected && sessionState.verified) {
				// Was connected before, now disconnected - reconnecting
				update(s => ({
					...s,
					connectionState: 'reconnecting',
					reconnectAttempts: s.reconnectAttempts + 1
				}));
			} else if (wsState.error) {
				// Connection error
				update(s => ({ ...s, connectionState: 'disconnected' }));
			}
		});

		unsubscribe = websocket.onMessage((data) => {
			switch (data.type) {
				case 'stream_chunk':
					update(s => ({
						...s,
						currentStream: s.currentStream + data.content,
						isStreaming: !data.done,
					}));

					if (data.done) {
						update(s => {
							const assistantMsg: Message = {
								role: 'assistant',
								content: s.currentStream,
								timestamp: new Date(),
								traceId: data.trace_id,
							};
							const newMessages = [...s.messages, assistantMsg];

							// Auto-save to localStorage
							if (s.sessionId && s.currentDivision) {
								saveSessionToStorage(s.sessionId, s.currentDivision, newMessages);
							}

							return {
								...s,
								messages: newMessages,
								currentStream: '',
								isStreaming: false,
							};
						});
					}
					break;

				case 'verified':
					// Auth complete - check if division matches what we want
					const backendDivision = data.division || 'warehouse';
					update(s => ({
						...s,
						verified: true,
						currentDivision: backendDivision,
						connectionState: 'connected',
						reconnectAttempts: 0,
					}));

					console.log('[Session] Verified with division:', backendDivision);

					// If we have a pending division that differs, send set_division NOW
					if (pendingDivision && pendingDivision !== backendDivision) {
						console.log('[Session] Resending set_division:', pendingDivision, '(backend had:', backendDivision, ')');
						websocket.send({
							type: 'set_division',
							division: pendingDivision,
						});
					}
					pendingDivision = null;
					break;

				case 'division_changed':
					// Backend confirmed division change
					update(s => ({
						...s,
						currentDivision: data.division,
					}));
					console.log('[Session] Division changed to:', data.division);
					break;

				case 'cognitive_state':
					update(s => ({
						...s,
						cognitiveState: {
							phase: data.phase,
							temperature: data.temperature,
							driftDetected: data.drift_detected,
							gapCount: data.gap_count,
						},
					}));
					break;

				case 'session_analytics':
					update(s => ({
						...s,
						analytics: {
							phase: data.phase ?? s.analytics.phase,
							phaseDescription: data.phase_description ?? s.analytics.phaseDescription,
							stability: data.stability ?? s.analytics.stability,
							temperature: data.temperature ?? s.analytics.temperature,
							focusScore: data.focus_score ?? s.analytics.focusScore,
							driftSignal: data.drift_signal ?? s.analytics.driftSignal,
							driftMagnitude: data.drift_magnitude ?? s.analytics.driftMagnitude,
							recurringPatterns: data.recurring_patterns ?? s.analytics.recurringPatterns,
							hotspotTopics: data.hotspot_topics ?? s.analytics.hotspotTopics,
							emergingTopics: data.emerging_topics ?? s.analytics.emergingTopics,
							sessionDurationMinutes: data.session_duration_minutes ?? s.analytics.sessionDurationMinutes,
							totalQueries: data.total_queries ?? s.analytics.totalQueries,
							totalTokens: data.total_tokens ?? s.analytics.totalTokens,
							predictionAccuracy: data.prediction_accuracy ?? s.analytics.predictionAccuracy,
							suggestion: data.suggestion ?? s.analytics.suggestion,
							recentTransitions: data.recent_transitions ?? s.analytics.recentTransitions,
						},
					}));
					break;

				case 'connected':
					console.log('[Session] Connected:', data.session_id);
					break;

				case 'error':
					console.error('[Session] Error:', data.message);
					// Handle division access errors
					if (data.message?.includes('No access to department')) {
						console.warn('[Session] Division change rejected, reverting');
						// Revert to first accessible department from auth store
						const authState = get(auth);
						const fallbackDivision = authState?.user?.departments?.[0] || 'warehouse';
						update(s => ({
							...s,
							currentDivision: fallbackDivision,
						}));
					}
					break;
			}
		});
	}

	return {
		subscribe,

		init(sessionId: string, department?: string) {
			// Store session ID for persistence
			update(s => ({ ...s, sessionId, connectionState: 'connecting' }));

			// Try to restore from localStorage first
			const saved = loadSessionFromStorage(sessionId);
			if (saved) {
				console.log(`[Session] Restoring ${saved.messages.length} messages from localStorage`);
				update(s => ({
					...s,
					messages: saved.messages,
					currentDivision: saved.department
				}));
				// Use saved department if current doesn't match
				if (saved.department && saved.department !== department) {
					department = saved.department;
				}
			}

			// Store the department we want (will be checked after verify)
			pendingDivision = department || null;

			websocket.connect(sessionId);
			initMessageHandler();

			// Send verify message with auth after connection
			const email = auth.getEmail();
			if (email) {
				// Wait for connection to establish, then verify
				const checkConnection = setInterval(() => {
					const wsState = get(websocket as any);
					if (wsState?.connected) {
						clearInterval(checkConnection);
						console.log('[Session] Sending verify with division:', department);
						websocket.send({
							type: 'verify',
							email: email,
							division: department,  // Include division in verify
						});
					}
				}, 100);

				// Clear interval after 5 seconds if not connected
				setTimeout(() => clearInterval(checkConnection), 5000);
			}
		},

		setDivision(division: string) {
			const state = get(store);
			
			// If not verified yet, just store as pending
			if (!state.verified) {
				pendingDivision = division;
				console.log('[Session] Queued division change (not verified yet):', division);
				return;
			}
			
			// If already on this division, skip
			if (state.currentDivision === division) {
				console.log('[Session] Already on division:', division);
				return;
			}
			
			// Send to backend
			console.log('[Session] Sending set_division:', division);
			websocket.send({
				type: 'set_division',
				division: division,
			});
			
			// Optimistically update (will be confirmed by division_changed)
			update(s => ({ ...s, currentDivision: division }));
		},

		cleanup() {
			if (unsubscribe) {
				unsubscribe();
				unsubscribe = null;
			}
			if (wsUnsubscribe) {
				wsUnsubscribe();
				wsUnsubscribe = null;
			}
			pendingDivision = null;
			websocket.disconnect();
		},

		sendMessage(content?: string) {
			// Use parameter or fall back to store's inputValue
			const messageContent = content || get(store).inputValue.trim();

			if (!messageContent) return;

			// Add user message
			const userMsg: Message = {
				role: 'user',
				content: messageContent,
				timestamp: new Date(),
			};

			update(s => {
				const newMessages = [...s.messages, userMsg];

				// Auto-save to localStorage
				if (s.sessionId && s.currentDivision) {
					saveSessionToStorage(s.sessionId, s.currentDivision, newMessages);
				}

				return {
					...s,
					messages: newMessages,
					inputValue: '',
					currentStream: '',
					isStreaming: true,
				};
			});

			// Get current division to include in message
			const state = get(store);

			// Send to backend WITH division (belt and suspenders)
			websocket.send({
				type: 'message',
				content: messageContent,
				division: state.currentDivision,  // Include division in every message
			});
		},

		clearMessages() {
			update(s => ({
				...s,
				messages: [],
				currentStream: '',
			}));
		},
	};
}

export const session = createSessionStore();