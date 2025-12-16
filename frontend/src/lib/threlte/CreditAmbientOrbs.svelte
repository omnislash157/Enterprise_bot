<script lang="ts">
    import { T, useTask } from '@threlte/core';
  
    // Minimal orb count - enough for atmosphere, not overwhelming
    const ORB_COUNT = 25;
    
    interface Orb {
      x: number;
      y: number;
      z: number;
      size: number;
      speed: number;
      phase: number;
    }
  
    const orbs: Orb[] = Array.from({ length: ORB_COUNT }, () => ({
      x: (Math.random() - 0.5) * 40,
      y: (Math.random() - 0.5) * 30,
      z: -10 - Math.random() * 20, // All pushed back
      size: 0.08 + Math.random() * 0.15,
      speed: 0.2 + Math.random() * 0.3,
      phase: Math.random() * Math.PI * 2,
    }));
  
    let time = 0;
  
    useTask((delta) => {
      time += delta;
    });
  
    function getOrbY(orb: Orb): number {
      return orb.y + Math.sin(time * orb.speed + orb.phase) * 0.5;
    }
  </script>
  
  <!-- Static camera - no controls needed -->
  <T.PerspectiveCamera makeDefault position={[0, 0, 20]} fov={50} />
  
  <!-- Minimal green ambient light -->
  <T.AmbientLight intensity={0.15} color="#00ff41" />
  
  <!-- Single accent light -->
  <T.PointLight position={[-15, 10, 10]} intensity={0.4} color="#00ff41" distance={50} />
  
  <!-- Floating orbs with subtle glow -->
  {#each orbs as orb, i (i)}
    <T.Mesh
      position.x={orb.x}
      position.y={getOrbY(orb)}
      position.z={orb.z}
    >
      <T.IcosahedronGeometry args={[orb.size, 1]} />
      <T.MeshBasicMaterial
        color="#00ff41"
        transparent
        opacity={0.25}
      />
    </T.Mesh>
  {/each}