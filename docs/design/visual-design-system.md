# Secure SSI Platform visual design system

This file documents the implemented shared tokens in `apps/web/src/visual-refresh.css` and their consumers. It is a dark, high-contrast **Civic Night** system for a multi-role academic prototype.

## Color tokens

| Token | Value | Use |
|---|---|---|
| `--bg-app` | `#0b1220` | Main application canvas |
| `--bg-surface` | `#121e2d` | Header, cards, role workspaces |
| `--bg-surface-elevated` | `#192a3d` | Nested surfaces and panels |
| `--bg-subtle` | `#203349` | Prototype notice and low-emphasis surfaces |
| `--bg-input` | `#091522` | Inputs and role switcher |
| `--border-default` | `#2b3e54` | Standard separators |
| `--border-subtle` | `#3d526b` | Scrollbar thumb and stronger secondary borders |
| `--border-accent` | `#5689e8` | Focus/selected accents |
| `--color-primary` | `#326acb` | Primary action and active brand marker |
| `--color-primary-hover` | `#2a5db4` | Primary action hover |
| `--color-accent` | `#62d2be` | Secondary trust accent |
| `--color-success` | `#1da784` | Success semantics |
| `--color-warning` | `#d9a441` | Warning semantics |
| `--color-danger` | `#df5d66` | Error and destructive semantics |
| `--color-info` | `#57a9d6` | Informational status |
| `--text-main` | `#f3f6fa` | Primary text |
| `--text-secondary` | `#d3dce7` | Supporting text |
| `--text-muted` | `#aab7c7` | Descriptions and labels |
| `--text-tertiary` | `#8495a9` | Lower-emphasis metadata |
| `--text-mono-accent` | `#81d4e6` | Technical identifiers |
| `--focus-ring` | `#8ce0cf` | Keyboard focus outline |

Status labels remain textual and keep their semantic icon/label treatment. A color is not the only status signal.

## Typography and layout

- Sans: `ui-sans-serif`, system UI, platform-native fallbacks. No remote font request is required.
- Monospace: platform monospace fallbacks for DIDs, hashes, and protocol values.
- Public hero title: responsive `clamp()` scale, balanced wrapping, and a smaller mobile scale.
- Shared content gutter: `--content-gutter`, responsive from 16 px to 32 px.
- Panel radius: `--radius-panel` (14 px); controls: `--radius-control` (9 px).
- Mobile/tablet navigation moves below the brand row, remains horizontally scrollable, and keeps each link at least 40 px high. The role portal layouts continue to use their existing responsive structures.

## Shared components and states

The tokens are used by the root shell, prototype banner, top navigation, role switcher, public footer, holder navigation, institutional workspace surfaces, existing shared form/panel classes, visible focus outlines, and scrollbar treatment. Motion is reduced when `prefers-reduced-motion: reduce` is active.

The project still uses a Tailwind CDN because existing screens contain Tailwind utility classes and the package does not include a local Tailwind build. Removing that runtime dependency safely needs a separate build-tool migration; the web-font CDN was removed in this visual pass.

