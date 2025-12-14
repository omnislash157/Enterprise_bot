<script lang="ts">
  import { T, useTask } from '@threlte/core';

  // Core configuration
  const CORE_SIZE = 3.5;

  // Animation state
  let scale = 1;
  let rotationY = 0;
  let rotationZ = 0;
  let innerRotationX = 0;
  let pulsePhase = 0;

  // Orbit ring rotations
  let ring1Rotation = 0;
  let ring2Rotation = 0;
  let ring3Rotation = 0;

  useTask((delta) => {
    const time = performance.now() / 1000;

    // Breathing pulse - subtle
    pulsePhase = time * 2;
    scale = 1 + Math.sin(pulsePhase) * 0.08;

    // Slow rotations for the core
    rotationY += delta * 0.3;
    rotationZ += delta * 0.15;
    innerRotationX += delta * 0.5;

    // Orbit rings at different speeds
    ring1Rotation += delta * 0.4;
    ring2Rotation -= delta * 0.25;
    ring3Rotation += delta * 0.6;
  });

  // Pulse intensity for lights
  $: lightIntensity = 1.5 + Math.sin(pulsePhase) * 0.5;
  $: glowIntensity = 0.6 + Math.sin(pulsePhase * 1.5) * 0.2;
</script>

<T.Group position.y={2}>
  <!-- Outer wireframe shell - Green -->
  <T.Group scale={[scale, scale, scale]}>
    <T.Mesh rotation.y={rotationY} rotation.z={rotationZ}>
      <T.IcosahedronGeometry args={[CORE_SIZE, 1]} />
      <T.MeshStandardMaterial
        color="#001a00"
        emissive="#00ff41"
        emissiveIntensity={glowIntensity}
        wireframe={true}
        roughness={0.1}
        metalness={0.9}
      />
    </T.Mesh>

    <!-- Middle shell - Magenta accent -->
    <T.Mesh rotation.y={-rotationY * 0.7} rotation.x={innerRotationX}>
      <T.IcosahedronGeometry args={[CORE_SIZE * 0.75, 1]} />
      <T.MeshStandardMaterial
        color="#1a0010"
        emissive="#ff0055"
        emissiveIntensity={glowIntensity * 0.6}
        wireframe={true}
        roughness={0.2}
        metalness={0.8}
      />
    </T.Mesh>

    <!-- Inner solid core -->
    <T.Mesh rotation.y={rotationY * 1.5} rotation.z={-rotationZ}>
      <T.OctahedronGeometry args={[CORE_SIZE * 0.35, 0]} />
      <T.MeshBasicMaterial color="#ff0055" />
    </T.Mesh>

    <!-- Innermost glow sphere -->
    <T.Mesh>
      <T.SphereGeometry args={[CORE_SIZE * 0.2, 16, 16]} />
      <T.MeshBasicMaterial color="#ffffff" transparent opacity={0.8} />
    </T.Mesh>
  </T.Group>

  <!-- Orbit ring 1 - Horizontal -->
  <T.Mesh rotation.x={Math.PI / 2} rotation.z={ring1Rotation}>
    <T.TorusGeometry args={[CORE_SIZE * 1.8, 0.03, 8, 64]} />
    <T.MeshBasicMaterial color="#00ff41" transparent opacity={0.4} />
  </T.Mesh>

  <!-- Orbit ring 2 - Tilted -->
  <T.Mesh rotation.x={Math.PI / 3} rotation.y={ring2Rotation}>
    <T.TorusGeometry args={[CORE_SIZE * 2.2, 0.02, 8, 64]} />
    <T.MeshBasicMaterial color="#00ffff" transparent opacity={0.3} />
  </T.Mesh>

  <!-- Orbit ring 3 - Vertical -->
  <T.Mesh rotation.z={ring3Rotation}>
    <T.TorusGeometry args={[CORE_SIZE * 1.5, 0.025, 8, 64]} />
    <T.MeshBasicMaterial color="#ff0055" transparent opacity={0.35} />
  </T.Mesh>

  <!-- Core point light - pulses -->
  <T.PointLight
    color="#ff0055"
    intensity={lightIntensity * 2}
    distance={25}
  />

  <!-- Secondary glow - green -->
  <T.PointLight
    color="#00ff41"
    intensity={lightIntensity}
    distance={40}
    position={[0, 3, 0]}
  />
</T.Group>
