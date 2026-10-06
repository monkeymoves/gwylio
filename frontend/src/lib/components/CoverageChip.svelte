<script lang="ts" module>
	import type { CoverageStatus } from '$lib/data/types.generated';

	export interface CoverageChipProps {
		status: CoverageStatus;
		/** The status label from the enums; a blind spot always reads "blind spot: not scannable". */
		label?: string;
		/** What the status means, shown as the title. */
		meaning?: string | null;
		/** A count to show before the label, for group summaries. */
		count?: number;
	}

	/** The text a blind spot chip always carries: it is never quiet. */
	export const BLIND_SPOT_TEXT = 'blind spot: not scannable';

	/** The chip's visible text for a status. */
	export function coverageText(status: CoverageStatus, label?: string): string {
		if (status === 'blind_spot') return BLIND_SPOT_TEXT;
		return label ?? status;
	}

	const ICONS: Record<CoverageStatus, string> = {
		covered: '●',
		thin: '◐',
		quiet: '○',
		blind_spot: '⊘'
	};
</script>

<script lang="ts">
	let { status, label, meaning, count }: CoverageChipProps = $props();
	const text = $derived(coverageText(status, label));
</script>

<span
	class="chip status-{status.replace('_', '-')}"
	data-status={status}
	title={meaning ?? undefined}
>
	<span class="icon" aria-hidden="true">{ICONS[status]}</span>
	{#if count !== undefined}<span class="count">{count}</span>{/if}
	<span class="text">{text}</span>
</span>

<style>
	.chip {
		display: inline-flex;
		align-items: baseline;
		gap: var(--space-1);
		padding: 0 var(--space-2);
		border: 1px solid currentColor;
		border-radius: var(--radius);
		background: var(--color-surface);
		font-size: var(--text-sm);
		font-weight: 600;
		line-height: 1.6;
		white-space: nowrap;
	}

	.icon {
		font-size: 0.8em;
	}

	.count {
		font-variant-numeric: tabular-nums;
	}

	.status-covered {
		color: var(--color-good);
	}

	.status-thin {
		color: var(--color-warn);
	}

	.status-quiet {
		color: var(--color-neutral);
		font-weight: 500;
	}

	/* A blind spot is inverse ink with a hatch, so it can never be mistaken for quiet. */
	.status-blind-spot {
		border-color: var(--chip-blind-bg);
		background-color: var(--chip-blind-bg);
		background-image: repeating-linear-gradient(
			45deg,
			var(--chip-blind-hatch) 0 2px,
			transparent 2px 6px
		);
		color: var(--chip-blind-text);
	}
</style>
