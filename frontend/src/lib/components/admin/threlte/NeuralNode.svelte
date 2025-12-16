<!--
  NeuralNode - Single glowing node in the neural network

  Props:
    position: [x, y, z]
    color: hex color
    size: base size (scaled by activity)
    activity: 0-1 activity level (affects glow intensity)
    pulseSpeed: animation speed multiplier
-->

<script lang="ts">
    import { T, useTask } from '@threlte/core';
    import { Float } from '@threlte/extras';

    export let position: [number, number, number] = [0, 0, 0];
    export let color: string = '#00ff41';
    export let size: number = 1;
    export let activity: number = 0.5;
    export let pulseSpeed: number = 1;

    // Animated values
    let glowIntensity = 0.5;
    let currentScale = size;
    let time = 0;

    useTask((delta) => {
        time += delta * pulseSpeed;

        // Pulse based on activity level
        const basePulse = Math.sin(time * 2) * 0.15;
        const activityBoost = activity * 0.3;

        glowIntensity = 0.4 + basePulse + activityBoost;
        currentScale = size * (1 + basePulse * 0.2 + activity * 0.1);
    });
</script>

<T.Group {position}>
    <Float
        floatIntensity={0.3 + activity * 0.2}
        speed={1 + activity}
        rotationSpeed={0.2}
    >
        <!-- Outer glow sphere -->
        <T.Mesh scale={currentScale * 1.5}>
            <T.IcosahedronGeometry args={[1, 2]} />
            <T.MeshBasicMaterial
                {color}
                transparent
                opacity={glowIntensity * 0.3}
            />
        </T.Mesh>

        <!-- Core sphere -->
        <T.Mesh scale={currentScale}>
            <T.IcosahedronGeometry args={[1, 3]} />
            <T.MeshStandardMaterial
                {color}
                emissive={color}
                emissiveIntensity={glowIntensity}
                roughness={0.2}
                metalness={0.8}
                transparent
                opacity={0.9}
            />
        </T.Mesh>

        <!-- Inner bright core -->
        <T.Mesh scale={currentScale * 0.4}>
            <T.SphereGeometry args={[1, 16, 16]} />
            <T.MeshBasicMaterial
                color="#ffffff"
                transparent
                opacity={0.6 + activity * 0.4}
            />
        </T.Mesh>

        <!-- Point light for glow effect -->
        <T.PointLight
            {color}
            intensity={glowIntensity * 2 + activity * 3}
            distance={8 + activity * 4}
        />
    </Float>
</T.Group>
