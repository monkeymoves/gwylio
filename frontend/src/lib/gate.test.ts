import { describe, expect, it } from 'vitest';
import { GATE_STORAGE_KEY, configuredGateHash, hashPassword, isUnlocked, rememberUnlock } from './gate';

// printf 'gwylio-site:%s' 'open sesame' | shasum -a 256, as make site-password runs it.
const OPEN_SESAME = '6503a68a8cd729564b34ef8efa32fc23203ddd24fbca79613df9bbc67996d8c1';

describe('gate', () => {
	it('hashes the salted password exactly as make site-password does', async () => {
		expect(await hashPassword('open sesame')).toBe(OPEN_SESAME);
		expect(await hashPassword('open sesame ')).not.toBe(OPEN_SESAME);
	});

	it('turns the screen off unless a well-formed hash is configured', () => {
		expect(configuredGateHash(undefined)).toBeNull();
		expect(configuredGateHash('')).toBeNull();
		expect(configuredGateHash('not-a-hash')).toBeNull();
		expect(configuredGateHash(` ${OPEN_SESAME.toUpperCase()}\n`)).toBe(OPEN_SESAME);
	});

	it('remembers an unlock per hash, so a new password asks again', () => {
		localStorage.clear();
		expect(isUnlocked(OPEN_SESAME)).toBe(false);
		rememberUnlock(OPEN_SESAME);
		expect(localStorage.getItem(GATE_STORAGE_KEY)).toBe(OPEN_SESAME);
		expect(isUnlocked(OPEN_SESAME)).toBe(true);
		expect(isUnlocked('0'.repeat(64))).toBe(false);
	});

	it('treats storage that throws as locked, never as an error', () => {
		const broken = {
			getItem: () => {
				throw new Error('blocked');
			},
			setItem: () => {
				throw new Error('blocked');
			}
		} as unknown as Storage;
		expect(isUnlocked(OPEN_SESAME, broken)).toBe(false);
		expect(() => rememberUnlock(OPEN_SESAME, broken)).not.toThrow();
	});
});
