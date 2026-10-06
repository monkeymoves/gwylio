import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { enums, snapshot } from '../fixtures';
import type { DateCheck } from '$lib/data/types.generated';
import Page from '../../src/routes/verify/+page.svelte';

const datecheck = snapshot<DateCheck>('datecheck.json');

function renderQueue(check: DateCheck) {
	const data = { datecheck: check, enums } as unknown as Parameters<typeof Page>[1]['data'];
	return render(Page, { data });
}

describe('verify page', () => {
	it('groups the findings by kind with a count line each', () => {
		const { container } = renderQueue(datecheck);
		const kinds = [...container.querySelectorAll('section[data-kind]')].map((s) =>
			s.getAttribute('data-kind')
		);
		expect(kinds).toEqual(['passed_horizon', 'future_language', 'stale_verification', 'never_verified']);
		for (const group of datecheck.groups) {
			expect(screen.getByTestId(`count-${group.kind}`)).toHaveTextContent(
				new RegExp(`^${group.count} finding`)
			);
		}
	});

	it('links every finding to its report, with the detail text', () => {
		const { container } = renderQueue(datecheck);
		const links = container.querySelectorAll('.findings a');
		expect(links).toHaveLength(datecheck.total);
		const first = datecheck.groups.find((g) => g.findings.length > 0)?.findings[0];
		if (!first) throw new Error('no finding');
		expect(container.querySelector(`a[href="/reports/${first.report_id}"]`)).toHaveTextContent(first.title);
		expect(screen.getAllByText(first.detail).length).toBeGreaterThan(0);
	});

	it('shows an empty state when the check is clean', () => {
		renderQueue({
			...datecheck,
			total: 0,
			reports_flagged: 0,
			groups: datecheck.groups.map((g) => ({ ...g, count: 0, findings: [] }))
		});
		expect(screen.getByText('Nothing to verify')).toBeInTheDocument();
		expect(document.querySelectorAll('section[data-kind]')).toHaveLength(0);
	});
});
