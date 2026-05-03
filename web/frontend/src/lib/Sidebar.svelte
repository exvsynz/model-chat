<script lang="ts">
    import type { ConversationSummary, Memory } from './api';

    let {
        conversations = [],
        memories = [],
        onLoad,
        onNew,
        onDelete,
        onDeleteMemory,
    }: {
        conversations?: ConversationSummary[];
        memories?: Memory[];
        onLoad: (id: string) => void;
        onNew: () => void;
        onDelete: (id: string) => void;
        onDeleteMemory: (slug: string) => void;
    } = $props();

    let memoriesExpanded = $state(false);
</script>

<div class="w-64 border-r border-zinc-300 dark:border-zinc-700 flex flex-col h-full bg-zinc-50 dark:bg-[rgb(20,20,20)]">
    <div class="p-3">
        <button
            onclick={onNew}
            class="w-full bg-zinc-200 dark:bg-zinc-700 hover:bg-zinc-300 dark:hover:bg-zinc-600 text-zinc-900 dark:text-zinc-100 text-sm rounded-lg px-3 py-2 transition-colors"
        >
            + New Chat
        </button>
    </div>

    <div class="flex-1 overflow-y-auto px-2 space-y-1">
        {#each conversations as convo}
            <div class="group flex items-center rounded-lg hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-colors">
                <button
                    onclick={() => onLoad(convo.id)}
                    class="flex-1 text-left px-3 py-2 text-sm text-zinc-700 dark:text-zinc-300 truncate"
                    title={convo.id}
                >
                    <div class="truncate">{convo.title || convo.id}</div>
                    <div class="text-xs text-zinc-500">{convo.model.split('/').pop()} · {convo.message_count} msgs</div>
                </button>
                <button
                    onclick={(e) => { e.stopPropagation(); onDelete(convo.id); }}
                    class="hidden group-hover:block px-2 text-zinc-500 hover:text-red-400 text-xs"
                    title="Delete"
                >
                    ✕
                </button>
            </div>
        {/each}

        {#if conversations.length === 0}
            <p class="text-xs text-zinc-500 px-3 py-2">No saved conversations</p>
        {/if}
    </div>

    <!-- Memories section -->
    <div class="border-t border-zinc-300 dark:border-zinc-700">
        <button
            onclick={() => memoriesExpanded = !memoriesExpanded}
            class="w-full text-left px-4 py-2 text-xs font-medium text-zinc-500 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors flex justify-between items-center"
        >
            <span>Memories ({memories.length})</span>
            <span class="text-[10px]">{memoriesExpanded ? '▼' : '▶'}</span>
        </button>
        {#if memoriesExpanded}
            <div class="px-2 pb-2 space-y-1 max-h-48 overflow-y-auto">
                {#each memories as mem}
                    <div class="group flex items-center rounded text-xs px-2 py-1 hover:bg-zinc-200 dark:hover:bg-zinc-700">
                        <span class="flex-1 text-zinc-600 dark:text-zinc-400 truncate" title={mem.summary}>
                            {mem.summary}
                        </span>
                        <button
                            onclick={() => onDeleteMemory(mem.file.replace('.md', ''))}
                            class="hidden group-hover:block text-zinc-400 hover:text-red-400 ml-1"
                        >
                            ✕
                        </button>
                    </div>
                {/each}
                {#if memories.length === 0}
                    <p class="text-xs text-zinc-500 px-2 py-1">No memories yet</p>
                {/if}
            </div>
        {/if}
    </div>
</div>
