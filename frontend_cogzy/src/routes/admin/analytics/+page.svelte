<!--
    Analytics Deep Dive - Detailed charts and insights
    
    Enhanced with heuristics-based analytics:
    - AI-inferred department usage (content-based, not dropdown)
    - Query intent classification
    - Complexity distribution
    - 3D Nerve Center visualization
  -->
  
  <script lang="ts">
      import { onMount, onDestroy } from 'svelte';
      import {
          analyticsStore,
          categories,
          departments,
          departmentUsageInferred,
          queryIntents,
          memoryGraphData,
          errors,
          periodHours as periodHoursStore
      } from '$lib/stores/analytics';
      import LineChart from '$lib/components/admin/charts/LineChart.svelte';
      import DoughnutChart from '$lib/components/admin/charts/DoughnutChart.svelte';
      import BarChart from '$lib/components/admin/charts/BarChart.svelte';
      import ExportButton from '$lib/components/admin/charts/ExportButton.svelte';
      import DateRangePicker from '$lib/components/admin/charts/DateRangePicker.svelte';
      import NerveCenterWidget from '$lib/components/admin/charts/NerveCenterWidget.svelte';
      import {
          exportQueries,
          exportCategories,
          exportDepartments,
          exportErrors
      } from '$lib/utils/csvExport';
  
      let queriesByHour: Array<{ hour: string; count: number }> = [];
      let refreshInterval: ReturnType<typeof setInterval> | null = null;
  
      // Transform query intents for donut chart
      $: intentChartData = ($memoryGraphData?.intents || []).map(i => ({
          category: formatIntentLabel(i.intent),
          count: i.count
      }));
  
      // Transform inferred departments for bar chart
      $: inferredDeptChartData = ($memoryGraphData?.departments || []).map(d => ({
          department: d.department,
          query_count: d.query_count,
          avg_complexity: d.avg_complexity
      }));
  
      // Calculate complexity distribution from inferred data
      $: complexityDistribution = calculateComplexityDistribution($memoryGraphData?.departments || []);
  
      function formatIntentLabel(intent: string): string {
          return intent
              .replace(/_/g, ' ')
              .toLowerCase()
              .replace(/\b\w/g, c => c.toUpperCase());
      }
  
      function calculateComplexityDistribution(depts: Array<{ avg_complexity: number; query_count: number }>) {
          let simple = 0, medium = 0, complex = 0;
          
          for (const d of depts) {
              if (d.avg_complexity < 0.33) {
                  simple += d.query_count;
              } else if (d.avg_complexity < 0.66) {
                  medium += d.query_count;
              } else {
                  complex += d.query_count;
              }
          }
  
          return [
              { category: 'Simple', count: simple },
              { category: 'Medium', count: medium },
              { category: 'Complex', count: complex }
          ].filter(c => c.count > 0);
      }
  
      onMount(async () => {
          await analyticsStore.loadAll();
          analyticsStore.startAutoRefresh();
  
          analyticsStore.subscribe((s) => {
              queriesByHour = s.queriesByHour;
          });
      });
  
      onDestroy(() => {
          analyticsStore.stopAutoRefresh();
      });
  </script>
  
  <svelte:head>
      <title>Analytics | Cogzy</title>
  </svelte:head>
  
  <div class="analytics-page p-6">
      <!-- Header -->
      <div class="header flex items-center justify-between mb-6">
          <div>
              <h1 class="text-xl font-bold text-[#00ff41]">Analytics Deep Dive</h1>
              <p class="text-sm text-[#808080]">Query patterns, performance, and AI-powered insights</p>
          </div>
  
          <!-- Period Selector -->
          <DateRangePicker
              hours={$periodHoursStore}
              on:change={(e) => analyticsStore.reloadWithPeriod(e.detail.hours)}
          />
      </div>
  
      <!-- ====================================================================== -->
      <!-- NEW: AI HEURISTICS SECTION -->
      <!-- ====================================================================== -->
      
      <div class="heuristics-section mb-8">
          <div class="section-header mb-4">
              <h2 class="text-lg font-semibold text-[#00ffff] flex items-center gap-2">
                  <span class="pulse-dot"></span>
                  AI-POWERED ANALYTICS
              </h2>
              <p class="text-xs text-[#808080] mt-1">
                  Content-based classification - departments and intents inferred from query text, not user selection
              </p>
          </div>
  
          <!-- 3D Nerve Center Widget -->
          <div class="nerve-center-row mb-6">
              <NerveCenterWidget height="400px" />
          </div>
  
          <!-- Heuristics Charts Grid -->
          <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
              <!-- AI-Inferred Department Usage -->
              <div class="chart-section panel p-4">
                  <div class="chart-header flex items-center justify-between mb-4">
                      <div>
                          <h3 class="text-sm font-semibold text-[#00ffff]">INFERRED DEPARTMENT USAGE</h3>
                          <p class="text-xs text-[#666] mt-1">Based on query content analysis</p>
                      </div>
                  </div>
                  {#if inferredDeptChartData.length > 0}
                      <BarChart
                          data={inferredDeptChartData}
                          labelKey="department"
                          valueKey="query_count"
                          height="220px"
                      />
                  {:else}
                      <div class="empty-state">
                          <p>No inferred department data available</p>
                      </div>
                  {/if}
              </div>
  
              <!-- Query Intent Breakdown -->
              <div class="chart-section panel p-4">
                  <div class="chart-header flex items-center justify-between mb-4">
                      <div>
                          <h3 class="text-sm font-semibold text-[#ff00ff]">QUERY INTENT CLASSIFICATION</h3>
                          <p class="text-xs text-[#666] mt-1">AI-classified query purposes</p>
                      </div>
                  </div>
                  {#if intentChartData.length > 0}
                      <DoughnutChart data={intentChartData} height="220px" />
                  {:else}
                      <div class="empty-state">
                          <p>No intent classification data available</p>
                      </div>
                  {/if}
              </div>
  
              <!-- Complexity Distribution -->
              <div class="chart-section panel p-4">
                  <div class="chart-header flex items-center justify-between mb-4">
                      <div>
                          <h3 class="text-sm font-semibold text-[#ffaa00]">COMPLEXITY DISTRIBUTION</h3>
                          <p class="text-xs text-[#666] mt-1">Query complexity scoring (0-1 scale)</p>
                      </div>
                  </div>
                  {#if complexityDistribution.length > 0}
                      <DoughnutChart data={complexityDistribution} height="220px" />
                  {:else}
                      <div class="empty-state">
                          <p>No complexity data available</p>
                      </div>
                  {/if}
              </div>
          </div>
  
          <!-- Intent Legend -->
          <div class="intent-legend panel p-3 mb-6">
              <div class="flex flex-wrap gap-4 text-xs">
                  <div class="legend-item">
                      <span class="legend-dot" style="background: #00ff41"></span>
                      <strong>Information Seeking:</strong> Looking up facts, data, or procedures
                  </div>
                  <div class="legend-item">
                      <span class="legend-dot" style="background: #00ffff"></span>
                      <strong>Action Oriented:</strong> Requests to perform tasks or make changes
                  </div>
                  <div class="legend-item">
                      <span class="legend-dot" style="background: #ff00ff"></span>
                      <strong>Troubleshooting:</strong> Problem diagnosis and resolution
                  </div>
                  <div class="legend-item">
                      <span class="legend-dot" style="background: #ffaa00"></span>
                      <strong>Clarification:</strong> Follow-up questions for more detail
                  </div>
              </div>
          </div>
      </div>
  
      <!-- ====================================================================== -->
      <!-- TRADITIONAL ANALYTICS (PRESERVED) -->
      <!-- ====================================================================== -->
  
      <div class="traditional-section">
          <div class="section-header mb-4">
              <h2 class="text-lg font-semibold text-[#808080]">TRADITIONAL METRICS</h2>
              <p class="text-xs text-[#666] mt-1">
                  Standard analytics based on user selections and basic categorization
              </p>
          </div>
  
          <!-- Query Volume Trend -->
          <div class="chart-section panel p-4 mb-6">
              <div class="chart-header flex items-center justify-between mb-4">
                  <h3 class="text-sm font-semibold text-[#808080]">QUERY VOLUME TREND</h3>
                  <ExportButton on:click={() => exportQueries(queriesByHour)} />
              </div>
              <LineChart data={queriesByHour} label="Queries" height="250px" />
          </div>
  
          <!-- Two Column Layout -->
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
              <!-- Category Breakdown -->
              <div class="chart-section panel p-4">
                  <div class="chart-header flex items-center justify-between mb-4">
                      <h3 class="text-sm font-semibold text-[#808080]">QUERY CATEGORIES</h3>
                      <ExportButton on:click={() => exportCategories($categories)} />
                  </div>
                  <DoughnutChart data={$categories} height="280px" />
              </div>
  
              <!-- Department Comparison (Traditional) -->
              <div class="chart-section panel p-4">
                  <div class="chart-header flex items-center justify-between mb-4">
                      <h3 class="text-sm font-semibold text-[#808080]">DEPARTMENT COMPARISON</h3>
                      <ExportButton on:click={() => exportDepartments($departments)} />
                  </div>
                  <BarChart
                      data={$departments}
                      labelKey="department"
                      valueKey="query_count"
                      height="280px"
                  />
                  <p class="text-xs text-[#666] mt-2 text-center italic">
                      Based on user-selected department (dropdown)
                  </p>
              </div>
          </div>
  
          <!-- Response Time by Department -->
          <div class="chart-section panel p-4 mb-6">
              <div class="chart-header flex items-center justify-between mb-4">
                  <h3 class="text-sm font-semibold text-[#808080]">RESPONSE TIME BY DEPARTMENT</h3>
                  <ExportButton on:click={() => exportDepartments($departments)} />
              </div>
              <BarChart
                  data={$departments}
                  labelKey="department"
                  valueKey="avg_response_time_ms"
                  height="200px"
              />
          </div>
  
          <!-- Recent Errors -->
          <div class="errors-section panel p-4">
              <div class="chart-header flex items-center justify-between mb-4">
                  <h3 class="text-sm font-semibold text-[#808080]">RECENT ERRORS</h3>
                  <ExportButton
                      on:click={() => exportErrors($errors)}
                      disabled={$errors.length === 0}
                  />
              </div>
  
              {#if $errors.length === 0}
                  <div class="text-center text-[#808080] py-8">
                      No errors in the selected period
                  </div>
              {:else}
                  <div class="errors-table overflow-x-auto">
                      <table class="w-full text-sm">
                          <thead>
                              <tr class="text-left text-[#808080] border-b border-[#222]">
                                  <th class="pb-2">Time</th>
                                  <th class="pb-2">User</th>
                                  <th class="pb-2">Type</th>
                                  <th class="pb-2">Message</th>
                              </tr>
                          </thead>
                          <tbody>
                              {#each $errors as error}
                                  <tr class="border-b border-[#1a1a1a]">
                                      <td class="py-2 text-[#808080]">
                                          {new Date(error.created_at).toLocaleTimeString()}
                                      </td>
                                      <td class="py-2 text-[#e0e0e0]">
                                          {error.user_email || '-'}
                                      </td>
                                      <td class="py-2 text-[#ff4444]">
                                          {error.error_type || 'Unknown'}
                                      </td>
                                      <td class="py-2 text-[#808080] truncate max-w-[300px]">
                                          {error.error_message || '-'}
                                      </td>
                                  </tr>
                              {/each}
                          </tbody>
                      </table>
                  </div>
              {/if}
          </div>
      </div>
  </div>
  
  <style>
      .analytics-page {
          min-height: 100vh;
          background: var(--bg-primary);
      }
  
      .chart-section {
          background: var(--bg-secondary);
          border: 1px solid var(--border-dim);
          border-radius: 8px;
      }
  
      /* Heuristics section styling */
      .heuristics-section {
          background: rgba(0, 255, 255, 0.02);
          border: 1px solid rgba(0, 255, 255, 0.2);
          border-radius: 12px;
          padding: 1.5rem;
      }
  
      .heuristics-section .chart-section {
          border-color: rgba(0, 255, 255, 0.3);
      }
  
      .section-header h2 {
          letter-spacing: 0.05em;
      }
  
      .pulse-dot {
          display: inline-block;
          width: 8px;
          height: 8px;
          background: #00ffff;
          border-radius: 50%;
          animation: pulse 2s infinite;
      }
  
      @keyframes pulse {
          0%, 100% { box-shadow: 0 0 0 0 rgba(0, 255, 255, 0.7); }
          50% { box-shadow: 0 0 0 6px rgba(0, 255, 255, 0); }
      }
  
      .empty-state {
          display: flex;
          align-items: center;
          justify-content: center;
          height: 200px;
          color: #666;
          font-size: 0.875rem;
      }
  
      .intent-legend {
          background: rgba(0, 0, 0, 0.3);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 8px;
      }
  
      .legend-item {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          color: #a0a0a0;
      }
  
      .legend-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
      }
  
      .legend-item strong {
          color: #e0e0e0;
      }
  
      /* Traditional section styling */
      .traditional-section {
          opacity: 0.9;
      }
  
      .traditional-section .chart-section {
          border-color: rgba(128, 128, 128, 0.3);
      }
  
      .errors-section {
          background: var(--bg-secondary);
          border: 1px solid var(--border-dim);
          border-radius: 8px;
      }
  </style>