/**
 * CSV Export Utility
 *
 * Usage:
 *   downloadCSV(data, 'queries-by-hour.csv')
 */

export function arrayToCSV(data: Array<Record<string, unknown>>): string {
    if (data.length === 0) return '';

    const headers = Object.keys(data[0]);
    const rows = data.map((row) =>
        headers
            .map((h) => {
                const val = row[h];
                // Escape quotes and wrap in quotes if contains comma
                if (typeof val === 'string' && (val.includes(',') || val.includes('"'))) {
                    return `"${val.replace(/"/g, '""')}"`;
                }
                return val ?? '';
            })
            .join(',')
    );

    return [headers.join(','), ...rows].join('\n');
}

export function downloadCSV(data: Array<Record<string, unknown>>, filename: string): void {
    const csv = arrayToCSV(data);
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.style.display = 'none';

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    URL.revokeObjectURL(url);
}

// Convenience exports for specific data types
export function exportQueries(data: Array<{ hour: string; count: number }>): void {
    downloadCSV(data, `queries-${new Date().toISOString().split('T')[0]}.csv`);
}

export function exportCategories(data: Array<{ category: string; count: number }>): void {
    downloadCSV(data, `categories-${new Date().toISOString().split('T')[0]}.csv`);
}

export function exportDepartments(data: Array<Record<string, unknown>>): void {
    downloadCSV(data, `departments-${new Date().toISOString().split('T')[0]}.csv`);
}

export function exportErrors(data: Array<Record<string, unknown>>): void {
    downloadCSV(data, `errors-${new Date().toISOString().split('T')[0]}.csv`);
}
