import { expect, test, type Page, type TestInfo } from '@playwright/test';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// WP8: the picture, the report list and one report, at desktop and phone width.
// Expectations are computed from the published snapshot, not hard-coded.

const here = path.dirname(fileURLToPath(import.meta.url));
const evidenceDir = path.resolve(here, '..', '..', 'docs', 'evidence', 'WP8');
const dataDir = path.resolve(here, '..', 'static', 'data');

interface Assessment {
	requirement_id: string;
	direction: string;
}

interface Summary {
	id: string;
	title: string;
	grading: string;
	flags: string[];
	assessments: Assessment[];
}

const reports = JSON.parse(readFileSync(path.join(dataDir, 'reports.json'), 'utf8')) as Summary[];
const meta = JSON.parse(readFileSync(path.join(dataDir, 'meta.json'), 'utf8')) as {
	default_requirement_set_id: string;
};
const setId = meta.default_requirement_set_id;

async function expectNoHorizontalScroll(page: Page): Promise<void> {
	const overflow = await page.evaluate(
		() => document.documentElement.scrollWidth - document.documentElement.clientWidth
	);
	expect(overflow).toBeLessThanOrEqual(0);
}

async function evidence(page: Page, testInfo: TestInfo, name: string): Promise<void> {
	await page.screenshot({
		path: path.join(evidenceDir, `${name}__${testInfo.project.name}.png`),
		fullPage: true
	});
}

function countWhere(requirement: string, direction: string): number {
	return reports.filter((r) =>
		r.assessments.some((a) => a.requirement_id === requirement && a.direction === direction)
	).length;
}

test('picture: tiles per group and requirement, SI12 reads blind spot, not quiet', async ({
	page
}, testInfo) => {
	await page.goto(`/picture/${setId}`);
	await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
	await expect(page.getByRole('heading', { name: 'Well-being objectives' })).toBeVisible();
	await expect(page.getByRole('heading', { name: 'Impacts' })).toBeVisible();

	const si12 = page.locator('[data-requirement="si12"]');
	const chip = si12.locator('[data-status="blind_spot"]');
	await expect(chip).toHaveText(/blind spot: not scannable/);
	await expect(chip).toHaveClass(/status-blind-spot/);
	await expect(chip).not.toHaveClass(/status-quiet/);
	await expect(si12).toHaveAttribute('href', '/reports?requirement=si12');

	await expect(page.getByRole('complementary').filter({ hasText: 'Date check' })).toBeVisible();
	await expectNoHorizontalScroll(page);
	await evidence(page, testInfo, `picture-${setId}`);
});

test('reports: every report listed, and a filter writes itself to the URL', async ({
	page
}, testInfo) => {
	await page.goto('/reports');
	const count = page.getByTestId('report-count');
	await expect(count).toHaveText(`${reports.length} of ${reports.length} reports`);
	await expect(page.locator('tbody tr')).toHaveCount(reports.length);
	await expectNoHorizontalScroll(page);
	await evidence(page, testInfo, 'reports');

	const threatens = reports.filter((r) => r.assessments.some((a) => a.direction === 'threatens'));
	await expect(async () => {
		await page.getByLabel('Direction').selectOption('threatens');
		await expect(page).toHaveURL(/\/reports\?direction=threatens$/, { timeout: 1000 });
	}).toPass();
	await expect(count).toHaveText(`${threatens.length} of ${reports.length} reports`);
});

test('reports filtered by requirement and direction from the URL', async ({ page }, testInfo) => {
	const expected = countWhere('si4', 'threatens');
	await page.goto('/reports?requirement=si4&direction=threatens');
	await expect(page.getByTestId('report-count')).toHaveText(
		`${expected} of ${reports.length} reports`
	);
	await expect(page.locator('tbody tr')).toHaveCount(expected);
	await expect(page.getByLabel('Requirement')).toHaveValue('si4');
	await expect(page.getByLabel('Direction')).toHaveValue('threatens');
	await expectNoHorizontalScroll(page);
	await evidence(page, testInfo, 'reports-si4-threatens');
});

test('report detail: grading badge with both labels, stale marks and a safe source link', async ({
	page
}, testInfo) => {
	const report = reports.find((r) => r.flags.includes('passed_horizon')) ?? reports[0];
	if (!report) throw new Error('The snapshot has no reports');
	await page.goto(`/reports/${report.id}`);
	await expect(page.getByRole('heading', { level: 1 })).toHaveText(report.title);

	const badge = page.locator('.badge').first();
	await expect(badge).toHaveText(report.grading);
	await expect(badge).toHaveAttribute('title', /Source reliability .+\. Information credibility .+\./);

	const source = page.getByRole('link', { name: /Open the source/ });
	await expect(source).toHaveAttribute('target', '_blank');
	await expect(source).toHaveAttribute('rel', 'noopener');

	if (report.flags.includes('passed_horizon')) {
		await expect(page.locator('.stale').first()).toBeVisible();
	}
	await expectNoHorizontalScroll(page);
	await evidence(page, testInfo, 'report-detail');
});
