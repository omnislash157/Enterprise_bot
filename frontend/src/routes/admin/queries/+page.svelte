<script lang="ts">
    /**
     * Query Log Viewer - Admin page to see what users are asking
     * 
     * Priority feature: "Where can we see the questions?"
     * Shows paginated, searchable, filterable list of all user queries.
     */
    import { onMount, onDestroy } from 'svelte';
    import { observabilityStore, queries, queriesTotal, queryStats } from '$lib/stores/observability';
    import { Search, Download, ChevronDown, ChevronRight, Clock, User, MessageSquare, Zap, Filter, RefreshCw } from 'lucide-svelte';
    
    // Filters
    let hours = 24;
    let department = '';
    let userEmail = '';
    let searchQuery = '';
    let limit = 50;
    let offset = 0;
    
    // UI State
    let expandedRow: string | null = null;
    let loading = false;
    let autoRefresh = false;
    let refreshTimer: ReturnType<typeof setInterval> | null = null;
    
    // Departments for filter dropdown (populated from stats)
    $: departments = $queryStats?.by_department?.map(d => d.department) || [];
    
    // Pagination
    $: totalPages = Math.ceil($queriesTotal / limit);
    $: currentPage = Math.floor(offset / limit) + 1;
    
    async function loadData() {
        loading = true;
        await Promise.all([
            observabilityStore.loadQueries({
                hours,
                department: department || undefined,
                user_email: userEmail || undefined,
                search: searchQuery || undefined,
                limit,
                offset,
            }),
            observabilityStore.loadQueryStats(hours),
        ]);
        loading = false;
    }
    
    function handleSearch() {
        offset = 0;
        loadData();
    }
    
    function goToPage(page: number) {
        offset = (page - 1) * limit;
        loadData();
    }
    
    function toggleRow(id: string) {
        expandedRow = expandedRow === id ? null : id;
    }
    
    function formatTime(dateStr: string): string {
        const date = new Date(dateStr);
        return date.toLocaleTimeString('en-US', { 
            hour: '2-digit', 
            minute: '2-digit',
            second: '2-digit'
        });
    }
    
    function formatDate(dateStr: string): string {
        const date = new Date(dateStr);
        const today = new Date();
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);
        
        if (date.toDateString() === today.toDateString()) {
            return 'Today';
        } else if (date.toDateString() === yesterday.toDateString()) {
            return 'Yesterday';
        }
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }
    
    function truncate(text: string, length: number): string {
        if (!text) return '';
        return text.length > length ? text.substring(0, length) + '...' : text;
    }
    
    function getResponseTimeColor(ms: number): string {
        if (ms < 500) return 'text-green-400';
        if (ms < 1500) return 'text-yellow-400';
        return 'text-red-400';
    }
    
    function toggleAutoRefresh() {
        autoRefresh = !autoRefresh;
        if (autoRefresh) {
            refreshTimer = setInterval(loadData, 30000);
        } else if (refreshTimer) {
            clearInterval(refreshTimer);
            refreshTimer = null;
        }
    }
    
    function exportCsv() {
        const url = observabilityStore.getQueryExportUrl(hours, department || undefined);
        window.open(url, '_blank');
    }
    
    onMount(() => {
        loadData();
    });
    
    onDestroy(() => {
        if (refreshTimer) {
            clearInterval(refreshTimer);
        }
    });
</script>

<svelte:head>
    <title>Query Log | CogTwin Admin</title>
</svelte:head>

