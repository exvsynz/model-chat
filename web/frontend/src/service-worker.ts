/// <reference types="@sveltejs/kit" />
/// <reference no-default-lib="true"/>
/// <reference lib="esnext" />
/// <reference lib="webworker" />

import { build, files, version } from '$service-worker';

const CACHE = `cache-${version}`;
const ASSETS = [...build, ...files];

self.addEventListener('install', (event: ExtendableEvent) => {
	event.waitUntil(
		caches
			.open(CACHE)
			.then((cache) => cache.addAll(ASSETS))
			.then(() => {
				(self as unknown as ServiceWorkerGlobalScope).skipWaiting();
			}),
	);
});

self.addEventListener('activate', (event: ExtendableEvent) => {
	event.waitUntil(
		caches.keys().then(async (keys) => {
			for (const key of keys) {
				if (key !== CACHE) await caches.delete(key);
			}
			(self as unknown as ServiceWorkerGlobalScope).clients.claim();
		}),
	);
});

self.addEventListener('fetch', (event: FetchEvent) => {
	if (event.request.method !== 'GET') return;

	const url = new URL(event.request.url);

	// Don't cache API calls or external requests
	if (url.origin !== location.origin) return;
	if (url.pathname.startsWith('/api/')) return;

	event.respondWith(
		(async () => {
			const cachedResponse = await caches.match(event.request);
			if (cachedResponse) return cachedResponse;

			try {
				const response = await fetch(event.request);
				if (response.status === 200) {
					const cache = await caches.open(CACHE);
					cache.put(event.request, response.clone());
				}
				return response;
			} catch {
				// If offline and not cached, just let it fail
				return new Response('Offline', { status: 503 });
			}
		})(),
	);
});
