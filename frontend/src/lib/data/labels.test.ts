import { describe, expect, it } from 'vitest';
import { enums } from '../../../tests/fixtures';
import {
	capitalise,
	enumLabel,
	enumMeaning,
	formatDate,
	formatInstant,
	humaniseId,
	labelMap,
	plural
} from './labels';

describe('enum labels come from the snapshot', () => {
	it('looks up labels and meanings', () => {
		expect(enumLabel(enums, 'direction', 'neutral')).toBe('two-way');
		expect(enumLabel(enums, 'credibility', 2)).toBe('probably true');
		expect(enumMeaning(enums, 'coverage_status', 'blind_spot')).toMatch(/never call it quiet/);
		expect(labelMap(enums, 'bucket')).toMatchObject({ follow_up: 'follow up' });
	});

	it('falls back to the value when the vocabulary lacks it', () => {
		expect(enumLabel(undefined, 'bucket', 'follow_up')).toBe('follow up');
		expect(enumMeaning(enums, 'bucket', 'brief')).toBeNull();
	});
});

describe('formatting', () => {
	it('writes dates the British way, with a fallback for none', () => {
		expect(formatDate('2026-07-25')).toBe('25 Jul 2026');
		expect(formatDate(null)).toBe('none');
		expect(formatDate(null, 'never')).toBe('never');
		expect(formatDate('soon')).toBe('soon');
	});

	it('writes instants in UTC', () => {
		expect(formatInstant('2026-10-06T10:19:08Z')).toBe('6 Oct 2026, 10:19 UTC');
	});

	it('handles words', () => {
		expect(capitalise('impact')).toBe('Impact');
		expect(humaniseId('drought-and-low-flows')).toBe('Drought and low flows');
		expect(plural(1, 'report')).toBe('1 report');
		expect(plural(3, 'report')).toBe('3 reports');
	});
});