<div class="p-6 space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
        <div>
            <h1 class="text-2xl font-bold text-white">Query Log</h1>
            <p class="text-gray-400 text-sm mt-1">
                See what users are asking the bot
            </p>
        </div>
        
        <div class="flex items-center gap-3">
            <button
                on:click={toggleAutoRefresh}
                class="flex items-center gap-2 px-3 py-2 rounded-lg transition-colors
                       {autoRefresh ? 'bg-green-600/20 text-green-400' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}"
            >
                <RefreshCw size={16} class={autoRefresh ? 'animate-spin' : ''} />
                {autoRefresh ? 'Auto-refreshing' : 'Auto-refresh'}
            </button>
            
            <button
                on:click={exportCsv}
                class="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 
                       text-white rounded-lg transition-colors"
            >
                <Download size={16} />
                Export CSV
            </button>
        </div>
    </div>
    
    <!-- Stats Cards -->
    {#if $queryStats}
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div class="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
                <div class="text-3xl font-bold text-white">{$queryStats.total_queries}</div>
                <div class="text-sm text-gray-400">Total Queries</div>
            </div>
            <div class="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
                <div class="text-3xl font-bold text-cyan-400">{$queryStats.unique_users}</div>
                <div class="text-sm text-gray-400">Unique Users</div>
            </div>
            <div class="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
                <div class="text-3xl font-bold text-emerald-400">{$queryStats.avg_response_time_ms}ms</div>
                <div class="text-sm text-gray-400">Avg Response Time</div>
            </div>
            <div class="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
                <div class="text-3xl font-bold text-amber-400">{$queryStats.avg_chunks_used}</div>
                <div class="text-sm text-gray-400">Avg Chunks Used</div>
            </div>
        </div>
    {/if}
    
    <!-- Filters -->
    <div class="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
        <div class="flex items-center gap-2 mb-3 text-gray-400">
            <Filter size={16} />
            <span class="text-sm font-medium">Filters</span>
        </div>
        
        <div class="grid grid-cols-1 md:grid-cols-5 gap-4">
            <!-- Time Range -->
            <select
                bind:value={hours}
                on:change={handleSearch}
                class="bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white
                       focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            >
                <option value={1}>Last 1 hour</option>
                <option value={6}>Last 6 hours</option>
                <option value={24}>Last 24 hours</option>
                <option value={48}>Last 48 hours</option>
                <option value={168}>Last 7 days</option>
            </select>
            
            <!-- Department -->
            <select
                bind:value={department}
                on:change={handleSearch}
                class="bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white
                       focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            >
                <option value="">All Departments</option>
                {#each departments as dept}
                    <option value={dept}>{dept}</option>
                {/each}
            </select>
            
            <!-- User Email -->
            <input
                type="text"
                bind:value={userEmail}
                placeholder="Filter by user..."
                class="bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white
                       placeholder-gray-400 focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            />
            
            <!-- Search -->
            <div class="relative md:col-span-2">
                <Search size={16} class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                    type="text"
                    bind:value={searchQuery}
                    placeholder="Search queries..."
                    on:keydown={(e) => e.key === 'Enter' && handleSearch()}
                    class="w-full bg-gray-700 border border-gray-600 rounded-lg pl-10 pr-4 py-2 text-white
                           placeholder-gray-400 focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
            </div>
        </div>
    </div>
    
    <!-- Query Table -->
    <div class="bg-gray-800/50 rounded-lg border border-gray-700 overflow-hidden">
        {#if loading}
            <div class="flex items-center justify-center py-12">
                <div class="animate-spin rounded-full h-8 w-8 border-2 border-indigo-500 border-t-transparent"></div>
            </div>
        {:else if $queries.length === 0}
            <div class="text-center py-12 text-gray-400">
                <MessageSquare size={48} class="mx-auto mb-4 opacity-50" />
                <p>No queries found for the selected filters.</p>
            </div>
        {:else}
            <table class="w-full">
                <thead class="bg-gray-900/50 text-gray-400 text-xs uppercase">
                    <tr>
                        <th class="w-8 px-4 py-3"></th>
                        <th class="px-4 py-3 text-left">Timestamp</th>
                        <th class="px-4 py-3 text-left">User</th>
                        <th class="px-4 py-3 text-left">Query</th>
                        <th class="px-4 py-3 text-left">Dept</th>
                        <th class="px-4 py-3 text-right">Response Time</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-gray-700">
                    {#each $queries as query (query.id)}
                        <tr
                            class="hover:bg-gray-700/30 cursor-pointer transition-colors"
                            on:click={() => toggleRow(query.id)}
                        >
                            <td class="px-4 py-3 text-gray-400">
                                {#if expandedRow === query.id}
                                    <ChevronDown size={16} />
                                {:else}
                                    <ChevronRight size={16} />
                                {/if}
                            </td>
                            <td class="px-4 py-3 text-gray-300 whitespace-nowrap">
                                <div class="text-sm">{formatDate(query.created_at)}</div>
                                <div class="text-xs text-gray-500">{formatTime(query.created_at)}</div>
                            </td>
                            <td class="px-4 py-3">
                                <div class="flex items-center gap-2">
                                    <User size={14} class="text-gray-500" />
                                    <span class="text-gray-300 text-sm">
                                        {query.user_email?.split('@')[0] || 'anonymous'}
                                    </span>
                                </div>
                            </td>
                            <td class="px-4 py-3 text-white max-w-md">
                                <span class="text-sm">{truncate(query.query_text, 60)}</span>
                            </td>
                            <td class="px-4 py-3">
                                <span class="text-xs px-2 py-1 rounded-full bg-gray-700 text-gray-300">
                                    {query.inferred_department || query.department || 'general'}
                                </span>
                            </td>
                            <td class="px-4 py-3 text-right">
                                <span class="text-sm font-mono {getResponseTimeColor(query.response_time_ms)}">
                                    {query.response_time_ms?.toFixed(0) || '?'}ms
                                </span>
                            </td>
                        </tr>
                        
                        <!-- Expanded Detail Row -->
                        {#if expandedRow === query.id}
                            <tr class="bg-gray-900/50">
                                <td colspan="6" class="px-4 py-4">
                                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                                        <!-- Full Query -->
                                        <div>
                                            <h4 class="text-sm font-medium text-gray-400 mb-2 flex items-center gap-2">
                                                <MessageSquare size={14} />
                                                Full Query
                                            </h4>
                                            <div class="bg-gray-800 rounded-lg p-3 text-white text-sm max-h-40 overflow-y-auto">
                                                {query.query_text || 'No query text'}
                                            </div>
                                        </div>
                                        
                                        <!-- Response -->
                                        <div>
                                            <h4 class="text-sm font-medium text-gray-400 mb-2 flex items-center gap-2">
                                                <Zap size={14} />
                                                Response
                                            </h4>
                                            <div class="bg-gray-800 rounded-lg p-3 text-gray-300 text-sm max-h-40 overflow-y-auto">
                                                {truncate(query.response_text || 'No response', 500)}
                                            </div>
                                        </div>
                                        
                                        <!-- Metadata -->
                                        <div class="md:col-span-2">
                                            <h4 class="text-sm font-medium text-gray-400 mb-2">Details</h4>
                                            <div class="flex flex-wrap gap-4 text-sm">
                                                <div class="bg-gray-800 rounded px-3 py-1">
                                                    <span class="text-gray-500">Complexity:</span>
                                                    <span class="text-white ml-1">{query.complexity_score || 'N/A'}</span>
                                                </div>
                                                <div class="bg-gray-800 rounded px-3 py-1">
                                                    <span class="text-gray-500">Intent:</span>
                                                    <span class="text-white ml-1">{query.intent_type || 'Unknown'}</span>
                                                </div>
                                                <div class="bg-gray-800 rounded px-3 py-1">
                                                    <span class="text-gray-500">Chunks Used:</span>
                                                    <span class="text-white ml-1">{query.chunks_used ?? 'N/A'}</span>
                                                </div>
                                                <div class="bg-gray-800 rounded px-3 py-1">
                                                    <span class="text-gray-500">Category:</span>
                                                    <span class="text-white ml-1">{query.query_category || 'Unclassified'}</span>
                                                </div>
                                                {#if query.trace_id}
                                                    <a 
                                                        href="/admin/traces?trace_id={query.trace_id}"
                                                        class="bg-indigo-600/20 text-indigo-400 rounded px-3 py-1 hover:bg-indigo-600/30"
                                                    >
                                                        View Trace
                                                    </a>
                                                {/if}
                                            </div>
                                        </div>
                                    </div>
                                </td>
                            </tr>
                        {/if}
                    {/each}
                </tbody>
            </table>
            
            <!-- Pagination -->
            <div class="flex items-center justify-between px-4 py-3 border-t border-gray-700">
                <div class="text-sm text-gray-400">
                    Showing {offset + 1} - {Math.min(offset + limit, $queriesTotal)} of {$queriesTotal} queries
                </div>
                
                <div class="flex items-center gap-2">
                    <button
                        disabled={currentPage === 1}
                        on:click={() => goToPage(currentPage - 1)}
                        class="px-3 py-1 rounded bg-gray-700 text-gray-300 disabled:opacity-50 
                               disabled:cursor-not-allowed hover:bg-gray-600"
                    >
                        Previous
                    </button>
                    
                    {#each Array(Math.min(5, totalPages)) as _, i}
                        {@const page = Math.max(1, Math.min(currentPage - 2, totalPages - 4)) + i}
                        {#if page <= totalPages}
                            <button
                                on:click={() => goToPage(page)}
                                class="w-8 h-8 rounded text-sm transition-colors
                                       {page === currentPage 
                                           ? 'bg-indigo-600 text-white' 
                                           : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}"
                            >
                                {page}
                            </button>
                        {/if}
                    {/each}
                    
                    <button
                        disabled={currentPage === totalPages}
                        on:click={() => goToPage(currentPage + 1)}
                        class="px-3 py-1 rounded bg-gray-700 text-gray-300 disabled:opacity-50 
                               disabled:cursor-not-allowed hover:bg-gray-600"
                    >
                        Next
                    </button>
                </div>
            </div>
        {/if}
    </div>
</div>