<script lang="ts" module>
	import type {
		CoverageCellView,
		CoverageMatrixView,
		CoverageRowView,
		CoverageStatus,
		LegendEntry
	} from '$lib/data/types.generated';
	import { HEAT_BINS, binLabel, heatStep } from '$lib/data/viz';

	export interface HeatmapProps {
		matrix: CoverageMatrixView;
		/** Names the table for screen readers. */
		caption: string;
		/** The heading of the row header column, such as Requirement. */
		rowHeading: string;
		/** The four statuses with their labels and meanings, from the coverage read model. */
		legend: LegendEntry[];
		/** What a cell counts, for the cell titles, such as active reports. */
		unit?: string;
		/** Add a column with how many requirements expect each row (taxonomy axes). */
		showExpected?: boolean;
		/** Add a total column. */
		showTotal?: boolean;
		/** Render the legend under the table. */
		showLegend?: boolean;
	}

	/** Legend order: most evidence first, the blind spot last and set apart. */
	export const STATUS_ORDER: readonly CoverageStatus[] = ['covered', 'thin', 'quiet', 'blind_spot'];

	/** What counts each status covers, in words, for the legend. */
	export function statusCounts(status: CoverageStatus): string {
		switch (status) {
			case 'covered':
				return '3 or more';
			case 'thin':
				return '1 to 2';
			case 'quiet':
				return '0, scannable';
			case 'blind_spot':
				return '0, not scannable';
		}
	}

	/** The swatches a legend entry shows: the ramp steps for counts, a texture or bare surface for none. */
	export function statusSteps(status: CoverageStatus): number[] {
		return HEAT_BINS.filter((bin) => bin.status === status).map((bin) => bin.step);
	}

	/** The title a cell carries: row, column, count and status. */
	export function cellTitle(
		row: CoverageRowView,
		columnName: string,
		cell: CoverageCellView,
		statusLabel: string,
		unit: string
	): string {
		return `${row.label}, ${columnName}: ${cell.count} ${unit} (${statusLabel})`;
	}

</script>

<script lang="ts">
	import CoverageChip from './CoverageChip.svelte';

	let {
		matrix,
		caption,
		rowHeading,
		legend,
		unit = 'active reports',
		showExpected = false,
		showTotal = true,
		showLegend = true
	}: HeatmapProps = $props();

	const columnNames = $derived(new Map(matrix.columns.map((c) => [c.id, c.name])));
	const legendByStatus = $derived(new Map(legend.map((entry) => [entry.status, entry])));
	const legendEntries = $derived(
		STATUS_ORDER.map((status) => legendByStatus.get(status)).filter(
			(entry): entry is LegendEntry => entry !== undefined
		)
	);

	function statusLabel(status: CoverageStatus): string {
		return legendByStatus.get(status)?.label ?? status.replace('_', ' ');
	}

	function cellsByColumn(row: CoverageRowView): CoverageCellView[] {
		const byId = new Map(row.cells.map((cell) => [cell.column_id, cell]));
		return matrix.columns.map(
			(column) => byId.get(column.id) ?? { column_id: column.id, count: 0, status: 'quiet' }
		);
	}
</script>

