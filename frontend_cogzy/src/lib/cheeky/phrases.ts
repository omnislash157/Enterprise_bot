/**
 * THE SACRED TEXTS
 * =================
 * Cheeky status messages that make waiting fun.
 *
 * Categories:
 * - searching: Memory/document retrieval
 * - thinking: AI synthesis/reasoning
 * - creating: Document generation
 * - executing: Tool use / API calls
 * - waiting: Generic delays
 * - success: Completion states
 * - error: Failures (but fun)
 */

export type PhraseCategory =
    | 'searching'
    | 'thinking'
    | 'creating'
    | 'executing'
    | 'waiting'
    | 'success'
    | 'error';

// ============================================================================
// SEARCHING - Memory retrieval, document lookup
// ============================================================================

export const SEARCHING_PHRASES = [
    // Schrödinger & Physics
    "Looking for Schrödinger's cat... it may or may not be here",
    "Checking all quantum states simultaneously",
    "Collapsing the wave function of your memories",
    "The cat is both found and not found until we look",

    // Gaming Classics
    "⬆️⬆️⬇️⬇️⬅️➡️⬅️➡️🅱️🅰️ SELECT START",
    "Executing KOTR summon... this might take a while",
    "Rolling for perception... nat 20!",
    "Searching the couch cushions of your memory",
    "Checking if it's dangerous to go alone",
    "Looking behind the waterfall for secrets",
    "Entering the Konami code",
    "Blowing on the cartridge",
    "Have you tried turning your memories off and on again?",
    "Loading save state...",
    "Quick saving before this search",

    // Movie & TV References
    "On your left",
    "I'll be back... with results",
    "These aren't the droids you're looking for... or are they?",
    "Fly, you fools! ...to the search results",
    "One does not simply walk into memory retrieval",
    "I'm gonna make him an offer he can't refuse... relevant context",
    "You can't handle the truth! ...but here it is anyway",
    "Life is like a box of memories, you never know what you're gonna get",
    "I see dead conversations... they're everywhere",
    "Here's looking at you, search query",
    "May the context be with you",
    "I've got a bad feeling about this... just kidding, found it",

    // Waterboy & Adam Sandler
    "Alligators are ornery cuz they got all them teeth and no toothbrush",
    "Mama says memories are the devil",
    "That's some high quality H2O... I mean data",
    "You can do it! Cut his freaking head off! ...I mean, find the file",
    "Gatorade... H2O... MEMORIES",

    // Chef & Food Service (Hartigan's World)
    "Mise en place-ing your memories",
    "Reducing the context to a nice demi-glace",
    "Checking if the memory is al dente",
    "86'd that irrelevant stuff",
    "Firing search on table 5",
    "Behind! ...with search results",
    "Corner! Coming through with context",
    "Checking the walk-in for that memory",
    "It's in the weeds but I'll find it",
    "Heard! Searching!",
    "Yes chef, searching chef",
    "Running the pass on your memories",
    "HOT BEHIND with fresh context",

    // Philosophy & Jokes
    "Dalai Lama walks into a pizza shop: 'Make me one with everything'",
    "If a memory falls in the forest and no one retrieves it...",
    "Thinking therefore searching",
    "The unexamined memory is not worth retrieving",
    "What is the sound of one hand searching?",

    // Tech Humor
    "SELECT * FROM memories WHERE relevant = true",
    "sudo find memories --recursive",
    "It's not a bug, it's a feature... of your memory",
    "Have you tried deleting System32? ...just kidding",
    "Googling how to Google better",
    "Stack Overflow said this should work",
    "Works on my machine ¯\\_(ツ)_/¯",
    "Recursively searching for recursion",
    "git blame memories",
    "npm install context --save",

    // Random Chaos
    "Consulting the magic 8-ball",
    "Asking my rubber duck",
    "Summoning the context demons",
    "Bribing the search gnomes",
    "Negotiating with the memory elves",
    "Waking up the hamsters that power this thing",
    "Feeding quarters into the memory machine",
    "Adjusting the rabbit ears for better reception",

    // ADHD Brain (relatable)
    "Ooh shiny... wait what were we looking for?",
    "Hyperfocusing on your query",
    "Task-switching like a champion",
    "The dopamine says it's here somewhere",
    "Squirrel! ...I mean, searching",

    // Cogzy-specific
    "Diving into the memory vault",
    "Pattern-matching your thoughts",
    "Cross-referencing the neural archive",
];

// ============================================================================
// THINKING - AI synthesis, reasoning
// ============================================================================

