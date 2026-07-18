/**
 * ParkArt — vintage engraved postage stamps, one per park.
 *
 * Styled after the 1934 U.S. National Parks issue: aged paper, perforated
 * edges (true transparency via SVG mask), each park printed in a single
 * engraving ink, and — like the originals — ONE monument per stamp.
 *
 * Scenes are drawn in grayscale line work (families of hatch lines clipped
 * to each surface, ruled skies broken around the sun, waterfalls/geysers as
 * unprinted paper) and converted to the park's ink by a luminance→ink-ramp
 * duotone filter, exactly like printing one plate in one ink.
 */

/* ------------------------------------------------------------------ inks */

interface StampSpec {
  title: string;
  denom: string;
  year: string;
  ink: string;
}

const STAMPS: Record<string, StampSpec> = {
  yosemite: { title: "YOSEMITE", denom: "1¢", year: "1890", ink: "#33573d" },
  "grand-canyon": { title: "GRAND CANYON", denom: "2¢", year: "1919", ink: "#8f3324" },
  "grand-teton": { title: "GRAND TETON", denom: "3¢", year: "1929", ink: "#5b4a68" },
  "joshua-tree": { title: "JOSHUA TREE", denom: "4¢", year: "1994", ink: "#8a5a24" },
  yellowstone: { title: "YELLOWSTONE", denom: "5¢", year: "1872", ink: "#1e5c56" },
  acadia: { title: "ACADIA", denom: "7¢", year: "1919", ink: "#2f4b66" },
  zion: { title: "ZION", denom: "8¢", year: "1919", ink: "#7a4a28" },
  glacier: { title: "GLACIER", denom: "9¢", year: "1910", ink: "#7a3b52" },
};

const PAPER = "#f2e8d0";

function hexRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function mix(a: [number, number, number], b: [number, number, number], t: number) {
  return a.map((v, i) => v + (b[i] - v) * t) as [number, number, number];
}

/** Luminance→ink table: shadows print dense ink, highlights stay paper. */
function inkRamp(ink: string): { r: string; g: string; b: string } {
  const inkRgb = hexRgb(ink);
  const paperRgb = hexRgb(PAPER);
  const stops = [
    mix(inkRgb, [0, 0, 0], 0.45),
    inkRgb,
    mix(inkRgb, paperRgb, 0.45),
    mix(paperRgb, inkRgb, 0.09),
  ];
  const chan = (i: number) => stops.map((s) => (s[i] / 255).toFixed(3)).join(" ");
  return { r: chan(0), g: chan(1), b: chan(2) };
}

/* ---------------------------------------------------------- stamp chrome */

const W = 420;
const H = 330;
const WIN = { x: 22.5, y: 42, w: 375, h: 240 };

