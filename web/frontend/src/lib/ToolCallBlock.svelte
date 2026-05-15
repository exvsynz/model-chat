<script lang="ts">
	import type { ToolCallBlock } from './api';

	let { block }: { block: ToolCallBlock } = $props();

	let expanded = $state(false);
	let showFullOutput = $state(false);

	const OUTPUT_LINE_LIMIT = 20;

	let prevStatus = $derived(block.status);
	let lastStatus = $state('');
	$effect(() => {
		if (prevStatus === 'running') expanded = true;
		if (lastStatus === 'running' && prevStatus !== 'running') expanded = false;
		lastStatus = prevStatus;
	});

	let outputLines = $derived(block.output?.split('\n') ?? []);
	let isTruncated = $derived(outputLines.length > OUTPUT_LINE_LIMIT);
	let displayOutput = $derived(
		showFullOutput || !isTruncated
			? (block.output ?? '')
			: outputLines.slice(0, OUTPUT_LINE_LIMIT).join('\n'),
	);

	function formatArgs(args: Record<string, unknown>): string {
		const entries = Object.entries(args);
		if (entries.length === 0) return '';
		return entries
			.map(([k, v]) => {
				const val = typeof v === 'string' ? v : JSON.stringify(v);
				const short = val.length > 120 ? val.slice(0, 120) + '...' : val;
				return `${k}: ${short}`;
			})
			.join('\n');
	}

	const statusIcon = $derived(
		block.status === 'running' ? '⟳' : block.status === 'success' ? '✓' : '✗',
	);

	const borderClass = $derived(
		block.status === 'running'
			? 'border-blue-400/50 dark:border-blue-500/40'
			: block.status === 'error'
				? 'border-red-400/50 dark:border-red-500/40 bg-red-50/50 dark:bg-red-950/20'
				: 'border-zinc-300 dark:border-zinc-700',
	);

	const iconClass = $derived(
		block.status === 'running'
			? 'text-blue-500 animate-spin'
			: block.status === 'success'
				? 'text-green-500'
				: 'text-red-500',
	);
</script>

<div class="my-2 rounded-lg border {borderClass} text-sm overflow-hidden">
	<button
		class="w-full flex items-center gap-2 px-3 py-2 hover:bg-zinc-100 dark:hover:bg-zinc-800/50 transition-colors text-left"
		onclick={() => (expanded = !expanded)}
	>
		<span class="font-mono text-xs {iconClass} flex-shrink-0 w-4 text-center">{statusIcon}</span>
		<span class="font-mono text-xs text-zinc-600 dark:text-zinc-400 flex-1 truncate"
			>{block.name}</span
		>
		<span
			class="text-zinc-400 dark:text-zinc-500 text-xs flex-shrink-0 transition-transform {expanded
				? 'rotate-90'
				: ''}">▶</span
		>
	</button>

	{#if expanded}
		<div class="border-t border-zinc-200 dark:border-zinc-700/50 px-3 py-2 space-y-2">
			{#if Object.keys(block.arguments).length > 0}
				<pre
					class="text-xs text-zinc-500 dark:text-zinc-400 whitespace-pre-wrap break-all font-mono leading-relaxed">{formatArgs(
						block.arguments,
					)}</pre>
			{/if}

			{#if block.output != null}
				<div class="border-t border-zinc-200 dark:border-zinc-700/50 pt-2">
					<pre
						class="text-xs whitespace-pre-wrap break-all font-mono leading-relaxed {block.is_error
							? 'text-red-600 dark:text-red-400'
							: 'text-zinc-700 dark:text-zinc-300'}">{displayOutput}</pre>
					{#if isTruncated && !showFullOutput}
						<button
							class="text-xs text-blue-500 hover:text-blue-400 mt-1"
							onclick={(e: MouseEvent) => {
								e.stopPropagation();
								showFullOutput = true;
							}}
						>
							Show {outputLines.length - OUTPUT_LINE_LIMIT} more lines
						</button>
					{/if}
				</div>
			{/if}

			{#if block.status === 'running' && block.output == null}
				<p class="text-xs text-zinc-400 dark:text-zinc-500 italic">Running...</p>
			{/if}
		</div>
	{/if}
</div>
