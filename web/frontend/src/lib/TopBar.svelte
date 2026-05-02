<script lang="ts">
    import type { ModelsResponse } from './api';

    let {
        models,
        personas,
        currentModel = $bindable(),
        currentPersona = $bindable(),
        currentEffort = $bindable(),
    }: {
        models: ModelsResponse;
        personas: string[];
        currentModel: string;
        currentPersona: string | null;
        currentEffort: string | null;
    } = $props();

    let aliasEntries = $derived(Object.entries(models.aliases));

    function onModelChange(e: Event) {
        const select = e.target as HTMLSelectElement;
        currentModel = select.value;
    }

    function onPersonaChange(e: Event) {
        const select = e.target as HTMLSelectElement;
        currentPersona = select.value || null;
    }

    function setEffort(level: string | null) {
        currentEffort = currentEffort === level ? null : level;
    }
</script>

<div class="flex items-center gap-4 px-4 py-2 bg-zinc-800 border-b border-zinc-700">
    <span class="text-sm font-semibold text-zinc-400">model-chat</span>

    <select
        value={currentModel}
        onchange={onModelChange}
        class="bg-zinc-700 text-zinc-100 text-sm rounded px-2 py-1 border border-zinc-600 focus:outline-none focus:border-zinc-400"
    >
        {#each aliasEntries as [alias, fullId]}
            <option value={fullId}>{alias}</option>
        {/each}
    </select>

    <div class="flex gap-1">
        {#each ['low', 'medium', 'high'] as level}
            <button
                class="px-2 py-1 text-xs rounded {currentEffort === level ? 'bg-blue-600 text-white' : 'bg-zinc-700 text-zinc-300 hover:bg-zinc-600'}"
                onclick={() => setEffort(level)}
            >
                {level}
            </button>
        {/each}
    </div>

    <select
        value={currentPersona || ''}
        onchange={onPersonaChange}
        class="bg-zinc-700 text-zinc-100 text-sm rounded px-2 py-1 border border-zinc-600 focus:outline-none focus:border-zinc-400"
    >
        <option value="">No persona</option>
        {#each personas as name}
            <option value={name}>{name}</option>
        {/each}
    </select>
</div>
