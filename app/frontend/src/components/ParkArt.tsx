/**
 * ParkArt — hand-drawn, WPA-travel-poster-style SVG scenes, one per park.
 *
 * Each scene is flat layered silhouettes over a dusk/dawn gradient with a
 * paper-grain overlay, in a palette chosen per park. No external images —
 * everything renders offline and scales crisply at any size.
 */

interface SceneColors {
  skyTop: string;
  skyBottom: string;
  sun: string;
  sunRing?: string;
}

function Frame({
  colors,
  children,
  sunX = 350,
  sunY = 92,
  sunR = 34,
}: {
  colors: SceneColors;
  children: React.ReactNode;
  sunX?: number;
  sunY?: number;
  sunR?: number;
}) {
  // Unique-enough gradient ids so multiple posters coexist in one DOM.
  const gid = `sky-${colors.skyTop.slice(1)}-${colors.skyBottom.slice(1)}`;
  return (
    <svg viewBox="0 0 500 320" preserveAspectRatio="xMidYMid slice" role="img" className="park-art">
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={colors.skyTop} />
          <stop offset="100%" stopColor={colors.skyBottom} />
        </linearGradient>
        <filter id="grain">
          <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" stitchTiles="stitch" />
          <feColorMatrix type="saturate" values="0" />
          <feComponentTransfer>
            <feFuncA type="linear" slope="0.06" />
          </feComponentTransfer>
          <feComposite operator="over" in2="SourceGraphic" />
        </filter>
      </defs>
      <rect width="500" height="320" fill={`url(#${gid})`} />
      {colors.sunRing && (
        <circle cx={sunX} cy={sunY} r={sunR + 12} fill="none" stroke={colors.sunRing} strokeWidth="3" opacity="0.5" />
      )}
      <circle cx={sunX} cy={sunY} r={sunR} fill={colors.sun} />
      {children}
      <rect width="500" height="320" filter="url(#grain)" opacity="0.5" fill="transparent" />
    </svg>
  );
}

/* ---------------------------------------------------------------- scenes */

function Conifers({ y, color, xs }: { y: number; color: string; xs: number[] }) {
  return (
    <g fill={color}>
      {xs.map((x, i) => {
        const h = 26 + ((i * 7) % 12);
        return (
          <g key={i}>
            <polygon points={`${x},${y - h} ${x - 9},${y} ${x + 9},${y}`} />
            <polygon points={`${x},${y - h - 12} ${x - 7},${y - h + 8} ${x + 7},${y - h + 8}`} />
          </g>
        );
      })}
    </g>
  );
}

const Yosemite = () => (
  <Frame colors={{ skyTop: "#f9c74f", skyBottom: "#f3722c", sun: "#fff3b0", sunRing: "#fff3b0" }} sunX={330} sunY={84}>
    {/* Half Dome */}
    <path d="M280 320 L280 150 Q300 96 352 92 L380 96 L380 320 Z" fill="#8a5a63" />
    <path d="M280 320 L280 150 Q290 110 316 98 L322 320 Z" fill="#6e4552" />
    {/* El Capitan wall */}
    <path d="M0 320 L0 60 L96 78 L140 128 L150 320 Z" fill="#5c374c" />
    <path d="M0 320 L0 60 L52 68 L72 320 Z" fill="#472b3f" />
    {/* valley haze + floor */}
    <rect y="252" width="500" height="68" fill="#f9844a" opacity="0.45" />
    <path d="M0 320 L0 286 Q160 258 320 282 Q430 296 500 280 L500 320 Z" fill="#31572c" />
    <Conifers y={300} color="#132a13" xs={[40, 78, 118, 210, 250, 292, 420, 462]} />
    {/* waterfall on El Cap shoulder */}
    <path d="M96 78 L100 78 L104 208 L98 208 Z" fill="#ffe8d6" opacity="0.85" />
  </Frame>
);

