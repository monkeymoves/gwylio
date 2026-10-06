<script lang="ts">
	import type { Snippet } from 'svelte';
	import { page } from '$app/state';
	import { formatInstant } from '$lib/data/labels';
	import '$lib/styles/tokens.css';
	import type { LayoutData } from './$types';

	let { data, children }: { data: LayoutData; children: Snippet } = $props();

	const setId = $derived(data.meta.default_requirement_set_id);
	const nav = $derived([
		{ href: `/picture/${setId}`, match: '/picture', label: 'Picture' },
		{ href: '/reports', match: '/reports', label: 'Reports' },
		{ href: '/sources', match: '/sources', label: 'Sources' },
		{ href: '/scans', match: '/scans', label: 'Scans' },
		{ href: `/coverage/${setId}`, match: '/coverage', label: 'Coverage' },
		{ href: '/verify', match: '/verify', label: 'Verify' },
		{ href: '/intsum', match: '/intsum', label: 'INTSUM', title: 'Intelligence summary' },
		{ href: '/about', match: '/about', label: 'About' }
	]);

	function isCurrent(match: string): boolean {
		const path = page.url.pathname;
		return path === match || path.startsWith(`${match}/`);
	}
</script>

<a class="skip" href="#main">Skip to content</a>

<header class="site-header">
	<div class="inner bar">
		<a class="brand" href="/">Gwylio</a>
		<nav aria-label="Main">
			<ul>
				{#each nav as item (item.href)}
					<li>
						<a href={item.href} aria-current={isCurrent(item.match) ? 'page' : undefined}
							>{#if item.title}<abbr title={item.title}>{item.label}</abbr>{:else}{item.label}{/if}</a
						>
					</li>
				{/each}
			</ul>
		</nav>
	</div>
</header>

<main id="main" class="inner">
	{@render children()}
</main>

<footer class="site-footer">
	<div class="inner">
		<ul class="facts">
			<li>
				Snapshot generated <time datetime={data.meta.generated_at}
					>{formatInstant(data.meta.generated_at)}</time
				>
			</li>
			<li>Instrument {data.meta.instrument_version}</li>
			<li>Rubric {data.meta.rubric_version}</li>
		</ul>
	</div>
</footer>

<style>
	.inner {
		width: 100%;
		max-width: var(--content-max);
		margin: 0 auto;
		padding-inline: var(--gutter);
	}

	.skip {
		position: absolute;
		left: var(--space-2);
		top: -3rem;
		padding: var(--space-2) var(--space-3);
		background: var(--color-surface);
		z-index: 10;
	}

	.skip:focus {
		top: var(--space-2);
	}

	.site-header {
		background: var(--color-surface);
		border-bottom: 1px solid var(--color-border);
	}

	.bar {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: var(--space-2) var(--space-6);
		padding-block: var(--space-3);
	}

	.brand {
		color: var(--color-accent);
		font-size: var(--text-lg);
		font-weight: 700;
		text-decoration: none;
	}

	nav ul {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-1) var(--space-1);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	nav a {
		display: inline-block;
		padding: var(--space-1) var(--space-2);
		border-radius: var(--radius);
		color: var(--color-text);
		font-size: var(--text-sm);
		font-weight: 600;
		text-decoration: none;
	}

	nav a:hover {
		background: var(--color-bg);
	}

	nav a[aria-current='page'] {
		background: var(--color-accent);
		color: var(--color-accent-contrast);
	}

	nav abbr {
		text-decoration: none;
	}

	main {
		padding-top: var(--space-6);
		padding-bottom: var(--space-8);
	}

	.site-footer {
		border-top: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text-muted);
		font-size: var(--text-sm);
	}

	.facts {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-1) var(--space-4);
		margin: 0;
		padding: var(--space-4) 0;
		list-style: none;
	}

	@media (max-width: 600px) {
		.bar {
			gap: var(--space-2);
		}

		nav ul {
			gap: var(--space-1) 0;
		}
	}
</style>
