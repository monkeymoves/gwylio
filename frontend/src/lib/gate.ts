/**
 * The password screen in front of the hosted site.
 *
 * This is a curtain, not a lock (ADR 0005, docs/DEPLOY.md): the site is
 * static, so the pages and the JSON under /data stay fetchable by URL. It
 * keeps casual visitors out and nothing more. The build carries only a salted
 * SHA-256 hash of the password, read from PUBLIC_GWYLIO_SITE_PASSWORD_SHA256
 * (written to the gitignored frontend/.env.production.local by
 * `make site-password`). With no hash the screen is off, as it is in
 * development, continuous integration and the end to end tests.
 */

/** Prefixed to the password before hashing, so a bare SHA-256 table does not apply. */
export const GATE_SALT = 'gwylio-site:';

/** Where the browser remembers an unlock: the hash it matched, so a new password relocks. */
export const GATE_STORAGE_KEY = 'gwylio-site-unlocked';

/** The configured hash, lower case, or null when the screen is off. */
export function configuredGateHash(
	value: string | undefined = import.meta.env.PUBLIC_GWYLIO_SITE_PASSWORD_SHA256
): string | null {
	const trimmed = (value ?? '').trim().toLowerCase();
	return /^[0-9a-f]{64}$/.test(trimmed) ? trimmed : null;
}

/** Hex SHA-256 of the salted password; matches `make site-password`. */
export async function hashPassword(password: string): Promise<string> {
	const bytes = new TextEncoder().encode(`${GATE_SALT}${password}`);
	const digest = await crypto.subtle.digest('SHA-256', bytes);
	return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

/** Whether this browser has already unlocked the site for this hash. */
export function isUnlocked(hash: string, storage: Storage | undefined = safeStorage()): boolean {
	try {
		return storage?.getItem(GATE_STORAGE_KEY) === hash;
	} catch {
		return false;
	}
}

/** Remember the unlock; a browser that refuses storage simply asks again next time. */
export function rememberUnlock(hash: string, storage: Storage | undefined = safeStorage()): void {
	try {
		storage?.setItem(GATE_STORAGE_KEY, hash);
	} catch {
		// Private windows and blocked storage: the unlock lasts for this page only.
	}
}

function safeStorage(): Storage | undefined {
	try {
		return typeof localStorage === 'undefined' ? undefined : localStorage;
	} catch {
		return undefined;
	}
}