<div class="heatmap">
	<div class="table-scroll">
		<table>
			<caption class="visually-hidden">{caption}</caption>
			<thead>
				<tr>
					<th scope="col" class="row-head">{rowHeading}</th>
					{#each matrix.columns as column (column.id)}
						<th scope="col" class="col-head">{column.name}</th>
					{/each}
					{#if showTotal}<th scope="col" class="col-head total">Total</th>{/if}
					{#if showExpected}<th scope="col" class="col-head total">Requirements expecting it</th>{/if}
				</tr>
			</thead>
			<tbody>
				{#each matrix.rows as row (row.row_id)}
					<tr data-row={row.row_id} data-status={row.status}>
						<th scope="row" class="row-head">
							<span class="row-inner">
								<span class="row-label">{row.label}</span>
								<CoverageChip
									status={row.status}
									label={statusLabel(row.status)}
									meaning={legendByStatus.get(row.status)?.meaning}
								/>
							</span>
						</th>
						{#each cellsByColumn(row) as cell (cell.column_id)}
							{@const step = heatStep(cell.count)}
							<td
								class="cell"
								data-column={cell.column_id}
								data-status={cell.status}
								data-step={step}
								style:--cell-bg={step > 0 ? `var(--seq-${step})` : null}
								style:--cell-ink={step > 0 ? `var(--seq-ink-${step})` : null}
								title={cellTitle(
									row,
									columnNames.get(cell.column_id) ?? cell.column_id,
									cell,
									statusLabel(cell.status),
									unit
								)}><span class="num">{cell.count}</span></td
							>
						{/each}
						{#if showTotal}<td class="total" data-total>{row.total}</td>{/if}
						{#if showExpected}<td class="total">{row.expected ?? 'none'}</td>{/if}
					</tr>
				{/each}
			</tbody>
		</table>
	</div>

	{#if showLegend}
		<div class="legend">
			<p class="legend-title">Cell colour: active reports in the cell</p>
			<ul class="statuses" aria-label="Coverage statuses">
				{#each legendEntries as entry (entry.status)}
					<li data-status={entry.status}>
						<span class="swatches" aria-hidden="true">
							{#if entry.status === 'quiet'}
								<span class="swatch quiet"></span>
							{:else if entry.status === 'blind_spot'}
								<span class="swatch blind"></span>
							{:else}
								{#each statusSteps(entry.status) as step (step)}
									<span class="swatch" style:--cell-bg="var(--seq-{step})"></span>
								{/each}
							{/if}
						</span>
						<span class="entry-text">
							<strong>{entry.status === 'blind_spot' ? 'blind spot' : entry.label}</strong>
							<span class="counts">{statusCounts(entry.status)}</span>
							<span class="meaning">{entry.meaning}</span>
						</span>
					</li>
				{/each}
			</ul>
			<ul class="scale" aria-label="Shade by count">
				{#each HEAT_BINS as bin (bin.step)}
					<li>
						<span class="swatch" style:--cell-bg="var(--seq-{bin.step})" aria-hidden="true"></span>
						<span class="tabular">{binLabel(bin)}</span>
					</li>
				{/each}
			</ul>
		</div>
	{/if}
</div>

<style>
	.heatmap {
		display: grid;
		gap: var(--space-3);
		min-width: 0;
	}

	.table-scroll {
		width: 100%;
		overflow-x: auto;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
	}

	table {
		border-collapse: separate;
		border-spacing: 2px;
		font-size: var(--text-sm);
		overflow-wrap: normal;
		margin: var(--space-1);
	}

	th {
		font-weight: 600;
		color: var(--color-text-muted);
		text-align: left;
	}

	/* Count columns share a floor width and grow only to their longest word, so no header runs into the next. */
	.col-head {
		min-width: 4.5rem;
		padding: var(--space-1) 3px var(--space-2);
		font-size: 0.7rem;
		vertical-align: bottom;
		line-height: 1.25;
		text-align: center;
		hyphens: auto;
	}

	.row-head {
		position: sticky;
		left: 0;
		z-index: 1;
		width: 10.5rem;
		min-width: 10.5rem;
		max-width: 10.5rem;
		padding: var(--space-1) var(--space-2) var(--space-1) var(--space-1);
		background: var(--color-surface);
		vertical-align: middle;
	}

	tbody .row-head {
		color: var(--color-text);
	}

	.row-inner {
		display: grid;
		justify-items: start;
		gap: 2px;
	}

	.row-label {
		line-height: 1.3;
		overflow-wrap: anywhere;
	}

	/* The chip wraps inside the sticky header rather than spilling over the cells. */
	.row-inner :global(.chip) {
		max-width: 100%;
		white-space: normal;
	}

	.cell {
		min-width: 2.75rem;
		height: 2.5rem;
		padding: 0 var(--space-1);
		border-radius: 3px;
		background: var(--cell-bg, var(--heat-quiet-bg));
		color: var(--cell-ink, var(--color-text-muted));
		font-weight: 600;
		font-variant-numeric: tabular-nums;
		text-align: center;
		vertical-align: middle;
	}

	.cell[data-step='0'] {
		font-weight: 400;
	}

	/* A blind spot is a hatch, never a shade of the ramp and never the bare quiet surface. */
	.cell[data-status='blind_spot'],
	.swatch.blind {
		background-color: var(--heat-blind-bg);
		background-image: repeating-linear-gradient(
			45deg,
			var(--heat-blind-hatch) 0 1.5px,
			transparent 1.5px 6px
		);
		color: var(--color-text);
	}

	/* On the hatch the count sits on a small plate so it stays legible. */
	.cell[data-status='blind_spot'] .num {
		padding: 0 4px;
		border-radius: 2px;
		background: var(--heat-blind-bg);
	}

	.cell:hover {
		outline: 2px solid var(--color-text);
		outline-offset: -2px;
	}

	.total {
		min-width: 3rem;
		padding: 0 var(--space-2);
		font-weight: 700;
		font-variant-numeric: tabular-nums;
		text-align: center;
		vertical-align: middle;
		color: var(--color-text);
	}

	th.total {
		color: var(--color-text-muted);
		font-weight: 600;
	}

	.legend {
		display: grid;
		gap: var(--space-2);
		padding: var(--space-3) var(--space-4);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
		font-size: var(--text-sm);
	}

	.legend-title {
		margin: 0;
		font-weight: 600;
	}

	.statuses {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr));
		gap: var(--space-2) var(--space-4);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.statuses li {
		display: flex;
		align-items: flex-start;
		gap: var(--space-2);
	}

	.swatches {
		display: inline-flex;
		flex: none;
		gap: 2px;
		width: 3.5rem;
		padding-top: 2px;
	}

	.swatch {
		display: inline-block;
		width: 1rem;
		height: 1rem;
		border-radius: 3px;
		background: var(--cell-bg);
	}

	.swatch.quiet {
		background: var(--heat-quiet-bg);
		box-shadow: inset 0 0 0 1px var(--color-border);
	}

	.swatch.blind {
		width: 1.5rem;
		box-shadow: inset 0 0 0 1px var(--color-border);
	}

	.entry-text {
		display: grid;
	}

	.counts {
		font-variant-numeric: tabular-nums;
	}

	.meaning {
		color: var(--color-text-muted);
	}

	.scale {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-1) var(--space-4);
		margin: 0;
		padding: var(--space-2) 0 0;
		border-top: 1px solid var(--color-border);
		list-style: none;
	}

	.scale li {
		display: inline-flex;
		align-items: center;
		gap: var(--space-1);
		white-space: nowrap;
	}

	@media (max-width: 600px) {
		.row-head {
			width: 9rem;
			min-width: 9rem;
			max-width: 9rem;
		}

		.col-head {
			min-width: 4.25rem;
		}

		.legend {
			padding: var(--space-3);
		}
	}
</style>
