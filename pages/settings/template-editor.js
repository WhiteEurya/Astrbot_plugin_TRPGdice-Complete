import {EditorState} from "@codemirror/state";
import {Decoration, EditorView, ViewPlugin, keymap} from "@codemirror/view";
import {defaultKeymap, history, historyKeymap, isolateHistory} from "@codemirror/commands";

export function insertTemplateVariable(view, token) {
  view.dispatch({...view.state.replaceSelection(token), scrollIntoView: true,
    userEvent: "input", annotations: isolateHistory.of("full")});
  view.focus();
}

export function templateVariables(text) {
  // Escaped braces are literals in Python's str.format, not template variables.
  const pattern = /\{\{|\}\}|\{[A-Za-z_]\w*(?:\.[A-Za-z_]\w*|\[[^\]{}\n]+\])*(?:![rsa])?(?::[^{}\n]*)?\}/g;
  return [...text.matchAll(pattern)]
    .filter((match) => match[0] !== "{{" && match[0] !== "}}")
    .map((match) => ({from: match.index, to: match.index + match[0].length, text: match[0]}));
}

function decorations(view) {
  return Decoration.set(templateVariables(view.state.doc.toString()).map((variable) =>
    Decoration.mark({class: "template-variable", attributes: {title: `变量：${variable.text}`}})
      .range(variable.from, variable.to)));
}

const variableHighlight = ViewPlugin.fromClass(class {
  constructor(view) { this.decorations = decorations(view); }
  update(update) { if (update.docChanged) this.decorations = decorations(update.view); }
}, {decorations: (plugin) => plugin.decorations});

export function createTemplateEditor(parent, value, id, onChange) {
  const wrapper = document.createElement("div");
  wrapper.className = "template-editor";
  wrapper.style.height = `${Math.min(16, Math.max(3, value.split("\n").length)) * 23 + 22}px`;
  parent.append(wrapper);
  return new EditorView({
    parent: wrapper,
    state: EditorState.create({
      doc: value,
      extensions: [history(), keymap.of([...defaultKeymap, ...historyKeymap]),
        EditorView.lineWrapping, variableHighlight,
        EditorView.contentAttributes.of({id, "aria-labelledby": `${id}-label`, spellcheck: "false"}),
        EditorView.updateListener.of((update) => {
          if (update.docChanged) onChange(update.state.doc.toString());
        })],
    }),
  });
}
