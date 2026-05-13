<script lang="ts">
    import { marked } from 'marked';
    import hljs from 'highlight.js';
    import 'highlight.js/styles/github-dark.css';
    import ToolCallBlockView from './ToolCallBlock.svelte';
    import PermissionPrompt from './PermissionPrompt.svelte';
    import type { Message, ContentBlock } from './api';

    let {
        messages = [],
        streamingContent = '',
        streamingBlocks = [],
        pendingPermission = null,
        onPermissionRespond = (_: boolean) => {},
    }: {
        messages?: Message[];
        streamingContent?: string;
        streamingBlocks?: ContentBlock[];
        pendingPermission?: { requestId: string; toolName: string; args: Record<string, unknown> } | null;
        onPermissionRespond?: (approved: boolean) => void;
    } = $props();

    let chatContainer: HTMLDivElement | undefined = $state();

    const renderer = new marked.Renderer();
    renderer.code = ({ text, lang }: { text: string; lang?: string }) => {
        const language = lang && hljs.getLanguage(lang) ? lang : null;
        const highlighted = language
            ? hljs.highlight(text, { language }).value
            : hljs.highlightAuto(text).value;
        return `<pre><code class="hljs">${highlighted}</code></pre>`;
    };

    function renderMarkdown(text: string): string {
        return marked.parse(text, { renderer }) as string;
    }

    function formatUsage(usage: { prompt_tokens: number; completion_tokens: number; total_tokens: number; elapsed_seconds: number }): string {
        const tokens = usage.total_tokens.toLocaleString();
        const elapsed = usage.elapsed_seconds.toFixed(1);
        return `${tokens} tokens · ${elapsed}s`;
    }

    $effect(() => {
        void messages.length;
        void streamingContent;
        void streamingBlocks.length;
        void pendingPermission;
        if (chatContainer) {
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
    });
</script>

<div bind:this={chatContainer} class="flex-1 overflow-y-auto px-4 py-6 space-y-6">
    {#each messages as msg}
        <div class="max-w-3xl mx-auto">
            {#if msg.role === 'user'}
                <div class="flex justify-end">
                    <div class="bg-zinc-200 dark:bg-zinc-700 rounded-2xl px-4 py-2 max-w-[80%]">
                        <p class="text-sm whitespace-pre-wrap">{msg.content}</p>
                    </div>
                </div>
            {:else if msg.role === 'assistant'}
                {#if msg.blocks && msg.blocks.length > 0}
                    {#each msg.blocks as block}
                        {#if block.type === 'text'}
                            <div class="prose dark:prose-invert prose-sm max-w-none">
                                {@html renderMarkdown(block.content)}
                            </div>
                        {:else if block.type === 'tool_call'}
                            <ToolCallBlockView block={block.block} />
                        {/if}
                    {/each}
                {:else}
                    <div class="prose dark:prose-invert prose-sm max-w-none">
                        {@html renderMarkdown(msg.content)}
                    </div>
                {/if}
                {#if msg.usage}
                    <p class="text-xs text-zinc-400 dark:text-zinc-500 mt-1">{formatUsage(msg.usage)}</p>
                {/if}
            {/if}
        </div>
    {/each}

    {#if streamingBlocks.length > 0}
        <div class="max-w-3xl mx-auto">
            {#each streamingBlocks as block}
                {#if block.type === 'text'}
                    <div class="prose dark:prose-invert prose-sm max-w-none">
                        {@html renderMarkdown(block.content)}
                    </div>
                {:else if block.type === 'tool_call'}
                    <ToolCallBlockView block={block.block} />
                {/if}
            {/each}
        </div>
    {:else if streamingContent}
        <div class="max-w-3xl mx-auto">
            <div class="prose dark:prose-invert prose-sm max-w-none">
                {@html renderMarkdown(streamingContent)}
            </div>
        </div>
    {/if}

    {#if pendingPermission}
        <div class="max-w-3xl mx-auto">
            <PermissionPrompt
                toolName={pendingPermission.toolName}
                args={pendingPermission.args}
                onRespond={onPermissionRespond}
            />
        </div>
    {/if}

    {#if messages.length === 0 && !streamingContent && streamingBlocks.length === 0}
        <div class="flex items-center justify-center h-full text-zinc-500">
            <p>Start a conversation</p>
        </div>
    {/if}
</div>
