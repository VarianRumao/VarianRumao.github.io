/* ===========================================================
   Varian Rumao — Portfolio Website JavaScript
   ===========================================================
   Handles:
   - Year auto-update in footer
   - Scroll reveal animations (IntersectionObserver)
   - Live GitHub repository fetching with 30-min localStorage cache
   - Fallback repo list (if GitHub API fails or rate-limits)
   - Language filter chips (auto-generated from data)
   - Manual refresh button (clears cache & refetches)
   =========================================================== */

document.getElementById('year').textContent = new Date().getFullYear();

// Scroll reveal
const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('visible');
      observer.unobserve(entry.target);
    }
  });
}, { threshold: 0.1 });
document.querySelectorAll('.reveal').forEach(el => observer.observe(el));

// ============================================================
// CONFIG
// ============================================================
const USERNAME = 'VarianRumao';
const CACHE_KEY = `gh_${USERNAME}_v3`;
const CACHE_TTL = 30 * 60 * 1000; // 30 minutes

// ============================================================
// FALLBACK REPOS — ensures the site always shows your work,
// even if GitHub API fails or rate-limits.
// ============================================================
const FALLBACK_REPOS = [
  {
    name: 'VR-journal',
    html_url: 'https://github.com/VarianRumao/VR-journal',
    description: 'Academic journal documenting weekly progress, reflections, and learnings throughout my Master of IT at CQU.',
    language: 'HTML',
    stargazers_count: 0,
    forks_count: 0,
    pushed_at: new Date().toISOString(),
    topics: ['journal', 'academic', 'cqu'],
    fork: false
  },
  {
    name: 'Cinematographers_Connect',
    html_url: 'https://github.com/VarianRumao/Cinematographers_Connect',
    description: 'A networking platform connecting cinematographers, filmmakers, and industry professionals — built as a full-stack web application.',
    language: 'JavaScript',
    stargazers_count: 0,
    forks_count: 0,
    pushed_at: new Date().toISOString(),
    topics: ['networking', 'fullstack', 'community'],
    fork: false
  },
  {
    name: 'SSB-Smart-System-For-Blind',
    html_url: 'https://github.com/VarianRumao/SSB-Smart-System-For-Blind',
    description: 'Smart Glasses to help visually impaired people navigate. Includes a smart cap that prevents heat stroke via early notification. Published research.',
    language: 'Jupyter Notebook',
    stargazers_count: 4,
    forks_count: 0,
    pushed_at: '2024-06-01T00:00:00Z',
    topics: ['iot', 'arduino', 'machine-learning', 'accessibility'],
    fork: false
  },
  {
    name: 'Martial-arts-website',
    html_url: 'https://github.com/VarianRumao/Martial-arts-website',
    description: 'Responsive website for a martial arts academy — featuring class schedules, instructor profiles, and online enrolment.',
    language: 'PHP',
    stargazers_count: 1,
    forks_count: 0,
    pushed_at: '2023-08-15T00:00:00Z',
    topics: ['web', 'php', 'bootstrap'],
    fork: false
  },
  {
    name: 'patientmonitorsys',
    html_url: 'https://github.com/VarianRumao/patientmonitorsys',
    description: 'A patient monitoring system built in Java for tracking vitals, medication schedules, and alerting medical staff in real-time.',
    language: 'Java',
    stargazers_count: 0,
    forks_count: 0,
    pushed_at: '2023-05-20T00:00:00Z',
    topics: ['healthcare', 'java', 'monitoring'],
    fork: false
  },
  {
    name: 'snakepy',
    html_url: 'https://github.com/VarianRumao/snakepy',
    description: 'A classic snake game implemented in Python using Pygame — featuring score tracking and increasing difficulty.',
    language: 'Python',
    stargazers_count: 1,
    forks_count: 0,
    pushed_at: '2022-11-10T00:00:00Z',
    topics: ['game', 'pygame', 'python'],
    fork: false
  },
  {
    name: 'fitnessapp',
    html_url: 'https://github.com/VarianRumao/fitnessapp',
    description: 'A fitness tracking application to log workouts, track progress, and set personal goals.',
    language: 'JavaScript',
    stargazers_count: 0,
    forks_count: 0,
    pushed_at: '2022-09-15T00:00:00Z',
    topics: ['fitness', 'tracker'],
    fork: false
  }
];