function Stamp({ slug, children }: { slug: string; children: React.ReactNode }) {
  const spec = STAMPS[slug] ?? { title: slug.toUpperCase(), denom: "·", year: "", ink: "#3f4a3f" };
  const ramp = inkRamp(spec.ink);
  const perf: JSX.Element[] = [];
  for (let x = 0; x <= W; x += 15) {
    perf.push(<circle key={`t${x}`} cx={x} cy={0} r={5.4} fill="#000" />);
    perf.push(<circle key={`b${x}`} cx={x} cy={H} r={5.4} fill="#000" />);
  }
  for (let y = 15; y < H; y += 15) {
    perf.push(<circle key={`l${y}`} cx={0} cy={y} r={5.4} fill="#000" />);
    perf.push(<circle key={`r${y}`} cx={W} cy={y} r={5.4} fill="#000" />);
  }

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="park-art stamp-art" role="img" aria-label={`${spec.title} vintage stamp`}>
      <defs>
        <mask id={`perf-${slug}`}>
          <rect width={W} height={H} fill="#fff" />
          {perf}
        </mask>
        <filter id={`ink-${slug}`} colorInterpolationFilters="sRGB">
          <feColorMatrix
            type="matrix"
            values="0.2126 0.7152 0.0722 0 0  0.2126 0.7152 0.0722 0 0  0.2126 0.7152 0.0722 0 0  0 0 0 1 0"
          />
          <feComponentTransfer>
            <feFuncR type="table" tableValues={ramp.r} />
            <feFuncG type="table" tableValues={ramp.g} />
            <feFuncB type="table" tableValues={ramp.b} />
          </feComponentTransfer>
        </filter>
        <filter id={`grain-${slug}`}>
          <feTurbulence type="fractalNoise" baseFrequency="0.55" numOctaves="2" stitchTiles="stitch" />
          <feColorMatrix type="saturate" values="0" />
          <feComponentTransfer>
            <feFuncA type="linear" slope="0.055" />
          </feComponentTransfer>
          <feComposite operator="over" in2="SourceGraphic" />
        </filter>
        <radialGradient id={`age-${slug}`} cx="50%" cy="46%" r="75%">
          <stop offset="62%" stopColor="#6b4f2a" stopOpacity="0" />
          <stop offset="100%" stopColor="#6b4f2a" stopOpacity="0.22" />
        </radialGradient>
      </defs>

      <g mask={`url(#perf-${slug})`}>
        <rect width={W} height={H} fill={PAPER} />
        <rect width={W} height={H} fill={`url(#age-${slug})`} />
        <rect x={11} y={11} width={W - 22} height={H - 22} fill="none" stroke={spec.ink} strokeWidth="1" opacity="0.55" />

        <text x={W / 2} y={31} textAnchor="middle" fill={spec.ink} fontFamily="'Fraunces Variable', Georgia, serif" fontSize="12.5" fontWeight={620} letterSpacing="3.2">
          · UNITED STATES · NATIONAL PARKS ·
        </text>

        <g transform={`translate(${WIN.x} ${WIN.y}) scale(0.75)`} filter={`url(#ink-${slug})`}>
          {children}
        </g>
        <rect x={WIN.x} y={WIN.y} width={WIN.w} height={WIN.h} fill="none" stroke={spec.ink} strokeWidth="2.5" />
        <rect x={WIN.x - 4} y={WIN.y - 4} width={WIN.w + 8} height={WIN.h + 8} fill="none" stroke={spec.ink} strokeWidth="0.8" opacity="0.6" />

        <text x={26} y={310} fill={spec.ink} fontFamily="'Fraunces Variable', Georgia, serif" fontSize="11" fontWeight={600} letterSpacing="0.5" opacity="0.85">
          EST. {spec.year}
        </text>
        <text
          x={W / 2}
          y={313}
          textAnchor="middle"
          fill={spec.ink}
          fontFamily="'Fraunces Variable', Georgia, serif"
          fontSize={spec.title.length > 10 ? 19 : 23}
          fontWeight={700}
          letterSpacing={spec.title.length > 10 ? 1.5 : 2.5}
        >
          {spec.title}
        </text>
        <text x={W - 26} y={313} textAnchor="end" fill={spec.ink} fontFamily="'Fraunces Variable', Georgia, serif" fontSize="21" fontWeight={700}>
          {spec.denom}
        </text>

        <rect width={W} height={H} filter={`url(#grain-${slug})`} opacity="0.6" fill="transparent" />
      </g>
    </svg>
  );
}

/* ----------------------------------------------------- engraving engine */

const INK_DARK = "#1c1c1c";
const INK_MID = "#4a4a4a";

/** A family of parallel lines at `angle`, clipped to a region path. */
function Hatch({
  id,
  region,
  angle,
  spacing,
  width = 1,
  color = INK_DARK,
  opacity = 1,
}: {
  id: string;
  region: string;
  angle: number;
  spacing: number;
  width?: number;
  color?: string;
  opacity?: number;
}) {
  const lines: JSX.Element[] = [];
  for (let y = -360; y <= 680; y += spacing) {
    lines.push(<line key={y} x1={-360} y1={y} x2={860} y2={y} />);
  }
  return (
    <g>
      <clipPath id={id}>
        <path d={region} clipRule="evenodd" />
      </clipPath>
      <g clipPath={`url(#${id})`} stroke={color} strokeWidth={width} opacity={opacity}>
        <g transform={`rotate(${angle} 250 160)`}>{lines}</g>
      </g>
    </g>
  );
}

/** Ruled horizontal sky lines that leave a halo gap around the sun. */
function SkyLines({
  yTop,
  yBottom,
  sunX,
  sunY,
  sunR,
  x0 = 0,
  x1 = 500,
}: {
  yTop: number;
  yBottom: number;
  sunX: number;
  sunY: number;
  sunR: number;
  x0?: number;
  x1?: number;
}) {
  const halo = sunR + 9;
  let d = "";
  let y = yBottom;
  let gap = 3.6;
  while (y > yTop) {
    if (Math.abs(y - sunY) < halo) {
      const dx = Math.sqrt(halo * halo - (y - sunY) * (y - sunY)) + 3;
      const leftEnd = sunX - dx;
      const rightStart = sunX + dx;
      if (leftEnd > x0) d += `M${x0} ${y}L${leftEnd.toFixed(1)} ${y}`;
      if (rightStart < x1) d += `M${rightStart.toFixed(1)} ${y}L${x1} ${y}`;
    } else {
      d += `M${x0} ${y}L${x1} ${y}`;
    }
    y -= gap;
    gap *= 1.06;
  }
  return <path d={d} stroke={INK_MID} strokeWidth="0.75" fill="none" opacity="0.8" />;
}

function Sun({ x, y, r }: { x: number; y: number; r: number }) {
  return (
    <g>
      <circle cx={x} cy={y} r={r} fill="#fdfdfd" stroke={INK_DARK} strokeWidth="1.3" />
      <circle cx={x} cy={y} r={r + 5} fill="none" stroke={INK_MID} strokeWidth="0.6" opacity="0.7" />
    </g>
  );
}

