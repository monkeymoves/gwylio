import { render, screen, within } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import DirectionBar, { directionSegments } from './DirectionBar.svelte';

const counts = { supports: 3, threatens: 7, neutral: 0, informs_baseline: 2 };

describe('DirectionBar', () => {
	it('labels every direction with its count, zeros included', () => {
		render(DirectionBar, { counts, labels: { neutral: 'two-way' } });
		const legend = screen.getByRole('list', { name: 'By direction' });
		const items = within(legend).getAllByRole('listitem');
		expect(items.map((li) => li.textContent?.replace(/\s+/g, ' ').trim())).toEqual([
			'supports 3',
			'threatens 7',
			'two-way 0',
			'informs the baseline 2'
		]);
		expect(items[2]).toHaveClass('zero');
	});

	it('draws one segment per non-zero direction, sized by count, with a summary for screen readers', () => {
		const { container } = render(DirectionBar, { counts, caption: 'Active reports on SI1' });
		const segments = container.querySelectorAll<HTMLElement>('.segment');
		expect([...segments].map((s) => s.dataset.direction)).toEqual([
			'supports',
			'threatens',
			'informs_baseline'
		]);
		expect(segments[1]?.style.flexGrow).toBe('7');
		expect(screen.getByRole('img')).toHaveAttribute(
			'aria-label',
			'Active reports on SI1: supports 3, threatens 7, two-way 0, informs the baseline 2'
		);
	});

	it('handles all zeros with a sentence and no segments', () => {
		const zero = { supports: 0, threatens: 0, neutral: 0, informs_baseline: 0 };
		const { container } = render(DirectionBar, { counts: zero, emptyText: 'No active reports' });
		expect(screen.getByText('No active reports')).toBeInTheDocument();
		expect(container.querySelectorAll('.segment')).toHaveLength(0);
		expect(screen.queryByRole('img')).not.toBeInTheDocument();
	});

	it('computes shares that sum to one, and zero shares for an empty bar', () => {
		const shares = directionSegments(counts).map((s) => s.share);
		expect(shares.reduce((a, b) => a + b, 0)).toBeCloseTo(1);
		expect(
			directionSegments({ supports: 0, threatens: 0, neutral: 0, informs_baseline: 0 }).every(
				(s) => s.share === 0
			)
		).toBe(true);
	});
});
