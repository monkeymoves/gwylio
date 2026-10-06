import { loadMeta } from '$lib/data/client';
import type { LayoutLoad } from './$types';

// Every page is prerendered to static HTML for Firebase Hosting.
export const prerender = true;

/** The snapshot's meta feeds the nav (default set) and the footer on every page. */
export const load: LayoutLoad = async ({ fetch }) => {
	return { meta: await loadMeta(fetch) };
};
