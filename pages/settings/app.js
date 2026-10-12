import {createElement, CircleHelp, RotateCcw, RefreshCw, Save, Search} from "lucide";
import {createTemplateEditor, insertTemplateVariable, templateVariables} from "./template-editor.js";

const $ = (id) => document.getElementById(id);
const bridge = window.AstrBotPluginView || window.AstrBotPluginPage;
let snapshot, fields = [], selected = "basic", busy = false;
const drafts = new Map();
const editors = [];
const icons = {"circle-help": CircleHelp, "rotate-ccw": RotateCcw,
  "refresh-cw": RefreshCw, save: Save, search: Search};

function iconElement(name) {
  return createElement(icons[name], {width: 17, height: 17, "aria-hidden": "true"});
}

for (const node of document.querySelectorAll("[data-icon]")) {
  node.replaceWith(iconElement(node.dataset.icon));
}

function at(object, path) {
  return path.reduce((value, key) => value && typeof value === "object" ? value[key] : undefined, object);
}

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function iconButton(icon, title, action) {
  const button = element("button", undefined, "icon-button");
  button.type = "button";
  button.title = title;
  button.setAttribute("aria-label", title);
  button.append(iconElement(icon));
  button.addEventListener("click", action);
  return button;
}

function flatten(schema, path = [], labels = []) {
  const result = [];
  for (const [key, meta] of Object.entries(schema)) {
    if (meta.invisible) continue;
    const next = [...path, key], names = [...labels, meta.description || key];
    if (meta.type === "object") result.push(...flatten(meta.items, next, names));
    else {
      const output = next[0] === "output";
      const inherited = output ? at(snapshot.inherited_output, next.slice(1)) ?? "" : meta.default;
      const stored = at(snapshot.config, next);
      const value = output ? (stored || inherited) : stored ?? meta.default;
      result.push({path: next, key: next.join("."), meta, inherited, value,
        custom: output && typeof stored === "string" && stored !== "",
        category: output ? next[1] : "basic", categoryLabel: output ? names[1] : "基本设置",
        label: names.at(-1), section: names.slice(output ? 2 : 0, -1).join(" / ")});
    }
  }
  return result;
}

function matches(field, query) {
  return [field.key, field.label, field.categoryLabel, field.section, field.value].join(" ").toLowerCase().includes(query);
}

function updateState() {
  $("save-state").textContent = busy ? "正在保存" : drafts.size ? `${drafts.size} 项未保存` : "已同步";
  $("save").disabled = busy || !drafts.size;
  $("reload").disabled = busy || !snapshot;
}

function render() {
  for (const editor of editors.splice(0)) editor.destroy();
  const query = $("search").value.trim().toLowerCase();
  const visible = fields.filter((field) => matches(field, query));
  const categories = new Map();
  for (const field of visible) {
    if (!categories.has(field.category)) categories.set(field.category, {label: field.categoryLabel, count: 0});
    categories.get(field.category).count++;
  }
  if (!categories.has(selected)) selected = categories.keys().next().value;
  $("categories").replaceChildren();
  for (const [key, category] of categories) {
    const button = element("button");
    button.append(element("span", category.label), element("span", category.count, "count"));
    button.setAttribute("aria-current", key === selected ? "page" : "false");
    button.addEventListener("click", () => { selected = key; render(); });
    $("categories").append(button);
  }
  $("category-count").textContent = categories.size;
  $("section-title").textContent = categories.get(selected)?.label || "没有匹配的配置";
  $("section-path").textContent = selected === "basic" ? "SETTINGS" : `OUTPUT / ${selected || "SEARCH"}`;
  const current = visible.filter((field) => field.category === selected);
  $("field-count").textContent = `${current.length} 项`;
  $("fields").replaceChildren();
  if (!current.length) $("fields").append(element("p", "没有匹配结果", "empty"));
  for (const field of current) renderField(field);
  $("fields").setAttribute("aria-busy", "false");
  updateState();
}