/** A small engraved conifer: trunk stroke + chevron branches. */
function EngravedTree({ x, y, h }: { x: number; y: number; h: number }) {
  const rows = Math.max(3, Math.round(h / 6));
  const parts: string[] = [`M${x} ${y}L${x} ${y - h}`];
  for (let i = 0; i < rows; i++) {
    const t = i / rows;
    const yy = y - h + 4 + t * (h - 6);
    const w = 2 + t * (h * 0.32);
    parts.push(`M${x - w} ${yy + 3}L${x} ${yy}L${x + w} ${yy + 3}`);
  }
  return <path d={parts.join("")} stroke={INK_DARK} strokeWidth="1.1" fill="none" strokeLinecap="round" />;
}

/** Ruled ground band with a horizon rule at yTop. */
function GroundBand({ yTop, id }: { yTop: number; id: string }) {
  return (
    <g>
      <Hatch id={id} region={`M0 320 L0 ${yTop} L500 ${yTop} L500 320 Z`} angle={0} spacing={5} width={0.75} color={INK_MID} opacity={0.7} />
      <path d={`M0 ${yTop} L500 ${yTop}`} stroke={INK_DARK} strokeWidth="1" opacity="0.9" />
    </g>
  );
}

/** Spiky yucca-tuft star polygon (deterministic). */
function tuftPoints(cx: number, cy: number, rOuter = 16, rInner = 7, spikes = 9): string {
  const pts: string[] = [];
  for (let i = 0; i < spikes * 2; i++) {
    const r = i % 2 === 0 ? rOuter : rInner;
    const a = (Math.PI * i) / spikes - Math.PI / 2;
    pts.push(`${(cx + r * Math.cos(a)).toFixed(1)},${(cy + r * Math.sin(a)).toFixed(1)}`);
  }
  return pts.join(" ");
}

/* ============================== SCENES ================================= */
/* One monument per park, engraved in grayscale on white ground.           */

/* --- YOSEMITE · Half Dome from the Valley --- */

const HD_DOME =
  "M190 80 Q212 60 252 60 Q312 62 346 104 Q384 152 399 216 Q408 252 414 282 L150 282 Q180 252 205 225 Z";
const HD_FACE_BAND = "M190 80 L205 225 L228 219 L212 76 Z";
const HD_APRON = "M205 225 L150 282 L262 282 Z";

function FlankContours({ clipId }: { clipId: string }) {
  const S = [198, 76], C1 = [288, 58], C2 = [366, 138], E = [406, 278];
  const P = [214, 268];
  const L = (a: number[], t: number, i: number) => a[i] + (P[i] - a[i]) * t;
  const shells: JSX.Element[] = [];
  for (let k = 0; k < 10; k++) {
    const t = 0.07 + (k / 9) * 0.62;
    shells.push(
      <path
        key={k}
        d={`M ${L(S, t, 0)} ${L(S, t, 1)} C ${L(C1, t, 0)} ${L(C1, t, 1)}, ${L(C2, t, 0)} ${L(C2, t, 1)}, ${L(E, t, 0)} ${L(E, t, 1)}`}
        strokeWidth={0.7 + (1 - t) * 0.35}
      />
    );
  }
  return (
    <g clipPath={`url(#${clipId})`} stroke={INK_DARK} fill="none" opacity="0.8">
      {shells}
    </g>
  );
}

const Yosemite = () => (
  <g>
    <rect width="500" height="320" fill="#ffffff" />
    <SkyLines yTop={26} yBottom={272} sunX={88} sunY={76} sunR={20} />
    <Sun x={88} y={76} r={20} />

    <path d={HD_DOME} fill="#f2f2f2" />
    <clipPath id="yo-dome-clip">
      <path d={HD_DOME} />
    </clipPath>
    <FlankContours clipId="yo-dome-clip" />

    <path d={HD_FACE_BAND} fill="#e6e6e6" />
    <Hatch id="yo-face" region={HD_FACE_BAND} angle={94} spacing={3.4} width={0.9} />
    <path d="M196 104 L203 210 M204 88 Q208 150 211 212" stroke={INK_DARK} strokeWidth="1" fill="none" opacity="0.7" />
    <Hatch id="yo-apron" region={HD_APRON} angle={38} spacing={5.5} width={0.7} color={INK_MID} opacity={0.7} />

    <path d={HD_DOME} fill="none" stroke={INK_DARK} strokeWidth="2" />
    <path d="M190 80 L205 225 Q180 252 150 282" fill="none" stroke={INK_DARK} strokeWidth="2.2" />

    <path d="M136 128 Q142 122 148 128 M148 128 Q154 122 160 128 M124 152 Q129 147 134 152 M134 152 Q139 147 144 152" stroke={INK_MID} strokeWidth="1" fill="none" />

    <GroundBand yTop={282} id="yo-md" />
    <path d="M40 320 Q110 300 190 296 Q290 292 350 298" stroke="#ffffff" strokeWidth="12" fill="none" strokeLinecap="round" />
    <path d="M40 314 Q112 296 190 291 Q288 287 348 293 M52 320 Q120 305 196 301 Q292 297 352 303" stroke={INK_DARK} strokeWidth="0.85" fill="none" />
    {[20, 62, 104, 240, 292, 386, 428, 470].map((x, i) => (
      <EngravedTree key={x} x={x} y={318} h={24 + ((i * 7) % 11)} />
    ))}
    {[136, 176, 356, 494].map((x) => (
      <EngravedTree key={`s-${x}`} x={x} y={300} h={14} />
    ))}
  </g>
);