const Zion = () => (
  <Frame colors={{ skyTop: "#ffe8d6", skyBottom: "#ffb385", sun: "#fff1e6" }} sunX={250} sunY={78} sunR={30}>
    {/* far wall */}
    <path d="M120 320 L140 96 Q160 60 190 62 Q224 64 238 110 L260 320 Z" fill="#e07a5f" />
    {/* left canyon wall */}
    <path d="M0 320 L0 40 L60 34 Q110 40 122 96 L150 220 L160 320 Z" fill="#c1512f" />
    <path d="M0 320 L0 40 L34 36 L62 160 L78 320 Z" fill="#9c3b22" />
    {/* right canyon wall */}
    <path d="M500 320 L500 24 L430 30 Q382 44 372 104 L350 230 L340 320 Z" fill="#b04528" />
    <path d="M500 320 L500 24 L468 28 L440 170 L426 320 Z" fill="#83301a" />
    {/* strata lines */}
    <g stroke="#f4a261" strokeWidth="3" opacity="0.35">
      <path d="M0 92 L118 100" fill="none" />
      <path d="M0 150 L140 160" fill="none" />
      <path d="M382 96 L500 88" fill="none" />
      <path d="M362 170 L500 158" fill="none" />
    </g>
    {/* river + cottonwoods */}
    <path d="M0 320 L0 296 Q150 282 250 292 Q380 302 500 290 L500 320 Z" fill="#606c38" />
    <path d="M228 320 Q242 300 250 278 Q258 300 272 320 Z" fill="#94b0a2" opacity="0.9" />
    <circle cx="130" cy="290" r="14" fill="#283618" />
    <circle cx="386" cy="286" r="16" fill="#283618" />
  </Frame>
);

const GrandCanyon = () => (
  <Frame colors={{ skyTop: "#ffe5b4", skyBottom: "#f4978e", sun: "#fff8e7", sunRing: "#fff8e7" }} sunX={128} sunY={70} sunR={30}>
    {/* receding mesa layers */}
    <path d="M0 320 L0 176 L70 172 L92 148 L170 152 L198 176 L290 172 L318 148 L400 152 L428 176 L500 170 L500 320 Z" fill="#c9704a" />
    <path d="M0 320 L0 214 L88 210 L120 190 L214 194 L246 216 L338 210 L372 192 L452 196 L500 212 L500 320 Z" fill="#a34f2a" />
    <path d="M0 320 L0 252 L106 248 L142 230 L240 234 L280 254 L376 248 L416 232 L500 238 L500 320 Z" fill="#7d3216" />
    <path d="M0 320 L0 288 L130 284 L170 268 L272 272 L316 290 L420 284 L500 274 L500 320 Z" fill="#521e10" />
    {/* inner gorge notch */}
    <path d="M228 320 L246 260 L262 260 L284 320 Z" fill="#2f1008" />
    {/* haze bands */}
    <rect y="180" width="500" height="10" fill="#ffe5b4" opacity="0.25" />
    <rect y="220" width="500" height="8" fill="#ffe5b4" opacity="0.18" />
  </Frame>
);

const Yellowstone = () => (
  <Frame colors={{ skyTop: "#cfe1b9", skyBottom: "#a3b18a", sun: "#f7f3d7" }} sunX={396} sunY={74} sunR={28}>
    {/* distant ridge */}
    <path d="M0 320 L0 170 L120 128 L240 168 L360 132 L500 172 L500 320 Z" fill="#588157" />
    {/* geyser plume */}
    <path d="M236 236 Q228 180 244 130 Q252 100 240 66 Q268 90 262 130 Q288 108 282 74 Q300 112 280 152 Q272 200 268 236 Z" fill="#f8f9f5" opacity="0.95" />
    <ellipse cx="252" cy="242" rx="52" ry="12" fill="#e9f5ea" />
    {/* terrace pools */}
    <path d="M0 320 L0 262 Q120 246 252 254 Q390 262 500 250 L500 320 Z" fill="#d4a373" />
    <ellipse cx="150" cy="276" rx="46" ry="9" fill="#5fa8d3" />
    <ellipse cx="150" cy="276" rx="30" ry="6" fill="#89c2d9" />
    <ellipse cx="366" cy="284" rx="54" ry="10" fill="#e76f51" />
    <ellipse cx="366" cy="284" rx="36" ry="7" fill="#f4a261" />
    <Conifers y={258} color="#1d3b2a" xs={[36, 70, 452, 484]} />
    <path d="M0 320 L0 306 Q250 294 500 306 L500 320 Z" fill="#344e41" />
  </Frame>
);

