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

const PALETTE = {
  background: "#090A10",
  surface: "#11131D",
  surfaceRaised: "#171A27",
  line: "#30364D",
  text: "#F5F7FF",
  muted: "#A8B0CC",
  accent: "#7657FF",
  accentSoft: "#A99BFF",
  success: "#63D6A6",
};

export function escapeXml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function normalize(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

function sentences(content: string): string[] {
  const clean = normalize(content);
  if (!clean) return ["Editorial insight"];
  const parts = clean.match(/[^.!?]+[.!?]?/g)?.map((part) => part.trim()).filter(Boolean) ?? [clean];
  return parts.slice(0, 8);
}

function truncate(value: string, max: number): string {
  const clean = normalize(value);
  if (clean.length <= max) return clean;
  const shortened = clean.slice(0, max - 1).replace(/\s+\S*$/, "").trim();
  return `${shortened || clean.slice(0, max - 1)}…`;
}

function wrap(value: string, maxChars: number, maxLines: number): string[] {
  const words = normalize(value).split(" ").filter(Boolean);
  const lines: string[] = [];
  let line = "";
  for (const word of words) {
    const next = line ? `${line} ${word}` : word;
    if (next.length <= maxChars || !line) {
      line = next;
      continue;
    }
    lines.push(line);
    line = word;
    if (lines.length === maxLines - 1) break;
  }
  if (line && lines.length < maxLines) lines.push(line);
  const consumed = lines.join(" ").length;
  if (normalize(value).length > consumed && lines.length) {
    lines[lines.length - 1] = truncate(lines[lines.length - 1], Math.max(8, maxChars - 1)).replace(/…?$/, "…");
  }
  return lines.slice(0, maxLines);
}

function textLines(
  lines: string[],
  x: number,
  y: number,
  options: { size: number; lineHeight: number; fill?: string; weight?: number; anchor?: "start" | "middle" },
): string {
  const fill = options.fill ?? PALETTE.text;
  const weight = options.weight ?? 500;
  const anchor = options.anchor ?? "start";
  return `<text x="${x}" y="${y}" fill="${fill}" font-family="Inter, Arial, sans-serif" font-size="${options.size}" font-weight="${weight}" text-anchor="${anchor}">${lines
    .map((line, index) => `<tspan x="${x}" dy="${index === 0 ? 0 : options.lineHeight}">${escapeXml(line)}</tspan>`)
    .join("")}</text>`;
}

function frame(width: number, height: number, format: EditorialVisualFormat): string {
  return [
    `<rect width="${width}" height="${height}" fill="${PALETTE.background}"/>`,
    `<rect x="48" y="48" width="${width - 96}" height="${height - 96}" rx="34" fill="none" stroke="${PALETTE.line}" stroke-width="2"/>`,
    `<circle cx="82" cy="82" r="10" fill="${PALETTE.accent}"/>`,
    `<text x="108" y="91" fill="${PALETTE.muted}" font-family="Inter, Arial, sans-serif" font-size="22" font-weight="700" letter-spacing="2">prodAgentic · ${format.replaceAll("_", " ")}</text>`,
  ].join("");
}

function editorialPoster(content: string, width: number, height: number): string {
  const s = sentences(content);
  const headline = wrap(truncate(s[0], 150), width > 1300 ? 34 : 25, 5);
  const supporting = wrap(truncate(s[1] ?? s[0], 180), width > 1300 ? 55 : 42, 4);
  const titleSize = width > 1300 ? 66 : 62;
  const startY = Math.round(height * 0.28);
  return [
    `<rect x="72" y="${Math.round(height * 0.18)}" width="14" height="${Math.round(height * 0.48)}" rx="7" fill="${PALETTE.accent}"/>`,
    textLines(headline, 126, startY, { size: titleSize, lineHeight: Math.round(titleSize * 1.12), weight: 760 }),
    `<line x1="126" y1="${Math.round(height * 0.68)}" x2="${width - 126}" y2="${Math.round(height * 0.68)}" stroke="${PALETTE.line}" stroke-width="2"/>`,
    textLines(supporting, 126, Math.round(height * 0.75), { size: 28, lineHeight: 39, fill: PALETTE.muted, weight: 470 }),
    `<text x="${width - 126}" y="${height - 92}" fill="${PALETTE.accentSoft}" font-family="Inter, Arial, sans-serif" font-size="22" font-weight="700" text-anchor="end">POINT OF VIEW / 01</text>`,
  ].join("");
}

function processFlow(content: string, width: number, height: number): string {
  const s = sentences(content);
  const items = [s[0], s[1] ?? s[0], s[2] ?? s[1] ?? s[0], s[3] ?? s[2] ?? s[0]].map((item) => truncate(item, 115));
  const x = 116;
  const cardWidth = width - 232;
  const top = 190;
  const gap = Math.max(24, Math.round((height - top - 170 - items.length * 205) / Math.max(1, items.length - 1)));
  return items.map((item, index) => {
    const y = top + index * (205 + gap);
    const lines = wrap(item, width > 1300 ? 67 : 50, 3);
    const connector = index < items.length - 1
      ? `<line x1="${x + 45}" y1="${y + 178}" x2="${x + 45}" y2="${y + 205 + gap - 14}" stroke="${PALETTE.accent}" stroke-width="4"/><path d="M${x + 35} ${y + 205 + gap - 22} L${x + 45} ${y + 205 + gap - 10} L${x + 55} ${y + 205 + gap - 22}" fill="none" stroke="${PALETTE.accent}" stroke-width="4"/>`
      : "";
    return [
      `<rect x="${x}" y="${y}" width="${cardWidth}" height="178" rx="24" fill="${index === items.length - 1 ? PALETTE.surfaceRaised : PALETTE.surface}" stroke="${index === items.length - 1 ? PALETTE.accent : PALETTE.line}" stroke-width="2"/>`,
      `<circle cx="${x + 45}" cy="${y + 48}" r="24" fill="${index === items.length - 1 ? PALETTE.accent : PALETTE.surfaceRaised}" stroke="${PALETTE.accent}" stroke-width="2"/>`,
      `<text x="${x + 45}" y="${y + 56}" fill="${PALETTE.text}" font-family="Inter, Arial, sans-serif" font-size="22" font-weight="800" text-anchor="middle">0${index + 1}</text>`,
      textLines(lines, x + 92, y + 48, { size: 27, lineHeight: 35, fill: index === 0 ? PALETTE.text : PALETTE.muted, weight: 560 }),
      connector,
    ].join("");
  }).join("");
}

function architecture(content: string, width: number, height: number): string {
  const s = sentences(content);
  const snippets = [s[0], s[1] ?? s[0], s[2] ?? s[1] ?? s[0]].map((item) => truncate(item, 95));
  const cardWidth = width > 1300 ? 390 : 310;
  const cardHeight = 270;
  const centerY = Math.round(height * 0.5) - Math.round(cardHeight / 2);
  const margin = 90;
  const usable = width - margin * 2 - cardWidth * 3;
  const gap = Math.max(40, Math.round(usable / 2));
  const xs = [margin, margin + cardWidth + gap, margin + (cardWidth + gap) * 2];
  const labels = ["CONTEXT", "BOUNDARY", "OUTCOME"];
  return [
    `<line x1="${xs[0] + cardWidth}" y1="${centerY + cardHeight / 2}" x2="${xs[1]}" y2="${centerY + cardHeight / 2}" stroke="${PALETTE.accent}" stroke-width="4"/>`,
    `<line x1="${xs[1] + cardWidth}" y1="${centerY + cardHeight / 2}" x2="${xs[2]}" y2="${centerY + cardHeight / 2}" stroke="${PALETTE.accent}" stroke-width="4"/>`,
    ...xs.map((x, index) => {
      const lines = wrap(snippets[index], width > 1300 ? 31 : 24, 5);
      return [
        `<rect x="${x}" y="${centerY}" width="${cardWidth}" height="${cardHeight}" rx="28" fill="${index === 1 ? PALETTE.surfaceRaised : PALETTE.surface}" stroke="${index === 1 ? PALETTE.accent : PALETTE.line}" stroke-width="3"/>`,
        `<text x="${x + 28}" y="${centerY + 48}" fill="${index === 1 ? PALETTE.accentSoft : PALETTE.muted}" font-family="Inter, Arial, sans-serif" font-size="19" font-weight="800" letter-spacing="2">${labels[index]}</text>`,
        textLines(lines, x + 28, centerY + 96, { size: width > 1300 ? 25 : 23, lineHeight: 33, weight: 550 }),
      ].join("");
    }),
    `<text x="${width / 2}" y="${centerY - 80}" fill="${PALETTE.text}" font-family="Inter, Arial, sans-serif" font-size="34" font-weight="730" text-anchor="middle">A boundary should make the decision visible.</text>`,
  ].join("");
}

function comparison(content: string, width: number, height: number): string {
  const s = sentences(content);
  const left = wrap(truncate(s[0], 170), width > 1300 ? 42 : 33, 6);
  const right = wrap(truncate(s[1] ?? s[0], 170), width > 1300 ? 42 : 33, 6);
  const gap = 32;
  const x = 84;
  const top = 220;
  const cardWidth = (width - x * 2 - gap) / 2;
  const cardHeight = height - top - 150;
  return [
    `<text x="${x}" y="170" fill="${PALETTE.muted}" font-family="Inter, Arial, sans-serif" font-size="21" font-weight="800" letter-spacing="2">APPROACH A</text>`,
    `<text x="${x + cardWidth + gap}" y="170" fill="${PALETTE.accentSoft}" font-family="Inter, Arial, sans-serif" font-size="21" font-weight="800" letter-spacing="2">APPROACH B</text>`,
    `<rect x="${x}" y="${top}" width="${cardWidth}" height="${cardHeight}" rx="28" fill="${PALETTE.surface}" stroke="${PALETTE.line}" stroke-width="2"/>`,
    `<rect x="${x + cardWidth + gap}" y="${top}" width="${cardWidth}" height="${cardHeight}" rx="28" fill="${PALETTE.surfaceRaised}" stroke="${PALETTE.accent}" stroke-width="3"/>`,
    textLines(left, x + 34, top + 76, { size: 31, lineHeight: 43, fill: PALETTE.muted, weight: 530 }),
    textLines(right, x + cardWidth + gap + 34, top + 76, { size: 31, lineHeight: 43, weight: 600 }),
    `<circle cx="${width / 2}" cy="${top + cardHeight / 2}" r="34" fill="${PALETTE.accent}"/><text x="${width / 2}" y="${top + cardHeight / 2 + 9}" fill="white" font-family="Inter, Arial, sans-serif" font-size="22" font-weight="800" text-anchor="middle">VS</text>`,
  ].join("");
}

function artifactBoard(content: string, width: number, height: number): string {
  const s = sentences(content);
  const snippets = [s[0], s[1] ?? s[0], s[2] ?? s[1] ?? s[0]].map((item) => truncate(item, 130));
  const x = 92;
  const top = 190;
  const cardWidth = width - x * 2;
  const cardHeight = Math.round((height - top - 150 - 48) / 3);
  const labels = ["OBSERVATION", "CONSTRAINT", "ENGINEERING MOVE"];
  return snippets.map((item, index) => {
    const y = top + index * (cardHeight + 24);
    const lines = wrap(item, width > 1300 ? 76 : 55, 4);
    return [
      `<rect x="${x}" y="${y}" width="${cardWidth}" height="${cardHeight}" rx="26" fill="${PALETTE.surface}" stroke="${index === 2 ? PALETTE.accent : PALETTE.line}" stroke-width="2"/>`,
      `<rect x="${x + 28}" y="${y + 28}" width="12" height="${cardHeight - 56}" rx="6" fill="${index === 2 ? PALETTE.accent : PALETTE.line}"/>`,
      `<text x="${x + 66}" y="${y + 58}" fill="${index === 2 ? PALETTE.accentSoft : PALETTE.muted}" font-family="Inter, Arial, sans-serif" font-size="19" font-weight="800" letter-spacing="2">${labels[index]}</text>`,
      textLines(lines, x + 66, y + 104, { size: 27, lineHeight: 36, weight: 560 }),
    ].join("");
  }).join("");
}

function technicalDiagram(content: string, width: number, height: number): string {
  const s = sentences(content);
  const title = wrap(truncate(s[0], 135), width > 1300 ? 45 : 33, 4);
  const snippets = [s[1] ?? s[0], s[2] ?? s[0], s[3] ?? s[1] ?? s[0]].map((item) => truncate(item, 95));
  const centerX = width / 2;
  const centerY = height * 0.48;
  const nodeW = width > 1300 ? 350 : 280;
  const nodeH = 210;
  const positions = [
    [86, centerY - nodeH / 2],
    [width - 86 - nodeW, centerY - nodeH / 2],
    [centerX - nodeW / 2, height - 330],
  ];
  return [
    textLines(title, centerX, 205, { size: width > 1300 ? 48 : 43, lineHeight: 55, weight: 760, anchor: "middle" }),
    `<circle cx="${centerX}" cy="${centerY}" r="82" fill="${PALETTE.accent}"/><circle cx="${centerX}" cy="${centerY}" r="56" fill="${PALETTE.background}"/><circle cx="${centerX}" cy="${centerY}" r="18" fill="${PALETTE.accentSoft}"/>`,
    ...positions.map(([x, y], index) => {
      const lines = wrap(snippets[index], width > 1300 ? 30 : 24, 4);
      const targetX = x < centerX ? x + nodeW : x;
      return [
        `<line x1="${centerX}" y1="${centerY}" x2="${targetX}" y2="${y + nodeH / 2}" stroke="${PALETTE.line}" stroke-width="3"/>`,
        `<rect x="${x}" y="${y}" width="${nodeW}" height="${nodeH}" rx="24" fill="${PALETTE.surface}" stroke="${PALETTE.line}" stroke-width="2"/>`,
        `<text x="${x + 28}" y="${y + 46}" fill="${PALETTE.accentSoft}" font-family="Inter, Arial, sans-serif" font-size="19" font-weight="800">0${index + 1}</text>`,
        textLines(lines, x + 28, y + 88, { size: 24, lineHeight: 32, fill: PALETTE.muted, weight: 540 }),
      ].join("");
    }),
  ].join("");
}

export function buildEditorialSvg(
  content: string,
  visualFormat: EditorialVisualFormat,
  aspectRatio: string = "4:5",
): EditorialSvgResult {
  const [width, height] = DIMENSIONS[aspectRatio] ?? DIMENSIONS["4:5"];
  let body: string;
  switch (visualFormat) {
    case "EDITORIAL_POSTER": body = editorialPoster(content, width, height); break;
    case "PROCESS_FLOW": body = processFlow(content, width, height); break;
    case "ARCHITECTURE_SCHEMATIC": body = architecture(content, width, height); break;
    case "COMPARISON": body = comparison(content, width, height); break;
    case "ARTIFACT_BOARD": body = artifactBoard(content, width, height); break;
    default: body = technicalDiagram(content, width, height);
  }

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-label="prodAgentic editorial visual">${frame(width, height, visualFormat)}${body}</svg>`;
  return { svg, width, height };
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
    return {
      ...built,
      base64: bytesToBase64(bytes),
      sha256: bytesToHex(digest),
    };
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}
