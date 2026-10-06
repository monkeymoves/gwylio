import { render, screen, within } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { seed } from '../../../tests/fixtures';
import type { RunDetail } from '$lib/data/types.generated';
import FunnelDiagram from './FunnelDiagram.svelte';

const run = seed<RunDetail>('run_judged.json');

describe('FunnelDiagram', () => {
	it('draws the stages in order, raw hits down to new candidates', () => {
		const { container } = render(FunnelDiagram, { funnel: run.funnel, caption: 'Funnel' });
		const list = screen.getByRole('list', { name: 'Funnel' });
		const items = within(list).getAllByRole('listitem');
		expect(items.map((li) => li.getAttribute('data-stage'))).toEqual(['raw', 'passed', 'unique', 'new']);
		expect(items.map((li) => li.querySelector('.label')?.textContent)).toEqual([
			'Raw hits',
			'Passed the gates',
			'Unique candidates',
			'New candidates'
		]);
		expect(items.map((li) => li.querySelector('.count')?.textContent)).toEqual(
			[run.funnel.raw, run.funnel.passed, run.funnel.unique, run.funnel.new].map(String)
		);
		expect(container.querySelectorAll('.bar')).toHaveLength(4);
	});

	it('labels each bar with its drop reason and counts', () => {
		render(FunnelDiagram, { funnel: run.funnel });
		const f = run.funnel;
		expect(
			screen.getByText(
				`Dropped ${f.raw - f.passed}: own domain ${f.dropped_own}, negative term ${f.dropped_negative}, unrelated ${f.dropped_unrelated}.`
			)
		).toBeInTheDocument();
		expect(
			screen.getByText(
				`Set aside ${f.unique - f.new}: seen before ${f.seen_before}, reinforcements of a report ${f.reinforcements}.`
			)
		).toBeInTheDocument();
	});

	it('sizes bars as a share of the raw hits, raw at full width, never wider further down', () => {
		const { container } = render(FunnelDiagram, { funnel: run.funnel });
		const widths = [...container.querySelectorAll<HTMLElement>('.bar')].map((bar) =>
			parseFloat(bar.style.width)
		);
		expect(widths[0]).toBe(100);
		for (let i = 1; i < widths.length; i += 1) {
			expect(widths[i]).toBeLessThanOrEqual(widths[i - 1] ?? 0);
		}
	});

	it('draws no bar for an empty stage but keeps its label and zero', () => {
		const funnel = { ...run.funnel, new: 0, seen_before: run.funnel.unique, reinforcements: 0 };
		const { container } = render(FunnelDiagram, { funnel });
		const fresh = container.querySelector('[data-stage="new"]') as HTMLElement;
		expect(fresh.querySelector('.bar')).toBeNull();
		expect(fresh.querySelector('.count')).toHaveTextContent('0');
	});
});
