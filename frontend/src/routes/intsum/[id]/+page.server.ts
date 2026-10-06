import { productIds } from '$lib/server/snapshot';
import type { EntryGenerator } from './$types';

/** One static page per product in the published snapshot. */
export const entries: EntryGenerator = () => productIds().map((id) => ({ id }));
