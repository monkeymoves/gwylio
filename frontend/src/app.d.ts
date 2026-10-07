// See https://svelte.dev/docs/kit/types#app.d.ts for what belongs here.
declare global {
	interface ImportMetaEnv {
		/** Read API base, such as http://localhost:8000/api/v1; unset reads the snapshot. */
		readonly PUBLIC_GWYLIO_API_BASE?: string;
		/** Salted SHA-256 of the site password (`make site-password`); unset turns the screen off. */
		readonly PUBLIC_GWYLIO_SITE_PASSWORD_SHA256?: string;
	}

	namespace App {
		// interface Error {}
		// interface Locals {}
		// interface PageData {}
		// interface PageState {}
		// interface Platform {}
	}
}

export {};
