import { render, screen, within } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { seed, snapshot } from '../../../tests/fixtures';
import type { Coverage, CoverageMatrixView } from '$lib/data/types.generated';
import { heatStep } from '$lib/data/viz';
import { BLIND_SPOT_TEXT } from './CoverageChip.svelte';
import Heatmap, { STATUS_ORDER, cellTitle, statusCounts } from './Heatmap.svelte';

const real = snapshot<Coverage>('coverage_nrw-corporate-plan.json');
const seeded = seed<Coverage>('coverage.json');

function renderLanes(coverage: Coverage, props: Record<string, unknown> = {}) {
	return render(Heatmap, {
		matrix: coverage.lanes,
		caption: 'Requirements by lane',
		rowHeading: 'Requirement',
		legend: coverage.legend,
		...props
	});
}

function bodyRows(): HTMLElement[] {
	return within(screen.getAllByRole('rowgroup')[1] as HTMLElement).getAllByRole('row');
}

describe('Heatmap', () => {
	it('renders one row per requirement and one column per lane, as an accessible table', () => {
		renderLanes(real);
		expect(screen.getByRole('table', { name: 'Requirements by lane' })).toBeInTheDocument();
		const headers = screen.getAllByRole('columnheader').map((th) => th.textContent?.trim());
		expect(headers).toEqual(['Requirement', ...real.lanes.columns.map((c) => c.name), 'Total']);
		expect(bodyRows()).toHaveLength(real.lanes.rows.length);
		expect(screen.getAllByRole('rowheader')).toHaveLength(real.lanes.rows.length);
	});

	it('writes each cell as its count, in column order, with a shade step for the count', () => {
		const { container } = renderLanes(real);
		for (const row of real.lanes.rows) {
			const tr = container.querySelector(`tr[data-row="${row.row_id}"]`) as HTMLElement;
			const cells = [...tr.querySelectorAll('td.cell')];
			expect(cells.map((td) => td.textContent)).toEqual(row.cells.map((c) => String(c.count)));
			expect(cells.map((td) => td.getAttribute('data-step'))).toEqual(
				row.cells.map((c) => String(heatStep(c.count)))
			);
			expect(cells.map((td) => td.getAttribute('data-status'))).toEqual(row.cells.map((c) => c.status));
			expect(tr.querySelector('[data-total]')).toHaveTextContent(String(row.total));
		}
	});

	it('heads each row with its label and a coverage chip; a blind spot never reads quiet', () => {
		const { container } = renderLanes(real);
		const blind = real.lanes.rows.filter((r) => r.status === 'blind_spot');
		expect(blind.length).toBeGreaterThan(0);
		for (const row of blind) {
			const th = container.querySelector(`tr[data-row="${row.row_id}"] th`) as HTMLElement;
			expect(th).toHaveTextContent(row.label);
			const chip = th.querySelector('[data-status="blind_spot"]');
			expect(chip).toHaveTextContent(BLIND_SPOT_TEXT);
			expect(chip).not.toHaveClass('status-quiet');
			for (const td of th.parentElement?.querySelectorAll('td.cell') ?? []) {
				expect(td).toHaveAttribute('data-status', 'blind_spot');
				expect(td).toHaveAttribute('data-step', '0');
			}
		}
	});

	it('has a legend listing the four statuses with their counts and meanings, and the scale', () => {
		const { container } = renderLanes(real);
		const statuses = screen.getByRole('list', { name: 'Coverage statuses' });
		const items = within(statuses).getAllByRole('listitem');
		expect(items.map((li) => li.getAttribute('data-status'))).toEqual([...STATUS_ORDER]);
		expect(items.map((li) => li.querySelector('strong')?.textContent)).toEqual([
			'covered',
			'thin',
			'quiet',
			'blind spot'
		]);
		for (const entry of real.legend) {
			expect(statuses).toHaveTextContent(entry.meaning);
			expect(statuses).toHaveTextContent(statusCounts(entry.status));
		}
		const blindSwatch = container.querySelector('[data-status="blind_spot"] .swatch');
		expect(blindSwatch).toHaveClass('blind');
		expect(container.querySelector('[data-status="quiet"] .swatch')).toHaveClass('quiet');
		const scale = screen.getByRole('list', { name: 'Shade by count' });
		expect(within(scale).getAllByRole('listitem').map((li) => li.textContent?.trim())).toEqual([
			'1',
			'2',
			'3 to 4',
			'5 to 9',
			'10 or more'
		]);
	});

	it('titles each cell with row, column, count and status', () => {
		const row = seeded.lanes.rows[0];
		const cell = row?.cells[0];
		if (!row || !cell) throw new Error('empty seed coverage');
		expect(cellTitle(row, 'Welsh Government', cell, 'covered', 'active reports')).toBe(
			`${row.label}, Welsh Government: ${cell.count} active reports (covered)`
		);
	});

	it('adds an expected column for a taxonomy axis and can drop the total and the legend', () => {
		const axis = real.taxonomy[0];
		if (!axis) throw new Error('no taxonomy axis');
		render(Heatmap, {
			matrix: axis.matrix,
			caption: 'Taxonomy',
			rowHeading: 'Node',
			legend: real.legend,
			showTotal: false,
			showExpected: true,
			showLegend: false
		});
		const headers = screen.getAllByRole('columnheader').map((th) => th.textContent?.trim());
		expect(headers).toEqual(['Node', ...axis.matrix.columns.map((c) => c.name), 'Requirements expecting it']);
		expect(screen.queryByRole('list', { name: 'Coverage statuses' })).not.toBeInTheDocument();
	});

	it('fills a cell the read model left out as zero, so columns never shift', () => {
		const matrix: CoverageMatrixView = {
			columns: [
				{ id: 'a', name: 'A' },
				{ id: 'b', name: 'B' }
			],
			rows: [
				{
					row_id: 'r',
					label: 'R1 Row',
					code: 'R1',
					cells: [{ column_id: 'b', count: 4, status: 'covered' }],
					total: 4,
					status: 'covered',
					expected: null
				}
			],
			report_ids: []
		};
		const { container } = render(Heatmap, {
			matrix,
			caption: 'Gap',
			rowHeading: 'Row',
			legend: real.legend
		});
		expect([...container.querySelectorAll('td.cell')].map((td) => td.textContent)).toEqual(['0', '4']);
	});
});
