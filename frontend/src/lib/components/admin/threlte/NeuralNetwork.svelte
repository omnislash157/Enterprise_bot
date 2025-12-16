<!--
  NeuralNetwork - Complete neural network visualization

  Nodes represent query categories, sized/colored by volume
  Connections show relationships between categories

  Props:
    categories: Array<{ category: string; count: number }>
    totalQueries: number
    activeUsers: number
-->

<script lang="ts">
    import { T } from '@threlte/core';
    import NeuralNode from './NeuralNode.svelte';
    import DataSynapse from './DataSynapse.svelte';

    export let categories: Array<{ category: string; count: number }> = [];
    export let totalQueries: number = 0;
    export let activeUsers: number = 0;

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

    // Node positions in 3D space (arranged in a sphere)
    const nodePositions: Record<string, [number, number, number]> = {
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

    <!-- Category nodes -->
    {#each Object.entries(nodePositions) as [category, position]}
        <NeuralNode
            {position}
            color={categoryColors[category] || '#888888'}
            size={getNodeSize(category)}
            activity={getActivity(category)}
            pulseSpeed={1 + networkActivity}
        />
    {/each}

    <!-- Synapses connecting nodes -->
    {#each synapseConnections as [from, to]}
        <DataSynapse
            start={nodePositions[from]}
            end={nodePositions[to]}
            color={categoryColors[from]}
            activity={Math.max(getActivity(from), getActivity(to)) * networkActivity}
        />
    {/each}

    <!-- Connections to central core -->
    {#each Object.entries(nodePositions) as [category, position]}
        <DataSynapse
            start={[0, 0, 0]}
            end={position}
            color={categoryColors[category]}
            activity={getActivity(category) * 0.5}
        />
    {/each}
</T.Group>
