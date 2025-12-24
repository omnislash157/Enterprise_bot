import { writable, derived, get } from 'svelte/store';
import { websocket } from './websocket';
import { browser } from '$app/environment';

// ============================================================================
// API BASE
// ============================================================================

function getApiBase(): string {
    return import.meta.env.VITE_API_URL || 'http://localhost:8000';
}

// ============================================================================
// LANGUAGE STORE - Persisted to localStorage
// ============================================================================

export type Language = 'en' | 'es';

function createLanguageStore() {
    // Load from localStorage if in browser
    const stored = browser ? localStorage.getItem('userLanguage') as Language : null;
    const initial: Language = stored === 'es' ? 'es' : 'en';

    const { subscribe, set, update } = writable<Language>(initial);

    return {
        subscribe,
        set(lang: Language) {
            if (browser) {
                localStorage.setItem('userLanguage', lang);
            }
            set(lang);
        },
        toggle() {
            update(current => {
                const newLang = current === 'en' ? 'es' : 'en';
                if (browser) {
                    localStorage.setItem('userLanguage', newLang);
                }
                return newLang;
            });
        }
    };
}

export const userLanguage = createLanguageStore();

// ============================================================================
// VOICE SPEED STORE - Persisted to localStorage
// ============================================================================

function createVoiceSpeedStore() {
    const stored = browser ? localStorage.getItem('voiceSpeed') : null;
    const initial = stored ? parseFloat(stored) : 1.35;  // Default 1.35x

    const { subscribe, set } = writable<number>(initial);

    return {
        subscribe,
        set(speed: number) {
            // Clamp between 0.75 and 2.0
            const clamped = Math.max(0.75, Math.min(2.0, speed));
            if (browser) {
                localStorage.setItem('voiceSpeed', clamped.toString());
            }
            set(clamped);
        }
    };
}

export const voiceSpeed = createVoiceSpeedStore();

// ============================================================================
// TYPES
// ============================================================================

type RecordingState = 'idle' | 'requesting' | 'recording' | 'processing' | 'error';

export interface VoiceState {
    isRecording: boolean;
    state: RecordingState;
    transcript: string;
    finalTranscript: string;
    error: string | null;
    permissionGranted: boolean;
    permissionDenied: boolean;
}

// ============================================================================
// STORE
// ============================================================================

function createVoiceStore() {
    const { subscribe, set, update } = writable<VoiceState>({
        isRecording: false,
        state: 'idle',
        transcript: '',
        finalTranscript: '',
        error: null,
        permissionGranted: false,
        permissionDenied: false,
    });

    let mediaRecorder: MediaRecorder | null = null;
    let audioStream: MediaStream | null = null;

    async function requestPermission(): Promise<boolean> {
        update(s => ({ ...s, state: 'requesting' }));

        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    sampleRate: 16000,
                }
            });

            update(s => ({
                ...s,
                permissionGranted: true,
                permissionDenied: false,
                state: 'idle',
            }));

            audioStream = stream;
            return true;

        } catch (error) {
            console.error('[Voice] Permission denied:', error);
            update(s => ({
                ...s,
                permissionGranted: false,
                permissionDenied: true,
                state: 'error',
                error: 'Microphone permission denied',
            }));
            return false;
        }
    }

    async function startRecording() {
        const state = get({ subscribe });

        if (!state.permissionGranted) {
            const granted = await requestPermission();
            if (!granted) return;
        }

        if (!audioStream) {
            audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        }

        // Notify backend to open Deepgram connection with current language
        const currentLanguage = get(userLanguage);
        websocket.send({
            type: 'voice_start',
            timestamp: Date.now(),
            language: currentLanguage,  // 'en' or 'es'
        });

        mediaRecorder = new MediaRecorder(audioStream, {
            mimeType: 'audio/webm;codecs=opus',
        });

        mediaRecorder.ondataavailable = async (event) => {
            if (event.data.size > 0) {
                const reader = new FileReader();
                reader.onloadend = () => {
                    const base64 = (reader.result as string).split(',')[1];
                    websocket.send({
                        type: 'voice_chunk',
                        audio: base64,
                        timestamp: Date.now(),
                    });
                };
                reader.readAsDataURL(event.data);
            }
        };

        mediaRecorder.onerror = (error) => {
            console.error('[Voice] Recording error:', error);
            stopRecording();
            update(s => ({
                ...s,
                state: 'error',
                error: 'Recording failed',
            }));
        };

        mediaRecorder.start(100); // 100ms chunks

        update(s => ({
            ...s,
            isRecording: true,
            state: 'recording',
            transcript: '',
            error: null,
        }));

        console.log('[Voice] Recording started');
    }

    function stopRecording() {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
        }

        websocket.send({
            type: 'voice_stop',
            timestamp: Date.now(),
        });

        update(s => ({
            ...s,
            isRecording: false,
            state: 'processing',
        }));

        console.log('[Voice] Recording stopped');

        setTimeout(() => {
            update(s => ({ ...s, state: 'idle' }));
        }, 1000);
    }

    // Message handler for transcripts
    websocket.onMessage((data: any) => {
        if (data.type === 'voice_transcript') {
            if (data.is_final) {
                update(s => ({
                    ...s,
                    finalTranscript: s.finalTranscript + ' ' + data.transcript,
                    transcript: '',
                }));
            } else {
                update(s => ({
                    ...s,
                    transcript: data.transcript,
                }));
            }
        }

        if (data.type === 'voice_error') {
            update(s => ({
                ...s,
                state: 'error',
                error: data.error,
                isRecording: false,
            }));
            if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                mediaRecorder.stop();
            }
        }
    });

    return {
        subscribe,

        async toggle() {
            const state = get({ subscribe });
            if (state.isRecording) {
                stopRecording();
            } else {
                await startRecording();
            }
        },

        stop() {
            stopRecording();
        },

        clearTranscript() {
            update(s => ({ ...s, transcript: '', finalTranscript: '' }));
        },

        clearError() {
            update(s => ({ ...s, error: null, state: 'idle' }));
        },

        cleanup() {
            if (mediaRecorder) {
                mediaRecorder.stop();
                mediaRecorder = null;
            }
            if (audioStream) {
                audioStream.getTracks().forEach(track => track.stop());
                audioStream = null;
            }
        }
    };
}

