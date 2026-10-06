import { expect, test, type Page, type TestInfo } from '@playwright/test';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// WP9: the evaluation views (sources, scans, coverage, verify), the products
// and the method, at desktop and phone width. Expectations are computed from
// the published snapshot, not hard-coded.

const here = path.dirname(fileURLToPath(import.meta.url));
const evidenceDir = path.resolve(here, '..', '..', 'docs', 'evidence', 'WP9');
const dataDir = path.resolve(here, '..', 'static', 'data');

function data<T>(file: string): T {
	return JSON.parse(readFileSync(path.join(dataDir, file), 'utf8')) as T;
}

interface Source {
	id: string;
	lane: string;
	lane_name: string;
}

interface Run {
	run_id: string;
}

interface Health {
	silent_sources: string[];
	trend: unknown[];
}

interface Row {
	row_id: string;
	status: string;
	cells: { count: number }[];
}

interface Coverage {
	lanes: { columns: unknown[]; rows: Row[] };
	taxonomy: { axis_id: string }[];
}

interface DateCheck {
	total: number;
	groups: { kind: string; count: number }[];
}

interface Product {
	id: string;
	level: string;
	title: string;
	markdown_file: string;
	period: { end: string };
}

const sources = data<Source[]>('sources.json');
const health = data<Health>('sources_health.json');
const runs = data<Run[]>('runs.json');
const products = data<Product[]>('products.json');
const datecheck = data<DateCheck>('datecheck.json');
const meta = data<{ default_requirement_set_id: string }>('meta.json');
const setId = meta.default_requirement_set_id;
const coverage = data<Coverage>(`coverage_${setId}.json`);

async function expectNoHorizontalScroll(page: Page): Promise<void> {
	const overflow = await page.evaluate(
		() => document.documentElement.scrollWidth - document.documentElement.clientWidth
	);
	expect(overflow).toBeLessThanOrEqual(0);
}

/** At desktop width every table fits its own container; at phone width it may scroll inside it. */
async function expectTablesFitOnDesktop(page: Page, testInfo: TestInfo): Promise<void> {
	if (testInfo.project.name !== 'desktop') return;
	const overflows = await page.evaluate(() =>
		[...document.querySelectorAll('.table-scroll')].map((el) => el.scrollWidth - el.clientWidth)
	);
	expect(overflows.every((o) => o <= 0)).toBe(true);
}

async function evidence(page: Page, testInfo: TestInfo, name: string): Promise<void> {
	await page.screenshot({
		path: path.join(evidenceDir, `${name}__${testInfo.project.name}.png`),
		fullPage: true
	});
}

test('sources: the watchlist, silent sources and the lane filter in the URL', async ({
	page
}, testInfo) => {
	await page.goto('/sources');
	await expect(page.getByRole('heading', { level: 1, name: 'Sources' })).toBeVisible();
	const count = page.getByTestId('source-count');
	await expect(count).toHaveText(`${sources.length} of ${sources.length} sources`);
	await expect(page.locator('table tbody tr')).toHaveCount(sources.length);
	await expect(page.getByRole('heading', { name: 'Silent sources' })).toBeVisible();
	if (health.silent_sources.length > 0) {
		await expect(page.getByTestId('silent-count')).toContainText(
			`${health.silent_sources.length} of`
		);
	}
	const reliability = page.locator('abbr.letter').first();
	await expect(reliability).toHaveAttribute('title', /^[A-F]: .+/);
	if (health.trend.length === 0) {
		await expect(page.getByText('No scan runs yet')).toBeVisible();
	} else {
		await expect(page.getByText('Source: gwylio scan runs')).toBeVisible();
	}
	await expectNoHorizontalScroll(page);
	await expectTablesFitOnDesktop(page, testInfo);
	await evidence(page, testInfo, 'sources');

	const lane = sources.find((s) => s.lane === 'senedd') ?? sources[0];
	if (!lane) throw new Error('The snapshot has no sources');
	const inLane = sources.filter((s) => s.lane === lane.lane).length;
	await expect(async () => {
		await page.getByLabel('Lane').selectOption(lane.lane);
		await expect(page).toHaveURL(new RegExp(`/sources\\?lane=${lane.lane}$`), { timeout: 1000 });
	}).toPass();
	await expect(count).toHaveText(`${inLane} of ${sources.length} sources`);
	await expect(page.locator('table tbody tr')).toHaveCount(inLane);
});

test('sources: a lane in the address is applied on load', async ({ page }) => {
	const lane = sources[0]?.lane;
	if (!lane) throw new Error('The snapshot has no sources');
	const inLane = sources.filter((s) => s.lane === lane).length;
	await page.goto(`/sources?lane=${lane}`);
	await expect(page.getByTestId('source-count')).toHaveText(`${inLane} of ${sources.length} sources`);
	await expect(page.getByLabel('Lane')).toHaveValue(lane);
});

test('scans: the run list, or an empty state while no run is published', async ({
	page
}, testInfo) => {
	await page.goto('/scans');
	await expect(page.getByRole('heading', { level: 1, name: 'Scans' })).toBeVisible();
	if (runs.length === 0) {
		await expect(page.getByRole('status').filter({ hasText: 'No scan runs yet' })).toBeVisible();
		await expect(page.locator('table')).toHaveCount(0);
	} else {
		await expect(page.getByTestId('run-count')).toHaveText(`${runs.length} runs`);
		await expect(page.locator('table tbody tr')).toHaveCount(runs.length);
	}
	await expectNoHorizontalScroll(page);
	await evidence(page, testInfo, 'scans');
});

