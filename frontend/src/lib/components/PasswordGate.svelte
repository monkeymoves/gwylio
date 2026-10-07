<script lang="ts" module>
	import type { Snippet } from 'svelte';

	export interface PasswordGateProps {
		/** The salted SHA-256 hash to match; null turns the screen off. */
		hash: string | null;
		children: Snippet;
	}
</script>

<script lang="ts">
	import { onMount } from 'svelte';
	import { hashPassword, isUnlocked, rememberUnlock } from '$lib/gate';

	let { hash, children }: PasswordGateProps = $props();

	// Prerendered HTML always shows the screen when a hash is set; the browser
	// then lifts it at once if this visitor unlocked the site before.
	let unlocked = $state(false);
	let password = $state('');
	let wrong = $state(false);
	let checking = $state(false);

	onMount(() => {
		if (hash !== null && isUnlocked(hash)) unlocked = true;
	});

	async function submit(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		if (hash === null || checking) return;
		checking = true;
		const matches = (await hashPassword(password)) === hash;
		checking = false;
		if (matches) {
			rememberUnlock(hash);
			unlocked = true;
		} else {
			wrong = true;
			password = '';
		}
	}
</script>

{#if hash === null || unlocked}
	{@render children()}
{:else}
	<div class="splash">
		<form class="card" onsubmit={submit} aria-labelledby="gate-title">
			<p class="brand">Gwylio</p>
			<h1 id="gate-title">Welsh environmental horizon scan</h1>
			<p class="lede">This site is shared with invited readers. Enter the password to continue.</p>
			<label for="gate-password">Password</label>
			<input
				id="gate-password"
				type="password"
				autocomplete="current-password"
				required
				bind:value={password}
				oninput={() => (wrong = false)}
				aria-invalid={wrong}
				aria-describedby={wrong ? 'gate-error' : undefined}
			/>
			{#if wrong}
				<p id="gate-error" class="error" role="alert">That password is not right. Try again.</p>
			{/if}
			<button type="submit" disabled={checking}>Enter</button>
		</form>
	</div>
{/if}

<style>
	.splash {
		display: grid;
		min-height: 100vh;
		place-items: center;
		padding: var(--space-6) var(--gutter);
		background: var(--color-bg);
	}

	.card {
		display: flex;
		flex-direction: column;
		gap: var(--space-3);
		width: 100%;
		max-width: 26rem;
		padding: var(--space-8) var(--space-6);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
	}

	.brand {
		margin: 0;
		color: var(--color-accent);
		font-size: var(--text-lg);
		font-weight: 700;
	}

	h1 {
		margin: 0;
		font-size: var(--text-xl);
		line-height: 1.2;
	}

	.lede {
		margin: 0 0 var(--space-2);
		color: var(--color-text-muted);
	}

	label {
		font-size: var(--text-sm);
		font-weight: 600;
	}

	input {
		padding: var(--space-2) var(--space-3);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-bg);
		color: var(--color-text);
		font: inherit;
	}

	input[aria-invalid='true'] {
		border-color: var(--color-bad);
	}

	.error {
		margin: 0;
		color: var(--color-bad);
		font-size: var(--text-sm);
	}

	button {
		padding: var(--space-2) var(--space-4);
		border: 0;
		border-radius: var(--radius);
		background: var(--color-accent);
		color: var(--color-accent-contrast);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}

	button:disabled {
		opacity: 0.7;
		cursor: progress;
	}
</style>
