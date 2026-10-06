<script lang="ts" module>
	import type { Snippet } from 'svelte';

	export interface EmptyStateProps {
		title: string;
		/** One or two sentences on why it is empty and what to do. */
		message?: string;
		/** An optional action, such as a button that clears the filters. */
		children?: Snippet;
	}
</script>

<script lang="ts">
	let { title, message, children }: EmptyStateProps = $props();
</script>

<div class="empty" role="status">
	<p class="title">{title}</p>
	{#if message}<p class="message">{message}</p>{/if}
	{#if children}<div class="action">{@render children()}</div>{/if}
</div>

<style>
	.empty {
		padding: var(--space-6) var(--space-4);
		border: 1px dashed var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
		text-align: center;
	}

	.title {
		margin: 0;
		font-weight: 600;
	}

	.message {
		margin: var(--space-2) 0 0;
		color: var(--color-text-muted);
	}

	.action {
		margin-top: var(--space-3);
	}
</style>