/* --- GRAND CANYON · a temple butte over layered walls --- */

const GC_BUTTE_SOLID =
  "M215 108 L285 108 L302 150 L306 172 L322 198 L326 226 L340 282 L160 282 L172 226 L196 172 L200 150 Z";

const GrandCanyon = () => (
  <g>
    <rect width="500" height="320" fill="#ffffff" />
    <SkyLines yTop={26} yBottom={84} sunX={404} sunY={56} sunR={17} />
    <Sun x={404} y={56} r={17} />

    {/* far rim */}
    <path d="M0 88 L500 88" stroke={INK_DARK} strokeWidth="1.4" />
    <Hatch id="gc-far" region="M0 88 L500 88 L500 118 L0 118 Z" angle={0} spacing={4.5} width={0.7} color={INK_MID} opacity={0.6} />

    {/* canyon walls, three receding tiers */}
    <path d="M0 118 L84 114 L120 128 L212 124 L288 128 L360 122 L436 128 L500 122 L500 148 L0 148 Z" fill="#ececec" />
    <Hatch id="gc-t1" region="M0 118 L84 114 L120 128 L212 124 L288 128 L360 122 L436 128 L500 122 L500 148 L0 148 Z" angle={0} spacing={3.6} width={0.7} color={INK_MID} opacity={0.75} />
    <path d="M0 148 L60 144 L110 158 L230 152 L330 158 L430 150 L500 156 L500 196 L0 196 Z" fill="#e2e2e2" />
    <Hatch id="gc-t2" region="M0 148 L60 144 L110 158 L230 152 L330 158 L430 150 L500 156 L500 196 L0 196 Z" angle={0} spacing={3.2} width={0.8} opacity={0.7} />
    <path d="M0 196 L80 192 L150 206 L280 200 L390 208 L500 200 L500 250 L0 250 Z" fill="#d9d9d9" />
    <Hatch id="gc-t3" region="M0 196 L80 192 L150 206 L280 200 L390 208 L500 200 L500 250 L0 250 Z" angle={0} spacing={2.9} width={0.85} opacity={0.75} />
    <path d="M0 118 L84 114 L120 128 L212 124 L288 128 L360 122 L436 128 L500 122 M0 148 L60 144 L110 158 L230 152 L330 158 L430 150 L500 156 M0 196 L80 192 L150 206 L280 200 L390 208 L500 200" stroke={INK_DARK} strokeWidth="1" fill="none" opacity="0.9" />

    {/* the temple butte */}
    <path d={GC_BUTTE_SOLID} fill="#efefef" />
    <Hatch id="gc-bt" region={GC_BUTTE_SOLID} angle={0} spacing={3.4} width={0.8} opacity={0.85} />
    <Hatch id="gc-bts" region="M285 108 L302 150 L306 172 L322 198 L326 226 L340 282 L252 282 L252 108 Z" angle={64} spacing={5.5} width={0.75} opacity={0.7} />
    <path d={GC_BUTTE_SOLID} fill="none" stroke={INK_DARK} strokeWidth="2" />
    <path d="M200 150 L302 150 M196 172 L306 172 M178 198 L322 198 M172 226 L326 226" stroke={INK_DARK} strokeWidth="1" opacity="0.8" />

    {/* inner gorge */}
    <path d="M0 250 L500 250 L500 282 L0 282 Z" fill="#c9c9c9" />
    <Hatch id="gc-gorge" region="M0 250 L500 250 L500 282 L0 282 Z" angle={0} spacing={2.4} width={1} opacity={0.85} />
    <path d="M0 250 L500 250" stroke={INK_DARK} strokeWidth="1.2" />

    {/* rim at the viewer's feet */}
    <path d="M0 282 L500 282 L500 320 L0 320 Z" fill="#9a9a9a" />
    <Hatch id="gc-rim" region="M0 282 L500 282 L500 320 L0 320 Z" angle={26} spacing={3.2} width={1} />
    <path d="M0 282 L500 282" stroke={INK_DARK} strokeWidth="1.6" />
    <EngravedTree x={52} y={318} h={22} />
    <EngravedTree x={452} y={316} h={17} />
  </g>
);

/* --- GRAND TETON · the Grand's spike over the sage flats --- */

