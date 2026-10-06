<script lang="ts" module>
	import type { Direction } from '$lib/data/types.generated';

	/** The part of an assessment the tags need; both AssessmentLine and AssessmentDetail fit. */
	export interface TaggedAssessment {
		requirement_id: string;
		code: string | null;
		direction: Direction;
	}

	export interface DirectionGroup {
		direction: Direction;
		codes: string[];
	}

	/** Assessments grouped by direction, in vocabulary order, codes in the order given. Pure. */
	export function groupByDirection(assessments: readonly TaggedAssessment[]): DirectionGroup[] {
		const order: Direction[] = ['supports', 'threatens', 'neutral', 'informs_baseline'];
		return order
			.map((direction) => ({
				direction,
				codes: assessments
					.filter((a) => a.direction === direction)
					.map((a) => a.code ?? a.requirement_id)
			}))
			.filter((group) => group.codes.length > 0);
	}
</script>

<script lang="ts">
	import { DEFAULT_DIRECTION_LABELS } from './DirectionBar.svelte';

	let {
		assessments,
		labels = {}
	}: {
		assessments: readonly TaggedAssessment[];
		labels?: Partial<Record<Direction, string>>;
	} = $props();

	const groups = $derived(groupByDirection(assessments));
</script>

<ul class="tags">
	{#each groups as group (group.direction)}
		<li data-direction={group.direction}>
			<span class="swatch" aria-hidden="true"></span>
			<span class="label">{labels[group.direction] ?? DEFAULT_DIRECTION_LABELS[group.direction]}</span>
			<span class="codes"
				>{#each group.codes as code, i (code)}<span class="code">{code}</span
					>{#if i < group.codes.length - 1}{', '}{/if}{/each}</span
			>
		</li>
	{/each}
</ul>

<style>
	.tags {
		display: grid;
		gap: 2px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	li {
		display: flex;
		align-items: baseline;
		gap: var(--space-1);
	}

	.label {
		white-space: nowrap;
	}

	.swatch {
		flex: none;
		transform: translateY(1px);
		width: 10px;
		height: 10px;
		border-radius: 2px;
		background: var(--seg);
	}

	.codes {
		font-family: var(--font-mono);
		font-size: 0.85em;
		color: var(--color-text-muted);
	}

	.code {
		white-space: nowrap;
	}

	[data-direction='supports'] {
		--seg: var(--dir-supports);
	}

	[data-direction='threatens'] {
		--seg: var(--dir-threatens);
	}

	[data-direction='neutral'] {
		--seg: var(--dir-neutral);
	}

	[data-direction='informs_baseline'] {
		--seg: var(--dir-informs-baseline);
	}
</style>
