<script lang="ts">
	let {
		toolName,
		args,
		onRespond,
	}: {
		toolName: string;
		args: Record<string, unknown>;
		onRespond: (approved: boolean) => void;
	} = $props();

	function formatArgs(args: Record<string, unknown>): string {
		const entries = Object.entries(args);
		if (entries.length === 0) return '';
		return entries
			.map(([k, v]) => {
				const val = typeof v === 'string' ? v : JSON.stringify(v);
				const short = val.length > 200 ? val.slice(0, 200) + '...' : val;
				return `${k}: ${short}`;
			})
			.join('\n');
	}
</script>

<div
	class="my-2 rounded-lg border border-amber-400/60 dark:border-amber-500/40 bg-amber-50/50 dark:bg-amber-950/20 text-sm overflow-hidden"
>
	<div class="px-3 py-2 flex items-center gap-2">
		<span class="text-amber-500 flex-shrink-0">⚠</span>
		<span class="font-mono text-xs text-zinc-700 dark:text-zinc-300 flex-1">
			<span class="font-semibold">{toolName}</span> requires approval
		</span>
	</div>
	{#if Object.keys(args).length > 0}
		<div class="border-t border-amber-300/30 dark:border-amber-700/30 px-3 py-2">
			<pre
				class="text-xs text-zinc-500 dark:text-zinc-400 whitespace-pre-wrap break-all font-mono leading-relaxed">{formatArgs(
					args,
				)}</pre>
		</div>
	{/if}
	<div
		class="border-t border-amber-300/30 dark:border-amber-700/30 px-3 py-2 flex gap-2 justify-end"
	>
		<button
			class="px-3 py-1 text-xs rounded-md bg-zinc-200 dark:bg-zinc-700 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-300 dark:hover:bg-zinc-600 transition-colors"
			onclick={() => onRespond(false)}
		>
			Deny
		</button>
		<button
			class="px-3 py-1 text-xs rounded-md bg-blue-600 text-white hover:bg-blue-500 transition-colors"
			onclick={() => onRespond(true)}
		>
			Allow
		</button>
	</div>
</div>
