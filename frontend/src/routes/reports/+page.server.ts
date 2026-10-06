import { tagNames } from '$lib/server/snapshot';
import type { PageServerLoad } from './$types';

/**
 * Topic, hazard and place names for the filters, read from the snapshot's
 * report details at build time (reports.json carries ids only).
 */
export const load: PageServerLoad = () => ({ tagNames: tagNames() });
