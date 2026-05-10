<script lang="ts">
    import TopBar from '$lib/TopBar.svelte';
    import Chat from '$lib/Chat.svelte';
    import Sidebar from '$lib/Sidebar.svelte';
    import {
        fetchModels,
        fetchAllModels,
        fetchPersonas,
        fetchConversations,
        fetchMemories,
        deleteMemory,
        loadConversation,
        saveConversation,
        deleteConversation,
        streamChat,
        type ChatEvent,
        type ModelsResponse,
        type Message,
        type ConversationSummary,
        type OpenRouterModel,
        type Memory,
    } from '$lib/api';

    let models: ModelsResponse = $state({ aliases: {}, default: '' });
    let allModels: OpenRouterModel[] = $state([]);
    let personas: string[] = $state([]);
    let conversations: ConversationSummary[] = $state([]);
    let memories: Memory[] = $state([]);
    let messages: Message[] = $state([]);
    let currentModel = $state('');
    let currentPersona: string | null = $state(null);
    let currentEffort: string | null = $state(null);
    let streamingContent = $state('');
    let inputText = $state('');
    let isStreaming = $state(false);
    let inputEl: HTMLTextAreaElement | undefined = $state();

    $effect(() => {
        Promise.all([
            fetchModels(),
            fetchAllModels(),
            fetchPersonas(),
            fetchConversations(),
            fetchMemories(),
        ]).then(([m, am, p, c, mem]) => {
            models = m;
            allModels = am;
            personas = p;
            conversations = c;
            memories = mem;
            currentModel = m.default;
        });
    });

    async function sendMessage() {
        const text = inputText.trim();
        if (!text || isStreaming) return;

        inputText = '';
        messages = [...messages, { role: 'user', content: text }];
        isStreaming = true;
        streamingContent = '';

        try {
            for await (const event of streamChat(messages, currentModel, currentPersona, currentEffort)) {
                if (event.type === 'text') {
                    streamingContent += event.content;
                }
            }
            messages = [...messages, { role: 'assistant', content: streamingContent }];
            streamingContent = '';

            const firstUserMsg = messages.find(m => m.role === 'user');
            const title = firstUserMsg
                ? firstUserMsg.content.slice(0, 50) + (firstUserMsg.content.length > 50 ? '...' : '')
                : 'New conversation';

            const now = new Date().toISOString();
            const modelShort = currentModel.includes('/') ? currentModel.split('/').pop() : currentModel;
            const id = `${now.slice(0, 19).replace(/[T:]/g, '-')}_${modelShort}`;
            await saveConversation({
                id,
                model: currentModel,
                persona: currentPersona,
                title,
                created_at: now,
                updated_at: now,
                messages,
            });
            conversations = await fetchConversations();
            memories = await fetchMemories();
        } catch (e: any) {
            streamingContent = '';
            messages = [...messages, { role: 'assistant', content: `Error: ${e.message}` }];
        } finally {
            isStreaming = false;
        }
    }

    async function handleDelete(id: string) {
        await deleteConversation(id);
        conversations = await fetchConversations();
    }

    async function handleLoad(id: string) {
        const convo = await loadConversation(id);
        messages = convo.messages || [];
        currentModel = convo.model || currentModel;
        currentPersona = convo.persona || null;
    }

    async function handleDeleteMemory(slug: string) {
        await deleteMemory(slug);
        memories = await fetchMemories();
    }

    function handleNew() {
        messages = [];
        streamingContent = '';
    }

    function handleKeydown(e: KeyboardEvent) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    }
</script>

<div class="h-screen flex flex-col">
    <TopBar
        {models}
        {allModels}
        {personas}
        bind:currentModel
        bind:currentPersona
        bind:currentEffort
    />
    <div class="flex flex-1 overflow-hidden">
        <Sidebar
            {conversations}
            {memories}
            onLoad={handleLoad}
            onNew={handleNew}
            onDelete={handleDelete}
            onDeleteMemory={handleDeleteMemory}
        />
        <div class="flex flex-col flex-1">
            <Chat {messages} {streamingContent} />
            <div class="border-t border-zinc-300 dark:border-zinc-700 p-4">
                <div class="max-w-3xl mx-auto flex gap-2">
                    <textarea
                        bind:this={inputEl}
                        bind:value={inputText}
                        onkeydown={handleKeydown}
                        placeholder="Type a message..."
                        rows="1"
                        class="flex-1 bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 rounded-xl px-4 py-3 text-sm resize-none border border-zinc-300 dark:border-zinc-600 focus:outline-none focus:border-zinc-400 placeholder-zinc-400 dark:placeholder-zinc-500"
                        disabled={isStreaming}
                    ></textarea>
                    <button
                        onclick={sendMessage}
                        disabled={isStreaming || !inputText.trim()}
                        class="bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-300 dark:disabled:bg-zinc-700 disabled:text-zinc-500 text-white px-4 py-2 rounded-xl text-sm transition-colors"
                    >
                        Send
                    </button>
                </div>
            </div>
        </div>
    </div>
</div>
