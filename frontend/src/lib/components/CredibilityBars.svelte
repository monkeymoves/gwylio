<script lang="ts" module>
	import type { CredibilityBar } from '$lib/data/types.generated';

	export interface CredibilityBarsProps {
		/** One bar per digit, 1 to 6, from the read model. */
		bars: CredibilityBar[];
		/** Names the chart for screen readers, such as Promotions in this run by credibility. */
		caption: string;
		/** What a bar counts, such as reports. */
		unit?: string;
	}

	/** The six digits in order, each present even if the read model left one out. Pure. */
	export function sixDigits(bars: readonly CredibilityBar[]): CredibilityBar[] {
		const byDigit = new Map(bars.map((bar) => [bar.credibility, bar]));
		return ([1, 2, 3, 4, 5, 6] as const).map(
			(digit) => byDigit.get(digit) ?? { credibility: digit, label: '', count: 0 }
		);
	}
</script>

<script lang="ts">
	import { plural } from '$lib/data/labels';

	let { bars, caption, unit = 'report' }: CredibilityBarsProps = $props();

	const rows = $derived(sixDigits(bars));
	const max = $derived(Math.max(0, ...rows.map((row) => row.count)));
	const total = $derived(rows.reduce((sum, row) => sum + row.count, 0));
</script>

<figure class="credibility">
	<ol class="bars" aria-label={caption}>
		{#each rows as row (row.credibility)}
			<li class:zero={row.count === 0} data-credibility={row.credibility}>
				<span class="digit">{row.credibility}</span>
				<span class="label">{row.label}</span>
				<span class="track">
					{#if row.count > 0}
						<span
							class="bar"
							style:width="{(row.count / max) * 100}%"
							title="{row.credibility} {row.label}: {row.count}"
						></span>
					{/if}
				</span>
				<span class="count">{row.count}</span>
			</li>
		{/each}
	</ol>
	<figcaption>{plural(total, unit)} in all; Admiralty credibility, 1 confirmed to 6 cannot be judged.</figcaption>
</figure>

<style>
	.credibility {
		display: grid;
		gap: var(--space-2);
		margin: 0;
	}

	.bars {
		display: grid;
		grid-template-columns: 1.25rem minmax(6.5rem, auto) minmax(0, 1fr) 2.5rem;
		align-items: center;
		gap: var(--space-1) var(--space-2);
		margin: 0;
		padding: 0;
		list-style: none;
		font-size: var(--text-sm);
	}

	li {
		display: contents;
	}

	.digit {
		font-family: var(--font-mono);
		font-weight: 700;
	}

	.track {
		height: 14px;
		border-left: 1px solid var(--viz-axis);
	}

	.bar {
		display: block;
		height: 100%;
		min-width: 2px;
		border-radius: 0 4px 4px 0;
		background: var(--viz-series-1);
	}

	.count {
		font-weight: 700;
		font-variant-numeric: tabular-nums;
		text-align: right;
	}

	.zero .label,
	.zero .count,
	.zero .digit {
		color: var(--color-text-muted);
		font-weight: 400;
	}

	figcaption {
		color: var(--color-text-muted);
		font-size: var(--text-sm);
	}
</style>
