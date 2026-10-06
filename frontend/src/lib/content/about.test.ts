import { describe, expect, it } from 'vitest';
import { enums } from '../../../tests/fixtures';
import { ABOUT, COVERAGE_NOTES, CREDIBILITY_SCALE, LIFECYCLE_STATES, RELIABILITY_SCALE } from './about';

const EN_DASH = String.fromCharCode(0x2013);
const EM_DASH = String.fromCharCode(0x2014);

function allText(): string {
	return JSON.stringify({ ABOUT, COVERAGE_NOTES });
}

describe('about content', () => {
	it('spells both Admiralty scales as the published enums do', () => {
		expect(RELIABILITY_SCALE.map(([letter, label]) => [letter, label])).toEqual(
			enums.reliability.map((e) => [e.value, e.label])
		);
		expect(CREDIBILITY_SCALE.map(([digit, label]) => [digit, label])).toEqual(
			enums.credibility.map((e) => [e.value, e.label])
		);
	});

	it('lists every indicator state, in vocabulary order', () => {
		expect(LIFECYCLE_STATES.map(([state]) => state)).toEqual(
			enums.indicator_state.map((e) => e.value)
		);
	});

	it('covers what the brief asks for', () => {
		const ids = ABOUT.sections.map((s) => s.id);
		expect(ids).toEqual(
			expect.arrayContaining(['collect-then-judge', 'grading', 'lifecycle', 'bias-guards', 'horizons', 'blind-spot'])
		);
		const guards = ABOUT.sections.find((s) => s.id === 'bias-guards')?.list?.items ?? [];
		expect(guards.map((g) => g.term)).toEqual(['Optimism.', 'Mainstream.', 'Streetlight.']);
		expect(allText()).toContain('blind spot: not scannable');
	});

	it('has no en or em dash anywhere', () => {
		const text = allText();
		expect(text.includes(EN_DASH)).toBe(false);
		expect(text.includes(EM_DASH)).toBe(false);
	});
});