const GT_PEAK = "M250 44 L282 96 L276 112 L308 170 L302 186 L336 250 L344 282 L156 282 L168 244 L204 170 L214 152 L226 118 L238 96 Z";
const GT_PEAK_SHADOW = "M250 44 L282 96 L276 112 L308 170 L302 186 L336 250 L344 282 L250 282 Z";

const GrandTeton = () => (
  <g>
    <rect width="500" height="320" fill="#ffffff" />
    <SkyLines yTop={26} yBottom={274} sunX={84} sunY={70} sunR={19} />
    <Sun x={84} y={70} r={19} />

    {/* flanking summits, printed light */}
    <path d="M60 282 L118 148 L142 190 L166 160 L204 282 Z" fill="#f0f0f0" />
    <Hatch id="gt-l" region="M60 282 L118 148 L142 190 L166 160 L204 282 Z" angle={68} spacing={5.5} width={0.7} color={INK_MID} opacity={0.6} />
    <path d="M60 282 L118 148 L142 190 L166 160 L204 282" fill="none" stroke={INK_DARK} strokeWidth="1.1" opacity="0.8" />
    <path d="M304 282 L356 166 L378 204 L398 178 L442 282 Z" fill="#f0f0f0" />
    <Hatch id="gt-r" region="M304 282 L356 166 L378 204 L398 178 L442 282 Z" angle={-64} spacing={5.5} width={0.7} color={INK_MID} opacity={0.6} />
    <path d="M304 282 L356 166 L378 204 L398 178 L442 282" fill="none" stroke={INK_DARK} strokeWidth="1.1" opacity="0.8" />

    {/* the Grand */}
    <path d={GT_PEAK} fill="#ededed" />
    <Hatch id="gt-g" region={GT_PEAK} angle={76} spacing={4} width={0.8} opacity={0.8} />
    <Hatch id="gt-gs" region={GT_PEAK_SHADOW} angle={-58} spacing={4.4} width={0.9} />
    {/* snowfields: unprinted couloirs */}
    <path d="M250 44 L262 72 L252 96 L242 74 Z" fill="#ffffff" />
    <path d="M236 120 L250 128 L244 168 L228 156 Z" fill="#ffffff" opacity="0.95" />
    <path d="M282 150 L296 162 L290 196 L276 182 Z" fill="#ffffff" opacity="0.9" />
    <path d={GT_PEAK} fill="none" stroke={INK_DARK} strokeWidth="2" />

    {/* sage flats + the Snake */}
    <GroundBand yTop={282} id="gt-md" />
    <path d="M0 306 Q90 296 170 300 Q280 306 360 298 Q430 292 500 298" stroke="#ffffff" strokeWidth="11" fill="none" />
    <path d="M0 301 Q92 292 170 295 Q278 301 360 293 Q430 287 500 293 M0 312 Q96 303 176 306 Q284 312 364 304 Q434 298 500 304" stroke={INK_DARK} strokeWidth="0.85" fill="none" />
    {[36, 118, 424, 466].map((x) => (
      <EngravedTree key={x} x={x} y={318} h={15} />
    ))}
  </g>
);

/* --- JOSHUA TREE · one great tree, boulders, desert sun --- */

function JoshuaArm({ d, tuft }: { d: string; tuft: [number, number, number] }) {
  return (
    <g>
      <path d={d} fill={INK_DARK} />
      <polygon points={tuftPoints(tuft[0], tuft[1], tuft[2], tuft[2] * 0.45, 9)} fill={INK_DARK} />
    </g>
  );
}

