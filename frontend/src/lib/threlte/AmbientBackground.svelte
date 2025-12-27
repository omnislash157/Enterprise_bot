<!--
    AmbientBackground - Wrapper component for global particle effect
    
    Contains the Threlte Canvas + AmbientStream in one component.
    This allows the layout to use a simple static import with browser check.
  -->
  
  <script lang="ts">
      import { Canvas } from '@threlte/core';
      import AmbientStream from './ambientstream.svelte';
  </script>
  
  <div class="ambient-background">
      <Canvas>
          <AmbientStream />
      </Canvas>
  </div>
  
  <style>
      .ambient-background {
          position: fixed;
          top: 0;
          left: 0;
          width: 100vw;
          height: 100vh;
          z-index: 10;
          pointer-events: none;
          opacity: 0.6;
      }
  </style>