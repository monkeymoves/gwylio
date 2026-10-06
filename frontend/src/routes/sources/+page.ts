import { loadEnums, loadSources, loadSourcesHealth } from '$lib/data/client';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	const [sources, health, enums] = await Promise.all([
		loadSources(fetch),
		loadSourcesHealth(fetch),
		loadEnums(fetch)
	]);
	return { sources, health, enums };
};
