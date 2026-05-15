import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

export default {
	kit: {
		adapter: adapter({
			pages: '../static',
			assets: '../static',
			fallback: 'index.html',
		}),
	},
	preprocess: vitePreprocess(),
};
