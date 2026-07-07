# Varian Rumao — Personal Portfolio

A modern, responsive developer portfolio built with vanilla HTML, CSS, and JavaScript. Features a live dashboard that fetches all my repositories from the GitHub API in real-time.

🌐 **Live site:** [varianrumao.com](https://varianrumao.com)

---

## ✨ Features

- 📊 **Live GitHub Dashboard** — Repos load dynamically from the GitHub API with stats (stars, forks, languages)
- 🎯 **Language Filtering** — Filter projects by programming language
- ⚡ **Smart Caching** — 30-minute `localStorage` cache to be efficient with API calls
- 🛡️ **Fallback Mode** — If the API is unavailable, a curated repo list is shown
- 📱 **Fully Responsive** — Looks great on mobile, tablet, and desktop
- 🎨 **Custom Design** — Dark, terminal-inspired aesthetic with smooth animations
- ♿ **Accessible** — Semantic HTML and good color contrast

---

## 📁 Project Structure

```
.
├── index.html          # Main HTML structure
├── css/
│   └── styles.css      # All styling (~600 lines)
├── js/
│   └── main.js         # GitHub API logic, animations, filters
├── CNAME               # Custom domain config for GitHub Pages
└── README.md           # This file
```

---

## 🚀 Local Development

No build process needed. Just open `index.html` in your browser.

```bash
# Clone the repo
git clone https://github.com/VarianRumao/VarianRumao.github.io.git
cd VarianRumao.github.io

# Option 1: Open directly
open index.html

# Option 2: Run a local server (recommended for testing API calls)
python3 -m http.server 8000
# Then visit http://localhost:8000
```

---

## 🛠️ Tech Stack

- **HTML5** — Semantic, accessible markup
- **CSS3** — Custom properties, Grid, Flexbox, animations
- **Vanilla JavaScript** — No frameworks, no build step
- **GitHub REST API** — `api.github.com/users/VarianRumao/repos`
- **Google Fonts** — Bricolage Grotesque, Manrope, JetBrains Mono

---

## 🌐 Deployment

This site is hosted for free on **GitHub Pages** with a custom domain.

Any push to the `main` branch automatically deploys to [varianrumao.com](https://varianrumao.com) within a minute.

---

## 📬 Contact

- **Email:** varianrumao@gmail.com
- **LinkedIn:** [linkedin.com/in/varian-rumao-9496921b2](https://www.linkedin.com/in/varian-rumao-9496921b2/)
- **GitHub:** [@VarianRumao](https://github.com/VarianRumao)

---

© Varian Rumao — Built with ❤️ in Sydney
