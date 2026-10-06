<script lang="ts" module>
	/** One column of a DataTable. */
	export interface Column<T> {
		key: string;
		label: string;
		/** The value the column sorts by; leave out for a column that does not sort. */
		sortValue?: (row: T) => string | number | null;
		/** Right-align numbers. */
		align?: 'start' | 'end';
		/** A class for the header and cells, such as a width hint. */
		className?: string;
	}

	export type SortDirection = 'ascending' | 'descending';

	export interface SortState {
		key: string;
		direction: SortDirection;
	}

	/**
	 * The rows sorted by one column. Stable: equal values keep their order.
	 * Nulls sort last in either direction. Pure.
	 */
	export function sortRows<T>(rows: readonly T[], columns: readonly Column<T>[], sort: SortState | null): T[] {
		const column = sort ? columns.find((c) => c.key === sort.key) : undefined;
		if (!sort || !column?.sortValue) return [...rows];
		const value = column.sortValue;
		const sign = sort.direction === 'ascending' ? 1 : -1;
		return rows
			.map((row, index) => ({ row, index, v: value(row) }))
			.sort((a, b) => {
				if (a.v === b.v) return a.index - b.index;
				if (a.v === null) return 1;
				if (b.v === null) return -1;
				const order =
					typeof a.v === 'number' && typeof b.v === 'number'
						? a.v - b.v
						: String(a.v).localeCompare(String(b.v), 'en-GB');
				return order === 0 ? a.index - b.index : sign * order;
			})
			.map((entry) => entry.row);
	}

	/** The next sort after clicking a header: ascending, then descending, then ascending. */
	export function nextSort(current: SortState | null, key: string): SortState {
		if (current?.key === key && current.direction === 'ascending') {
			return { key, direction: 'descending' };
		}
		return { key, direction: 'ascending' };
	}
</script>

<script lang="ts" generics="T">
	import type { Snippet } from 'svelte';

	let {
		rows,
		columns,
		cell,
		rowKey,
		caption,
		initialSort = null,
		stack = false,
		compact = false
	}: {
		rows: readonly T[];
		columns: readonly Column<T>[];
		/** Renders one cell. */
		cell: Snippet<[T, Column<T>]>;
		rowKey: (row: T) => string;
		/** Names the table for screen readers; shown visually hidden. */
		caption: string;
		initialSort?: SortState | null;
		/**
		 * At phone width, show each row as a labelled card and the sortable
		 * headers as a row of sort buttons, instead of scrolling sideways.
		 */
		stack?: boolean;
		/**
		 * For wide tables: smaller type, tighter cells and headers that wrap
		 * (sort glyph included), so many columns fit the content width.
		 */
		compact?: boolean;
	} = $props();

	let chosen = $state<SortState | null>(null);
	const sort = $derived(chosen ?? initialSort);
	const sorted = $derived(sortRows(rows, columns, sort));

	function ariaSort(key: string): 'ascending' | 'descending' | 'none' {
		return sort?.key === key ? sort.direction : 'none';
	}
</script>

<div class="table-scroll" class:stack class:compact>
	<table>
		<caption class="visually-hidden">{caption}</caption>
		<thead>
			<tr>
				{#each columns as column (column.key)}
					<th
						scope="col"
						class={column.className}
						class:end={column.align === 'end'}
						aria-sort={column.sortValue ? ariaSort(column.key) : undefined}
					>
						{#if column.sortValue}
							<button type="button" onclick={() => (chosen = nextSort(sort, column.key))}>
								{column.label}
								<span class="indicator" aria-hidden="true"
									>{sort?.key === column.key
										? sort.direction === 'ascending'
											? '▲'
											: '▼'
										: '▴▾'}</span
								>
							</button>
						{:else}
							{column.label}
						{/if}
					</th>
				{/each}
			</tr>
		</thead>
		<tbody>
			{#each sorted as row (rowKey(row))}
				<tr>
					{#each columns as column (column.key)}
						<td
							class={column.className}
							class:end={column.align === 'end'}
							data-label={column.label}
						>
							{@render cell(row, column)}
						</td>
					{/each}
				</tr>
			{/each}
		</tbody>
	</table>
</div>

<style>
	.table-scroll {
		width: 100%;
		overflow-x: auto;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
	}

	/* overflow-wrap: anywhere on the body would let columns shrink below a word. */
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: var(--text-sm);
		overflow-wrap: normal;
	}

	th,
	td {
		padding: var(--space-2) var(--space-3);
		border-bottom: 1px solid var(--color-border);
		text-align: left;
		vertical-align: top;
		overflow-wrap: break-word;
	}

	tbody tr:last-child td {
		border-bottom: 0;
	}

	th {
		color: var(--color-text-muted);
		font-weight: 600;
		white-space: nowrap;
	}

	.end {
		text-align: right;
		font-variant-numeric: tabular-nums;
	}

	th button {
		display: inline-flex;
		align-items: center;
		gap: var(--space-1);
		padding: 0;
		border: 0;
		background: none;
		color: inherit;
		font: inherit;
		cursor: pointer;
	}

	th button:hover {
		color: var(--color-text);
	}

	.indicator {
		font-size: 0.75em;
		opacity: 0.8;
	}

	.compact table {
		font-size: 0.8125rem;
	}

	@media (min-width: 601px) {
		.compact th,
		.compact td {
			padding-inline: var(--space-2);
		}

		.compact th {
			white-space: normal;
		}

		.compact th button {
			flex-wrap: wrap;
			text-align: inherit;
		}

		.compact th.end button {
			justify-content: flex-end;
		}
	}

	@media (max-width: 600px) {
		.stack table,
		.stack tbody,
		.stack tr,
		.stack td {
			display: block;
			width: 100%;
		}

		.stack thead tr {
			display: flex;
			flex-wrap: wrap;
			gap: var(--space-1) var(--space-3);
			padding: var(--space-2) var(--space-3);
			border-bottom: 1px solid var(--color-border);
		}

		.stack thead th {
			padding: 0;
			border: 0;
		}

		.stack thead th:not([aria-sort]) {
			display: none;
		}

		.stack tbody tr {
			padding: var(--space-2) var(--space-3);
			border-bottom: 1px solid var(--color-border);
		}

		.stack tbody tr:last-child {
			border-bottom: 0;
		}

		.stack td {
			display: grid;
			/* A page can widen the label column with --stack-label for long single-word labels. */
			grid-template-columns: var(--stack-label, 6.5rem) minmax(0, 1fr);
			justify-items: start;
			gap: var(--space-2);
			padding: var(--space-1) 0;
			border: 0;
			min-width: 0;
		}

		.stack td::before {
			content: attr(data-label);
			min-width: 0;
			color: var(--color-text-muted);
			font-weight: 600;
			overflow-wrap: anywhere;
		}

		.stack .end {
			text-align: left;
		}
	}
</style>
