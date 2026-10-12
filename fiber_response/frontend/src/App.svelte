<script lang="ts">
	import { onMount } from 'svelte';

	type FilesResponse = {
		data_dir: string;
		files: string[];
	};
	type FiberInfo = {
		fibers: number;
		groups: number;
		active_sites: number;
	};

	let data = $state<FilesResponse | null>(null);
	let selected_file = $state<string>('');
	let plotUrl = $state<string | null>(null);
	let expInfo = $state<FiberInfo | null>(null);
	let loading = $state(false);
	let error = $state<string | null>(null);

	function fileName(path: string) {
		return path.split('/').pop() ?? path;
	}

	async function loadFiles() {
		const response = await fetch('/io/files');
		data = await response.json();
		if (!selected_file) selected_file = data?.files[0] ?? '';
	}
	onMount(loadFiles);

	async function handleUpload(e: Event) {
		const input = e.currentTarget as HTMLInputElement;
		if (!input.files?.length) return;

		const formData = new FormData();
		for (const file of input.files) {
			formData.append('files', file); // key must match the FastAPI parameter name
		}

		try {
			const response = await fetch('/io/upload', {
				method: 'POST',
				body: formData // no Content-Type header: the browser sets it
			});
			if (!response.ok) throw new Error(`Upload failed: HTTP ${response.status}`);
			await loadFiles(); // refresh the list with the new files
		} catch (err) {
			error = err instanceof Error ? err.message : String(err);
		} finally {
			input.value = ''; // allow re-selecting the same files later
		}
	}

	async function deleteFile(file: string) {
		if (!confirm(`Delete ${fileName(file)}?`)) return;
		error = null;
		try {
			const response = await fetch(
				'/io/file?' + new URLSearchParams({ filename: file }),
				{ method: 'DELETE' }
			);
			if (!response.ok) throw new Error(`Delete failed: HTTP ${response.status}`);
			if (selected_file === file) selected_file = ''; // loadFiles picks a new default
			await loadFiles();
		} catch (err) {
			error = err instanceof Error ? err.message : String(err);
		}
	}

	async function handleSubmit(e: SubmitEvent) {
		e.preventDefault();
		if (!selected_file) return;

		loading = true;
		error = null;
		expInfo = null;
		try {
			// 1. run the experiment loading
			const run = await fetch(
				'/exp/experiment?' + new URLSearchParams({ filename: selected_file }),
				{ method: 'POST' }
			);
			if (!run.ok) throw new Error(`Experiment failed: HTTP ${run.status}`);

			// 2. fetch the plot (only reached if step 1 succeeded)
			const plot = await fetch('/exp/plot');
			if (!plot.ok) throw new Error(`Plot failed: HTTP ${plot.status}`);

			const blob = await plot.blob();
			if (plotUrl) URL.revokeObjectURL(plotUrl); // free the previous image
			plotUrl = URL.createObjectURL(blob);

			// 3. fetch experiment info
			const response = await fetch('/exp/experiment/');
			if (!response.ok) throw new Error(`Info failed: HTTP ${response.status}`);
			expInfo = await response.json();
		} catch (err) {
			error = err instanceof Error ? err.message : String(err);
		} finally {
			loading = false;
		}
	}
</script>

{#if data}
	<form class="card" onsubmit={handleSubmit}>
		<header>
			<h3>Files</h3>
			<small>{data.data_dir}</small>
		</header>

		{#if data.files.length}
			<ul class="file-list">
				{#each data.files as file (file)}
					<li class:selected={file === selected_file}>
						<button
							type="button"
							class="file-btn"
							aria-pressed={file === selected_file}
							title={file}
							onclick={() => (selected_file = file)}
						>
							{fileName(file)}
						</button>
						<button
							type="button"
							class="delete-btn"
							aria-label={`Delete ${fileName(file)}`}
							onclick={() => deleteFile(file)}
						>
							✕
						</button>
					</li>
				{/each}
			</ul>
		{:else}
			<p class="empty">No files yet. Upload some below.</p>
		{/if}

		<button type="submit" class="run-btn" disabled={loading || !selected_file}>
			{loading ? 'Loading...' : 'Load experiment info'}
		</button>
	</form>
{/if}

<div class="upload">
	<label for="multi_upload">Upload experiment files:</label>
	<input id="multi_upload" type="file" multiple onchange={handleUpload} />
</div>

{#if error}
	<p class="error">{error}</p>
{/if}

{#if expInfo || plotUrl}
	<div class="results">
		{#if expInfo}
			<h3>Experiment information</h3>
			<dl>
				<dt>Fibers</dt>
				<dd>{expInfo.fibers}</dd>
				<dt>Clusters</dt>
				<dd>{expInfo.groups}</dd>
				<dt>Active sites</dt>
				<dd>{expInfo.active_sites}</dd>
			</dl>
		{/if}

		{#if plotUrl}
			<img src={plotUrl} alt="Experiment plot" />
		{/if}
	</div>
{/if}

<style>
	/* Files card */
	.card {
		width: min(50%, 800px);
		margin: 1.5rem auto;
		padding: 1rem 1.25rem;
		border: 1px solid rgba(128, 128, 128, 0.35);
		border-radius: 10px;
	}
	.card header {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 1rem;
		margin-bottom: 0.75rem;
	}
	.card h3 {
		margin: 0;
	}
	.card small {
		opacity: 0.6;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.file-list {
		list-style: none;
		margin: 0 0 1rem;
		padding: 0;
		max-height: 16rem;
		overflow-y: auto;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}
	.file-list li {
		display: flex;
		align-items: center;
		border: 1px solid rgba(128, 128, 128, 0.35);
		border-radius: 8px;
	}
	.file-list li:hover {
		background: rgba(128, 128, 128, 0.12);
	}
	.file-list li.selected {
		border-color: #3b82f6;
		background: rgba(59, 130, 246, 0.15);
	}
	.file-btn {
		flex: 1;
		text-align: left;
		padding: 0.5rem 0.75rem;
		background: none;
		border: none;
		color: inherit;
		font: inherit;
		cursor: pointer;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.delete-btn {
		padding: 0.5rem 0.75rem;
		background: none;
		border: none;
		color: inherit;
		opacity: 0.5;
		cursor: pointer;
	}
	.delete-btn:hover {
		opacity: 1;
		color: #ef4444;
	}
	.run-btn {
		width: 100%;
		padding: 0.5rem;
		cursor: pointer;
	}
	.empty {
		opacity: 0.6;
	}

	/* Upload + error */
	.upload {
		width: min(50%, 800px);
		margin: 0 auto 1rem;
	}
	.error {
		width: min(50%, 800px);
		margin: 0 auto 1rem;
		color: #ef4444;
	}

	/* Results */
	.results {
		width: min(50%, 800px);
		margin: 1.5rem auto;
	}
	dl {
		display: grid;
		grid-template-columns: max-content 1fr;
		gap: 0.25rem 1rem;
		margin: 0 0 1rem;
	}
	dt {
		font-weight: 600;
	}
	dd {
		margin: 0;
	}
	img {
		display: block;
		width: 100%;
	}
</style>
