<script lang="ts" module>
	/** Visual tone of a badge; maps to the status colour tokens. */
	export type BadgeTone = 'neutral' | 'good' | 'warn' | 'bad';
</script>

<script lang="ts">
	let { label, tone = 'neutral' }: { label: string; tone?: BadgeTone } = $props();
</script>

<span class="badge" data-tone={tone}>{label}</span>

<style>
	.badge {
		display: inline-block;
		padding: 0 var(--space-2);
		border: 1px solid currentColor;
		border-radius: var(--radius);
		font-size: var(--text-sm);
		font-weight: 600;
		line-height: 1.6;
		white-space: nowrap;
		color: var(--color-neutral);
	}

	.badge[data-tone='good'] {
		color: var(--color-good);
	}

	.badge[data-tone='warn'] {
		color: var(--color-warn);
	}

	.badge[data-tone='bad'] {
		color: var(--color-bad);
	}
</style>
