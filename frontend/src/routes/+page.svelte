<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	// Static hosting has no server redirect, so the prerendered page carries a
	// meta refresh and a link; once hydrated, the client router goes straight there.
	const target = $derived(`/picture/${data.meta.default_requirement_set_id}`);

	onMount(() => {
		void goto(target, { replaceState: true });
	});
</script>

<svelte:head>
	<title>Gwylio</title>
	<meta http-equiv="refresh" content="0; url={target}" />
</svelte:head>

<p class="placeholder">
	Opening the intelligence picture: <a href={target}>go to the picture</a>.
</p>

<style>
	.placeholder {
		color: var(--color-text-muted);
		margin: 0;
	}
</style>
