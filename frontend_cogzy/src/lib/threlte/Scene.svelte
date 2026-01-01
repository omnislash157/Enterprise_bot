<script lang="ts">
  import { T, useTask } from '@threlte/core';
  import { OrbitControls } from '@threlte/extras';
  import { onMount } from 'svelte';

  // Toxic green color palette
  const COLORS = {
    background: '#050505',
    matrixGreen: '#00ff41',
    voltageYellow: '#ccff00',
    coreGlow: '#00ff41'
  };

  // Floating particles state
  let particlePositions: Float32Array;
  let particleColors: Float32Array;
  const PARTICLE_COUNT = 150;

  // Initialize particles
  onMount(() => {
    particlePositions = new Float32Array(PARTICLE_COUNT * 3);
    particleColors = new Float32Array(PARTICLE_COUNT * 3);

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      // Spread particles in a sphere
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const r = 20 + Math.random() * 30;

      particlePositions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      particlePositions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      particlePositions[i * 3 + 2] = r * Math.cos(phi);

      // Random green/cyan hues
      const hue = Math.random() > 0.7 ? 0.5 : 0.33; // cyan or green
      particleColors[i * 3] = hue === 0.5 ? 0 : 0;
      particleColors[i * 3 + 1] = 1;
      particleColors[i * 3 + 2] = hue === 0.5 ? 1 : 0.25;
    }
  });

  // Animate particles gently
  let time = 0;
  useTask((delta) => {
    time += delta * 0.1;
  });
</script>

<!-- Camera with gentle auto-rotation -->
<T.PerspectiveCamera
  makeDefault
  position={[0, 15, 35]}
  fov={50}
>
  <OrbitControls
    enableDamping
    dampingFactor={0.02}
    autoRotate
    autoRotateSpeed={0.15}
    enableZoom={false}
    enablePan={false}
    maxPolarAngle={Math.PI * 0.65}
    minPolarAngle={Math.PI * 0.35}
  />
</T.PerspectiveCamera>

<!-- Fog for depth -->
<T.FogExp2 args={[COLORS.background, 0.012]} attach="fog" />

<!-- Ambient base - subtle -->
<T.AmbientLight intensity={0.25} color={COLORS.matrixGreen} />

<!-- Key light from above -->
<T.PointLight
  position={[0, 40, 0]}
  intensity={1.5}
  color="#ffffff"
  distance={120}
/>

<!-- Rim lights for depth -->
<T.SpotLight
  position={[-40, 20, 40]}
  intensity={8}
  color="#00ffff"
  angle={0.4}
  penumbra={0.8}
  distance={100}
/>

<T.SpotLight
  position={[40, 10, -30]}
  intensity={5}
  color="#ff0055"
  angle={0.3}
  penumbra={0.9}
  distance={80}
/>

<!-- Ground plane with grid effect -->
<T.Mesh rotation.x={-Math.PI / 2} position.y={-15}>
  <T.PlaneGeometry args={[200, 200, 50, 50]} />
  <T.MeshStandardMaterial
    color="#000000"
    emissive="#001a00"
    emissiveIntensity={0.2}
    wireframe={true}
    transparent
    opacity={0.15}
  />
</T.Mesh>

<!-- Floating particles -->
{#if particlePositions}
  <T.Points>
    <T.BufferGeometry>
      <T.BufferAttribute
        attach="attributes-position"
        args={[particlePositions, 3]}
      />
      <T.BufferAttribute
        attach="attributes-color"
        args={[particleColors, 3]}
      />
    </T.BufferGeometry>
    <T.PointsMaterial
      size={0.3}
      transparent
      opacity={0.6}
      vertexColors
      sizeAttenuation
    />
  </T.Points>
{/if}