const JoshuaTree = () => (
  <g>
    <rect width="500" height="320" fill="#ffffff" />
    <SkyLines yTop={26} yBottom={274} sunX={366} sunY={92} sunR={34} />
    <Sun x={366} y={92} r={34} />
    <circle cx={366} cy={92} r={44} fill="none" stroke={INK_MID} strokeWidth="0.5" opacity="0.5" />

    {/* boulder pile: rounded masses with wrapping contour arcs */}
    <g>
      <path d="M336 282 Q340 236 376 228 Q414 222 428 250 Q460 244 470 268 Q478 276 478 282 Z" fill="#ededed" />
      <path d="M336 282 Q340 236 376 228 Q414 222 428 250 Q460 244 470 268 Q478 276 478 282" fill="none" stroke={INK_DARK} strokeWidth="1.6" />
      <path d="M352 274 Q356 246 382 240 M368 278 Q372 252 398 246 M414 258 Q432 252 444 266 M428 276 Q444 266 458 272" stroke={INK_MID} strokeWidth="0.8" fill="none" opacity="0.85" />
      <path d="M390 252 Q412 240 428 250" stroke={INK_MID} strokeWidth="0.8" fill="none" opacity="0.85" />
    </g>

    {/* the tree: thick shaggy trunk, five arms */}
    <path d="M222 282 L228 190 Q230 176 238 168 Q246 176 250 190 L262 282 Z" fill={INK_DARK} />
    <JoshuaArm d="M234 180 Q214 160 208 136 L200 118 L214 112 L222 132 Q230 156 244 170 Z" tuft={[208, 106, 20]} />
    <JoshuaArm d="M242 172 Q262 150 268 126 L276 108 L290 116 L280 136 Q268 162 252 178 Z" tuft={[286, 102, 20]} />
    <JoshuaArm d="M236 172 Q236 148 240 132 L244 116 L258 120 L252 140 Q248 158 246 176 Z" tuft={[252, 108, 17]} />
    <JoshuaArm d="M230 200 Q206 196 190 182 L176 170 L184 158 L200 170 Q216 184 234 188 Z" tuft={[176, 160, 16]} />
    <JoshuaArm d="M252 202 Q276 200 292 190 L306 180 L314 192 L298 202 Q280 212 254 214 Z" tuft={[312, 182, 16]} />
    {/* shag marks on the trunk */}
    <path d="M228 210 L238 206 M226 226 L240 222 M224 244 L242 240 M223 262 L244 258" stroke="#ffffff" strokeWidth="1.2" fill="none" opacity="0.9" />

    {/* desert floor: stippled with small yuccas */}
    <GroundBand yTop={282} id="jt-md" />
    <polygon points={tuftPoints(84, 300, 10, 4, 8)} fill={INK_DARK} />
    <polygon points={tuftPoints(140, 310, 8, 3.5, 8)} fill={INK_DARK} />
    <polygon points={tuftPoints(462, 306, 9, 4, 8)} fill={INK_DARK} />
    <path d="M30 296 L38 296 M56 308 L66 308 M108 292 L116 292 M180 304 L190 304 M310 298 L320 298 M418 294 L428 294" stroke={INK_MID} strokeWidth="1.4" opacity="0.7" />
  </g>
);

/* --- YELLOWSTONE · Old Faithful in full eruption --- */

const YS_PLUME =
  "M244 244 Q238 200 240 160 Q236 120 228 96 Q222 74 230 58 Q238 44 252 40 Q270 38 278 52 Q286 66 280 88 Q292 82 296 94 Q300 108 288 116 Q282 160 278 200 Q274 232 270 244 Z";

const Yellowstone = () => (
  <g>
    <rect width="500" height="320" fill="#ffffff" />
    <SkyLines yTop={26} yBottom={252} sunX={94} sunY={66} sunR={18} />
    <Sun x={94} y={66} r={18} />

    {/* distant lodgepole ridge */}
    <path d="M0 236 L500 236" stroke={INK_DARK} strokeWidth="1" opacity="0.85" />
    {[16, 40, 64, 88, 112, 136, 160, 342, 366, 390, 414, 438, 462, 486].map((x, i) => (
      <EngravedTree key={x} x={x} y={236} h={16 + ((i * 5) % 9)} />
    ))}

    {/* the column: unprinted paper, billowed crown, drifting steam */}
    <path d={YS_PLUME} fill="#ffffff" />
    <path d={YS_PLUME} fill="none" stroke={INK_DARK} strokeWidth="1.5" />
    <path d="M252 224 Q248 180 250 140 M262 228 Q262 184 260 144 M256 100 Q250 76 256 58" stroke={INK_MID} strokeWidth="0.7" fill="none" opacity="0.7" />
    <path d="M288 116 Q310 112 314 126 Q318 140 304 142 M296 94 Q318 84 326 96 M230 70 Q214 62 212 76 Q210 88 222 88" stroke={INK_MID} strokeWidth="1" fill="none" opacity="0.8" />

    {/* sinter cone + terraced benches */}
    <path d="M204 262 Q226 240 244 238 L270 238 Q292 242 308 262 Z" fill="#e6e6e6" />
    <Hatch id="ys-cone" region="M204 262 Q226 240 244 238 L270 238 Q292 242 308 262 Z" angle={8} spacing={3.4} width={0.8} opacity={0.85} />
    <path d="M204 262 Q226 240 244 238 L270 238 Q292 242 308 262" fill="none" stroke={INK_DARK} strokeWidth="1.6" />
    <path d="M168 270 Q250 258 344 270 M140 278 Q250 266 372 278" stroke={INK_DARK} strokeWidth="0.9" fill="none" opacity="0.85" />

    {/* geyser basin flat with runoff pools */}
    <GroundBand yTop={282} id="ys-md" />
    <ellipse cx={166} cy={296} rx={34} ry={6} fill="#ffffff" />
    <ellipse cx={166} cy={296} rx={34} ry={6} fill="none" stroke={INK_DARK} strokeWidth="0.9" />
    <ellipse cx={352} cy={302} rx={42} ry={7} fill="#ffffff" />
    <ellipse cx={352} cy={302} rx={42} ry={7} fill="none" stroke={INK_DARK} strokeWidth="0.9" />
  </g>
);

/* --- ZION · the Great White Throne over the Virgin River --- */

const ZI_THRONE = "M258 282 L266 104 Q268 72 300 66 L404 74 Q420 78 424 100 L436 282 Z";

