# The Movie Database (TMDB) Brand Guidelines & Attribution

Any application, website, or service utilizing data or images provided by The Movie Database (TMDB) is required to properly attribute TMDB as the source in accordance with their terms of use.

---

## 1. Required Attribution Statement

When using TMDB APIs, data, or image assets, you must display an official TMDB logo and include the following disclaimer in a visible location (such as an "About" page, app footer, or settings view):

> **"This product uses the TMDB API but is not endorsed or certified by TMDB."**

---

## 2. Brand Color Palette

TMDB utilizes a distinct color palette across their brand assets and primary interface elements.

| Color Role | Name | Hex Code | RGB Values | Usage / Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Primary** | Dark Blue | `#0d253f` | `RGB(13, 37, 63)` | Base background and main branding elements |
| **Secondary** | Light Blue | `#01b4e4` | `RGB(1, 180, 228)` | Accent buttons, active states, highlights |
| **Tertiary** | Light Green | `#90cea1` | `RGB(144, 206, 161)` | Secondary accents, success indicators, gradients |

### Color Swatches (CSS Reference)

```css
:root {
  --tmdb-primary-dark-blue: #0d253f;
  --tmdb-secondary-light-blue: #01b4e4;
  --tmdb-tertiary-light-green: #90cea1;
}
```

---

## 3. Logo & Badge Usage Guidelines

- **Do:** Use official, unaltered TMDB logos provided by TMDB.
- **Do:** Ensure adequate spacing and contrast around the logo relative to background colors.
- **Don't:** Modify logo colors, stretch, skew, or obscure the logo.
- **Don't:** Imply official partnership, endorsement, or certification by TMDB in your branding or messaging.