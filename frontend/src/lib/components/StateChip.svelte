<script lang="ts" module>
	import type { IndicatorState } from '$lib/data/types.generated';

	export interface StateChipProps {
		state: IndicatorState;
		/** The state's label from the enums, such as emerging. */
		label?: string;
		/** A count to show after the label, for state mixes. */
		count?: number;
		/** The state's meaning, shown as the title. */
		meaning?: string | null;
	}
</script>

<script lang="ts">
	let { state, label, count, meaning }: StateChipProps = $props();
</script>

<span class="chip" data-state={state} title={meaning ?? undefined}
	>{label ?? state}{#if count !== undefined}<span class="count">{count}</span>{/if}</span
>

<style>
	.chip {
		display: inline-flex;
		align-items: baseline;
		gap: var(--space-1);
		padding: 0 var(--space-2);
		border: 1px solid var(--color-border);
		border-radius: 999px;
		background: var(--color-surface);
		color: var(--color-text);
		font-size: var(--text-sm);
		line-height: 1.6;
		white-space: nowrap;
	}

	.count {
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}

	.chip[data-state='reinforced'],
	.chip[data-state='tracking'] {
		border-color: var(--color-accent);
	}

	.chip[data-state='faded'],
	.chip[data-state='parked'] {
		color: var(--color-text-muted);
		border-style: dotted;
	}
</style>