function renderField(field) {
  const row = element("section", undefined, "field");
  const heading = element("div", undefined, "field-heading");
  const title = element("div");
  const id = `field-${field.key}`;
  const label = element("label", [field.section, field.label].filter(Boolean).join(" / "));
  label.id = `${id}-label`;
  label.htmlFor = id;
  title.append(label, element("div", field.key, "field-path"));
  const actions = element("div", undefined, "field-actions");
  const changed = drafts.has(field.key);
  const source = element("span", changed ? "未保存" : field.custom ? "自定义" : "沿用配置", "source");
  if (changed || field.custom) source.classList.add("custom");
  actions.append(source);
  if (field.meta.hint) actions.append(iconButton("circle-help", `字段说明：${field.label}`, () => {
    $("hint-title").textContent = field.label;
    $("hint-text").textContent = field.meta.hint;
    $("hint-dialog").showModal();
  }));
  actions.append(iconButton("rotate-ccw", field.path[0] === "output" ? "恢复为沿用配置文件" : "恢复默认设置", () => {
    drafts.set(field.key, field.path[0] === "output" ? "" : field.meta.default);
    render();
  }));
  heading.append(title, actions);
  row.append(heading);
  const params = element("div", undefined, "parameters");
  let editor;
  function updateTokens(text) {
    const tokens = [...new Set([field.inherited, text].flatMap((value) =>
      templateVariables(String(value ?? "")).map((variable) => variable.text)))];
    params.replaceChildren(...tokens.map((token) => {
      const button = element("button", undefined, "variable-token");
      button.type = "button";
      button.title = `插入变量 ${token}`;
      button.setAttribute("aria-label", button.title);
      button.append(element("code", token));
      button.addEventListener("mousedown", (event) => event.preventDefault());
      button.addEventListener("click", () => insertTemplateVariable(editor, token));
      return button;
    }));
    params.hidden = !tokens.length;
  }
  function changedValue(value) {
    drafts.set(field.key, value);
    source.textContent = "未保存";
    source.classList.add("custom");
    if (typeof value === "string") updateTokens(value);
    updateState();
  }
  const draft = changed ? drafts.get(field.key) : field.value;
  const value = field.path[0] === "output" && draft === "" ? field.inherited : draft;
  if (field.meta.type === "text") {
    editor = createTemplateEditor(row, String(value ?? ""), id, changedValue);
    editors.push(editor);
    updateTokens(String(value ?? ""));
    row.append(params);
    $("fields").append(row);
    return;
  }
  let input;
  if (field.meta.options) {
    input = element("select");
    for (const option of field.meta.options) {
      const node = element("option", option);
      node.value = option;
      input.append(node);
    }
  } else if (field.meta.type === "bool") {
    input = element("input"); input.type = "checkbox";
  } else if (field.meta.type === "int") {
    input = element("input"); input.type = "number"; input.step = "1";
    if (field.key === "group_post_wait_seconds") { input.min = "1"; input.max = "86400"; }
  } else { input = element("input"); input.type = "text"; }
  input.id = id;
  if (input.type === "checkbox") input.checked = Boolean(value);
  else input.value = value ?? "";
  input.addEventListener("input", () => {
    let value = input.type === "checkbox" ? input.checked : input.value;
    if (field.meta.type === "int") value = input.value === "" ? null : Number(input.value);
    changedValue(value);
  });
  row.append(input);
  $("fields").append(row);
}

function error(message) {
  $("banner").hidden = !message;
  $("banner").textContent = message || "";
}

async function load() {
  try {
    error("");
    const data = await bridge.apiGet("config");
    snapshot = data; drafts.clear(); fields = flatten(data.schema); render();
  } catch (reason) { error(reason.message); }
}

$("search").addEventListener("input", render);
$("reload").addEventListener("click", () => drafts.size ? $("discard-dialog").showModal() : load());
$("cancel-discard").addEventListener("click", () => $("discard-dialog").close());
$("close-hint").addEventListener("click", () => $("hint-dialog").close());
$("confirm-discard").addEventListener("click", () => { $("discard-dialog").close(); load(); });
$("save").addEventListener("click", async () => {
  if (busy || !drafts.size) return;
  busy = true; updateState();
  const submitted = new Map(drafts);
  try {
    error("");
    const changes = [...submitted].map(([key, value]) => ({path: key.split("."), value}));
    snapshot = await bridge.apiPost("config/save", {revision: snapshot.revision, changes});
    for (const [key, value] of submitted) if (drafts.get(key) === value) drafts.delete(key);
    fields = flatten(snapshot.schema); render();
  } catch (reason) { error(reason.message); }
  finally { busy = false; updateState(); }
});
window.addEventListener("beforeunload", (event) => { if (drafts.size) { event.preventDefault(); event.returnValue = ""; } });

async function initialize() {
  try {
    if (!bridge) throw new Error("请从 AstrBot 插件详情页打开配置中心。当前 AstrBot 需支持 Plugin Pages。");
    const context = await bridge.ready();
    const theme = (context) => { document.documentElement.dataset.theme = context.isDark ? "dark" : "light"; };
    theme(context);
    bridge.onContext?.(theme);
    await load();
  } catch (reason) { error(reason.message); $("fields").replaceChildren(); }
}

initialize();
