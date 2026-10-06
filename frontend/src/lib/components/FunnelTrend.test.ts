import { render, screen, within } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { seed } from '../../../tests/fixtures';
import type { SourcesHealth } from '$lib/data/types.generated';
import FunnelTrend, { TREND_MEASURES, measureOf } from './FunnelTrend.svelte';

const health = seed<SourcesHealth>('sources_health.json');

describe('FunnelTrend', () => {
	it('draws one small chart per measure, raw, unique, new and reinforcements', () => {
		const { container } = render(FunnelTrend, { trend: health.trend });
		const panels = [...container.querySelectorAll('[data-measure]')];
		expect(panels.map((p) => p.getAttribute('data-measure'))).toEqual([
			'raw',
			'unique',
			'new',
			'reinforcements'
		]);
		expect(screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual(
			TREND_MEASURES.map((m) => m.label)
		);
	});

	it('has one column per run in each chart, oldest first, with its value', () => {
		const { container } = render(FunnelTrend, { trend: health.trend });
		for (const measure of TREND_MEASURES) {
			const panel = container.querySelector(`[data-measure="${measure.key}"]`) as HTMLElement;
			const columns = within(panel).getAllByRole('listitem');
			expect(columns).toHaveLength(health.trend.length);
			expect(columns.map((c) => c.getAttribute('title'))).toEqual(
				health.trend.map((p) => expect.stringContaining(`run ${p.run_id}: ${measureOf(p, measure.key)}`))
			);
		}
	});

	it('shares one labelled scale across the charts and names its source', () => {
		const { container } = render(FunnelTrend, { trend: health.trend });
		const ticks = [...container.querySelectorAll('[data-measure="raw"] .tick')].map((t) => t.textContent);
		expect(ticks).toEqual(['0', '25', '50']);
		const newTicks = [...container.querySelectorAll('[data-measure="new"] .tick')].map((t) => t.textContent);
		expect(newTicks).toEqual(ticks);
		expect(screen.getByText(/Vertical axis: count per run/)).toBeInTheDocument();
		expect(screen.getByText(/Horizontal axis: scan runs by start date/)).toBeInTheDocument();
		expect(screen.getByText('Source: gwylio scan runs')).toBeInTheDocument();
	});

	it('labels the latest run in each chart and dates the first and last runs', () => {
		const { container } = render(FunnelTrend, { trend: health.trend });
		const last = health.trend[health.trend.length - 1];
		if (!last) throw new Error('empty trend');
		const labels = [...container.querySelectorAll('.end-label')].map((l) => l.textContent);
		expect(labels).toEqual(TREND_MEASURES.map((m) => String(measureOf(last, m.key))));
		const axis = container.querySelector('[data-measure="raw"] .x-axis');
		expect(axis).toHaveTextContent('1 Sep 2026');
		expect(axis).toHaveTextContent('4 Oct 2026');
	});
});
