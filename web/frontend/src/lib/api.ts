const BASE = `${window.location.origin}`;

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

export interface ToolCallBlock {
	id: string;
	name: string;
	arguments: Record<string, unknown>;
	status: 'running' | 'success' | 'error';
	output?: string;
	is_error?: boolean;
}

export type ContentBlock =
	| { type: 'text'; content: string }
	| { type: 'tool_call'; block: ToolCallBlock };

export interface UsageStats {
	prompt_tokens: number;
	completion_tokens: number;
	total_tokens: number;
	elapsed_seconds: number;
}

export interface Message {
	role: 'user' | 'assistant' | 'system';
	content: string;
	blocks?: ContentBlock[];
	usage?: UsageStats | null;
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

export async function loadConversation(
	id: string,
): Promise<{ messages: Message[]; model: string; persona: string }> {
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

export interface Memory {
	file: string;
	summary: string;
}

export async function fetchMemories(): Promise<Memory[]> {
	const res = await fetch(`${BASE}/api/memories`);
	return res.json();
}

export async function addMemory(
	content: string,
	type: string = 'fact',
): Promise<{ status: string; file: string | null }> {
	const res = await fetch(`${BASE}/api/memories`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ content, type }),
	});
	return res.json();
}

export async function deleteMemory(slug: string): Promise<void> {
	await fetch(`${BASE}/api/memories/${slug}`, { method: 'DELETE' });
}

export type ChatEvent =
	| { type: 'text'; content: string }
	| { type: 'tool_call'; id: string; name: string; arguments: Record<string, unknown> }
	| { type: 'tool_result'; id: string; name: string; output: string; is_error: boolean }
	| {
			type: 'permission_request';
			request_id: string;
			tool_name: string;
			arguments: Record<string, unknown>;
	  }
	| {
			type: 'done';
			usage: {
				prompt_tokens: number;
				completion_tokens: number;
				total_tokens: number;
				elapsed_seconds: number;
			} | null;
	  };

export async function respondToPermission(requestId: string, approved: boolean): Promise<void> {
	await fetch(`${BASE}/api/chat/permission/${requestId}`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ approved }),
	});
}

export async function* streamChat(
	messages: Message[],
	model: string,
	persona: string | null,
	effort: string | null,
): AsyncGenerator<ChatEvent, void> {
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
				if (payload.type === 'done') {
					yield payload as ChatEvent;
					return;
				}
				if (payload.type) {
					yield payload as ChatEvent;
				}
			}
		}
	}
}
