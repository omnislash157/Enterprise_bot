<script lang="ts">
    import { T, useTask } from '@threlte/core';
    import { InstancedMesh, Instance } from '@threlte/extras';
    import { onMount } from 'svelte';
  
    // Configuration - tuned for subtle background life
    const COUNT = 200;
    const SPREAD_X = 60;      // horizontal spread
    const SPREAD_Y = 40;      // vertical spread  
    const DEPTH_NEAR = -10;   // closest z
    const DEPTH_FAR = -80;    // furthest z
    const STREAM_SPEED = 8;   // forward velocity
    const TWINKLE_SPEED = 3;  // oscillation frequency
    const TWINKLE_AMOUNT = 0.015; // scale oscillation range
  
    interface Particle {
      x: number;
      y: number; 
      z: number;
      baseScale: number;
      phase: number;      // offset for oscillation
      speed: number;      // individual speed variance
      twinkleFreq: number;
    }
  
    let particles: Particle[] = [];
    let instances: any[] = [];
    let mounted = false;
  
    // Initialize particle field
    onMount(() => {
      particles = Array.from({ length: COUNT }, () => ({
        x: (Math.random() - 0.5) * SPREAD_X,
        y: (Math.random() - 0.5) * SPREAD_Y,
        z: DEPTH_NEAR + Math.random() * (DEPTH_FAR - DEPTH_NEAR),
        baseScale: 0.02 + Math.random() * 0.04, // very small: 0.02 - 0.06
        phase: Math.random() * Math.PI * 2,
        speed: 0.7 + Math.random() * 0.6, // 0.7 - 1.3x speed variance
        twinkleFreq: 2 + Math.random() * 3 // 2-5 Hz twinkle
      }));
      mounted = true;
    });
  
    // Animate all particles in one efficient loop
    useTask((delta) => {
      if (!mounted || instances.length === 0) return;
  
      const time = performance.now() * 0.001;
  
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        const inst = instances[i];
        if (!inst) continue;
  
        // Stream forward (toward camera = positive Z)
        p.z += STREAM_SPEED * delta * p.speed;
  
        // Wrap when past camera
        if (p.z > DEPTH_NEAR + 5) {
          p.z = DEPTH_FAR;
          // Randomize position on wrap for organic feel
          p.x = (Math.random() - 0.5) * SPREAD_X;
          p.y = (Math.random() - 0.5) * SPREAD_Y;
        }
  
        // Twinkle: oscillate scale
        const twinkle = Math.sin(time * p.twinkleFreq + p.phase);
        const scale = p.baseScale + twinkle * TWINKLE_AMOUNT;
  
        // Update instance
        inst.position.set(p.x, p.y, p.z);
        inst.scale.setScalar(Math.max(0.005, scale)); // clamp to avoid negative
      }
    });
  </script>
  
  {#if mounted}
    <InstancedMesh limit={COUNT}>
      <!-- Low-poly sphere for performance -->
      <T.IcosahedronGeometry args={[1, 0]} />
      
      <!-- Additive blending for subtle glow effect -->
      <T.MeshBasicMaterial
        color="#00ff41"
        transparent
        opacity={0.4}
        depthWrite={false}
        blending={2}
      />
  
      {#each particles as p, i}
        <Instance
          bind:ref={instances[i]}
          position={[p.x, p.y, p.z]}
          scale={p.baseScale}
        />
      {/each}
    </InstancedMesh>
  {/if}