const Zion = () => (
  <g>
    <rect width="500" height="320" fill="#ffffff" />
    <SkyLines yTop={26} yBottom={270} sunX={96} sunY={64} sunR={17} x1={500} />
    <Sun x={96} y={64} r={17} />

    {/* canyon wall closing the left edge */}
    <path d="M0 282 L0 40 L58 46 L84 92 L96 160 L104 282 Z" fill="#dedede" />
    <Hatch id="zi-wall" region="M0 282 L0 40 L58 46 L84 92 L96 160 L104 282 Z" angle={88} spacing={3.2} width={0.95} />
    <path d="M0 40 L58 46 L84 92 L96 160 L104 282" fill="none" stroke={INK_DARK} strokeWidth="1.8" />

    {/* the Throne: pale crown, darkening base */}
    <path d={ZI_THRONE} fill="#f4f4f4" />
    <Hatch id="zi-th-top" region="M266 104 Q268 72 300 66 L404 74 Q420 78 424 100 L426 150 L264 144 Z" angle={90} spacing={6.5} width={0.6} color={INK_MID} opacity={0.55} />
    <Hatch id="zi-th-mid" region="M264 144 L426 150 L430 216 L261 212 Z" angle={90} spacing={4.4} width={0.8} opacity={0.7} />
    <Hatch id="zi-th-base" region="M261 212 L430 216 L436 282 L258 282 Z" angle={90} spacing={3.2} width={0.95} opacity={0.85} />
    <path d="M264 144 L426 150 M261 212 L430 216 M266 178 L428 183" stroke={INK_DARK} strokeWidth="0.9" opacity="0.75" />
    <path d={ZI_THRONE} fill="none" stroke={INK_DARK} strokeWidth="2" />

    {/* the Virgin river bend with cottonwoods */}
    <GroundBand yTop={282} id="zi-md" />
    <path d="M500 300 Q420 288 330 294 Q220 300 150 310 Q90 316 30 314" stroke="#ffffff" strokeWidth="13" fill="none" />
    <path d="M500 295 Q420 283 330 289 Q222 295 152 305 Q92 311 30 309 M500 306 Q424 294 334 300 Q226 306 156 315" stroke={INK_DARK} strokeWidth="0.9" fill="none" />
    {[196, 236, 460].map((x) => (
      <g key={x}>
        <path d={`M${x} 318 L${x} 302`} stroke={INK_DARK} strokeWidth="1.2" />
        <path d={`M${x - 9} 302 Q${x - 8} 290 ${x} 291 Q${x + 10} 290 ${x + 9} 300 Q${x + 8} 308 ${x} 306 Q${x - 9} 308 ${x - 9} 302 Z`} fill="none" stroke={INK_DARK} strokeWidth="1" />
      </g>
    ))}
  </g>
);

/* --- GLACIER · a horn peak over an alpine lake --- */

const GL_HORN = "M240 56 Q224 158 170 234 L312 234 Q258 158 240 56 Z";

const Glacier = () => (
  <g>
    <rect width="500" height="320" fill="#ffffff" />
    <SkyLines yTop={26} yBottom={228} sunX={414} sunY={66} sunR={19} />
    <Sun x={414} y={66} r={19} />

    {/* companion ridge */}
    <path d="M300 234 L352 150 L384 192 L420 160 L468 234 Z" fill="#f0f0f0" />
    <Hatch id="gl-ridge" region="M300 234 L352 150 L384 192 L420 160 L468 234 Z" angle={-62} spacing={5.5} width={0.7} color={INK_MID} opacity={0.6} />
    <path d="M300 234 L352 150 L384 192 L420 160 L468 234" fill="none" stroke={INK_DARK} strokeWidth="1.1" opacity="0.8" />

    {/* the horn */}
    <path d={GL_HORN} fill="#ededed" />
    <Hatch id="gl-horn" region={GL_HORN} angle={74} spacing={4} width={0.8} opacity={0.8} />
    <Hatch id="gl-horn-s" region="M240 56 Q258 158 312 234 L240 234 Z" angle={-56} spacing={4.4} width={0.9} />
    {/* snow couloir: an unprinted ribbon down from the summit */}
    <path d="M240 56 L250 108 L243 168 L233 112 Z" fill="#ffffff" opacity="0.95" />
    {/* the glacier: unprinted ice with crevasse ticks */}
    <path d="M186 214 Q218 196 252 200 Q284 204 296 220 L300 234 L172 234 Z" fill="#ffffff" />
    <path d="M186 214 Q218 196 252 200 Q284 204 296 220 L300 234" fill="none" stroke={INK_DARK} strokeWidth="1.2" />
    <path d="M204 218 L212 228 M232 208 L238 222 M262 208 L266 222 M282 216 L288 226" stroke={INK_MID} strokeWidth="0.9" opacity="0.8" />
    <path d={GL_HORN} fill="none" stroke={INK_DARK} strokeWidth="2" />

    {/* lake: ruled water with the horn's broken reflection */}
    <path d="M0 234 L500 234 L500 320 L0 320 Z" fill="#fbfbfb" />
    <path d="M0 234 L500 234" stroke={INK_DARK} strokeWidth="1.3" />
    <Hatch id="gl-lake" region="M0 234 L500 234 L500 320 L0 320 Z" angle={0} spacing={4.6} width={0.7} color={INK_MID} opacity={0.7} />
    <path d="M226 240 L262 300 M244 240 L270 286 M262 240 L282 272" stroke={INK_DARK} strokeWidth="0.9" opacity="0.5" />
    <EngravedTree x={36} y={252} h={20} />
    <EngravedTree x={62} y={248} h={15} />
    <EngravedTree x={452} y={250} h={18} />
  </g>
);

