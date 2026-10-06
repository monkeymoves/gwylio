import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import DirectionTags, { groupByDirection } from './DirectionTags.svelte';

const assessments = [
	{ requirement_id: 'si4', code: 'SI4', direction: 'threatens' as const },
	{ requirement_id: 'si1', code: 'SI1', direction: 'supports' as const },
	{ requirement_id: 'si8', code: null, direction: 'threatens' as const }
];

describe('DirectionTags', () => {
	it('groups codes by direction in vocabulary order', () => {
		expect(groupByDirection(assessments)).toEqual([
			{ direction: 'supports', codes: ['SI1'] },
			{ direction: 'threatens', codes: ['SI4', 'si8'] }
		]);
	});

	it('labels each group, so colour is never alone', () => {
		render(DirectionTags, { assessments, labels: { threatens: 'threatens' } });
		const items = screen.getAllByRole('listitem');
		expect(items.map((li) => li.textContent?.replace(/\s+/g, ' ').trim())).toEqual([
			'supports SI1',
			'threatens SI4, si8'
		]);
	});
});
