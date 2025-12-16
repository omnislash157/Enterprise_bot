<!--
  NerveCenterScene - Complete 3D scene for the admin dashboard

  Combines:
  - Neural network visualization
  - Ambient particles
  - Cyberpunk lighting
-->

<script lang="ts">
    import { T, useTask } from '@threlte/core';
    import { OrbitControls } from '@threlte/extras';
    import NeuralNetwork from './NeuralNetwork.svelte';
    import type { CategoryData } from '$lib/stores/analytics';

    export let categories: CategoryData[] = [];
    export let totalQueries: number = 0;
    export let activeUsers: number = 0;

    // Background particles
    const particleCount = 100;
    const particles = Array.from({ length: particleCount }, () => ({
        position: [
            (Math.random() - 0.5) * 30,
            (Math.random() - 0.5) * 20,
            (Math.random() - 0.5) * 30
        ] as [number, number, number],
        speed: 0.2 + Math.random() * 0.5,
        phase: Math.random() * Math.PI * 2
    }));

    // Animate particles
    let time = 0;
    useTask((delta) => {
        time += delta;
    });
</script>

<!-- Camera -->
<T.PerspectiveCamera makeDefault position={[12, 8, 12]} fov={45}>
    <OrbitControls
        enableDamping
        dampingFactor={0.05}
        autoRotate
        autoRotateSpeed={0.3}
        enableZoom={true}
        enablePan={false}
        minDistance={8}
        maxDistance={25}
        maxPolarAngle={Math.PI * 0.7}
        minPolarAngle={Math.PI * 0.2}
    />
</T.PerspectiveCamera>

<!-- Fog for depth -->
<T.FogExp2 args={['#050505', 0.025]} attach="fog" />

<!-- Ambient light -->
<T.AmbientLight intensity={0.15} color="#00ff41" />

<!-- Key lights -->
<T.DirectionalLight position={[10, 15, 10]} intensity={0.5} color="#ffffff" />

<T.PointLight position={[-10, 10, -10]} intensity={1} color="#00ffff" distance={40} />

<T.PointLight position={[10, -5, 10]} intensity={0.8} color="#ff0055" distance={30} />

<!-- Grid floor -->
<T.Mesh rotation.x={-Math.PI / 2} position.y={-6}>
    <T.PlaneGeometry args={[50, 50, 25, 25]} />
    <T.MeshStandardMaterial
        color="#000000"
        emissive="#00ff41"
        emissiveIntensity={0.05}
        wireframe
        transparent
        opacity={0.2}
    />
</T.Mesh>

<!-- Neural Network -->
<NeuralNetwork {categories} {totalQueries} {activeUsers} />

<!-- Ambient floating particles -->
{#each particles as particle}
    <T.Mesh
        position={[
            particle.position[0],
            particle.position[1] + Math.sin(time * particle.speed + particle.phase) * 0.5,
            particle.position[2]
        ]}
        scale={0.05}
    >
        <T.SphereGeometry args={[1, 4, 4]} />
        <T.MeshBasicMaterial
            color="#00ff41"
            transparent
            opacity={0.3 + Math.sin(time + particle.phase) * 0.2}
        />
    </T.Mesh>
{/each}
