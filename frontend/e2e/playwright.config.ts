import { defineConfig, devices } from '@playwright/test';

// Chromium only. Two projects give the two viewports the evidence screenshots need.
// The browser comes from PLAYWRIGHT_BROWSERS_PATH locally (preinstalled build 1194,
// which is why @playwright/test is pinned to 1.56.1) and from
// `playwright install chromium` in continuous integration.
export default defineConfig({
	testDir: '.',
	outputDir: '../test-results',
	fullyParallel: true,
	forbidOnly: !!process.env.CI,
	retries: process.env.CI ? 1 : 0,
	reporter: [['list']],
	use: {
		baseURL: 'http://localhost:4173',
		browserName: 'chromium',
		trace: 'retain-on-failure'
	},
	projects: [
		{
			name: 'desktop',
			use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } }
		},
		{
			name: 'phone',
			use: {
				...devices['Desktop Chrome'],
				viewport: { width: 390, height: 844 },
				hasTouch: true
			}
		}
	],
	webServer: {
		command: 'pnpm build && pnpm preview --port 4173 --strictPort',
		cwd: '..',
		url: 'http://localhost:4173',
		reuseExistingServer: !process.env.CI,
		timeout: 180_000
	}
});
