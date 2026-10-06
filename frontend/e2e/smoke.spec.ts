import { expect, test } from '@playwright/test';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
const evidenceDir = path.resolve(here, '..', '..', 'docs', 'evidence', 'WP0');

test('home page renders the header and placeholder without horizontal scroll', async ({
	page
}, testInfo) => {
	await page.goto('/');
	await expect(page.getByRole('banner')).toContainText('Gwylio');
	await expect(page.getByRole('main')).toContainText('intelligence picture');

	const overflow = await page.evaluate(
		() => document.documentElement.scrollWidth - document.documentElement.clientWidth
	);
	expect(overflow).toBeLessThanOrEqual(0);

	const background = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
	expect(background).not.toBe('rgba(0, 0, 0, 0)');

	await page.screenshot({
		path: path.join(evidenceDir, `home__${testInfo.project.name}.png`),
		fullPage: true
	});
});