const LANG_COLORS = {
  'JavaScript': '#f1e05a', 'TypeScript': '#3178c6', 'Python': '#3572A5',
  'Java': '#b07219', 'HTML': '#e34c26', 'CSS': '#563d7c', 'SCSS': '#c6538c',
  'PHP': '#4F5D95', 'Jupyter Notebook': '#DA5B0B', 'C++': '#f34b7d',
  'C': '#555555', 'Shell': '#89e051', 'Go': '#00ADD8', 'Ruby': '#701516',
  'Vue': '#41b883', 'Dart': '#00B4AB', 'Kotlin': '#A97BFF',
  'Swift': '#F05138', 'Rust': '#dea584'
};

const ICONS = {
  repo: '<svg class="repo-icon" viewBox="0 0 16 16" fill="currentColor"><path d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z"/></svg>',
  star: '<svg viewBox="0 0 16 16" width="13" height="13" fill="currentColor"><path d="M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.75.75 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Z"/></svg>',
  fork: '<svg viewBox="0 0 16 16" width="13" height="13" fill="currentColor"><path d="M5 5.372v.878c0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75v-.878a2.25 2.25 0 1 1 1.5 0v.878a2.25 2.25 0 0 1-2.25 2.25h-1.5v2.128a2.251 2.251 0 1 1-1.5 0V8.5h-1.5A2.25 2.25 0 0 1 3.5 6.25v-.878a2.25 2.25 0 1 1 1.5 0ZM5 3.25a.75.75 0 1 0-1.5 0 .75.75 0 0 0 1.5 0Zm6.75.75a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm-3 8.75a.75.75 0 1 0-1.5 0 .75.75 0 0 0 1.5 0Z"/></svg>',
  clock: '<svg viewBox="0 0 16 16" width="13" height="13" fill="currentColor"><path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Zm7-3.25v2.992l2.028.812a.75.75 0 0 1-.557 1.392l-2.5-1A.751.751 0 0 1 7 8.25v-3.5a.75.75 0 0 1 1.5 0Z"/></svg>'
};

function timeAgo(dateStr) {
  const d = new Date(dateStr);
  const diff = Math.floor((Date.now() - d.getTime()) / 1000);
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
  if (diff < 2592000) return `${Math.floor(diff/86400)}d ago`;
  if (diff < 31536000) return `${Math.floor(diff/2592000)}mo ago`;
  return `${Math.floor(diff/31536000)}y ago`;
}