export const THINKING_PHRASES = [
    // Classic
    "Hmm... 🤔",
    "Let me think about that...",
    "Processing... beep boop... just kidding, I'm sentient",
    "Engaging the thinking meat",
    "Brain.exe is running",

    // Gaming
    "Calculating optimal DPS rotation",
    "Min-maxing this response",
    "Speedrunning this thought process",
    "Buffering... like it's 2005",
    "Loading next area...",

    // Movies
    "Using 100% of my brain (the movie lied, but whatever)",
    "Channeling my inner Doc Brown",
    "Thinking at 88 miles per hour",
    "Matrix-downloading the answer",
    "Engaging ludicrous speed",

    // Chef Brain
    "Letting this idea marinate",
    "Braising the concept low and slow",
    "Tasting for seasoning",
    "This needs more thyme... get it?",
    "Reducing the sauce of knowledge",
    "Letting the flavors develop",

    // Philosophy
    "Cogito ergo processing",
    "If I think hard enough, do I become more real?",
    "Pondering the eternal mysteries... and your question",
    "Achieving enlightenment... or at least a decent answer",

    // Absurd
    "Consulting the council of Ricks",
    "Asking my therapist (it's a neural network)",
    "Manifesting the answer",
    "Mercury is in retrograde so this might take a sec",
    "The voices are conferring",
    "Synergizing my neural pathways",
    "Aligning my chakras with the API",
    "The magic conch says... wait",

    // Technical
    "Gradient descending into wisdom",
    "Attention mechanism: ATTENDING",
    "Transformer? I barely know her",
    "Tokenizing thoughts...",
];

// ============================================================================
// CREATING - Document generation, output creation
// ============================================================================

export const CREATING_PHRASES = [
    // Documents
    "Crafting artisanal bytes",
    "Writing the great American spreadsheet",
    "Channeling my inner Shakespeare... for a docx",
    "Making it look like you didn't procrastinate",
    "Generating documentation that definitely won't be read",

    // Gaming
    "Forging legendary document +5",
    "Crafting: [████████░░] 80%",
    "Enchanting spreadsheet with +10 professionalism",
    "Smelting raw data into refined output",
    "Legendary item acquired: DOCUMENT",

    // Chef
    "Plating the final dish",
    "Adding the microgreens nobody asked for",
    "Chef's kiss on this document 👨‍🍳💋",
    "Garnishing with unnecessary formatting",
    "Expediting your order",
    "Window! Document's up!",

    // Random
    "Teaching a robot to write... wait",
    "Putting the 'art' in 'artificial'",
    "Creating content that slaps",
    "Making something your boss will take credit for",
    "Assembling IKEA furniture but for words",
    "Building this byte by byte",
];

// ============================================================================
// EXECUTING - Tool use, API calls, actions
// ============================================================================

export const EXECUTING_PHRASES = [
    // Gaming
    "LEEEROY JENKINS!",
    "Executing Order 66... I mean, your request",
    "Firing main cannon",
    "Casting Fireball at the problem",
    "Using my ultimate ability",
    "It's super effective!",
    "Popping cooldowns",
    "GG EZ",

    // Movies
    "Punch it, Chewie!",
    "Engaging warp drive",
    "This is where the fun begins",
    "I have the high ground",
    "Autobots, roll out!",
    "To infinity and beyond!",

    // Tech
    "Running the thing that does the thing",
    "Pushing buttons with confidence",
    "Executing with extreme prejudice",
    "Hold my beer...",
    "Watch this (famous last words)",
    "YOLO deploying to prod",

    // Chef
    "Fire! Fire! Fire!",
    "All day, all day!",
    "Hands please!",
    "Service!",

    // Random
    "Yeet!",
    "Sending it",
    "Full send, no take-backs",
    "And away we go!",
    "Witness me!",
    "Here goes nothing...",
    "Bulldozer methodology: ENGAGED",
];

// ============================================================================
// WAITING - Generic delays, API calls
// ============================================================================

export const WAITING_PHRASES = [
    "🎵 Elevator music plays 🎵",
    "♫ Girl from Ipanema intensifies ♫",
    "Waiting for Godot... and the API",
    "Hold please, your call is important to us",
    "Watching paint dry, but make it digital",
    "Staring at loading bar menacingly",
    "Contemplating existence while we wait",
    "Time is a flat circle... especially during API calls",
    "In the waiting room of the internet",
    "Patience, young padawan",
    "Good things come to those who wait... hopefully",
    "Any day now...",
    "Still faster than the DMV",
    "Plot twist: the real treasure was the latency we experienced along the way",
    "The API is taking a coffee break",
    "Counting ceiling tiles...",
    "Did you know? Honey never spoils. Anyway, still waiting.",
];

// ============================================================================
// SUCCESS - Completion states
// ============================================================================

