import { runIds } from '$lib/server/snapshot';
import type { EntryGenerator } from './$types';

/**
 * One static page per scan run in the published snapshot. While the snapshot
 * holds no run this is an empty list; `svelte.config.js` lets this route (and
 * only the routes it names) go unrendered rather than fail the build.
 */
export const entries: EntryGenerator = () => runIds().map((id) => ({ id }));
