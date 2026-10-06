import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import type { ReportQuery } from '$lib/data/filters';
import FilterBar, { SELECT_FILTERS, type FilterOptions } from './FilterBar.svelte';

function options(): FilterOptions {
	const empty = Object.fromEntries(SELECT_FILTERS.map((key) => [key, []])) as unknown as FilterOptions;
	return {
		...empty,
		requirement: [
			{ value: 'si4', label: 'SI4 Pollution to land and water' },
			{ value: 'si12', label: 'SI12 NRW colleague engagement' }
		],
		direction: [
			{ value: 'supports', label: 'supports' },
			{ value: 'threatens', label: 'threatens' }
		],
		credibility: [{ value: '2', label: '2: probably true' }]
	};
}

describe('FilterBar', () => {
	it('shows the current query in its controls', () => {
		render(FilterBar, {
			query: { requirement: 'si4', direction: 'threatens', q: 'mine' },
			options: options(),
			onchange: () => {}
		});
		expect(screen.getByLabelText('Requirement')).toHaveValue('si4');
		expect(screen.getByLabelText('Direction')).toHaveValue('threatens');
		expect(screen.getByLabelText('Search titles and summaries')).toHaveValue('mine');
		expect(screen.getByLabelText('State')).toHaveValue('');
	});

	it('emits the whole new query when a select changes', async () => {
		const onchange = vi.fn<(q: ReportQuery) => void>();
		render(FilterBar, { query: { requirement: 'si4' }, options: options(), onchange });
		await fireEvent.change(screen.getByLabelText('Direction'), { target: { value: 'threatens' } });
		expect(onchange).toHaveBeenCalledWith({ requirement: 'si4', direction: 'threatens' });
	});

	it('emits a number for credibility and removes a filter set back to any', async () => {
		const onchange = vi.fn<(q: ReportQuery) => void>();
		render(FilterBar, { query: { requirement: 'si4' }, options: options(), onchange });
		await fireEvent.change(screen.getByLabelText('Credibility'), { target: { value: '2' } });
		expect(onchange).toHaveBeenLastCalledWith({ requirement: 'si4', credibility: 2 });
		await fireEvent.change(screen.getByLabelText('Requirement'), { target: { value: '' } });
		expect(onchange).toHaveBeenLastCalledWith({});
	});

	it('emits on every keystroke in the search', async () => {
		const onchange = vi.fn<(q: ReportQuery) => void>();
		render(FilterBar, { query: {}, options: options(), onchange });
		await fireEvent.input(screen.getByLabelText('Search titles and summaries'), {
			target: { value: 'drought' }
		});
		expect(onchange).toHaveBeenCalledWith({ q: 'drought' });
	});

	it('clears every filter, and is disabled when none is set', async () => {
		const onchange = vi.fn<(q: ReportQuery) => void>();
		const { rerender } = render(FilterBar, {
			query: { requirement: 'si4', direction: 'threatens' },
			options: options(),
			onchange
		});
		const clear = screen.getByRole('button', { name: 'Clear filters (2)' });
		await fireEvent.click(clear);
		expect(onchange).toHaveBeenCalledWith({});
		await rerender({ query: {}, options: options(), onchange });
		expect(screen.getByRole('button', { name: 'Clear filters' })).toBeDisabled();
	});
});
