import { render, screen, within } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { enums, seed } from '../fixtures';
import type { RunDetail } from '$lib/data/types.generated';
import Page from '../../src/routes/scans/[id]/+page.svelte';

// The real snapshot has no scan run, so the run page is proven on the seed runs.
const first = seed<RunDetail>('run_first.json');
const judged = seed<RunDetail>('run_judged.json');

function renderRun(run: RunDetail) {
	// The page reads only run and enums; the layout's meta is not used here.
	const data = { run, enums } as unknown as Parameters<typeof Page>[1]['data'];
	return render(Page, { data });
}

describe('scan run page', () => {
	it('shows the run, its funnel, dispositions and promotion rate', () => {
		const { container } = renderRun(first);
		expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(`Scan run ${first.run_id}`);
		expect(container.querySelectorAll('[data-stage]')).toHaveLength(4);
		const outcomes = container.querySelector('table.outcomes') as HTMLElement;
		expect(within(outcomes).getByText('promoted').closest('tr')).toHaveTextContent(
			String(first.dispositions.counts.promoted)
		);
		expect(screen.getByText(/Promotion rate: 59%/)).toBeInTheDocument();
		expect(screen.getByText(/1 waiting/)).toBeInTheDocument();
	});

	it('shows the credibility of the promotions as six bars and links each new report', () => {
		const { container } = renderRun(first);
		expect(container.querySelectorAll('[data-credibility]')).toHaveLength(6);
		for (const id of first.promoted_report_ids) {
			expect(container.querySelector(`a[href="/reports/${id}"]`)).not.toBeNull();
		}
	});

	it('counts sightings by source, naming the open web', () => {
		renderRun(judged);
		const table = screen.getByRole('table', { name: 'Sightings and candidates by source in this run' });
		expect(within(table).getAllByRole('row')).toHaveLength(judged.per_source.length + 1);
		expect(within(table).getByText('open web (no watched source)')).toBeInTheDocument();
	});

	it('lists warnings and notes, or says there were none', () => {
		renderRun(judged);
		expect(screen.getByText(/raised no warning/)).toBeInTheDocument();
	});

	it('lists each warning and note when there are some', () => {
		renderRun({ ...judged, warnings: ['feed audit-wales: malformed XML'], notes: ['budget reached'] });
		expect(screen.getByText('feed audit-wales: malformed XML')).toBeInTheDocument();
		expect(screen.getByText('budget reached')).toBeInTheDocument();
	});
});
