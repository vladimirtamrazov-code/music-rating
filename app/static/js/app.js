// Формула продублирована из app/scoring.py — держите их синхронными
const BASE_K = 1.4;
const MAX_SCORE = 90;
const VIBE_MAX_BONUS = MAX_SCORE / (BASE_K * 4 * 10) - 1;

function calcScore(p) {
  const base = (p.rhymes + p.structure + p.style + p.charisma) * BASE_K;
  const mult = 1 + ((p.vibe - 1) / 9) * VIBE_MAX_BONUS;
  return Math.min(MAX_SCORE, Math.round(base * mult));
}

function tier(score) {
  if (score >= 80) return "tier-gold";
  if (score >= 65) return "tier-high";
  if (score >= 45) return "tier-mid";
  return "tier-low";
}

function initCalculators() {
  document.querySelectorAll("[data-calc]").forEach((root) => {
    const inputs = root.querySelectorAll("input[data-crit]");
    const out = root.querySelector("[data-score-out]");
    const update = () => {
      const p = {};
      inputs.forEach((inp) => {
        p[inp.dataset.crit] = Number(inp.value);
        const o = inp.parentElement.querySelector("output");
        if (o) o.textContent = inp.value;
        inp.style.setProperty("--fill", ((inp.value - 1) / 9) * 100 + "%");
      });
      const s = calcScore(p);
      out.textContent = s;
      out.className = "score score-xl " + tier(s);
    };
    inputs.forEach((inp) => inp.addEventListener("input", update));
    update();
  });
}

function csrfToken() {
  const m = document.querySelector('meta[name="csrf-token"]');
  return m ? m.content : "";
}

function initLikes() {
  document.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-like]");
    if (!btn || btn.disabled) return;
    e.preventDefault();
    btn.disabled = true;
    try {
      const res = await fetch(btn.dataset.like, {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken(), Accept: "application/json" },
        credentials: "same-origin",
      });
      const data = await res.json().catch(() => ({}));
      if (res.status === 401) {
        window.location.href = "/auth/login?next=" + encodeURIComponent(location.pathname);
        return;
      }
      if (!res.ok) {
        alert(data.error || "Не удалось поставить лайк");
        return;
      }
      btn.classList.toggle("liked", data.liked);
      btn.querySelector("span").textContent = data.count;
    } finally {
      btn.disabled = false;
    }
  });
}

function initConfirm() {
  document.addEventListener("submit", (e) => {
    const msg = e.target.dataset && e.target.dataset.confirm;
    if (msg && !confirm(msg)) e.preventDefault();
  });
  document.querySelectorAll("select[data-autosubmit]").forEach((s) =>
    s.addEventListener("change", () => s.form.submit())
  );
}

function initNav() {
  const btn = document.querySelector('[data-toggle="nav"]');
  const nav = document.getElementById("nav");
  if (btn && nav) btn.addEventListener("click", () => nav.classList.toggle("open"));
}

document.addEventListener("DOMContentLoaded", () => {
  initCalculators();
  initLikes();
  initConfirm();
  initNav();
});
