<!--
  DataSynapse - Animated connection line between neural nodes

  Props:
    start: [x, y, z] start position
    end: [x, y, z] end position
    color: hex color
    activity: 0-1 data flow intensity
-->

<script lang="ts">
    import { T, useTask } from '@threlte/core';
    import * as THREE from 'three';

    export let start: [number, number, number] = [0, 0, 0];
    export let end: [number, number, number] = [1, 1, 1];
    export let color: string = '#00ff41';
    export let activity: number = 0.3;

    // Create curved line
    const curve = new THREE.QuadraticBezierCurve3(
        new THREE.Vector3(...start),
        new THREE.Vector3(
            (start[0] + end[0]) / 2,
            (start[1] + end[1]) / 2 + 1.5, // Arc upward
            (start[2] + end[2]) / 2
        ),
        new THREE.Vector3(...end)
    );

    const points = curve.getPoints(20);
    const geometry = new THREE.BufferGeometry().setFromPoints(points);

    // Animated opacity
    let opacity = 0.3;
    let time = 0;

    // Data packet position (0-1 along curve)
    let packetT = 0;
    let packetPosition: [number, number, number] = [...start];

    useTask((delta) => {
        time += delta;
        // Pulse along with activity
        opacity = 0.15 + Math.sin(time * 3) * 0.1 + activity * 0.3;

        // Animate packet along curve
        if (activity > 0.2) {
            packetT = (packetT + delta * (0.5 + activity)) % 1;
            const point = curve.getPoint(packetT);
            packetPosition = [point.x, point.y, point.z];
        }
    });
</script>

<T.Line {geometry}>
    <T.LineBasicMaterial {color} transparent {opacity} linewidth={1} />
</T.Line>

<!-- Data packet traveling along synapse -->
{#if activity > 0.2}
    <T.Mesh position={packetPosition} scale={0.15 + activity * 0.1}>
        <T.SphereGeometry args={[1, 8, 8]} />
        <T.MeshBasicMaterial {color} transparent opacity={0.8} />
    </T.Mesh>
{/if}
