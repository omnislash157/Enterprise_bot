<script lang="ts">
    import '../app.css';
</script>

<div class="app">
    <slot />
</div>

<style>
    .app {
        min-height: 100vh;
        background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
    }
</style>
