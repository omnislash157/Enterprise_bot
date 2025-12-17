/**
 * CheekyStatus Engine
 * ====================
 * Makes waiting fun with rotating personality phrases.
 */

import {
    PHRASE_BANKS,
    SEASONAL_PHRASES,
    SPINNERS,
    type PhraseCategory
} from './phrases';

export interface CheekyConfig {
    /** Enable cheeky phrases (false = boring mode) */
    enableCheeky: boolean;
    /** Include emoji in phrases */
    enableEmoji: boolean;
    /** Add seasonal phrases based on date */
    enableSeasonal: boolean;
    /** Max phrase length before truncation */
    maxLength: number;
    /** How many recent phrases to avoid repeating */
    recentAvoidCount: number;
    /** Phrase rotation interval in ms */
    rotationInterval: number;
}

const DEFAULT_CONFIG: CheekyConfig = {
    enableCheeky: true,
    enableEmoji: true,
    enableSeasonal: true,
    maxLength: 100,
    recentAvoidCount: 10,
    rotationInterval: 3000,
};

export class CheekyStatus {
    private config: CheekyConfig;
    private recent: string[] = [];
    private customPhrases: Record<string, string[]> = {};

    constructor(config: Partial<CheekyConfig> = {}) {
        this.config = { ...DEFAULT_CONFIG, ...config };
    }

    /**
     * Get a cheeky phrase for the given category.
     */
    get(category: PhraseCategory, context?: string): string {
        if (!this.config.enableCheeky) {
            return this.getBoring(category);
        }

        // Build phrase pool
        let phrases = [...(PHRASE_BANKS[category] || PHRASE_BANKS.waiting)];

        // Add custom phrases
        if (this.customPhrases[category]) {
            phrases = [...phrases, ...this.customPhrases[category]];
        }

        // Add seasonal phrases
        if (this.config.enableSeasonal) {
            const seasonal = this.getSeasonalPhrases();
            phrases = [...phrases, ...seasonal];
        }

        // Filter emoji if disabled
        if (!this.config.enableEmoji) {
            phrases = phrases.map(p => this.stripEmoji(p));
        }

        // Avoid recent phrases
        let available = phrases.filter(p => this.recent.indexOf(p) === -1);
        if (available.length === 0) {
            available = phrases;
            this.recent = [];
        }

        // Random selection
        const phrase = available[Math.floor(Math.random() * available.length)];

        // Track recent
        this.recent.push(phrase);
        if (this.recent.length > this.config.recentAvoidCount) {
            this.recent.shift();
        }

        // Truncate if needed
        if (phrase.length > this.config.maxLength) {
            return phrase.slice(0, this.config.maxLength - 3) + '...';
        }

        return phrase;
    }

    /**
     * Get a random spinner frame set.
     */
    getSpinner(type: keyof typeof SPINNERS = 'food'): string[] {
        return SPINNERS[type] || SPINNERS.dots;
    }

    /**
     * Add custom phrases to a category.
     */
    addPhrases(category: string, phrases: string[]): void {
        if (!this.customPhrases[category]) {
            this.customPhrases[category] = [];
        }
        this.customPhrases[category].push(...phrases);
    }

    /**
     * Toggle cheeky mode on/off.
     */
    setCheeky(enabled: boolean): void {
        this.config.enableCheeky = enabled;
    }

    /**
     * Update configuration.
     */
    configure(updates: Partial<CheekyConfig>): void {
        this.config = { ...this.config, ...updates };
    }

    // ========== Private Methods ==========

    private getBoring(category: PhraseCategory): string {
        const boring: Record<PhraseCategory, string> = {
            searching: 'Searching...',
            thinking: 'Thinking...',
            creating: 'Creating...',
            executing: 'Executing...',
            waiting: 'Please wait...',
            success: 'Done!',
            error: 'An error occurred.',
        };
        return boring[category] || 'Processing...';
    }

    private getSeasonalPhrases(): string[] {
        const now = new Date();
        const phrases: string[] = [];

        // Christmas (December)
        if (now.getMonth() === 11) {
            phrases.push(...(SEASONAL_PHRASES.christmas || []));
        }

        // Halloween (Oct 15-31)
        if (now.getMonth() === 9 && now.getDate() >= 15) {
            phrases.push(...(SEASONAL_PHRASES.halloween || []));
        }

        // Friday
        if (now.getDay() === 5) {
            phrases.push(...(SEASONAL_PHRASES.friday || []));
        }

        // Monday
        if (now.getDay() === 1) {
            phrases.push(...(SEASONAL_PHRASES.monday || []));
        }

        return phrases;
    }

    private stripEmoji(text: string): string {
        // Remove common emoji ranges
        return text
            .replace(/[\uD83C-\uDBFF\uDC00-\uDFFF]+/g, '')
            .replace(/[\u2600-\u27BF]/g, '')
            .trim();
    }
}

// Global singleton instance
export const cheeky = new CheekyStatus();

// Quick helper
export function getStatus(category: PhraseCategory): string {
    return cheeky.get(category);
}
