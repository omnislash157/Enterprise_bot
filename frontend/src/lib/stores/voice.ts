import { writable, derived, get } from 'svelte/store';
import { websocket } from './websocket';

// ============================================================================
// API BASE
// ============================================================================

function getApiBase(): string {
    return import.meta.env.VITE_API_URL || 'http://localhost:8000';
}

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

        // Notify backend to open Deepgram connection
        websocket.send({
            type: 'voice_start',
            timestamp: Date.now(),
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
// TEXT-TO-SPEECH (Deepgram Aura)
// ============================================================================

export async function speakText(text: string, voice = 'professional'): Promise<void> {
    try {
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
        speechSynthesis.speak(utterance);
    }
}
