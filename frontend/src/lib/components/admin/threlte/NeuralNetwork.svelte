<!--
  NeuralNetwork - Complete neural network visualization with rotating memory graph

  Nodes represent query categories, sized/colored by volume
  Department nodes in outer rotating orbit show inferred usage
  Connections show relationships between categories and department flows

  Props:
    categories: Array<{ category: string; count: number }>
    totalQueries: number
    activeUsers: number
    departmentUsage: Array<{ department: string; query_count: number; avg_complexity: number }>
    queryIntents: Array<{ intent: string; count: number; complexity: number }>
    temporalPatterns: any
-->

<script lang="ts">
    import { T, useTask } from '@threlte/core';
    import NeuralNode from './NeuralNode.svelte';
    import DataSynapse from './DataSynapse.svelte';
    import MemoryOrbit from './MemoryOrbit.svelte';

    export let categories: Array<{ category: string; count: number }> = [];
    export let totalQueries: number = 0;
    export let activeUsers: number = 0;
    export let departmentUsage: Array<{ department: string; query_count: number; avg_complexity: number }> = [];
    export let queryIntents: Array<{ intent: string; count: number; complexity: number }> = [];
    export let temporalPatterns: any = null;

    // Category colors (matches chartTheme.ts)
    const categoryColors: Record<string, string> = {
        PROCEDURAL: '#00ff41',
        LOOKUP: '#00ffff',
        TROUBLESHOOTING: '#ff00ff',
        POLICY: '#ffaa00',
        CONTACT: '#ff4444',
        RETURNS: '#00ff88',
        INVENTORY: '#8800ff',
        SAFETY: '#ff8800',
        SCHEDULE: '#0088ff',
        ESCALATION: '#ff0088',
        OTHER: '#888888'
    };

    // Category node positions in 3D space (arranged in a sphere - inner layer)
    const categoryPositions: Record<string, [number, number, number]> = {
        PROCEDURAL: [0, 3, 0], // Top
        LOOKUP: [2.5, 1.5, 1.5], // Upper right
        TROUBLESHOOTING: [-2.5, 1.5, 1.5], // Upper left
        POLICY: [0, 0, 3], // Front
        CONTACT: [3, 0, 0], // Right
        RETURNS: [-3, 0, 0], // Left
        INVENTORY: [2, -1.5, -1.5], // Lower right back
        SAFETY: [-2, -1.5, -1.5], // Lower left back
        SCHEDULE: [0, -2, 2], // Lower front
        ESCALATION: [0, -3, 0], // Bottom
        OTHER: [0, 0, -2.5] // Back center
    };

    // Department memory node positions (outer orbit - radius ~5-6 units)
    const departmentPositions: Record<string, [number, number, number]> = {
        warehouse: [5, 2, 0],
        hr: [3.5, 3.5, 3.5],
        it: [-3.5, 3.5, 3.5],
        finance: [-5, 2, 0],
        safety: [-3.5, -3.5, 3.5],
        maintenance: [3.5, -3.5, 3.5],
        general: [0, 0, 5]
    };

    // Memory orbit rotation (slow rotation)
    let orbitRotation = 0;

    useTask((delta) => {
        orbitRotation += delta * 0.1; // Slow rotation (0.1 radians per second)
    });

    // Synapse connections (which nodes connect)
    const synapseConnections: Array<[string, string]> = [
        ['PROCEDURAL', 'LOOKUP'],
        ['PROCEDURAL', 'TROUBLESHOOTING'],
        ['PROCEDURAL', 'POLICY'],
        ['LOOKUP', 'INVENTORY'],
        ['LOOKUP', 'CONTACT'],
        ['TROUBLESHOOTING', 'ESCALATION'],
        ['TROUBLESHOOTING', 'SAFETY'],
        ['POLICY', 'RETURNS'],
        ['POLICY', 'SAFETY'],
        ['CONTACT', 'ESCALATION'],
        ['INVENTORY', 'RETURNS'],
        ['SCHEDULE', 'CONTACT'],
        ['SCHEDULE', 'POLICY'],
        ['OTHER', 'LOOKUP'],
        ['OTHER', 'TROUBLESHOOTING']
    ];

    // Calculate node sizes based on query counts
    function getNodeSize(category: string): number {
        const cat = categories.find((c) => c.category === category);
        if (!cat || totalQueries === 0) return 0.5;

        const ratio = cat.count / totalQueries;
        return 0.4 + ratio * 2; // Scale between 0.4 and 2.4
    }

    // Calculate activity level (0-1)
    function getActivity(category: string): number {
        const cat = categories.find((c) => c.category === category);
        if (!cat || totalQueries === 0) return 0.1;

        return Math.min(cat.count / (totalQueries * 0.3), 1); // Normalize
    }

    // Calculate department node size based on query_count
    function getDepartmentNodeSize(dept: string): number {
        const usage = departmentUsage.find(d => d.department === dept);
        if (!usage) return 0.3;
        const totalDeptQueries = departmentUsage.reduce((sum, d) => sum + d.query_count, 0);
        if (totalDeptQueries === 0) return 0.3;
        const ratio = usage.query_count / totalDeptQueries;
        return 0.5 + ratio * 2; // Scale between 0.5 and 2.5
    }

    // Calculate department node color based on avg_complexity
    function getDepartmentColor(dept: string): string {
        const usage = departmentUsage.find(d => d.department === dept);
        if (!usage) return '#888888';

        // Color gradient: low complexity = cyan, high complexity = red
        const complexity = usage.avg_complexity || 0;
        if (complexity < 0.3) return '#00ffff'; // Cyan (simple)
        if (complexity < 0.6) return '#ffaa00'; // Orange (medium)
        return '#ff0055'; // Red (complex)
    }

    // Calculate department activity level
    function getDepartmentActivity(dept: string): number {
        const usage = departmentUsage.find(d => d.department === dept);
        if (!usage) return 0.1;
        const totalDeptQueries = departmentUsage.reduce((sum, d) => sum + d.query_count, 0);
        if (totalDeptQueries === 0) return 0.1;
        return Math.min(usage.query_count / (totalDeptQueries * 0.3), 1);
    }

    // Get category to department flow connections
    function getCategoryToDeptFlows(): Array<{ category: string; dept: string; strength: number }> {
        // Logical flows based on category-to-department relationships
        // In a real implementation, this would be calculated from actual query logs
        const flows: Array<{ category: string; dept: string; strength: number }> = [];

        // Map categories to likely departments
        const categoryDeptMap: Record<string, string[]> = {
            PROCEDURAL: ['warehouse', 'hr', 'maintenance'],
            LOOKUP: ['it', 'warehouse', 'hr'],
            TROUBLESHOOTING: ['it', 'maintenance'],
            POLICY: ['hr', 'safety'],
            CONTACT: ['hr', 'it'],
            RETURNS: ['warehouse'],
            INVENTORY: ['warehouse'],
            SAFETY: ['safety'],
            SCHEDULE: ['hr', 'warehouse'],
            ESCALATION: ['it', 'maintenance'],
            OTHER: ['general']
        };

        // Create flows for each category that exists in data
        categories.forEach(cat => {
            const depts = categoryDeptMap[cat.category] || ['general'];
            const strength = Math.min(cat.count / (totalQueries * 0.3), 1);
            depts.forEach(dept => {
                if (departmentPositions[dept]) {
                    flows.push({ category: cat.category, dept, strength: strength * 0.6 });
                }
            });
        });

        return flows;
    }

    // Overall network activity based on active users
    $: networkActivity = Math.min(activeUsers / 20, 1);