export const voice = createVoiceStore();
export const isRecording = derived(voice, $voice => $voice.isRecording);

// ============================================================================
// TEXT-TO-SPEECH (Deepgram Aura) - Synchronized Streaming
// ============================================================================

// Audio queue with callbacks for text sync
interface QueuedAudio {
    audio: HTMLAudioElement;
    sentence: string;
    onStart?: () => void;
}

let audioQueue: QueuedAudio[] = [];
let isPlaying = false;

/**
 * Queue a sentence for TTS playback with optional callback when audio STARTS.
 * This enables synchronized text reveal - text appears as audio plays.
 * @param language - 'en' or 'es' for voice selection
 */
export async function queueSentenceAudio(
    sentence: string,
    onStart?: () => void,
    language: Language = 'en'
): Promise<void> {
    try {
        // Use language-specific voice
        const voice = language === 'es' ? 'es' : 'default';
        const response = await fetch(`${getApiBase()}/api/tts`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: sentence, voice })
        });

        if (!response.ok) {
            // Still call onStart so text appears even if TTS fails
            onStart?.();
            return;
        }

        const blob = await response.blob();
        const audio = new Audio(URL.createObjectURL(blob));
        audioQueue.push({ audio, sentence, onStart });

        if (!isPlaying) playNext();
    } catch (err) {
        console.error('[TTS] Sentence queue failed:', err);
        // Still reveal text on error
        onStart?.();
    }
}

function playNext(): void {
    if (audioQueue.length === 0) {
        isPlaying = false;
        return;
    }
    isPlaying = true;
    const { audio, onStart } = audioQueue.shift()!;

    // Apply voice speed setting
    audio.playbackRate = get(voiceSpeed);

    // Call onStart callback when audio begins - this reveals the text
    onStart?.();

    audio.onended = () => {
        URL.revokeObjectURL(audio.src);
        playNext();
    };
    audio.onerror = () => {
        URL.revokeObjectURL(audio.src);
        playNext(); // Skip failed audio, continue queue
    };
    audio.play().catch(() => playNext()); // Handle autoplay restrictions
}

/**
 * Detect complete sentences in streaming text.
 * Returns the completed sentence (if any) and remaining buffer.
 */
export function streamingSentenceDetector(chunk: string, buffer: string): { buffer: string; sentence: string | null } {
    buffer += chunk;
    // Match sentence ending with . ! or ? followed by whitespace
    const match = buffer.match(/^(.*?[.!?])\s+(.*)$/s);
    if (match) {
        return { buffer: match[2], sentence: match[1] };
    }
    return { buffer, sentence: null };
}

/**
 * Clear the audio queue (e.g., when user sends new message)
 */
export function clearAudioQueue(): void {
    audioQueue.forEach(({ audio }) => {
        audio.pause();
        URL.revokeObjectURL(audio.src);
    });
    audioQueue = [];
    isPlaying = false;
}

/**
 * Legacy: Speak full text at once (fallback for short responses)
 * @param language - 'en' or 'es' for voice selection
 */
export async function speakText(text: string, language: Language = 'en'): Promise<void> {
    try {
        // Use language-specific voice
        const voice = language === 'es' ? 'es' : 'professional';
        const response = await fetch(`${getApiBase()}/api/tts`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, voice })
        });

        if (!response.ok) throw new Error('TTS failed');

        const audioBlob = await response.blob();
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);

        audio.onended = () => URL.revokeObjectURL(audioUrl);
        await audio.play();

    } catch (err) {
        console.error('[TTS] Failed:', err);
        // Fallback to browser TTS
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = language === 'es' ? 'es-ES' : 'en-US';
        speechSynthesis.speak(utterance);
    }
}
