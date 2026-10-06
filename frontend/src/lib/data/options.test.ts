import { describe, expect, it } from 'vitest';
import { enums, report, snapshot } from '../../../tests/fixtures';
import { buildFilterOptions } from './options';
import type { RequirementSetDetail } from './types.generated';

const set = snapshot<RequirementSetDetail>('requirement_set_nrw-corporate-plan.json');

describe('buildFilterOptions', () => {
	const reports = [
		report({ id: 'a', lane: 'senedd', lane_name: 'Senedd', hazards: ['legal-challenge'] }),
		report({ id: 'b', topics: ['peatland'], places: ['wales'] })
	];
	const options = buildFilterOptions(reports, enums, [set], {
		topics: { peatland: 'Peatland' },
		hazards: {},
		places: { wales: 'Wales' }
	});

	it('lists every requirement of the set with its code and short name', () => {
		expect(options.requirement).toHaveLength(set.requirements.length);
		expect(options.requirement[11]).toEqual({ value: 'si12', label: 'SI12 NRW colleague engagement' });
	});

	it('lists closed vocabularies in full with their labels', () => {
		expect(options.direction.map((o) => o.label)).toContain('two-way');
		expect(options.credibility).toHaveLength(6);
		expect(options.reliability[1]).toEqual({ value: 'B', label: 'B: usually reliable' });
	});

	it('offers only the lanes and tags some report carries, named where known', () => {
		expect(options.lane).toEqual([
			{ value: 'senedd', label: 'Senedd' },
			{ value: 'welsh-government', label: 'Welsh Government' }
		]);
		expect(options.topic).toEqual([{ value: 'peatland', label: 'Peatland' }]);
		expect(options.hazard).toEqual([{ value: 'legal-challenge', label: 'Legal challenge' }]);
		expect(options.place).toEqual([{ value: 'wales', label: 'Wales' }]);
	});
});
