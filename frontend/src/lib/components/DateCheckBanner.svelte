<script lang="ts" module>
	import type { DateCheckCounts, Enums, FindingKind } from '$lib/data/types.generated';

	export interface DateCheckBannerProps {
		counts: DateCheckCounts;
		enums: Enums;
		/** Where the verification queue lives. */
		href?: string;
	}

	export const FINDING_KINDS: readonly FindingKind[] = [
		'passed_horizon',
		'future_language',
		'stale_verification',
		'never_verified'
	];
</script>

<script lang="ts">
	import { enumLabel, enumMeaning, plural } from '$lib/data/labels';

	let { counts, enums, href = '/verify' }: DateCheckBannerProps = $props();
</script>

{#if counts.total > 0}
	<aside class="banner" aria-labelledby="datecheck-heading">
		<h2 id="datecheck-heading">
			Date check: {plural(counts.total, 'finding')} on {plural(counts.reports_flagged, 'report')}
		</h2>
		<ul>
			{#each FINDING_KINDS as kind (kind)}
				<li title={enumMeaning(enums, 'finding_kind', kind) ?? undefined} class:zero={counts[kind] === 0}>
					<span class="count">{counts[kind]}</span>
					{enumLabel(enums, 'finding_kind', kind)}
				</li>
			{/each}
		</ul>
		<a {href}>Open the verification queue</a>
	</aside>
{/if}

<style>
	.banner {
		display: grid;
		gap: var(--space-2);
		padding: var(--space-3) var(--space-4);
		border: 1px solid var(--banner-border);
		border-left-width: 4px;
		border-radius: var(--radius);
		background: var(--banner-bg);
	}

	h2 {
		margin: 0;
		font-size: var(--text-md);
	}

	ul {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-1) var(--space-4);
		margin: 0;
		padding: 0;
		list-style: none;
		font-size: var(--text-sm);
	}

	li.zero {
		color: var(--color-text-muted);
	}

	.count {
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}

	a {
		font-size: var(--text-sm);
		font-weight: 600;
		justify-self: start;
	}
</style>
