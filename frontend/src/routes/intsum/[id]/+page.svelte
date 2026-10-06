<script lang="ts">
	import ProductScreen from '$lib/components/ProductScreen.svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
</script>

<ProductScreen products={data.products} product={data.product} enums={data.enums} />
