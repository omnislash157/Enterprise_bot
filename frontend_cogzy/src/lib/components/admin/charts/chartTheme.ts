/**
 * Chart.js Cyberpunk Theme
 * Matches the app.css color scheme
 */

export const chartColors = {
    primary: '#00ff41',      // Matrix green (--neon-green)
    secondary: '#00ffff',    // Cyan (--neon-cyan)
    tertiary: '#ff00ff',     // Magenta (--neon-magenta)
    warning: '#ffaa00',      // Amber
    danger: '#ff4444',       // Red
    muted: '#444444',        // Dark gray
    background: '#0a0a0a',   // Near black (--bg-primary)
    surface: '#111111',      // (--bg-secondary)
    grid: 'rgba(0, 255, 65, 0.1)',  // Faint green grid
    text: '#808080',         // (--text-muted)
    textBright: '#e0e0e0',   // (--text-primary)
};

// Category colors for pie/bar charts
export const categoryColors = [
    '#00ff41', // PROCEDURAL - green
    '#00ffff', // LOOKUP - cyan
    '#ff00ff', // TROUBLESHOOTING - magenta
    '#ffaa00', // POLICY - amber
    '#ff4444', // CONTACT - red
    '#00ff88', // RETURNS - mint
    '#8800ff', // INVENTORY - purple
    '#ff8800', // SAFETY - orange
    '#0088ff', // SCHEDULE - blue
    '#ff0088', // ESCALATION - pink
    '#888888', // OTHER - gray
];

export const defaultChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: {
            labels: {
                color: chartColors.text,
                font: { family: "'Inter', sans-serif" },
            },
        },
        tooltip: {
            backgroundColor: chartColors.surface,
            titleColor: chartColors.textBright,
            bodyColor: chartColors.text,
            borderColor: chartColors.primary,
            borderWidth: 1,
        },
    },
    scales: {
        x: {
            grid: {
                color: chartColors.grid,
                drawBorder: false,
            },
            ticks: {
                color: chartColors.text,
                font: { family: "'Inter', sans-serif", size: 11 },
            },
        },
        y: {
            grid: {
                color: chartColors.grid,
                drawBorder: false,
            },
            ticks: {
                color: chartColors.text,
                font: { family: "'Inter', sans-serif", size: 11 },
            },
        },
    },
};

// Line chart with glow effect
export const lineChartOptions = {
    ...defaultChartOptions,
    elements: {
        line: {
            tension: 0.3,
            borderWidth: 2,
        },
        point: {
            radius: 3,
            hoverRadius: 5,
            backgroundColor: chartColors.primary,
            borderColor: chartColors.primary,
        },
    },
};

// Bar chart options
export const barChartOptions = {
    ...defaultChartOptions,
    plugins: {
        ...defaultChartOptions.plugins,
        legend: { display: false },
    },
};

// Doughnut/pie options
export const doughnutOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: {
            position: 'right' as const,
            labels: {
                color: chartColors.text,
                font: { family: "'Inter', sans-serif", size: 11 },
                padding: 12,
            },
        },
    },
    cutout: '60%',
};
