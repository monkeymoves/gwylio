import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import Harness from '../../../tests/harness/DataTableHarness.svelte';
import { nextSort, sortRows, type Column } from './DataTable.svelte';

const rows = [
	{ id: 'a', name: 'Bravo', count: 2 },
	{ id: 'b', name: 'alpha', count: null },
	{ id: 'c', name: 'Charlie', count: 10 },
	{ id: 'd', name: 'Delta', count: 2 }
];

function names(): string[] {
	return within(screen.getAllByRole('rowgroup')[1] as HTMLElement)
		.getAllByRole('row')
		.map((row) => row.querySelector('td')?.textContent?.trim() ?? '');
}

describe('DataTable', () => {
	it('renders rows in the order given, with a caption and column headers', () => {
		render(Harness, { rows });
		expect(screen.getByRole('table', { name: 'Test rows' })).toBeInTheDocument();
		expect(screen.getAllByRole('columnheader').map((th) => th.textContent?.trim())).toEqual([
			expect.stringContaining('Name'),
			expect.stringContaining('Count'),
			'Note'
		]);
		expect(names()).toEqual(['Bravo', 'alpha', 'Charlie', 'Delta']);
	});

	it('sorts by a header button, ascending then descending, and says so in aria-sort', async () => {
		render(Harness, { rows });
		const header = screen.getByRole('columnheader', { name: /Count/ });
		expect(header).toHaveAttribute('aria-sort', 'none');
		const button = within(header).getByRole('button');
		await fireEvent.click(button);
		expect(header).toHaveAttribute('aria-sort', 'ascending');
		expect(names()).toEqual(['Bravo', 'Delta', 'Charlie', 'alpha']);
		await fireEvent.click(button);
		expect(header).toHaveAttribute('aria-sort', 'descending');
		expect(names()).toEqual(['Charlie', 'Bravo', 'Delta', 'alpha']);
	});

	it('uses real buttons, so the keyboard can sort', () => {
		render(Harness, { rows });
		const buttons = screen.getAllByRole('button');
		expect(buttons).toHaveLength(2);
		for (const button of buttons) expect(button.tagName).toBe('BUTTON');
		expect(screen.getByRole('columnheader', { name: 'Note' })).not.toHaveAttribute('aria-sort');
	});
});

describe('sortRows and nextSort', () => {
	const columns: Column<(typeof rows)[number]>[] = [
		{ key: 'name', label: 'Name', sortValue: (r) => r.name },
		{ key: 'plain', label: 'Plain' }
	];

	it('compares text without regard to case and keeps ties stable', () => {
		const sorted = sortRows(rows, columns, { key: 'name', direction: 'ascending' });
		expect(sorted.map((r) => r.id)).toEqual(['b', 'a', 'c', 'd']);
		expect(sortRows(rows, columns, null)).toEqual(rows);
		expect(sortRows(rows, columns, { key: 'plain', direction: 'ascending' })).toEqual(rows);
	});

	it('cycles ascending and descending, and starts ascending on a new column', () => {
		expect(nextSort(null, 'name')).toEqual({ key: 'name', direction: 'ascending' });
		expect(nextSort({ key: 'name', direction: 'ascending' }, 'name').direction).toBe('descending');
		expect(nextSort({ key: 'name', direction: 'descending' }, 'name').direction).toBe('ascending');
		expect(nextSort({ key: 'name', direction: 'descending' }, 'count').direction).toBe('ascending');
	});
});
