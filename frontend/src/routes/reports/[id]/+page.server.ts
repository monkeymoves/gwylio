import { reportIds } from '$lib/server/snapshot';
import type { EntryGenerator } from './$types';

/** One static page per report in the published snapshot, so deep links work without a fallback. */
export const entries: EntryGenerator = () => reportIds().map((id) => ({ id }));
