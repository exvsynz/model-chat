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
        respondToPermission,
        type ChatEvent,
        type ModelsResponse,
        type Message,
        type ConversationSummary,
        type OpenRouterModel,
        type Memory,
        type ContentBlock,
        type UsageStats,
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
    let streamingBlocks: ContentBlock[] = $state([]);
    let lastUsage: UsageStats | null = $state(null);
    let pendingPermission: { requestId: string; toolName: string; args: Record<string, unknown> } | null = $state(null);
    let inputText = $state('');
    let isStreaming = $state(false);
    let inputEl: HTMLTextAreaElement | undefined = $state();
    let sidebarOpen = $state(false);

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

    function appendTextToBlocks(blocks: ContentBlock[], text: string): ContentBlock[] {
        const last = blocks[blocks.length - 1];
        if (last && last.type === 'text') {
            return [...blocks.slice(0, -1), { type: 'text', content: last.content + text }];
        }
        return [...blocks, { type: 'text', content: text }];
    }

    async function sendMessage() {
        const text = inputText.trim();
        if (!text || isStreaming) return;

        inputText = '';
        messages = [...messages, { role: 'user', content: text }];
        isStreaming = true;
        streamingContent = '';
        streamingBlocks = [];
        lastUsage = null;

        try {
            for await (const event of streamChat(messages, currentModel, currentPersona, currentEffort)) {
                if (event.type === 'text') {
                    streamingContent += event.content;
                    streamingBlocks = appendTextToBlocks(streamingBlocks, event.content);
                } else if (event.type === 'tool_call') {
                    streamingBlocks = [...streamingBlocks, {
                        type: 'tool_call',
                        block: {
                            id: event.id,
                            name: event.name,
                            arguments: event.arguments,
                            status: 'running',
                        },
                    }];
                } else if (event.type === 'tool_result') {
                    streamingBlocks = streamingBlocks.map(b =>
                        b.type === 'tool_call' && b.block.id === event.id
                            ? { ...b, block: { ...b.block, status: event.is_error ? 'error' as const : 'success' as const, output: event.output, is_error: event.is_error } }
                            : b
                    );
                } else if (event.type === 'permission_request') {
                    pendingPermission = {
                        requestId: event.request_id,
                        toolName: event.tool_name,
                        args: event.arguments,
                    };
                } else if (event.type === 'done') {
                    lastUsage = event.usage;
                }
            }
            const hasToolCalls = streamingBlocks.some(b => b.type === 'tool_call');
            messages = [...messages, {
                role: 'assistant',
                content: streamingContent,
                ...(hasToolCalls ? { blocks: streamingBlocks } : {}),
                ...(lastUsage ? { usage: lastUsage } : {}),
            }];
            streamingContent = '';
            streamingBlocks = [];

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
            streamingBlocks = [];
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

    async function handlePermission(approved: boolean) {
        if (!pendingPermission) return;
        const { requestId } = pendingPermission;
        pendingPermission = null;
        await respondToPermission(requestId, approved);
    }

    function handleNew() {
        messages = [];
        streamingContent = '';
        streamingBlocks = [];
        lastUsage = null;
        pendingPermission = null;
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
        onToggleSidebar={() => sidebarOpen = !sidebarOpen}
    />
    <div class="flex flex-1 overflow-hidden">
        <Sidebar
            {conversations}
            {memories}
            open={sidebarOpen}
            onLoad={handleLoad}
            onNew={handleNew}
            onDelete={handleDelete}
            onDeleteMemory={handleDeleteMemory}
            onClose={() => sidebarOpen = false}
        />
        <div class="flex flex-col flex-1">
            <Chat {messages} {streamingContent} {streamingBlocks} {pendingPermission} onPermissionRespond={handlePermission} />
            <div class="border-t border-zinc-300 dark:border-zinc-700 p-2 md:p-4">
                <div class="max-w-full md:max-w-3xl md:mx-auto flex gap-2">
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