/* --- ACADIA · Bass Harbor Head Light on its granite cliff --- */

const Acadia = () => (
  <g>
    <rect width="500" height="320" fill="#ffffff" />
    <SkyLines yTop={26} yBottom={196} sunX={110} sunY={70} sunR={19} />
    <Sun x={110} y={70} r={19} />
    <path d="M196 96 Q202 90 208 96 M208 96 Q214 90 220 96 M244 120 Q249 115 254 120 M254 120 Q259 115 264 120" stroke={INK_MID} strokeWidth="1" fill="none" />

    {/* granite headland from the right */}
    <path d="M500 320 L500 118 L446 124 L400 142 L372 168 L348 200 L336 240 L330 320 Z" fill="#e8e8e8" />
    <Hatch id="ac-cliff" region="M500 320 L500 118 L446 124 L400 142 L372 168 L348 200 L336 240 L330 320 Z" angle={18} spacing={3.8} width={0.9} />
    <path d="M500 118 L446 124 L400 142 L372 168 L348 200 L336 240 L330 320" fill="none" stroke={INK_DARK} strokeWidth="1.8" />
    {[418, 444, 470, 494].map((x, i) => (
      <EngravedTree key={x} x={x} y={128 + (i % 2) * 4} h={22} />
    ))}

    {/* the light: white tower, dark lantern, keeper's house */}
    <g>
      <path d="M372 166 L392 166 L388 108 L376 108 Z" fill="#ffffff" />
      <path d="M372 166 L392 166 L388 108 L376 108 Z" fill="none" stroke={INK_DARK} strokeWidth="1.4" />
      <path d="M375 128 L389 128 M374 148 L390 148" stroke={INK_MID} strokeWidth="0.8" />
      <rect x={373} y={100} width={18} height={8} fill={INK_DARK} />
      <polygon points="371,100 393,100 382,88" fill={INK_DARK} />
      <circle cx={382} cy={104} r={3.4} fill="#ffffff" />
      <path d="M371 102 L322 92 M371 106 L322 116" stroke={INK_MID} strokeWidth="0.7" opacity="0.7" />
      <path d="M392 166 L392 146 L410 146 L418 156 L418 166 Z" fill="#ffffff" stroke={INK_DARK} strokeWidth="1.2" />
    </g>

    {/* the sea: ruled swell with glints and surf at the rocks */}
    <path d="M0 200 L336 200 L330 320 L0 320 Z" fill="#fbfbfb" />
    <path d="M0 200 L348 200" stroke={INK_DARK} strokeWidth="1.3" />
    <Hatch id="ac-sea" region="M0 200 L336 200 L330 320 L0 320 Z" angle={0} spacing={4.2} width={0.7} color={INK_MID} opacity={0.75} />
    <path d="M24 226 L74 226 M120 250 L182 250 M60 278 L128 278 M210 236 L268 236 M180 302 L262 302" stroke="#ffffff" strokeWidth="4" opacity="0.9" />
    <path d="M320 214 Q334 206 348 212 M312 240 Q330 230 344 238 M304 268 Q326 258 342 268" stroke={INK_DARK} strokeWidth="1" fill="none" opacity="0.85" />
  </g>
);

/* ------------------------------------------------------------- registry */

const SCENES: Record<string, () => JSX.Element> = {
  yosemite: Yosemite,
  zion: Zion,
  "grand-canyon": GrandCanyon,
  yellowstone: Yellowstone,
  glacier: Glacier,
  "grand-teton": GrandTeton,
  "joshua-tree": JoshuaTree,
  acadia: Acadia,
};

export default function ParkArt({ slug }: { slug: string }) {
  const Scene =
    SCENES[slug] ??
    (() => (
      <g>
        <rect width="500" height="320" fill="#ffffff" />
        <SkyLines yTop={26} yBottom={270} sunX={100} sunY={70} sunR={20} />
        <Sun x={100} y={70} r={20} />
        <path d="M0 282 L160 120 L320 282 Z" fill="#ededed" stroke={INK_DARK} strokeWidth="2" />
        <GroundBand yTop={282} id="fallback-g" />
      </g>
    ));
  return (
    <Stamp slug={slug}>
      <Scene />
    </Stamp>
  );
}
