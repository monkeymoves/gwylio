import { render, screen, within } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { seed } from '../../../tests/fixtures';
import type { RunDetail } from '$lib/data/types.generated';
import CredibilityBars, { sixDigits } from './CredibilityBars.svelte';

const run = seed<RunDetail>('run_first.json');

describe('CredibilityBars', () => {
	it('shows the six digits 1 to 6 with their labels and counts', () => {
		render(CredibilityBars, { bars: run.credibility, caption: 'Promotions by credibility' });
		const items = within(screen.getByRole('list', { name: 'Promotions by credibility' })).getAllByRole(
			'listitem'
		);
		expect(items.map((li) => li.getAttribute('data-credibility'))).toEqual(['1', '2', '3', '4', '5', '6']);
		expect(items.map((li) => li.querySelector('.label')?.textContent)).toEqual([
			'confirmed',
			'probably true',
			'possibly true',
			'doubtful',
			'improbable',
			'cannot be judged'
		]);
		expect(items.map((li) => li.querySelector('.count')?.textContent)).toEqual(
			run.credibility.map((bar) => String(bar.count))
		);
	});

	it('draws bars only for non-zero digits, the largest at full width', () => {
		const { container } = render(CredibilityBars, { bars: run.credibility, caption: 'C' });
		const max = Math.max(...run.credibility.map((b) => b.count));
		const bars = [...container.querySelectorAll<HTMLElement>('.bar')];
		expect(bars).toHaveLength(run.credibility.filter((b) => b.count > 0).length);
		expect(bars.map((b) => parseFloat(b.style.width))).toContain(100);
		const two = container.querySelector('[data-credibility="2"] .bar') as HTMLElement;
		expect(parseFloat(two.style.width)).toBeCloseTo((5 / max) * 100);
		expect(container.querySelector('[data-credibility="4"]')).toHaveClass('zero');
	});

	it('states the total', () => {
		render(CredibilityBars, { bars: run.credibility, caption: 'C', unit: 'promotion' });
		expect(screen.getByText(/^10 promotions in all/)).toBeInTheDocument();
	});

	it('fills in a digit the read model left out, and copes with no reports at all', () => {
		expect(sixDigits([{ credibility: 3, label: 'possibly true', count: 2 }]).map((b) => b.count)).toEqual([
			0, 0, 2, 0, 0, 0
		]);
		const { container } = render(CredibilityBars, { bars: [], caption: 'Empty' });
		expect(container.querySelectorAll('li')).toHaveLength(6);
		expect(container.querySelectorAll('.bar')).toHaveLength(0);
		expect(screen.getByText(/^0 reports in all/)).toBeInTheDocument();
	});
});