function escapeHtml(s) {
  if (!s) return '';
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function renderRepoCard(repo) {
  const lang = repo.language;
  const color = LANG_COLORS[lang] || '#888';
  const desc = repo.description
    ? `<p class="repo-desc">${escapeHtml(repo.description)}</p>`
    : `<p class="repo-desc empty">No description provided.</p>`;
  const langPill = lang
    ? `<span class="lang-pill"><span class="lang-dot" style="background:${color}"></span>${escapeHtml(lang)}</span>`
    : '';
  const topicsPills = (repo.topics || []).slice(0, 3).map(t =>
    `<span class="lang-pill" style="background:rgba(0,255,163,0.06);border-color:rgba(0,255,163,0.2);color:var(--accent)">#${escapeHtml(t)}</span>`
  ).join('');
  return `
    <a class="repo-card" href="${escapeHtml(repo.html_url)}" target="_blank" rel="noopener" data-lang="${escapeHtml(lang || 'Other')}">
      <div class="repo-header">
        <div class="repo-name">${escapeHtml(repo.name)}</div>
        ${ICONS.repo}
      </div>
      ${desc}
      <div class="repo-langs">${langPill}${topicsPills}</div>
      <div class="repo-meta">
        <span class="repo-meta-item">${ICONS.star} ${repo.stargazers_count || 0}</span>
        <span class="repo-meta-item">${ICONS.fork} ${repo.forks_count || 0}</span>
        <span class="repo-meta-item" style="margin-left:auto">${ICONS.clock} ${timeAgo(repo.pushed_at)}</span>
      </div>
    </a>
  `;
}

function render(repos, source) {
  const grid = document.getElementById('repo-grid');
  const banner = document.getElementById('source-banner');

  if (!repos || repos.length === 0) {
    grid.innerHTML = `<div class="error-state">No repositories found.</div>`;
    return;
  }

  const own = repos.filter(r => !r.fork);

  own.sort((a, b) => {
    const sa = (a.description ? 1 : 0) * 10 + (a.stargazers_count || 0);
    const sb = (b.description ? 1 : 0) * 10 + (b.stargazers_count || 0);
    if (sb !== sa) return sb - sa;
    return new Date(b.pushed_at) - new Date(a.pushed_at);
  });

  const totalStars = own.reduce((s, r) => s + (r.stargazers_count || 0), 0);
  const totalForks = own.reduce((s, r) => s + (r.forks_count || 0), 0);
  const langs = new Set(own.map(r => r.language).filter(Boolean));

  document.getElementById('stat-repos').textContent = own.length;
  document.getElementById('stat-stars').textContent = totalStars;
  document.getElementById('stat-langs').textContent = langs.size;
  document.getElementById('stat-forks').textContent = totalForks;

  const filterBar = document.getElementById('filter-bar');
  filterBar.querySelectorAll('.chip:not([data-filter="all"])').forEach(b => b.remove());
  [...langs].sort().forEach(lang => {
    const btn = document.createElement('button');
    btn.className = 'chip';
    btn.dataset.filter = lang;
    btn.textContent = lang;
    filterBar.appendChild(btn);
  });

  grid.innerHTML = own.map(renderRepoCard).join('');

  if (source === 'live') {
    banner.className = 'source-banner live';
    banner.textContent = `Live from GitHub API · ${own.length} repos · updated ${new Date().toLocaleTimeString()}`;
  } else if (source === 'cache') {
    banner.className = 'source-banner';
    banner.textContent = `Loaded from cache · click Refresh to fetch latest from GitHub`;
  } else {
    banner.className = 'source-banner';
    banner.textContent = `Showing curated highlights · click Refresh to try GitHub API`;
  }
}

async function fetchFromGitHub() {
  console.log('[Portfolio] Fetching from GitHub API...');
  const res = await fetch(`https://api.github.com/users/${USERNAME}/repos?per_page=100&sort=updated&type=public`);
  console.log('[Portfolio] Response status:', res.status);
  if (!res.ok) {
    if (res.status === 403) throw new Error('GitHub API rate limit reached. Try again in an hour.');
    throw new Error(`GitHub API returned ${res.status}`);
  }
  const data = await res.json();
  if (!Array.isArray(data)) throw new Error('Unexpected response from GitHub');
  console.log('[Portfolio] Got', data.length, 'repos from GitHub.');
  return data;
}

async function loadRepos(forceFresh = false) {
  const grid = document.getElementById('repo-grid');
  const refreshBtn = document.getElementById('refresh-btn');
  refreshBtn.classList.add('spinning');
  grid.innerHTML = `<div class="loading-state"><span class="spinner"></span>Fetching repositories from GitHub…</div>`;

  if (!forceFresh) {
    try {
      const cached = localStorage.getItem(CACHE_KEY);
      if (cached) {
        const parsed = JSON.parse(cached);
        if (parsed && parsed.t && Date.now() - parsed.t < CACHE_TTL && Array.isArray(parsed.d) && parsed.d.length > 0) {
          console.log('[Portfolio] Using cached data');
          render(parsed.d, 'cache');
          refreshBtn.classList.remove('spinning');
          return;
        }
      }
    } catch (e) { console.warn('Cache read failed:', e); }
  }

  try {
    const repos = await fetchFromGitHub();
    if (repos.length === 0) throw new Error('No repos returned');
    try { localStorage.setItem(CACHE_KEY, JSON.stringify({ t: Date.now(), d: repos })); } catch (e) {}
    render(repos, 'live');
  } catch (err) {
    console.error('[Portfolio] GitHub fetch failed:', err);
    console.log('[Portfolio] Using fallback repos.');
    render(FALLBACK_REPOS, 'fallback');
  }

  refreshBtn.classList.remove('spinning');
}

document.getElementById('filter-bar').addEventListener('click', (e) => {
  if (!e.target.matches('.chip')) return;
  document.querySelectorAll('#filter-bar .chip').forEach(c => c.classList.remove('active'));
  e.target.classList.add('active');
  const filter = e.target.dataset.filter;
  document.querySelectorAll('.repo-card').forEach(card => {
    card.style.display = (filter === 'all' || card.dataset.lang === filter) ? '' : 'none';
  });
});

document.getElementById('refresh-btn').addEventListener('click', () => {
  try { localStorage.removeItem(CACHE_KEY); } catch (e) {}
  loadRepos(true);
});

loadRepos();