const Glacier = () => (
  <Frame colors={{ skyTop: "#bde0fe", skyBottom: "#ffc8dd", sun: "#fff9ec" }} sunX={112} sunY={86} sunR={26}>
    {/* jagged range */}
    <path d="M0 320 L0 210 L56 128 L102 186 L150 84 L208 190 L242 140 L286 196 L318 96 L382 200 L430 150 L500 208 L500 320 Z" fill="#31465f" />
    <path d="M0 320 L0 210 L56 128 L88 170 L60 210 L120 320 Z" fill="#22303f" />
    {/* snow caps */}
    <path d="M150 84 L172 124 L150 118 L134 128 Z" fill="#f4f7fb" />
    <path d="M318 96 L338 134 L318 128 L300 138 Z" fill="#f4f7fb" />
    <path d="M56 128 L70 154 L56 148 L44 158 Z" fill="#f4f7fb" />
    {/* lake with reflection */}
    <path d="M0 320 L0 250 Q250 234 500 250 L500 320 Z" fill="#5b8bb0" />
    <path d="M118 250 L150 320 L104 320 Z" fill="#31465f" opacity="0.35" />
    <path d="M300 250 L330 320 L282 320 Z" fill="#31465f" opacity="0.3" />
    <Conifers y={252} color="#1b3a2f" xs={[452, 480, 424]} />
  </Frame>
);

const GrandTeton = () => (
  <Frame colors={{ skyTop: "#ffb5a7", skyBottom: "#b5838d", sun: "#ffe5d9", sunRing: "#ffe5d9" }} sunX={382} sunY={78} sunR={30}>
    {/* the three spires straight off the flats */}
    <path d="M0 320 L0 236 L70 168 L120 226 L176 92 L226 208 L268 64 L318 200 L364 122 L420 224 L500 232 L500 320 Z" fill="#4a4e69" />
    <path d="M176 92 L196 140 L176 132 L158 146 Z" fill="#f2e9e4" />
    <path d="M268 64 L292 122 L268 112 L246 126 Z" fill="#f2e9e4" />
    <path d="M364 122 L380 158 L364 150 L348 162 Z" fill="#f2e9e4" />
    <path d="M0 320 L0 236 L70 168 L100 210 L60 320 Z" fill="#22223b" />
    {/* sage flats + winding river */}
    <path d="M0 320 L0 268 Q250 254 500 268 L500 320 Z" fill="#6b705c" />
    <path d="M0 300 Q120 292 190 300 Q260 308 320 298 Q420 286 500 296 L500 308 Q400 300 322 310 Q252 318 182 310 Q110 302 0 312 Z" fill="#a9c5d3" />
  </Frame>
);

/** Spiky yucca-tuft star polygon, precomputed per call (deterministic). */
function tuftPoints(cx: number, cy: number, rOuter = 16, rInner = 7, spikes = 9): string {
  const pts: string[] = [];
  for (let i = 0; i < spikes * 2; i++) {
    const r = i % 2 === 0 ? rOuter : rInner;
    const a = (Math.PI * i) / spikes - Math.PI / 2;
    pts.push(`${(cx + r * Math.cos(a)).toFixed(1)},${(cy + r * Math.sin(a)).toFixed(1)}`);
  }
  return pts.join(" ");
}

