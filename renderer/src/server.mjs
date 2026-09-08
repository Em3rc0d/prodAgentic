import http from "node:http";
import { chromium } from "@playwright/test";

const PORT = Number.parseInt(process.env.PORT || "4100", 10);
const MAX_BODY_BYTES = 2 * 1024 * 1024;
const RENDERER_NAME = "ChromiumRendererAdapter";
const RENDERER_VERSION = "playwright-1.62.1-chromium-v1";
const ALLOWED_TOP_LEVEL = new Set([
  "schema_version", "contract_version", "render_id", "revision_id", "visual_spec_id",
  "visual_spec_digest", "content_spec_digest", "design_profile_digest", "visual_pattern",
  "format", "canvas_width", "canvas_height", "safe_zone", "theme", "pages", "render_input_digest",
]);

const COLOR_TOKENS = Object.freeze({
  "surface.canvas": "#f4f1ea",
  "surface.paper": "#fffdf8",
  "surface.ink": "#101214",
  "surface.charcoal": "#1b1f23",
  "text.ink": "#17191c",
  "text.on_dark": "#f7f6f2",
  "text.muted": "#626870",
  "text.muted_on_dark": "#b9c0c7",
  "accent.signal": "#1667d9",
  "accent.signal_strong": "#ea4a2a",
  "border.hairline": "#d8d4ca",
  "border.dark_hairline": "#343b42",
});

let browserPromise = null;
function getBrowser() {
  if (!browserPromise) {
    browserPromise = chromium.launch({ headless: true });
  }
  return browserPromise;
}

function fail(message, status = 400) {
  const error = new Error(message);
  error.status = status;
  throw error;
}

function assertExactKeys(value, allowed, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail(`${label} must be an object`);
  for (const key of Object.keys(value)) {
    if (!allowed.has(key)) fail(`${label} contains unsupported field: ${key}`);
  }
}

