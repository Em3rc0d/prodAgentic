export type EditorialVisualFormat =
  | "TECHNICAL_DIAGRAM"
  | "ARCHITECTURE_SCHEMATIC"
  | "PROCESS_FLOW"
  | "COMPARISON"
  | "ARTIFACT_BOARD"
  | "EDITORIAL_POSTER";

export interface EditorialSvgResult {
  svg: string;
  width: number;
  height: number;
}

export interface EditorialPngResult extends EditorialSvgResult {
  base64: string;
  sha256: string;
}

const DIMENSIONS: Record<string, [number, number]> = {
  "4:5": [1080, 1350],
  "1:1": [1200, 1200],
  "16:9": [1600, 900],
};

const C = {
  bg: "#090A10",
  surface: "#11131D",
  raised: "#171A27",
  line: "#30364D",
  text: "#F5F7FF",
  muted: "#A8B0CC",
  accent: "#7657FF",
  accentSoft: "#A99BFF",
};

export function escapeXml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function clean(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

function sentenceList(content: string): string[] {
  const normalized = clean(content);
  if (!normalized) return ["Editorial insight"];
  return (normalized.match(/[^.!?]+[.!?]?/g) ?? [normalized])
    .map((part) => part.trim())
    .filter(Boolean)
    .slice(0, 8);
}

function shorten(value: string, max: number): string {
  const normalized = clean(value);
  if (normalized.length <= max) return normalized;
  const head = normalized.slice(0, max - 1).replace(/\s+\S*$/, "").trim();
  return `${head || normalized.slice(0, max - 1)}…`;
}

function wrap(value: string, maxChars: number, maxLines: number): string[] {
  const words = clean(value).split(" ").filter(Boolean);
  const lines: string[] = [];
  let line = "";
  let index = 0;
  while (index < words.length) {
    const word = words[index];
    const candidate = line ? `${line} ${word}` : word;
    if (candidate.length <= maxChars || !line) {
      line = candidate;
      index += 1;
      continue;
    }
    lines.push(line);
    line = "";
    if (lines.length >= maxLines - 1) break;
  }
  if (line && lines.length < maxLines) lines.push(line);
  if (index < words.length && lines.length) {
    lines[lines.length - 1] = `${lines[lines.length - 1].replace(/[.…]+$/, "")}…`;
  }
  return lines.slice(0, maxLines);
}

function text(
  lines: string[],
  x: number,
  y: number,
  size: number,
  lineHeight: number,
  options: { fill?: string; weight?: number; anchor?: "start" | "middle" } = {},
): string {
  const fill = options.fill ?? C.text;
  const weight = options.weight ?? 550;
  const anchor = options.anchor ?? "start";
  return `<text x="${x}" y="${y}" fill="${fill}" font-family="Inter, Arial, sans-serif" font-size="${size}" font-weight="${weight}" text-anchor="${anchor}">${lines
    .map((line, index) => `<tspan x="${x}" dy="${index === 0 ? 0 : lineHeight}">${escapeXml(line)}</tspan>`)
    .join("")}</text>`;
}

function chrome(width: number, height: number, format: EditorialVisualFormat): string {
  const label = format.replace(/_/g, " ");
  return [
    `<rect width="${width}" height="${height}" fill="${C.bg}"/>`,
    `<rect x="48" y="48" width="${width - 96}" height="${height - 96}" rx="34" fill="none" stroke="${C.line}" stroke-width="2"/>`,
    `<circle cx="82" cy="82" r="10" fill="${C.accent}"/>`,
    `<text x="108" y="91" fill="${C.muted}" font-family="Inter, Arial, sans-serif" font-size="21" font-weight="760" letter-spacing="2">prodAgentic · ${label}</text>`,
  ].join("");
}

function card(
  x: number,
  y: number,
  width: number,
  height: number,
  index: number,
  body: string,
  options: { active?: boolean; maxChars?: number; maxLines?: number; size?: number } = {},
): string {
  const active = Boolean(options.active);
  const size = options.size ?? 26;
  const lines = wrap(
    shorten(body, 155),
    options.maxChars ?? Math.max(24, Math.floor(width / 15)),
    options.maxLines ?? 4,
  );
  return [
    `<rect x="${x}" y="${y}" width="${width}" height="${height}" rx="26" fill="${active ? C.raised : C.surface}" stroke="${active ? C.accent : C.line}" stroke-width="${active ? 3 : 2}"/>`,
    `<circle cx="${x + 42}" cy="${y + 44}" r="21" fill="${active ? C.accent : C.raised}" stroke="${C.accent}" stroke-width="2"/>`,
    `<text x="${x + 42}" y="${y + 51}" fill="${C.text}" font-family="Inter, Arial, sans-serif" font-size="18" font-weight="820" text-anchor="middle">0${index + 1}</text>`,
    text(lines, x + 78, y + 49, size, size + 10, { fill: active ? C.text : C.muted, weight: active ? 620 : 540 }),
  ].join("");
}

function poster(content: string, width: number, height: number): string {
  const s = sentenceList(content);
  const headline = wrap(shorten(s[0], 155), width >= 1500 ? 34 : 24, 5);
  const support = wrap(shorten(s[1] ?? s[0], 190), width >= 1500 ? 58 : 42, 4);
  const titleSize = width >= 1500 ? 66 : 60;
  return [
    `<rect x="78" y="${Math.round(height * 0.19)}" width="14" height="${Math.round(height * 0.46)}" rx="7" fill="${C.accent}"/>`,
    text(headline, 128, Math.round(height * 0.28), titleSize, Math.round(titleSize * 1.12), { weight: 780 }),
    `<line x1="128" y1="${Math.round(height * 0.69)}" x2="${width - 128}" y2="${Math.round(height * 0.69)}" stroke="${C.line}" stroke-width="2"/>`,
    text(support, 128, Math.round(height * 0.76), 27, 38, { fill: C.muted, weight: 480 }),
  ].join("");
}

function verticalSequence(content: string, width: number, height: number, architectureMode = false): string {
  const s = sentenceList(content);
  const items = [s[0], s[1] ?? s[0], s[2] ?? s[1] ?? s[0], ...(architectureMode ? [] : [s[3] ?? s[2] ?? s[0]])];
  const x = width <= 1200 ? 112 : 150;
  const top = width <= 1200 ? 180 : 150;
  const cardWidth = width - x * 2;
  const available = height - top - 120;
  const gap = 24;
  const cardHeight = Math.floor((available - gap * (items.length - 1)) / items.length);
  return items.map((item, index) => {
    const y = top + index * (cardHeight + gap);
    const connector = index < items.length - 1
      ? `<line x1="${x + 42}" y1="${y + cardHeight}" x2="${x + 42}" y2="${y + cardHeight + gap}" stroke="${C.accent}" stroke-width="4"/>`
      : "";
    return card(x, y, cardWidth, cardHeight, index, item, {
      active: architectureMode ? index === 1 : index === items.length - 1,
      maxChars: width <= 1200 ? 48 : 72,
      maxLines: 4,
      size: width <= 1200 ? 25 : 27,
    }) + connector;
  }).join("");
}

function architecture(content: string, width: number, height: number): string {
  if (width <= 1200) return verticalSequence(content, width, height, true);
  const s = sentenceList(content);
  const items = [s[0], s[1] ?? s[0], s[2] ?? s[1] ?? s[0]];
  const margin = 92;
  const gap = 40;
  const cardWidth = Math.floor((width - margin * 2 - gap * 2) / 3);
  const cardHeight = Math.min(360, Math.round(height * 0.46));
  const y = Math.round((height - cardHeight) / 2) + 30;
  return items.map((item, index) => {
    const x = margin + index * (cardWidth + gap);
    const connector = index < items.length - 1
      ? `<line x1="${x + cardWidth}" y1="${y + cardHeight / 2}" x2="${x + cardWidth + gap}" y2="${y + cardHeight / 2}" stroke="${C.accent}" stroke-width="4"/>`
      : "";
    return card(x, y, cardWidth, cardHeight, index, item, { active: index === 1, maxChars: 31, maxLines: 6, size: 24 }) + connector;
  }).join("");
}

function comparison(content: string, width: number, height: number): string {
  const s = sentenceList(content);
  const items = [s[0], s[1] ?? s[0]];
  if (width <= 1200) {
    const x = 104;
    const top = 205;
    const gap = 38;
    const cardHeight = Math.floor((height - top - 120 - gap) / 2);
    const cardWidth = width - x * 2;
    return items.map((item, index) => card(x, top + index * (cardHeight + gap), cardWidth, cardHeight, index, item, {
      active: index === 1, maxChars: 47, maxLines: 6, size: 28,
    })).join("") + `<circle cx="${width / 2}" cy="${top + cardHeight + gap / 2}" r="32" fill="${C.accent}"/><text x="${width / 2}" y="${top + cardHeight + gap / 2 + 8}" fill="white" font-family="Inter, Arial, sans-serif" font-size="19" font-weight="820" text-anchor="middle">VS</text>`;
  }
  const margin = 100;
  const gap = 50;
  const cardWidth = (width - margin * 2 - gap) / 2;
  const cardHeight = height - 300;
  const y = 185;
  return card(margin, y, cardWidth, cardHeight, 0, items[0], { maxChars: 43, maxLines: 8, size: 30 })
    + card(margin + cardWidth + gap, y, cardWidth, cardHeight, 1, items[1], { active: true, maxChars: 43, maxLines: 8, size: 30 })
    + `<circle cx="${width / 2}" cy="${y + cardHeight / 2}" r="34" fill="${C.accent}"/><text x="${width / 2}" y="${y + cardHeight / 2 + 8}" fill="white" font-family="Inter, Arial, sans-serif" font-size="20" font-weight="820" text-anchor="middle">VS</text>`;
}

function artifactBoard(content: string, width: number, height: number): string {
  const s = sentenceList(content);
  const items = [s[0], s[1] ?? s[0], s[2] ?? s[1] ?? s[0]];
  const x = width <= 1200 ? 100 : 126;
  const top = width <= 1200 ? 190 : 160;
  const gap = 26;
  const cardWidth = width - x * 2;
  const cardHeight = Math.floor((height - top - 120 - gap * 2) / 3);
  return items.map((item, index) => card(x, top + index * (cardHeight + gap), cardWidth, cardHeight, index, item, {
    active: index === 2,
    maxChars: width <= 1200 ? 52 : 77,
    maxLines: 4,
    size: width <= 1200 ? 26 : 28,
  })).join("");
}

function technical(content: string, width: number, height: number): string {
  const s = sentenceList(content);
  const title = wrap(shorten(s[0], 145), width >= 1500 ? 46 : 31, 4);
  const items = [s[1] ?? s[0], s[2] ?? s[0], s[3] ?? s[1] ?? s[0]];
  const titleY = width <= 1200 ? 190 : 160;
  const titleSize = width >= 1500 ? 48 : 43;
  const bodyTop = width <= 1200 ? 410 : 330;
  const margin = width <= 1200 ? 100 : 88;
  const gap = width <= 1200 ? 24 : 32;
  if (width <= 1200) {
    const cardWidth = width - margin * 2;
    const cardHeight = Math.floor((height - bodyTop - 120 - gap * 2) / 3);
    return text(title, width / 2, titleY, titleSize, titleSize + 10, { weight: 770, anchor: "middle" })
      + items.map((item, index) => card(margin, bodyTop + index * (cardHeight + gap), cardWidth, cardHeight, index, item, {
        active: index === 1, maxChars: 50, maxLines: 4, size: 25,
      })).join("");
  }
  const cardWidth = Math.floor((width - margin * 2 - gap * 2) / 3);
  const cardHeight = height - bodyTop - 120;
  return text(title, width / 2, titleY, titleSize, titleSize + 9, { weight: 770, anchor: "middle" })
    + items.map((item, index) => card(margin + index * (cardWidth + gap), bodyTop, cardWidth, cardHeight, index, item, {
      active: index === 1, maxChars: 31, maxLines: 7, size: 25,
    })).join("");
}

export function buildEditorialSvg(
  content: string,
  visualFormat: EditorialVisualFormat,
  aspectRatio: string = "4:5",
): EditorialSvgResult {
  const [width, height] = DIMENSIONS[aspectRatio] ?? DIMENSIONS["4:5"];
  let body: string;
  switch (visualFormat) {
    case "EDITORIAL_POSTER": body = poster(content, width, height); break;
    case "PROCESS_FLOW": body = verticalSequence(content, width, height, false); break;
    case "ARCHITECTURE_SCHEMATIC": body = architecture(content, width, height); break;
    case "COMPARISON": body = comparison(content, width, height); break;
    case "ARTIFACT_BOARD": body = artifactBoard(content, width, height); break;
    default: body = technical(content, width, height);
  }
  return {
    svg: `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-label="prodAgentic editorial visual">${chrome(width, height, visualFormat)}${body}</svg>`,
    width,
    height,
  };
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
  }
  return btoa(binary);
}

function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes).map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

export async function rasterizeEditorialVisual(
  content: string,
  visualFormat: EditorialVisualFormat,
  aspectRatio: string = "4:5",
): Promise<EditorialPngResult> {
  if (typeof document === "undefined" || typeof Image === "undefined") {
    throw new Error("Deterministic visual rasterization requires a browser environment");
  }
  const built = buildEditorialSvg(content, visualFormat, aspectRatio);
  const svgBlob = new Blob([built.svg], { type: "image/svg+xml;charset=utf-8" });
  const objectUrl = URL.createObjectURL(svgBlob);
  try {
    const image = new Image();
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () => reject(new Error("Could not rasterize deterministic SVG"));
      image.src = objectUrl;
    });
    const canvas = document.createElement("canvas");
    canvas.width = built.width;
    canvas.height = built.height;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Canvas 2D context is unavailable");
    context.drawImage(image, 0, 0, built.width, built.height);
    const pngBlob = await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error("Canvas PNG encoding failed")), "image/png");
    });
    const bytes = new Uint8Array(await pngBlob.arrayBuffer());
    const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
    return { ...built, base64: bytesToBase64(bytes), sha256: bytesToHex(digest) };
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}