test('scan run detail from the snapshot', async ({ page }, testInfo) => {
	const run = runs[runs.length - 1];
	test.skip(!run, 'The published snapshot holds no scan run yet; the /scans spec asserts the empty state.');
	if (!run) return;
	await page.goto(`/scans/${run.run_id}`);
	await expect(page.getByRole('heading', { level: 1 })).toContainText(run.run_id);
	await expect(page.locator('[data-stage]')).toHaveCount(4);
	await expect(page.locator('[data-credibility]')).toHaveCount(6);
	await expectNoHorizontalScroll(page);
	await evidence(page, testInfo, 'scan-detail');
});

test('coverage: two heatmaps with a legend, blind spots hatched and never quiet', async ({
	page
}, testInfo) => {
	await page.goto(`/coverage/${setId}`);
	await expect(page.getByRole('heading', { name: 'Requirements by lane' })).toBeVisible();
	const lanes = page.getByRole('table', { name: 'Active reports by requirement and lane' });
	await expect(lanes.locator('tbody tr')).toHaveCount(coverage.lanes.rows.length);
	await expect(lanes.locator('thead th')).toHaveCount(coverage.lanes.columns.length + 2);
	await expect(page.locator('section').filter({ hasText: 'Taxonomy:' })).toHaveCount(
		coverage.taxonomy.length
	);

	const first = coverage.lanes.rows[0];
	if (!first) throw new Error('The coverage matrix is empty');
	await expect(lanes.locator(`tr[data-row="${first.row_id}"] td.cell`).first()).toHaveText(
		String(first.cells[0]?.count)
	);

	const blind = coverage.lanes.rows.find((r) => r.status === 'blind_spot');
	if (blind) {
		const row = lanes.locator(`tr[data-row="${blind.row_id}"]`);
		await expect(row.locator('[data-status="blind_spot"]').first()).toHaveText(
			/blind spot: not scannable/
		);
		const quietCell = page.locator('td.cell[data-status="quiet"]').first();
		const blindCell = row.locator('td.cell').first();
		const look = (el: typeof blindCell) =>
			el.evaluate((node) => {
				const style = getComputedStyle(node);
				return `${style.backgroundColor} ${style.backgroundImage}`;
			});
		expect(await look(blindCell)).not.toBe(await look(quietCell));
		expect(await look(blindCell)).toContain('repeating-linear-gradient');
	}
	const legend = page.getByRole('list', { name: 'Coverage statuses' }).first();
	await expect(legend.getByRole('listitem')).toHaveCount(4);
	await expectNoHorizontalScroll(page);
	await expectTablesFitOnDesktop(page, testInfo);
	await evidence(page, testInfo, `coverage-${setId}`);
});

test('verify: the date check queue grouped by kind, each finding linking to its report', async ({
	page
}, testInfo) => {
	await page.goto('/verify');
	await expect(page.getByRole('heading', { level: 1, name: 'Verify' })).toBeVisible();
	if (datecheck.total === 0) {
		await expect(page.getByText('Nothing to verify')).toBeVisible();
	} else {
		for (const group of datecheck.groups) {
			await expect(page.getByTestId(`count-${group.kind}`)).toContainText(
				`${group.count} finding`
			);
		}
		await expect(page.locator('.findings a')).toHaveCount(datecheck.total);
	}
	await expectNoHorizontalScroll(page);
	await evidence(page, testInfo, 'verify');
});

test('intsum: the latest operational product, a selector and the Markdown', async ({
	page,
	request
}, testInfo) => {
	const operational = products
		.filter((p) => p.level === 'operational')
		.sort((a, b) => b.period.end.localeCompare(a.period.end))[0];
	if (!operational) throw new Error('The snapshot has no operational product');
	await page.goto('/intsum');
	await expect(page.getByRole('heading', { level: 1 })).toHaveText(operational.title);
	const selector = page.getByRole('navigation', { name: 'Published products' });
	await expect(selector.getByRole('link')).toHaveCount(products.length);
	await expect(selector.locator(`a[data-product="${operational.id}"]`)).toHaveAttribute(
		'aria-current',
		'page'
	);
	const markdown = page.getByRole('link', { name: /Download the Markdown/ });
	await expect(markdown).toHaveAttribute('href', `/products/${operational.markdown_file}`);
	const response = await request.get(`/products/${operational.markdown_file}`);
	expect(response.ok()).toBe(true);
	expect(await response.text()).toContain('## ');
	await expectNoHorizontalScroll(page);
	await expectTablesFitOnDesktop(page, testInfo);
	await evidence(page, testInfo, 'intsum');

	const other = products.find((p) => p.id !== operational.id);
	if (other) {
		await selector.locator(`a[data-product="${other.id}"]`).click();
		await expect(page).toHaveURL(new RegExp(`/intsum/${other.id}$`));
		await expect(page.getByRole('heading', { level: 1 })).toHaveText(other.title);
		await expectNoHorizontalScroll(page);
	}
});

test('about: the method, both grading scales and the blind spot rule', async ({
	page
}, testInfo) => {
	await page.goto('/about');
	await expect(page.getByRole('heading', { level: 1 })).toContainText('About Gwylio');
	for (const heading of [
		'Collect, then judge',
		'Admiralty grading',
		'The lifecycle of a report',
		'Three bias guards',
		'Two horizons',
		'A blind spot is not quiet'
	]) {
		await expect(page.getByRole('heading', { level: 2, name: heading })).toBeVisible();
	}
	await expect(page.getByRole('table', { name: 'Source reliability, A to F' }).locator('tbody tr')).toHaveCount(6);
	await expect(
		page.getByRole('table', { name: 'Information credibility, 1 to 6' }).locator('tbody tr')
	).toHaveCount(6);
	await expectNoHorizontalScroll(page);
	await expectTablesFitOnDesktop(page, testInfo);
	await evidence(page, testInfo, 'about');
});
