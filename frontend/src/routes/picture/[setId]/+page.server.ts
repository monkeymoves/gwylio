import { requirementSetIds } from '$lib/server/snapshot';
import type { EntryGenerator } from './$types';

/** One static page per requirement set in the published snapshot. */
export const entries: EntryGenerator = () => requirementSetIds().map((setId) => ({ setId }));
