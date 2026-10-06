import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** Dynamic routes whose entries come from snapshot lists that may be empty. */
const SNAPSHOT_ROUTES = new Set(['/scans/[id]', '/intsum/[id]', '/products/[file]']);

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),
	compilerOptions: {
		runes: true
	},
	kit: {
		// Static site for Firebase Hosting: every page is prerendered, no SPA fallback.
		adapter: adapter({
			pages: 'build',
			assets: 'build',
			precompress: false,
			strict: true
		}),
		prerender: {
			// A dynamic route whose entries come from the snapshot may have none:
			// with no scan run published, /scans/[id] has no page to render. Only
			// the routes named here may go unrendered; any other unseen route
			// still fails the build.
			handleUnseenRoutes: ({ routes, message }) => {
				const unexpected = routes.filter((route) => !SNAPSHOT_ROUTES.has(route));
				if (unexpected.length > 0) throw new Error(message);
				console.warn(`No snapshot entries yet for ${routes.join(', ')}; nothing to prerender there.`);
			}
		}
	}
};

export default config;
