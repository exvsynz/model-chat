const BASE = 'http://127.0.0.1:8000';

export interface ModelsResponse {
    aliases: Record<string, string>;
    default: string;
}

export interface ConversationSummary {
    id: string;
    model: string;
    persona: string;
    title: string;
    created_at: string;
    updated_at: string;
    message_count: number;
}

export interface Message {
    role: 'user' | 'assistant' | 'system';
    content: string;
}

export interface OpenRouterModel {
    id: string;
    name: string;
}

export async function fetchModels(): Promise<ModelsResponse> {
    const res = await fetch(`${BASE}/api/models`);
    return res.json();
}

export async function fetchAllModels(): Promise<OpenRouterModel[]> {
    const res = await fetch(`${BASE}/api/models/all`);
    return res.json();
}

export async function fetchPersonas(): Promise<string[]> {
    const res = await fetch(`${BASE}/api/personas`);
    return res.json();
}

export async function fetchConversations(): Promise<ConversationSummary[]> {
    const res = await fetch(`${BASE}/api/conversations`);
    return res.json();
}

export async function loadConversation(id: string): Promise<{ messages: Message[]; model: string; persona: string }> {
    const res = await fetch(`${BASE}/api/conversations/${id}`);
    return res.json();
}

export async function saveConversation(convo: {
    id: string;
    model: string;
    persona: string | null;
    title: string | null;
    created_at: string;
    updated_at: string;
    messages: Message[];
}): Promise<void> {
    await fetch(`${BASE}/api/conversations/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(convo),
    });
}

export async function deleteConversation(id: string): Promise<void> {
    await fetch(`${BASE}/api/conversations/${id}`, { method: 'DELETE' });
}

export async function* streamChat(
    messages: Message[],
    model: string,
    persona: string | null,
    effort: string | null,
): AsyncGenerator<string, void> {
    const res = await fetch(`${BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages, model, persona, effort }),
    });

    if (!res.ok || !res.body) {
        throw new Error(`Chat request failed: ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
            if (line.startsWith('data: ')) {
                const payload = JSON.parse(line.slice(6));
                if (payload.done) return;
                if (payload.token) yield payload.token;
            }
        }
    }
}
