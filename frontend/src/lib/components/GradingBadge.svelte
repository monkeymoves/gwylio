<script lang="ts" module>
	import type { Credibility, Reliability } from '$lib/data/types.generated';

	export interface GradingBadgeProps {
		reliability: Reliability;
		credibility: Credibility;
		/** Admiralty wording for the letter, such as usually reliable. */
		reliabilityLabel: string;
		/** Admiralty wording for the digit, such as probably true. */
		credibilityLabel: string;
		/** Spell both labels out beside the badge, not only in its title. */
		showLabels?: boolean;
	}

	/** The title attribute: both scales spelt out. */
	export function gradingTitle(p: GradingBadgeProps): string {
		return `Source reliability ${p.reliability}: ${p.reliabilityLabel}. Information credibility ${p.credibility}: ${p.credibilityLabel}.`;
	}
</script>

<script lang="ts">
	let props: GradingBadgeProps = $props();
	const title = $derived(gradingTitle(props));
</script>

<span class="grading">
	<abbr class="badge" {title} data-reliability={props.reliability}
		>{props.reliability}{props.credibility}</abbr
	>
	{#if props.showLabels}
		<span class="labels"
			>source <strong>{props.reliabilityLabel}</strong>, information
			<strong>{props.credibilityLabel}</strong></span
		>
	{/if}
</span>

<style>
	.grading {
		display: inline-flex;
		align-items: baseline;
		gap: var(--space-2);
		flex-wrap: wrap;
	}

	.badge {
		display: inline-block;
		min-width: 2.5em;
		padding: 0 var(--space-2);
		border: 1px solid var(--color-accent);
		border-radius: var(--radius);
		background: var(--color-surface);
		color: var(--color-accent);
		font-family: var(--font-mono);
		font-size: var(--text-sm);
		font-weight: 700;
		line-height: 1.7;
		text-align: center;
		text-decoration: none;
		cursor: help;
	}

	.labels {
		color: var(--color-text-muted);
		font-size: var(--text-sm);
	}

	.labels strong {
		color: var(--color-text);
		font-weight: 600;
	}
</style>
