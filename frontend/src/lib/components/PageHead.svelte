<script lang="ts" module>
	import type { Snippet } from 'svelte';

	export interface PageHeadProps {
		title: string;
		/** A small label above the title, such as Evaluation. */
		eyebrow?: string;
		/** The lead paragraph or paragraphs under the title. */
		children?: Snippet;
	}
</script>

<script lang="ts">
	let { title, eyebrow, children }: PageHeadProps = $props();
</script>

<svelte:head>
	<title>{title} | Gwylio</title>
</svelte:head>

<header class="page-head">
	{#if eyebrow}<p class="eyebrow">{eyebrow}</p>{/if}
	<h1>{title}</h1>
	{#if children}<div class="lead">{@render children()}</div>{/if}
</header>

<style>
	.page-head {
		margin-bottom: var(--space-6);
	}

	.eyebrow {
		margin: 0;
		color: var(--color-accent);
		font-size: var(--text-sm);
		font-weight: 700;
		letter-spacing: 0.04em;
		text-transform: uppercase;
	}

	h1 {
		margin: var(--space-1) 0 var(--space-2);
		font-size: var(--text-xl);
		line-height: 1.2;
	}

	.lead {
		max-width: 60rem;
		color: var(--color-text-muted);
	}

	.lead :global(p) {
		margin: 0 0 var(--space-2);
	}

	.lead :global(p:last-child) {
		margin-bottom: 0;
	}
</style>
