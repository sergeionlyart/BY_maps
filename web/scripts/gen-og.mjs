import sharp from 'sharp';
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const webDir = resolve(__dirname, '..');

// --- 1. Read + parse the Belarus outline ------------------------------------
const outlinePath =
  '/private/tmp/claude-501/-Users-sergejavdejcik-Code-BY-maps/e6ea4743-cd1d-4e3e-b6d9-7a25edbea11a/scratchpad/by_outline.txt';
const raw = readFileSync(outlinePath, 'utf8').trim().split('\n');
const [W, H] = raw[0].trim().split(/\s+/).map(Number); // ~1000 511
const d = raw[1].trim();

// --- 2. Fit the outline into the right ~45% ---------------------------------
// Right region: x 640..1180 (540 wide). Belarus aspect ~1.96:1 (wide),
// so width is the binding constraint. Target width ~520px.
const targetW = 520;
const scale = targetW / W;                 // ~0.52
const scaledH = H * scale;                 // ~266
const tx = 655;                            // x span 655..1175 (inside 640..1180)
const ty = Math.round((630 - scaledH) / 2);// vertical centre
const gTransform = `translate(${tx}, ${ty}) scale(${scale.toFixed(4)})`;

// Decorative copper "city" dots near the map centre.
const cx = tx + 500 * scale;
const cy = ty + 255 * scale;
const dots = [
  [cx, cy - 14],
  [cx - 46, cy + 26],
  [cx + 44, cy - 34],
  [cx - 8, cy + 48],
]
  .map(([x, y]) => `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="6" fill="#9a5220"/>`)
  .join('\n    ');

// --- 3. Build the full 1200x630 SVG -----------------------------------------
const FONT = 'Helvetica, Arial, system-ui, sans-serif';
const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <rect x="0" y="0" width="1200" height="630" fill="#f9f9f7"/>

  <!-- Belarus outline hero -->
  <g transform="${gTransform}">
    <path d="${d}" fill="#2266bd" fill-opacity="0.06" stroke="#2266bd" stroke-width="3"
      stroke-linejoin="round" stroke-linecap="round"/>
  </g>
  <g>
    ${dots}
  </g>

  <!-- Left text column -->
  <text x="80" y="132" font-family="${FONT}" font-size="24" fill="#9a5220"
    letter-spacing="2" font-weight="600">ОТКРЫТОЕ ИССЛЕДОВАНИЕ · 1897–2075</text>

  <text x="80" y="220" font-family="${FONT}" font-size="66" fill="#0b0b0b" font-weight="700">Население</text>
  <text x="80" y="290" font-family="${FONT}" font-size="66" fill="#0b0b0b" font-weight="700">Беларуси</text>

  <text x="80" y="352" font-family="${FONT}" font-size="28" fill="#52514e">129 лет переписей и прогноз до 2075 —</text>
  <text x="80" y="390" font-family="${FONT}" font-size="28" fill="#52514e">на проверяемых данных</text>

  <line x1="80" y1="440" x2="200" y2="440" stroke="#9a5220" stroke-width="2"/>
  <text x="80" y="484" font-family="${FONT}" font-size="26" fill="#9a5220" font-weight="700">Сергей Авдейчик · AI/ML Engineer</text>

  <text x="80" y="598" font-family="${FONT}" font-size="20" fill="#726f68">by-population-maps.vercel.app</text>
</svg>`;

// --- 4. Rasterize ------------------------------------------------------------
const outPng = resolve(webDir, 'public/og.png');
const info = await sharp(Buffer.from(svg), { density: 200 })
  .resize(1200, 630)
  .png()
  .toFile(outPng);

const bytes = readFileSync(outPng).length;
const note =
  `og.png render succeeded\n` +
  `dimensions: ${info.width}x${info.height}\n` +
  `bytes: ${bytes}\n` +
  `g transform: ${gTransform}\n`;
writeFileSync(resolve(webDir, 'public/og-debug-note.txt'), note);

console.log(note);