const JoshuaTree = () => (
  <Frame colors={{ skyTop: "#ffba08", skyBottom: "#e85d04", sun: "#fff5d6", sunRing: "#fff5d6" }} sunX={250} sunY={100} sunR={44}>
    {/* stacked monzogranite piles */}
    <g fill="#a9714b">
      <rect x="20" y="216" width="76" height="52" rx="24" />
      <rect x="58" y="186" width="60" height="44" rx="20" />
      <rect x="30" y="246" width="110" height="48" rx="22" />
      <rect x="384" y="210" width="82" height="54" rx="26" />
      <rect x="420" y="180" width="56" height="42" rx="20" />
      <rect x="372" y="244" width="112" height="50" rx="24" />
    </g>
    <g fill="#7f5539">
      <rect x="44" y="262" width="84" height="40" rx="18" />
      <rect x="396" y="258" width="86" height="42" rx="19" />
    </g>
    {/* desert floor */}
    <path d="M0 320 L0 282 Q250 268 500 282 L500 320 Z" fill="#bc6c25" />
    {/* joshua tree silhouette — thick trunk, two arms, spiky tufts */}
    <g fill="#2b2118">
      <path d="M231 320 L234 250 Q236 236 240 230 Q244 236 246 250 L251 320 Z" />
      <path d="M238 246 Q220 234 212 212 L202 190 L214 184 L224 206 Q232 222 242 232 Z" />
      <path d="M240 246 Q258 232 264 210 L272 190 L284 196 L274 216 Q264 234 246 234 Z" />
      <polygon points={tuftPoints(206, 182)} />
      <polygon points={tuftPoints(281, 188)} />
      <polygon points={tuftPoints(240, 222, 13, 6, 8)} />
      {/* a distant companion tree */}
      <path d="M348 300 L350 268 Q351 262 353 260 Q355 262 356 268 L358 300 Z" />
      <polygon points={tuftPoints(353, 256, 10, 4.5, 8)} />
    </g>
  </Frame>
);

const Acadia = () => (
  <Frame colors={{ skyTop: "#cfe8ef", skyBottom: "#f6bd60", sun: "#fff8e1" }} sunX={140} sunY={82} sunR={30}>
    {/* rounded pink-granite summit (Cadillac) */}
    <path d="M500 320 L500 120 Q430 96 366 130 L330 172 L318 320 Z" fill="#b0847a" />
    <path d="M500 320 L500 120 Q456 106 420 122 L432 320 Z" fill="#8d6258" />
    {/* sea */}
    <path d="M0 320 L0 226 Q170 216 330 226 L318 320 Z" fill="#1d6a96" />
    <path d="M0 320 L0 262 Q160 252 320 264 L318 320 Z" fill="#134b6b" />
    {/* headland with lighthouse */}
    <path d="M0 320 L0 190 L96 182 L148 206 L170 232 L150 320 Z" fill="#3e5641" />
    <g>
      <rect x="86" y="132" width="22" height="52" fill="#f4f1ea" />
      <rect x="86" y="150" width="22" height="12" fill="#c1512f" />
      <rect x="82" y="126" width="30" height="8" fill="#33312e" />
      <polygon points="88,126 106,126 97,112" fill="#33312e" />
      <circle cx="97" cy="121" r="4" fill="#ffd166" />
    </g>
    {/* surf + gulls */}
    <path d="M154 236 Q200 230 240 236 Q280 242 318 238" stroke="#e9f5f2" strokeWidth="4" fill="none" opacity="0.7" />
    <g stroke="#3d405b" strokeWidth="3" fill="none" strokeLinecap="round">
      <path d="M224 96 Q232 88 240 96 M240 96 Q248 88 256 96" />
      <path d="M280 130 Q286 124 292 130 M292 130 Q298 124 304 130" />
    </g>
    <Conifers y={208} color="#22331f" xs={[24, 52, 128]} />
  </Frame>
);

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
  const Scene = SCENES[slug];
  if (!Scene) {
    // Unknown park: generic peaks fallback.
    return (
      <Frame colors={{ skyTop: "#bde0fe", skyBottom: "#ffc8dd", sun: "#fff9ec" }}>
        <path d="M0 320 L0 220 L120 120 L240 220 L360 130 L500 230 L500 320 Z" fill="#31465f" />
      </Frame>
    );
  }
  return <Scene />;
}
