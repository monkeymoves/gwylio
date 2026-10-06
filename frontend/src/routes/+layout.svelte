<script lang="ts">
	import type { Snippet } from 'svelte';
	import '$lib/styles/tokens.css';

	let { children }: { children: Snippet } = $props();
</script>

<header class="site-header">
	<div class="inner">
		<a class="brand" href="/">Gwylio</a>
	</div>
</header>

<main class="inner">
	{@render children()}
</main>

<style>
	.inner {
		width: 100%;
		max-width: var(--content-max);
		margin: 0 auto;
		padding-inline: var(--gutter);
	}

	.site-header {
		background: var(--color-surface);
		border-bottom: 1px solid var(--color-border);
		padding: var(--space-3) 0;
	}

	.brand {
		color: var(--color-accent);
		font-size: var(--text-lg);
		font-weight: 700;
		text-decoration: none;
	}

	main {
		padding-top: var(--space-6);
		padding-bottom: var(--space-8);
	}
</style>
