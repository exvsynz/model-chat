<script lang="ts">
    import type { ModelsResponse, OpenRouterModel } from './api';

    let {
        models,
        allModels = [],
        personas,
        currentModel = $bindable(),
        currentPersona = $bindable(),
        currentEffort = $bindable(),
    }: {
        models: ModelsResponse;
        allModels: OpenRouterModel[];
        personas: string[];
        currentModel: string;
        currentPersona: string | null;
        currentEffort: string | null;
    } = $props();

    let search = $state('');
    let showDropdown = $state(false);
    let inputEl: HTMLInputElement | undefined = $state();

    let currentModelName = $derived(
        allModels.find(m => m.id === currentModel)?.name
        || Object.entries(models.aliases).find(([_, id]) => id === currentModel)?.[0]
        || currentModel
    );

    let filteredModels = $derived(
        search
            ? allModels.filter(m =>
                m.id.toLowerCase().includes(search.toLowerCase()) ||
                m.name.toLowerCase().includes(search.toLowerCase())
              ).slice(0, 100)
            : allModels.slice(0, 100)
    );

    function selectModel(id: string) {
        currentModel = id;
        search = '';
        showDropdown = false;
    }

    function onPersonaChange(e: Event) {
        const select = e.target as HTMLSelectElement;
        currentPersona = select.value || null;
    }

    function setEffort(level: string | null) {
        currentEffort = currentEffort === level ? null : level;
    }

    function handleInputFocus() {
        showDropdown = true;
        search = '';
    }

    function handleInputBlur() {
        setTimeout(() => { showDropdown = false; }, 200);
    }
</script>

<div class="flex items-center gap-4 px-4 py-2 bg-zinc-800 border-b border-zinc-700">
    <span class="text-sm font-semibold text-zinc-400">model-chat</span>

    <div class="relative">
        <input
            bind:this={inputEl}
            type="text"
            value={showDropdown ? search : currentModelName}
            oninput={(e) => { search = (e.target as HTMLInputElement).value; }}
            onfocus={handleInputFocus}
            onblur={handleInputBlur}
            placeholder="Search models..."
            class="bg-zinc-700 text-zinc-100 text-sm rounded px-2 py-1 border border-zinc-600 focus:outline-none focus:border-zinc-400 w-72"
        />
        {#if showDropdown}
            <div class="absolute top-full left-0 mt-1 w-96 max-h-80 overflow-y-auto bg-zinc-800 border border-zinc-600 rounded-lg shadow-xl z-50">
                {#each filteredModels as model}
                    <button
                        onmousedown={() => selectModel(model.id)}
                        class="w-full text-left px-3 py-2 text-sm hover:bg-zinc-700 transition-colors {model.id === currentModel ? 'bg-zinc-700 text-blue-400' : 'text-zinc-300'}"
                    >
                        <div class="truncate font-medium">{model.name}</div>
                        <div class="text-xs text-zinc-500 truncate">{model.id}</div>
                    </button>
                {/each}
                {#if filteredModels.length === 0}
                    <div class="px-3 py-2 text-sm text-zinc-500">No models found</div>
                {/if}
            </div>
        {/if}
    </div>

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
