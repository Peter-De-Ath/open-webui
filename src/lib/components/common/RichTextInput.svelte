<script lang="ts">
	import { marked } from 'marked';
	import TurndownService from 'turndown';
	const turndownService = new TurndownService({
		codeBlockStyle: 'fenced',
		headingStyle: 'atx'
	});
	turndownService.escape = (string) => string;

	import { onMount, onDestroy, tick } from 'svelte';
	import { createEventDispatcher } from 'svelte';
	const eventDispatch = createEventDispatcher();

	import { EditorState, Plugin, PluginKey, TextSelection } from 'prosemirror-state';
	import { Decoration, DecorationSet } from 'prosemirror-view';

	import { Editor } from '@tiptap/core';

	import { AIAutocompletion } from './RichTextInput/AutoCompletion.js';

	import CodeBlockLowlight from '@tiptap/extension-code-block-lowlight';
	import Placeholder from '@tiptap/extension-placeholder';
	import Highlight from '@tiptap/extension-highlight';
	import Typography from '@tiptap/extension-typography';
	import StarterKit from '@tiptap/starter-kit';
	import { all, createLowlight } from 'lowlight';

	import { PASTED_TEXT_CHARACTER_LIMIT } from '$lib/constants';

	export let oncompositionstart = (e) => {};
	export let oncompositionend = (e) => {};
	export let onChange = (e) => {};

	// create a lowlight instance with all languages loaded
	const lowlight = createLowlight(all);

	export let className = 'input-prose';
	export let placeholder = 'Type here...';

	export let id = '';
	export let value = '';
	export let html = '';

	export let json = false;
	export let raw = false;
	export let editable = true;

	export let preserveBreaks = false;
	export let generateAutoCompletion: Function = async () => null;
	export let autocomplete = false;
	export let messageInput = false;
	export let shiftEnter = false;
	export let largeTextAsFile = false;

	let element;
	let editor;

	// State for floating button
	let showFloatingButton = false;
	let floatingButtonTop = 0;
	let floatingButtonLeft = 0;
	let floatingButtonElement; // Reference to the button element itself

	const options = {
		throwOnError: false
	};

	$: if (editor) {
		editor.setOptions({
			editable: editable
		});
		// Close button if editor becomes non-editable
		if (!editable) {
			closeFloatingButton();
		}
	}

	$: if (value === null && html !== null && editor) {
		editor.commands.setContent(html);
	}

	// Function to find the next template in the document
	function findNextTemplate(doc, from = 0) {
		const patterns = [{ start: '{{', end: '}}' }];

		let result = null;

		doc.nodesBetween(from, doc.content.size, (node, pos) => {
			if (result) return false; // Stop if we've found a match
			if (node.isText) {
				const text = node.text;
				let index = Math.max(0, from - pos);
				while (index < text.length) {
					for (const pattern of patterns) {
						if (text.startsWith(pattern.start, index)) {
							const endIndex = text.indexOf(pattern.end, index + pattern.start.length);
							if (endIndex !== -1) {
								result = {
									from: pos + index,
									to: pos + endIndex + pattern.end.length
								};
								return false; // Stop searching
							}
						}
					}
					index++;
				}
			}
		});

		return result;
	}

	// Function to select the next template in the document
	function selectNextTemplate(state, dispatch) {
		const { doc, selection } = state;
		const from = selection.to;
		let template = findNextTemplate(doc, from);

		if (!template) {
			// If not found, search from the beginning
			template = findNextTemplate(doc, 0);
		}

		if (template) {
			if (dispatch) {
				const tr = state.tr.setSelection(TextSelection.create(doc, template.from, template.to));
				dispatch(tr);
			}
			return true;
		}
		return false;
	}

	export const setContent = (content) => {
		editor.commands.setContent(content);
	};

	export const replaceSelection = (newText) => {
		if (editor && editor.state.selection && !editor.state.selection.empty) {
			// Use insertContentAt to replace the selection range
			const { from, to } = editor.state.selection;
			editor.chain().focus().insertContentAt({ from, to }, newText).run();
		}
		closeFloatingButton();
	};

	// Add method to get selected text
	export const getSelectedText = () => {
		if (!editor || !editor.state.selection || editor.state.selection.empty) {
			return '';
		}
		const { from, to } = editor.state.selection;
		return editor.state.doc.textBetween(from, to);
	};

	const selectTemplate = () => {
		if (value !== '') {
			// After updating the state, try to find and select the next template
			setTimeout(() => {
				const templateFound = selectNextTemplate(editor.view.state, editor.view.dispatch);
				if (!templateFound) {
					// If no template found, set cursor at the end
					const endPos = editor.view.state.doc.content.size;
					editor.view.dispatch(
						editor.view.state.tr.setSelection(TextSelection.create(editor.view.state.doc, endPos))
					);
				}
			}, 0);
		}
	};

	// --- Floating Button Logic ---
	const updateButtonPosition = (event) => {
		// Check if the click is outside the editor and the button itself
		if (
			!element?.contains(event.target) &&
			!floatingButtonElement?.contains(event.target)
		) {
			closeFloatingButton();
			return;
		}

		// Use timeout to allow selection to finalize
		setTimeout(async () => {
			await tick(); // Ensure DOM updates are processed

			// Double-check if the event target is still within the editor after the tick
			if (!element?.contains(event.target)) {
				// If the final click/mouseup was outside, ensure button is closed
				 // Allow clicking the button itself
				if (!floatingButtonElement?.contains(event.target)) {
					closeFloatingButton();
				}
				return;
			}

			let selection = window.getSelection();

			if (selection && selection.toString().trim().length > 0 && editable) {
				const range = selection.getRangeAt(0);
				const rect = range.getBoundingClientRect();
				const parentRect = element.getBoundingClientRect();

				// Calculate position relative to the editor element's viewport
				const top = rect.bottom - parentRect.top + element.scrollTop;
				let left = rect.left - parentRect.left + element.scrollLeft;

				floatingButtonTop = top;
				floatingButtonLeft = left;
				showFloatingButton = true;

				// Adjust position if button goes off-screen
				await tick(); // Wait for button to render to get its dimensions
				if (floatingButtonElement) {
					const buttonRect = floatingButtonElement.getBoundingClientRect();
					const editorVisibleWidth = element.clientWidth; // Use clientWidth for visible area

					if (left + buttonRect.width > editorVisibleWidth + element.scrollLeft) {
						// If button goes off the right edge, align its right edge with the editor's right edge
						floatingButtonLeft = editorVisibleWidth + element.scrollLeft - buttonRect.width - 5; // Adjust with padding
					}
					if (floatingButtonLeft < element.scrollLeft) {
						// If button goes off the left edge, align its left edge
						floatingButtonLeft = element.scrollLeft + 5;
					}
				}

			} else {
				// Only close if the click wasn't on the button itself
				if (!floatingButtonElement?.contains(event.target)) {
					closeFloatingButton();
				}
			}
		}, 0);
	};

	const closeFloatingButton = () => {
		showFloatingButton = false;
	};

	const handleInlineEditClick = () => {
		const selectedText = getSelectedText();
		if (selectedText) {
			eventDispatch('inline-edit', { content: selectedText });
		}
		// Don't close immediately, let the parent component handle it or replacement
		// closeFloatingButton();
	};

	const keydownHandler = (e) => {
		if (e.key === 'Escape') {
			closeFloatingButton();
		}
	};


	onMount(async () => {
		let content = value;

		if (!json) {
			if (preserveBreaks) {
				turndownService.addRule('preserveBreaks', {
					filter: 'br', // Target <br> elements
					replacement: function (content) {
						return '<br/>';
					}
				});
			}

			if (!raw) {
				async function tryParse(value, attempts = 3, interval = 100) {
					try {
						// Try parsing the value
						return marked.parse(value.replaceAll(`\n<br/>`, `<br/>`), {
							breaks: false
						});
					} catch (error) {
						// If no attempts remain, fallback to plain text
						if (attempts <= 1) {
							return value;
						}
						// Wait for the interval, then retry
						await new Promise((resolve) => setTimeout(resolve, interval));
						return tryParse(value, attempts - 1, interval); // Recursive call
					}
				}

				// Usage example
				content = await tryParse(value);
			}
		} else {
			if (html && !content) {
				content = html;
			}
		}

		console.log('content', content);

		editor = new Editor({
			element: element,
			extensions: [
				StarterKit,
				CodeBlockLowlight.configure({
					lowlight
				}),
				Highlight,
				Typography,
				Placeholder.configure({ placeholder }),
				...(autocomplete
					? [
							AIAutocompletion.configure({
								generateCompletion: async (text) => {
									if (text.trim().length === 0) {
										return null;
									}

									const suggestion = await generateAutoCompletion(text).catch(() => null);
									if (!suggestion || suggestion.trim().length === 0) {
										return null;
									}

									return suggestion;
								}
							})
						]
					: [])
			],
			content: content,
			autofocus: messageInput ? true : false,
			onTransaction: () => {
				// force re-render so `editor.isActive` works as expected
				editor = editor;

				html = editor.getHTML();

				onChange({
					html: editor.getHTML(),
					json: editor.getJSON(),
					md: turndownService.turndown(editor.getHTML())
				});

				if (json) {
					value = editor.getJSON();
				} else {
					if (!raw) {
						let newValue = turndownService
							.turndown(
								editor
									.getHTML()
									.replace(/<p><\/p>/g, '<br/>')
									.replace(/ {2,}/g, (m) => m.replace(/ /g, '\u00a0'))
							)
							.replace(/\u00a0/g, ' ');

						if (!preserveBreaks) {
							newValue = newValue.replace(/<br\/>/g, '');
						}

						if (value !== newValue) {
							value = newValue;

							// check if the node is paragraph as well
							if (editor.isActive('paragraph')) {
								if (value === '') {
									editor.commands.clearContent();
								}
							}
						}
					} else {
						value = editor.getHTML();
					}
				}
			},
			editorProps: {
				attributes: { id },
				handleDOMEvents: {
					compositionstart: (view, event) => {
						oncompositionstart(event);
						return false;
					},
					compositionend: (view, event) => {
						oncompositionend(event);
						return false;
					},
					focus: (view, event) => {
						eventDispatch('focus', { event });
						return false;
					},
					blur: (view, event) => {
						// Delay closing to allow clicking the button
						setTimeout(() => {
							// Check if the newly focused element is the button itself
							if (document.activeElement !== floatingButtonElement) {
								closeFloatingButton();
							}
						}, 200);
						return false;
					},
					keyup: (view, event) => {
						eventDispatch('keyup', { event });
						return false;
					},
					keydown: (view, event) => {
						if (messageInput) {
							// Handle Tab Key
							if (event.key === 'Tab') {
								const handled = selectNextTemplate(view.state, view.dispatch);
								if (handled) {
									event.preventDefault();
									return true;
								}
							}

							if (event.key === 'Enter') {
								// Check if the current selection is inside a structured block (like codeBlock or list)
								const { state } = view;
								const { $head } = state.selection;

								// Recursive function to check ancestors for specific node types
								function isInside(nodeTypes: string[]): boolean {
									let currentNode = $head;
									while (currentNode) {
										if (nodeTypes.includes(currentNode.parent.type.name)) {
											return true;
										}
										if (!currentNode.depth) break; // Stop if we reach the top
										currentNode = state.doc.resolve(currentNode.before()); // Move to the parent node
									}
									return false;
								}

								const isInCodeBlock = isInside(['codeBlock']);
								const isInList = isInside(['listItem', 'bulletList', 'orderedList']);
								const isInHeading = isInside(['heading']);

								if (isInCodeBlock || isInList || isInHeading) {
									// Let ProseMirror handle the normal Enter behavior
									return false;
								}
							}

							// Handle shift + Enter for a line break
							if (shiftEnter) {
								if (event.key === 'Enter' && event.shiftKey && !event.ctrlKey && !event.metaKey) {
									editor.commands.setHardBreak(); // Insert a hard break
									view.dispatch(view.state.tr.scrollIntoView()); // Move viewport to the cursor
									event.preventDefault();
									return true;
								}
							}
						}
						// Handle Escape key globally via document listener now
						// if (event.key === 'Escape') {
						// 	closeFloatingButton();
						// }
						eventDispatch('keydown', { event });
						return false;
					},
					paste: (view, event) => {
						if (event.clipboardData) {
							// Extract plain text from clipboard and paste it without formatting
							const plainText = event.clipboardData.getData('text/plain');
							if (plainText) {
								if (largeTextAsFile) {
									if (plainText.length > PASTED_TEXT_CHARACTER_LIMIT) {
										// Dispatch paste event to parent component
										eventDispatch('paste', { event });
										event.preventDefault();
										return true;
									}
								}
								return false;
							}

							// Check if the pasted content contains image files
							const hasImageFile = Array.from(event.clipboardData.files).some((file) =>
								file.type.startsWith('image/')
							);

							// Check for image in dataTransfer items (for cases where files are not available)
							const hasImageItem = Array.from(event.clipboardData.items).some((item) =>
								item.type.startsWith('image/')
							);
							if (hasImageFile) {
								// If there's an image, dispatch the event to the parent
								eventDispatch('paste', { event });
								event.preventDefault();
								return true;
							}

							if (hasImageItem) {
								// If there's an image item, dispatch the event to the parent
								eventDispatch('paste', { event });
								event.preventDefault();
								return true;
							}
						}

						// For all other cases (text, formatted text, etc.), let ProseMirror handle it
						view.dispatch(view.state.tr.scrollIntoView()); // Move viewport to the cursor after pasting
						return false;
					}
				}
			}
		});

		if (messageInput) {
			selectTemplate();
		}

		// Add event listeners for floating button, I don't like this (should be more svelte-ish)
		element?.addEventListener('mouseup', updateButtonPosition);
		document.addEventListener('mouseup', updateButtonPosition); // Listen globally to close if clicked outside
		document.addEventListener('keydown', keydownHandler); // Listen for Escape key
	});

	onDestroy(() => {
		if (editor) {
			editor.destroy();
		}
		// Remove event listeners, still don't like this
		element?.removeEventListener('mouseup', updateButtonPosition);
		document.removeEventListener('mouseup', updateButtonPosition);
		document.removeEventListener('keydown', keydownHandler);
	});

	$: if (value !== null && editor) {
		onValueChange();
	}

	const onValueChange = () => {
		if (!editor) return;

		if (json) {
			if (JSON.stringify(value) !== JSON.stringify(editor.getJSON())) {
				editor.commands.setContent(value);
				selectTemplate();
			}
		} else {
			if (raw) {
				if (value !== editor.getHTML()) {
					editor.commands.setContent(value);
					selectTemplate();
				}
			} else {
				if (
					value !==
					turndownService
						.turndown(
							(preserveBreaks
								? editor.getHTML().replace(/<p><\/p>/g, '<br/>')
								: editor.getHTML()
							).replace(/ {2,}/g, (m) => m.replace(/ /g, '\u00a0'))
						)
						.replace(/\u00a0/g, ' ')
				) {
					preserveBreaks
						? editor.commands.setContent(value)
						: editor.commands.setContent(
								marked.parse(value.replaceAll(`\n<br/>`, `<br/>`), {
									breaks: false
								})
							); // Update editor content

					selectTemplate();
				}
			}
		}
	};
</script>

<div bind:this={element} class="relative w-full min-w-full h-full min-h-fit {className}">
	{#if showFloatingButton && editable}
		<div class="absolute flex flex-row gap-0.5 shrink-0 p-1 bg-white dark:bg-gray-850 dark:text-gray-100 text-medium rounded-lg shadow-xl" style="top: {floatingButtonTop}px; left: {floatingButtonLeft}px;">
			<button
				bind:this={floatingButtonElement}
				class="px-1 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-sm flex items-center gap-1 min-w-fit"
				style="top: {floatingButtonTop}px; left: {floatingButtonLeft}px;"
				on:click={handleInlineEditClick}
				on:mousedown|stopPropagation={() => {}}
			>
				Inline Edit
			</button>
		</div>
	{/if}
</div>
