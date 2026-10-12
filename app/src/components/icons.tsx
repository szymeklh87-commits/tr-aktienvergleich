/* Schlichte Linien-Icons (24 px Raster, 1.75 px Strich). Dekorativ → aria-hidden. */

const base = {
  width: 24,
  height: 24,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.75,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': true,
  focusable: false,
} as const;

export const IconStart = () => (
  <svg {...base}>
    <path d="M4 11.5 12 5l8 6.5" />
    <path d="M6.5 10v9h11v-9" />
  </svg>
);

/** Rendite-Leiter: senkrechte Sprossen unterschiedlicher Länge. */
export const IconLadder = () => (
  <svg {...base}>
    <path d="M5 4v16" />
    <path d="M5 7h13M5 11h9M5 15h11M5 19h6" />
  </svg>
);

export const IconRanking = () => (
  <svg {...base}>
    <path d="M4 6h3M4 12h3M4 18h3" />
    <path d="M10 6h10M10 12h7M10 18h4" />
  </svg>
);

export const IconFrequency = () => (
  <svg {...base}>
    <rect x="4" y="4" width="4" height="4" rx="1" />
    <rect x="10" y="4" width="4" height="4" rx="1" />
    <rect x="16" y="4" width="4" height="4" rx="1" />
    <rect x="4" y="10" width="4" height="4" rx="1" />
    <rect x="10" y="10" width="4" height="4" rx="1" />
    <rect x="4" y="16" width="4" height="4" rx="1" />
  </svg>
);

export const IconGrid = () => (
  <svg {...base}>
    <rect x="3.5" y="3.5" width="7.5" height="7.5" rx="1.5" />
    <rect x="13" y="3.5" width="7.5" height="7.5" rx="1.5" />
    <rect x="3.5" y="13" width="7.5" height="7.5" rx="1.5" />
    <path d="M14 19l2.2-3 2 2 2.3-4" />
  </svg>
);

export const IconMore = () => (
  <svg {...base}>
    <path d="M4 7h16M4 12h16M4 17h16" />
  </svg>
);

export const IconClose = () => (
  <svg {...base}>
    <path d="M6 6l12 12M18 6 6 18" />
  </svg>
);

export const IconCopy = () => (
  <svg {...base}>
    <rect x="8.5" y="8.5" width="11" height="11" rx="2" />
    <path d="M15.5 8.5V6a1.5 1.5 0 0 0-1.5-1.5H6A1.5 1.5 0 0 0 4.5 6v8A1.5 1.5 0 0 0 6 15.5h2.5" />
  </svg>
);

export const IconCheck = () => (
  <svg {...base}>
    <path d="M5 12.5l4.5 4.5L19 7.5" />
  </svg>
);

export const IconBack = () => (
  <svg {...base}>
    <path d="M14.5 5.5 8 12l6.5 6.5" />
  </svg>
);

export const IconChevron = ({ open = false }: { open?: boolean }) => (
  <svg {...base} style={{ transform: open ? 'rotate(180deg)' : undefined, transition: 'transform 120ms' }}>
    <path d="M6.5 9.5 12 15l5.5-5.5" />
  </svg>
);

export const IconStar = ({ filled = false }: { filled?: boolean }) => (
  <svg {...base} fill={filled ? 'currentColor' : 'none'}>
    <path d="M12 4.2l2.4 4.9 5.4.8-3.9 3.8.9 5.4L12 16.6l-4.8 2.5.9-5.4-3.9-3.8 5.4-.8z" />
  </svg>
);

export const IconDownload = () => (
  <svg {...base}>
    <path d="M12 4v11M7.5 10.5 12 15l4.5-4.5M5 19.5h14" />
  </svg>
);

export const IconPlus = () => (
  <svg {...base}>
    <path d="M12 5v14M5 12h14" />
  </svg>
);

export const IconMinus = () => (
  <svg {...base}>
    <path d="M5 12h14" />
  </svg>
);

export const IconReset = () => (
  <svg {...base}>
    <path d="M5 12a7 7 0 1 0 2.1-5" />
    <path d="M5 4.5V8h3.5" />
  </svg>
);

export const IconInfo = () => (
  <svg {...base}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 11v5M12 8h.01" />
  </svg>
);
