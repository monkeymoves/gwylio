<script lang="ts" module>
	import type { CoverageStatus, Direction, Enums, GroupTile } from '$lib/data/types.generated';

	export interface GroupMember {
		id: string;
		code: string;
		href: string;
	}

	export interface GroupTileProps {
		group: GroupTile;
		enums: Enums;
		/** The member requirements, each linking to its filtered report list. */
		members: GroupMember[];
		/** The group's note from the requirement set, such as who else contributes. */
		note?: string | null;
	}

	const STATUS_ORDER: readonly CoverageStatus[] = ['covered', 'thin', 'quiet', 'blind_spot'];
</script>

<script lang="ts">
	import CoverageChip from './CoverageChip.svelte';
	import DirectionBar from './DirectionBar.svelte';
	import StateChip from './StateChip.svelte';
	import { STATES } from '$lib/data/filters';
	import { enumLabel, enumMeaning, formatDate, labelMap } from '$lib/data/labels';

	let { group, enums, members, note = null }: GroupTileProps = $props();

	const directionLabels = $derived(labelMap(enums, 'direction') as Partial<Record<Direction, string>>);
	const states = $derived(STATES.filter((state) => group.states[state] > 0));
	const statuses = $derived(STATUS_ORDER.filter((status) => group.statuses[status] > 0));
</script>

<article class="tile" data-group={group.group_id}>
	<h3 class="name">{group.name}</h3>
	{#if group.statement}<p class="statement">{group.statement}</p>{/if}
	{#if note}<p class="note">{note}</p>{/if}
	<DirectionBar
		counts={group.directions}
		labels={directionLabels}
		caption="Active reports on {group.name} by direction"
	/>
	<p class="line">
		<span class="tabular"><strong>{group.active}</strong> active</span>
		<span class="muted">of {group.total} in the register</span>
	</p>
	{#if states.length > 0}
		<ul class="chips" aria-label="Reports by state">
			{#each states as state (state)}
				<li>
					<StateChip
						{state}
						label={enumLabel(enums, 'indicator_state', state)}
						count={group.states[state]}
					/>
				</li>
			{/each}
		</ul>
	{/if}
	<div class="members">
		<span class="muted">Requirements</span>
		<ul class="codes">
			{#each members as member (member.id)}
				<li><a href={member.href}>{member.code}</a></li>
			{/each}
		</ul>
	</div>
	<ul class="chips" aria-label="Member requirements by coverage status">
		{#each statuses as status (status)}
			<li>
				<CoverageChip
					{status}
					count={group.statuses[status]}
					label={enumLabel(enums, 'coverage_status', status)}
					meaning={enumMeaning(enums, 'coverage_status', status)}
				/>
			</li>
		{/each}
	</ul>
	<dl class="dates">
		<div>
			<dt>Latest horizon</dt>
			<dd>{formatDate(group.latest_event_horizon)}</dd>
		</div>
		<div>
			<dt>Last verified</dt>
			<dd>{formatDate(group.latest_verified)}</dd>
		</div>
	</dl>
</article>

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
		min-width: 0;
	}

	.name {
		margin: 0;
		font-size: var(--text-lg);
		line-height: 1.3;
	}

	.statement,
	.note {
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

	.chips,
	.codes {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-1);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.members {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--space-2);
		font-size: var(--text-sm);
	}

	.codes a {
		font-family: var(--font-mono);
		font-weight: 700;
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
