<script lang="ts">
    import type { ConversationSummary } from './api';

    let {
        conversations = [],
        onLoad,
        onNew,
    }: {
        conversations?: ConversationSummary[];
        onLoad: (id: string) => void;
        onNew: () => void;
    } = $props();
</script>

<div class="w-64 border-r border-zinc-700 flex flex-col h-full" style="background-color: rgb(20 20 20);">
    <div class="p-3">
        <button
            onclick={onNew}
            class="w-full bg-zinc-700 hover:bg-zinc-600 text-zinc-100 text-sm rounded-lg px-3 py-2 transition-colors"
        >
            + New Chat
        </button>
    </div>

    <div class="flex-1 overflow-y-auto px-2 space-y-1">
        {#each conversations as convo}
            <button
                onclick={() => onLoad(convo.id)}
                class="w-full text-left px-3 py-2 rounded-lg text-sm text-zinc-300 hover:bg-zinc-700 transition-colors truncate"
                title={convo.id}
            >
                <div class="truncate">{convo.id}</div>
                <div class="text-xs text-zinc-500">{convo.model.split('/').pop()} · {convo.message_count} msgs</div>
            </button>
        {/each}

        {#if conversations.length === 0}
            <p class="text-xs text-zinc-500 px-3 py-2">No saved conversations</p>
        {/if}
    </div>
</div>
