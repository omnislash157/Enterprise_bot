<!--
  MemoryOrbit - Rotating orbital ring showing "memory persistence"

  Props:
    radius: number - orbit radius
    segments: number - smoothness of circle
    color: string - line color (hex format)
    opacity: number - transparency (0-1)

  Description:
    Creates a circular ring using THREE.EllipseCurve that represents the orbital
    plane for department memory nodes in the Nerve Center visualization.
    The ring is rotated to be horizontal (orbit plane) and rendered with
    transparency for a cyberpunk glowing effect.
-->

<script lang="ts">
	import { T } from '@threlte/core';
	import * as THREE from 'three';

	// Props with defaults matching cyberpunk aesthetic
	export let radius: number = 5;
	export let segments: number = 64;
	export let color: string = '#00ff41';
	export let opacity: number = 0.3;

	// Create circle geometry using THREE.EllipseCurve
	// This creates a smooth circular path with the specified number of segments
	const curve = new THREE.EllipseCurve(
		0,
		0, // center x, y
		radius,
		radius, // xRadius, yRadius (equal for circular orbit)
		0,
		2 * Math.PI, // start angle, end angle (full circle)
		false, // clockwise
		0 // rotation
	);

	// Generate points along the curve and create geometry
	const points = curve.getPoints(segments);
	const geometry = new THREE.BufferGeometry().setFromPoints(points);
</script>

<!--
  Rotation: [Math.PI / 2, 0, 0] rotates the circle 90 degrees on X-axis
  to make it horizontal (orbit plane) instead of vertical
-->
<T.Group rotation={[Math.PI / 2, 0, 0]}>
	<T.Line {geometry}>
		<T.LineBasicMaterial {color} transparent {opacity} />
	</T.Line>
</T.Group>

<style>
	/*
	  No styles needed - all rendering handled by Threlte/Three.js
	  The cyberpunk glow effect comes from:
	  1. The transparent opacity creating a subtle presence
	  2. The bright green (#00ff41) color against dark backgrounds
	  3. Can be enhanced with bloom post-processing in the parent scene
	*/
</style>
