<script lang="ts" module>
	import type { Direction, Enums, RequirementTile } from '$lib/data/types.generated';

	export interface RequirementTileProps {
		tile: RequirementTile;
		enums: Enums;
		/** Where the tile links: the report list filtered to this requirement. */
		href: string;
		/** The requirement's scanability note, shown on a blind spot in place of a bar. */
		scanabilityNote?: string | null;
	}
</script>

<script lang="ts">
	import CoverageChip from './CoverageChip.svelte';
	import DirectionBar from './DirectionBar.svelte';
	import StateChip from './StateChip.svelte';
	import { STATES } from '$lib/data/filters';
	import { enumLabel, enumMeaning, formatDate, labelMap } from '$lib/data/labels';

	let { tile, enums, href, scanabilityNote = null }: RequirementTileProps = $props();

	const directionLabels = $derived(labelMap(enums, 'direction') as Partial<Record<Direction, string>>);
	const states = $derived(STATES.filter((state) => tile.states[state] > 0));
	const blind = $derived(tile.status === 'blind_spot');
</script>

<a class="tile" class:blind {href} data-requirement={tile.requirement_id}>
	<div class="head">
		<span class="code">{tile.code}</span>
		<CoverageChip
			status={tile.status}
			label={enumLabel(enums, 'coverage_status', tile.status)}
			meaning={enumMeaning(enums, 'coverage_status', tile.status)}
		/>
	</div>
	<h3 class="name" title={tile.name}>{tile.short}</h3>
	{#if blind}
		<p class="blind-note">
			{scanabilityNote ?? enumMeaning(enums, 'scanability', tile.scanability) ?? ''}
		</p>
	{:else}
		<DirectionBar
			counts={tile.directions}
			labels={directionLabels}
			caption="Active reports on {tile.code} by direction"
		/>
	{/if}
	<p class="line">
		<span class="tabular"><strong>{tile.active}</strong> active</span>
		<span class="muted">of {tile.total} in the register</span>
	</p>
	{#if states.length > 0}
		<ul class="states" aria-label="Reports by state">
			{#each states as state (state)}
				<li>
					<StateChip
						{state}
						label={enumLabel(enums, 'indicator_state', state)}
						count={tile.states[state]}
					/>
				</li>
			{/each}
		</ul>
	{/if}
	<dl class="dates">
		<div>
			<dt>Latest horizon</dt>
			<dd>{formatDate(tile.latest_event_horizon)}</dd>
		</div>
		<div>
			<dt>Last verified</dt>
			<dd>{formatDate(tile.latest_verified)}</dd>
		</div>
	</dl>
</a>

<style>
	.tile {
		display: grid;
		align-content: start;
		gap: var(--space-2);
		height: 100%;
		padding: var(--space-4);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
		color: var(--color-text);
		text-decoration: none;
		min-width: 0;
	}

	.tile:hover {
		border-color: var(--color-accent);
	}

	.tile.blind {
		border-style: dashed;
		border-color: var(--color-text-muted);
	}

	.head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-2);
		flex-wrap: wrap;
	}

	.code {
		font-family: var(--font-mono);
		font-weight: 700;
		color: var(--color-accent);
	}

	.name {
		margin: 0;
		font-size: var(--text-md);
		line-height: 1.3;
	}

	.blind-note {
		margin: 0;
		font-size: var(--text-sm);
		color: var(--color-text-muted);
	}

	.line {
		margin: 0;
		font-size: var(--text-sm);
		display: flex;
		gap: var(--space-1);
		flex-wrap: wrap;
	}

	.states {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-1);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.dates {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-1) var(--space-4);
		margin: 0;
		font-size: var(--text-sm);
	}

	.dates div {
		display: flex;
		gap: var(--space-1);
	}

	dt {
		color: var(--color-text-muted);
	}

	dd {
		margin: 0;
		font-variant-numeric: tabular-nums;
	}
</style>
