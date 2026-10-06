<script lang="ts" module>
	export interface ArrivesLaterProps {
		/** The page heading, such as Sources. */
		title: string;
		/** One sentence on what the page will show. */
		purpose: string;
	}
</script>

<script lang="ts">
	let { title, purpose }: ArrivesLaterProps = $props();
</script>

<svelte:head>
	<title>{title} | Gwylio</title>
</svelte:head>

<h1>{title}</h1>
<p>{purpose}</p>
<p class="muted">This page arrives in work package 9 (WP9) of the build.</p>
<p><a href="/">Back to the picture</a></p>

<style>
	h1 {
		margin: 0 0 var(--space-3);
		font-size: var(--text-xl);
	}

	p {
		margin: 0 0 var(--space-2);
	}
</style>
