<script lang="ts">
    import { marked } from 'marked';
    import hljs from 'highlight.js';
    import 'highlight.js/styles/github-dark.css';
    import type { Message } from './api';

    let {
        messages = [],
        streamingContent = '',
    }: {
        messages?: Message[];
        streamingContent?: string;
    } = $props();

    let chatContainer: HTMLDivElement | undefined = $state();

    // Use a custom renderer to apply highlight.js to fenced code blocks
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

    $effect(() => {
        // Re-run whenever messages or streamingContent changes so the view scrolls to bottom
        void messages.length;
        void streamingContent;
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
                <div class="prose dark:prose-invert prose-sm max-w-none">
                    {@html renderMarkdown(msg.content)}
                </div>
            {/if}
        </div>
    {/each}

    {#if streamingContent}
        <div class="max-w-3xl mx-auto">
            <div class="prose prose-invert prose-sm max-w-none">
                {@html renderMarkdown(streamingContent)}
            </div>
        </div>
    {/if}

    {#if messages.length === 0 && !streamingContent}
        <div class="flex items-center justify-center h-full text-zinc-500">
            <p>Start a conversation</p>
        </div>
    {/if}
</div>