</script>

<T.Group>
    <!-- Central core (the "brain") -->
    <T.Group position={[0, 0, 0]}>
        <T.Mesh scale={1 + networkActivity * 0.3}>
            <T.IcosahedronGeometry args={[1.2, 2]} />
            <T.MeshStandardMaterial
                color="#000000"
                emissive="#00ff41"
                emissiveIntensity={0.3 + networkActivity * 0.4}
                wireframe
                transparent
                opacity={0.6}
            />
        </T.Mesh>

        <!-- Inner core glow -->
        <T.Mesh scale={0.6}>
            <T.SphereGeometry args={[1, 16, 16]} />
            <T.MeshBasicMaterial color="#ff0055" transparent opacity={0.5 + networkActivity * 0.3} />
        </T.Mesh>

        <T.PointLight color="#ff0055" intensity={2 + networkActivity * 3} distance={15} />
    </T.Group>

    <!-- Category nodes (inner sphere) -->
    {#each Object.entries(categoryPositions) as [category, position]}
        <NeuralNode
            {position}
            color={categoryColors[category] || '#888888'}
            size={getNodeSize(category)}
            activity={getActivity(category)}
            pulseSpeed={1 + networkActivity}
        />
    {/each}

    <!-- Category synapses (inner connections between category nodes) -->
    {#each synapseConnections as [from, to]}
        <DataSynapse
            start={categoryPositions[from]}
            end={categoryPositions[to]}
            color={categoryColors[from]}
            activity={Math.max(getActivity(from), getActivity(to)) * networkActivity}
        />
    {/each}

    <!-- Connections from categories to central core -->
    {#each Object.entries(categoryPositions) as [category, position]}
        <DataSynapse
            start={[0, 0, 0]}
            end={position}
            color={categoryColors[category]}
            activity={getActivity(category) * 0.5}
        />
    {/each}

    <!-- NEW: Department memory nodes (outer orbit - ROTATING) -->
    <T.Group rotation={[0, orbitRotation, 0]}>
        {#each Object.entries(departmentPositions) as [dept, position]}
            {#if departmentUsage.find(d => d.department === dept)}
                <NeuralNode
                    {position}
                    color={getDepartmentColor(dept)}
                    size={getDepartmentNodeSize(dept)}
                    activity={getDepartmentActivity(dept)}
                    pulseSpeed={0.5}
                />
            {/if}
        {/each}

        <!-- Memory orbit ring -->
        <MemoryOrbit
            radius={6}
            segments={64}
            color="#00ff41"
            opacity={0.2}
        />
    </T.Group>

    <!-- NEW: Category → Department flow lines (shows query journey) -->
    {#each getCategoryToDeptFlows() as { category, dept, strength }}
        <DataSynapse
            start={categoryPositions[category]}
            end={departmentPositions[dept]}
            color={categoryColors[category]}
            activity={strength}
            dashed={true}
        />
    {/each}
</T.Group>
