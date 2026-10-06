<script lang="ts" module>
	import type { FilterKey, ReportQuery } from '$lib/data/filters';

	export interface FilterOption {
		value: string;
		label: string;
	}

	/** The select filters the bar shows, in order; the text search comes first. */
	export const SELECT_FILTERS = [
		'requirement',
		'direction',
		'state',
		'bucket',
		'lane',
		'hazard',
		'topic',
		'place',
		'reliability',
		'credibility'
	] as const satisfies readonly FilterKey[];

	export type SelectFilter = (typeof SELECT_FILTERS)[number];

	/** The choices for each select filter. */
	export type FilterOptions = Record<SelectFilter, FilterOption[]>;

	export const FILTER_LABELS: Record<SelectFilter | 'q', string> = {
		q: 'Search titles and summaries',
		requirement: 'Requirement',
		direction: 'Direction',
		state: 'State',
		bucket: 'Bucket',
		lane: 'Lane',
		hazard: 'Hazard',
		topic: 'Topic',
		place: 'Place',
		reliability: 'Reliability',
		credibility: 'Credibility'
	};

	export interface FilterBarProps {
		query: ReportQuery;
		options: FilterOptions;
		/** Called with the whole new query whenever one control changes. */
		onchange: (query: ReportQuery) => void;
	}
</script>

<script lang="ts">
	import { activeFilterCount, withFilter } from '$lib/data/filters';

	let { query, options, onchange }: FilterBarProps = $props();

	const active = $derived(activeFilterCount(query));

	function update(key: FilterKey, value: string): void {
		onchange(withFilter(query, key, value));
	}
</script>

<form class="filter-bar" role="search" onsubmit={(event) => event.preventDefault()}>
	<div class="field search">
		<label for="filter-q">{FILTER_LABELS.q}</label>
		<input
			id="filter-q"
			name="q"
			type="search"
			autocomplete="off"
			value={query.q ?? ''}
			oninput={(event) => update('q', event.currentTarget.value)}
		/>
	</div>
	{#each SELECT_FILTERS as key (key)}
		<div class="field">
			<label for="filter-{key}">{FILTER_LABELS[key]}</label>
			<select
				id="filter-{key}"
				name={key}
				value={query[key] === undefined ? '' : String(query[key])}
				onchange={(event) => update(key, event.currentTarget.value)}
			>
				<option value="">Any</option>
				{#each options[key] as option (option.value)}
					<option value={option.value}>{option.label}</option>
				{/each}
			</select>
		</div>
	{/each}
	<div class="actions">
		<button type="button" disabled={active === 0} onclick={() => onchange({})}>
			Clear filters{active > 0 ? ` (${active})` : ''}
		</button>
	</div>
</form>

<style>
	.filter-bar {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(11rem, 1fr));
		align-items: end;
		gap: var(--space-3);
		padding: var(--space-4);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
	}

	.field {
		display: grid;
		gap: var(--space-1);
		min-width: 0;
	}

	.search {
		grid-column: 1 / -1;
	}

	label {
		color: var(--color-text-muted);
		font-size: var(--text-sm);
		font-weight: 600;
	}

	input,
	select,
	button {
		width: 100%;
		min-width: 0;
		min-height: 2.25rem;
		padding: var(--space-1) var(--space-2);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-bg);
		color: var(--color-text);
		font: inherit;
		font-size: var(--text-sm);
	}

	.actions {
		display: flex;
		align-items: end;
	}

	button {
		cursor: pointer;
		font-weight: 600;
	}

	button:disabled {
		cursor: default;
		color: var(--color-text-muted);
	}

	@media (max-width: 600px) {
		.filter-bar {
			grid-template-columns: repeat(2, minmax(0, 1fr));
			padding: var(--space-3);
		}
	}
</style>