function validateRequest(value) {
  assertExactKeys(value, ALLOWED_TOP_LEVEL, "RendererRequestV1");
  if (value.schema_version !== 1 || value.contract_version !== "RendererRequestV1@1") fail("unsupported renderer contract");
  if (typeof value.render_id !== "string" || !value.render_id.startsWith("render-")) fail("invalid render_id");
  if (!/^[0-9a-f]{64}$/.test(value.render_input_digest || "")) fail("invalid render_input_digest");
  if (!["single_image", "carousel", "infographic"].includes(value.format)) fail("unsupported render format");
  if (!Number.isInteger(value.canvas_width) || value.canvas_width < 320 || value.canvas_width > 4096) fail("invalid canvas width");
  if (!Number.isInteger(value.canvas_height) || value.canvas_height < 320 || value.canvas_height > 4096) fail("invalid canvas height");
  if (!Array.isArray(value.pages) || value.pages.length < 1 || value.pages.length > 20) fail("invalid page count");
  value.pages.forEach((page, index) => {
    if (page.page_index !== index) fail("page indices must be contiguous");
    if (typeof page.page_id !== "string" || !page.page_id) fail("invalid page_id");
    if (!Array.isArray(page.blocks) || page.blocks.length < 1 || page.blocks.length > 64) fail("invalid page blocks");
  });
  for (const token of [
    value.theme?.background, value.theme?.surface, value.theme?.text,
    value.theme?.muted_text, value.theme?.accent, value.theme?.border,
  ]) {
    if (!Object.hasOwn(COLOR_TOKENS, token)) fail(`unmapped renderer color token: ${token}`);
  }
  return value;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function blockHtml(block, index) {
  const id = escapeHtml(block.block_id);
  if (block.kind === "text") {
    const role = ["headline", "body", "label", "footer", "microcopy"].includes(block.role) ? block.role : "body";
    return `<div class="block text ${role}" data-block-id="${id}">${escapeHtml(block.text)}</div>`;
  }
  if (block.kind === "metric") {
    return `<div class="block metric" data-block-id="${id}">${block.label ? `<span>${escapeHtml(block.label)}</span>` : ""}<strong>${escapeHtml(block.text)}</strong></div>`;
  }
  if (block.kind === "diagram") {
    const items = (block.items || []).map((item, itemIndex) => `<div class="diagram-node"><span>${itemIndex + 1}</span>${escapeHtml(item)}</div>`).join("");
    return `<div class="block diagram" data-block-id="${id}">${items}</div>`;
  }
  if (block.kind === "divider") {
    return `<div class="block divider" data-block-id="${id}"></div>`;
  }
  if (block.kind === "icon") {
    return `<div class="block icon" data-block-id="${id}" aria-hidden="true"><span>✦</span></div>`;
  }
  if (block.kind === "shape") {
    return `<div class="shape-marker" data-block-id="${id}" data-shape="${escapeHtml(block.shape)}" aria-hidden="true"></div>`;
  }
  fail(`unsupported resolved block kind: ${block.kind}`);
}

function htmlForPage(request, page) {
  const colors = {
    background: COLOR_TOKENS[request.theme.background],
    surface: COLOR_TOKENS[request.theme.surface],
    text: COLOR_TOKENS[request.theme.text],
    muted: COLOR_TOKENS[request.theme.muted_text],
    accent: COLOR_TOKENS[request.theme.accent],
    border: COLOR_TOKENS[request.theme.border],
  };
  const radius = request.theme.radius_scale === "soft" ? 40 : request.theme.radius_scale === "sharp" ? 6 : 24;
  const density = request.theme.density;
  const gap = density === "dense" ? 20 : density === "sparse" ? 42 : 30;
  const contentBlocks = page.blocks.filter((block) => block.kind !== "shape").map(blockHtml).join("");
  const layout = escapeHtml(page.layout_family);
  const pageNumber = request.pages.length > 1 ? `${page.page_index + 1} / ${request.pages.length}` : "";
  const safe = request.safe_zone;
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><style>
*{box-sizing:border-box}html,body{margin:0;width:${request.canvas_width}px;height:${request.canvas_height}px;overflow:hidden;background:${colors.background};color:${colors.text};font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased}
body{position:relative}.canvas{position:absolute;inset:0;background:${colors.background};padding:${safe.top}px ${safe.right}px ${safe.bottom}px ${safe.left}px;overflow:hidden}
.frame{position:relative;width:100%;height:100%;background:${colors.surface};border:2px solid ${colors.border};border-radius:${radius}px;padding:${density === "dense" ? 48 : density === "sparse" ? 68 : 58}px;display:flex;flex-direction:column;gap:${gap}px;overflow:hidden;box-shadow:0 22px 80px rgba(0,0,0,.08)}
.frame:before{content:"";position:absolute;left:0;top:0;width:14px;height:100%;background:${colors.accent}}
.kicker{font-size:23px;line-height:1;font-weight:800;letter-spacing:.14em;text-transform:uppercase;color:${colors.accent};padding-left:4px}.content{display:flex;flex:1;min-height:0;flex-direction:column;gap:${gap}px;justify-content:center}.block{position:relative;z-index:2}.text{white-space:pre-wrap;overflow-wrap:anywhere}.headline{font-weight:850;font-size:${density === "dense" ? 62 : density === "sparse" ? 78 : 70}px;line-height:1.02;letter-spacing:-.045em;max-width:900px}.body{font-size:${density === "dense" ? 35 : 39}px;line-height:1.22;font-weight:560;max-width:900px}.label{font-size:24px;line-height:1.12;font-weight:800;text-transform:uppercase;letter-spacing:.09em;color:${colors.accent}}.footer,.microcopy{margin-top:auto;font-size:24px;line-height:1.25;color:${colors.muted};font-weight:650}.divider{height:2px;background:${colors.border};width:100%}.metric{display:grid;gap:8px;padding:24px;border:2px solid ${colors.border};border-radius:${Math.max(8, radius - 8)}px}.metric span{font-size:22px;color:${colors.muted};text-transform:uppercase;letter-spacing:.08em}.metric strong{font-size:66px;line-height:1;color:${colors.accent}}.diagram{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.diagram-node{font-size:27px;line-height:1.2;font-weight:700;border:2px solid ${colors.border};border-radius:${Math.max(8, radius - 8)}px;padding:22px;background:${colors.background}}.diagram-node span{display:inline-grid;place-items:center;width:34px;height:34px;border-radius:50%;background:${colors.accent};color:white;font-size:18px;margin-right:12px}.icon{font-size:52px;color:${colors.accent}}
.meta{display:flex;justify-content:space-between;align-items:center;font-size:22px;line-height:1;color:${colors.muted};font-weight:700;letter-spacing:.04em}.meta .role{text-transform:uppercase;color:${colors.accent}}
.frame.card_grid .content,.frame.evidence_grid .content{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));align-content:center}.frame.card_grid .headline,.frame.evidence_grid .headline{grid-column:1/-1}.frame.card_grid .body,.frame.evidence_grid .body{padding:24px;border:2px solid ${colors.border};border-radius:${Math.max(8, radius - 8)}px;background:${colors.background};font-size:${density === "dense" ? 30 : 34}px}.frame.split_focus .content,.frame.split_evidence .content{display:grid;grid-template-columns:1.18fr .82fr;align-items:center}.frame.split_focus .headline,.frame.split_evidence .headline{grid-column:1/-1}.frame.split_focus .body:nth-of-type(even),.frame.split_evidence .body:nth-of-type(even){padding-left:26px;border-left:5px solid ${colors.accent}}.frame.editorial_poster .headline{font-size:${density === "dense" ? 70 : 88}px;max-width:860px}.frame.hero_stack .content{justify-content:center}.frame.metric_stack .content{justify-content:flex-start}.frame.metric_stack .metric{margin-top:8px}
</style></head><body><main class="canvas"><section class="frame ${layout}" data-page-id="${escapeHtml(page.page_id)}"><div class="kicker">${escapeHtml(request.format.replaceAll("_", " "))}</div><div class="content">${contentBlocks}</div><div class="meta"><span class="role">${escapeHtml(page.role)}</span><span>${escapeHtml(pageNumber)}</span></div></section></main></body></html>`;
}

async function renderPage(browser, request, pageSpec) {
  const context = await browser.newContext({
    viewport: { width: request.canvas_width, height: request.canvas_height },
    deviceScaleFactor: 1,
    colorScheme: "light",
    reducedMotion: "reduce",
  });
  try {
    await context.route("**/*", (route) => route.abort());
    const page = await context.newPage();
    await page.setContent(htmlForPage(request, pageSpec), { waitUntil: "load", timeout: 10_000 });
    await page.evaluate(async () => { if (document.fonts?.ready) await document.fonts.ready; });
    const data = await page.screenshot({ type: "png", fullPage: false, animations: "disabled", caret: "hide" });
    return {
      page_id: pageSpec.page_id,
      page_index: pageSpec.page_index,
      width: request.canvas_width,
      height: request.canvas_height,
      content_type: "image/png",
      data_base64: data.toString("base64"),
    };
  } finally {
    await context.close();
  }
}

async function readJson(req) {
  let size = 0;
  const chunks = [];
  for await (const chunk of req) {
    size += chunk.length;
    if (size > MAX_BODY_BYTES) fail("renderer request body too large", 413);
    chunks.push(chunk);
  }
  if (!chunks.length) fail("renderer request body required");
  try { return JSON.parse(Buffer.concat(chunks).toString("utf8")); }
  catch { fail("renderer request must be valid JSON"); }
}

function json(res, status, payload) {
  const body = Buffer.from(JSON.stringify(payload));
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": body.length,
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
  });
  res.end(body);
}

const server = http.createServer(async (req, res) => {
  try {
    if (req.method === "GET" && req.url === "/health") {
      return json(res, 200, { status: "ok", renderer_name: RENDERER_NAME, renderer_version: RENDERER_VERSION });
    }
    if (req.method !== "POST" || req.url !== "/render") return json(res, 404, { detail: "not found" });
    if (!(req.headers["content-type"] || "").toLowerCase().startsWith("application/json")) fail("application/json required", 415);
    const request = validateRequest(await readJson(req));
    const browser = await getBrowser();
    const pages = [];
    for (const pageSpec of request.pages) pages.push(await renderPage(browser, request, pageSpec));
    return json(res, 200, {
      render_id: request.render_id,
      render_input_digest: request.render_input_digest,
      renderer_name: RENDERER_NAME,
      renderer_version: RENDERER_VERSION,
      pages,
    });
  } catch (error) {
    console.error("[renderer]", error?.message || error);
    return json(res, Number.isInteger(error?.status) ? error.status : 500, { detail: error?.status ? error.message : "render failed" });
  }
});

server.listen(PORT, "0.0.0.0", () => console.log(`[renderer] listening on ${PORT}`));

async function shutdown() {
  server.close();
  if (browserPromise) {
    try { await (await browserPromise).close(); } catch {}
  }
  process.exit(0);
}
process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);
