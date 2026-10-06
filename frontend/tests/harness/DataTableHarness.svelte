<script lang="ts">
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';

	interface Row {
		id: string;
		name: string;
		count: number | null;
	}

	let { rows, compact = false }: { rows: Row[]; compact?: boolean } = $props();

	const columns: Column<Row>[] = [
		{ key: 'name', label: 'Name', sortValue: (r) => r.name },
		{ key: 'count', label: 'Count', sortValue: (r) => r.count, align: 'end' },
		{ key: 'note', label: 'Note' }
	];
</script>

<DataTable {rows} {columns} rowKey={(r) => r.id} caption="Test rows" {compact}>
	{#snippet cell(row: Row, column: Column<Row>)}
		{#if column.key === 'name'}{row.name}{:else if column.key === 'count'}{row.count ?? 'none'}{:else}n{/if}
	{/snippet}
</DataTable>