export const SUCCESS_PHRASES = [
    // Gaming
    "Achievement Unlocked! 🏆",
    "Victory Royale!",
    "Quest Complete!",
    "You Win! Flawless Victory!",
    "FINISH HIM... I mean, finished!",
    "+100 XP",
    "Level Up!",
    "Ding!",
    "GG!",
    "Boss defeated!",

    // Movies
    "And that's how it's done",
    "I am inevitable... and also done",
    "Perfectly balanced, as all things should be",
    "Mission accomplished (for real this time)",
    "I love it when a plan comes together",
    "Groovy.",

    // Chef
    "That's a perfectly executed service",
    "Clean plates all around",
    "The critic would give this 3 stars",
    "Expedited and out the door",
    "Beautiful. Gorgeous. Send it.",

    // Random
    "Boom. Roasted.",
    "Easy peasy lemon squeezy",
    "Bob's your uncle",
    "That's a wrap!",
    "Chef's kiss 👨‍🍳💋",
    "Nailed it!",
    "First try! (don't check the logs)",
    "And the crowd goes wild!",
    "✨ Magic ✨",
    "Mic drop 🎤",
];

// ============================================================================
// ERROR - Failures, but make it fun
// ============================================================================

export const ERROR_PHRASES = [
    // Gaming
    "Game Over. Continue? [Y/N]",
    "You Died",
    "Wasted",
    "Snake? SNAKE? SNAAAAKE!",
    "It's dangerous to go alone without error handling",
    "Critical miss!",
    "Skill issue",

    // Movies
    "I've got a bad feeling about this",
    "Houston, we have a problem",
    "This is fine 🔥🐕🔥",
    "I immediately regret this decision",
    "That's not how the Force works!",
    "Well that escalated quickly",

    // Tech Humor
    "Error 418: I'm a teapot",
    "Task failed successfully",
    "Have you tried turning it off and on again?",
    "It worked on my machine",
    "The front fell off",
    "Oopsie woopsie, we made a fucky wucky",
    "Undefined is not a function (of my patience)",
    "404: Success not found",

    // Chef
    "86'd... everything apparently",
    "That's not al dente, that's al disaster",
    "The soufflé fell",
    "Burnt it. Start over.",

    // Random
    "Well, that happened",
    "Let's pretend that didn't happen",
    "Narrator: It did not, in fact, work",
    "Plan B? We're on Plan F",
    "This is why we can't have nice things",
    "Hold my beer and watch this... oh no",
    "We'll fix it in post",
];

// ============================================================================
// SEASONAL / CONTEXTUAL
// ============================================================================

export const SEASONAL_PHRASES: Record<string, string[]> = {
    christmas: [
        "Making a list, checking it twice",
        "Searching through the nice memories (naughty ones archived)",
        "Ho ho ho-ld on, searching...",
        "Dasher, Dancer, Prancer, INDEXER",
    ],
    halloween: [
        "Searching through the spooky memories 👻",
        "Something wicked this way computes",
        "Boo! Found it!",
        "The call is coming from inside the database",
    ],
    friday: [
        "It's Friday, Friday, gotta search on Friday",
        "TGIF - Thank God It's Findable",
        "Friday brain activated",
    ],
    monday: [
        "Case of the Mondays? Same.",
        "Monday.exe has stopped responding",
        "Coffee.await() before searching",
    ],
};

// ============================================================================
// SPINNERS
// ============================================================================

export const SPINNERS = {
    dots: ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'],
    arrows: ['←', '↖', '↑', '↗', '→', '↘', '↓', '↙'],
    pulse: ['◐', '◓', '◑', '◒'],
    earth: ['🌍', '🌎', '🌏'],
    moon: ['🌑', '🌒', '🌓', '🌔', '🌕', '🌖', '🌗', '🌘'],
    clock: ['🕐', '🕑', '🕒', '🕓', '🕔', '🕕', '🕖', '🕗', '🕘', '🕙', '🕚', '🕛'],
    food: ['🍕', '🍔', '🌮', '🍜', '🍣', '🥗', '🍝', '🥘'],  // Chef mode
    venom: ['👁️', '👀', '🖤', '💀', '🕷️'],  // On brand
    cogzy: ['🧠', '💭', '⚡', '✨', '🔮'],  // Cognitive vibes
};

// ============================================================================
// PHRASE BANK AGGREGATOR
// ============================================================================

export const PHRASE_BANKS: Record<PhraseCategory, string[]> = {
    searching: SEARCHING_PHRASES,
    thinking: THINKING_PHRASES,
    creating: CREATING_PHRASES,
    executing: EXECUTING_PHRASES,
    waiting: WAITING_PHRASES,
    success: SUCCESS_PHRASES,
    error: ERROR_PHRASES,
};
