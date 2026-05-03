// POLIS — Community Ticket System (Phase 1: GitHub Backend)
// Depends on: config.js (POLIS_CONFIG)

var polisLang = "el";
var polisUser = null;
var polisTickets = [];
var polisPage = 1;
var polisSelectedTicket = null;
var polisMyVotes = {};

// ─── Translation ─────────────────────────────────────────────────────────────

function t(key) {
  var strings = POLIS_CONFIG.i18n[polisLang] || POLIS_CONFIG.i18n.el;
  return strings[key] || key;
}

function setPolisLang(lang) {
  polisLang = lang;
  // Re-render UI elements with data-polis-el/en
  document.querySelectorAll("[data-polis-el]").forEach(function(el) {
    el.textContent = el.getAttribute("data-polis-" + polisLang) || el.textContent;
  });
  // Re-render dynamic elements that use t()
  if (typeof renderAuthStatus === "function") renderAuthStatus();
}

// ─── Auth ────────────────────────────────────────────────────────────────────

function getToken() {
  return sessionStorage.getItem("polis_token");
}

function isLoggedIn() {
  return !!getToken();
}

function login(returnTo) {
  var state = crypto.randomUUID();
  sessionStorage.setItem("polis_oauth_state", state);
  sessionStorage.setItem("polis_return_to", returnTo || window.location.href);
  var params = new URLSearchParams({
    client_id: POLIS_CONFIG.oauth.clientId,
    redirect_uri: window.location.origin + POLIS_CONFIG.oauth.callbackPath,
    scope: "public_repo",
    state: state,
  });
  window.location.href = "https://github.com/login/oauth/authorize?" + params.toString();
}

function logout() {
  sessionStorage.removeItem("polis_token");
  polisUser = null;
  polisMyVotes = {};
  renderAuthStatus();
  renderTicketList();
}

async function getCurrentUser() {
  var token = getToken();
  if (!token) return null;
  try {
    var res = await fetch("https://api.github.com/user", {
      headers: { "Authorization": "Bearer " + token, "Accept": "application/vnd.github.v3+json" },
    });
    if (res.status === 401) { logout(); return null; }
    if (!res.ok) return null;
    polisUser = await res.json();
    return polisUser;
  } catch (e) { return null; }
}

async function initAuth() {
  if (isLoggedIn()) {
    await getCurrentUser();
  }
  renderAuthStatus();
}

// ─── GitHub API ──────────────────────────────────────────────────────────────

function apiHeaders() {
  var h = { "Accept": "application/vnd.github.v3+json" };
  var token = getToken();
  if (token) h["Authorization"] = "Bearer " + token;
  return h;
}

function repoUrl() {
  return "https://api.github.com/repos/" + POLIS_CONFIG.repo;
}

async function apiCall(url, options) {
  options = options || {};
  options.headers = Object.assign(apiHeaders(), options.headers || {});
  try {
    var res = await fetch(url, options);
    if (res.status === 401) { logout(); throw new Error(t("expired")); }
    if (res.status === 403) { throw new Error(t("rateLimited")); }
    if (res.status === 404) { throw new Error(t("repoNotFound")); }
    if (res.status === 422) {
      var err = await res.json();
      throw new Error(err.message || "Validation error");
    }
    if (!res.ok) throw new Error("HTTP " + res.status);
    return res;
  } catch (e) {
    if (e.name === "TypeError") throw new Error(t("networkError"));
    throw e;
  }
}

// ─── Tickets ─────────────────────────────────────────────────────────────────

function parseTicketMeta(body) {
  var match = body && body.match(/<!-- POLIS_META\s*([\s\S]*?)\s*-->/);
  if (!match) return {};
  try { return JSON.parse(match[1]); } catch (e) { return {}; }
}

function parseTicketDescription(body) {
  if (!body) return "";
  var desc = body.replace(/<!-- POLIS_META[\s\S]*?-->/, "").trim();
  // Remove footer
  var footerIdx = desc.lastIndexOf("---");
  if (footerIdx > 0) desc = desc.substring(0, footerIdx).trim();
  // Remove "## Περιγραφή" header
  desc = desc.replace(/^## (Περιγραφή|Description)\s*/i, "").trim();
  return desc;
}

function ticketStatus(issue) {
  var labels = (issue.labels || []).map(function(l) { return l.name; });
  if (labels.includes("status:resolved")) return "resolved";
  if (labels.includes("status:claimed")) return "claimed";
  if (labels.includes("status:open")) return "open";
  return "pending";
}

function ticketCategory(issue) {
  var labels = (issue.labels || []).map(function(l) { return l.name; });
  for (var i = 0; i < POLIS_CONFIG.categories.length; i++) {
    if (labels.includes("category:" + POLIS_CONFIG.categories[i].id)) {
      return POLIS_CONFIG.categories[i];
    }
  }
  return null;
}

function ticketVotes(issue) {
  // +1 reactions on the issue
  if (issue.reactions) return issue.reactions["+1"] || 0;
  return 0;
}

function formatTimeAgo(dateStr) {
  var now = Date.now();
  var then = new Date(dateStr).getTime();
  var diff = Math.floor((now - then) / 1000);
  if (diff < 60) return diff + "s";
  if (diff < 3600) return Math.floor(diff / 60) + "m";
  if (diff < 86400) return Math.floor(diff / 3600) + "h";
  return Math.floor(diff / 86400) + "d";
}

async function loadTickets(page, filters) {
  filters = filters || {};
  var params = new URLSearchParams({
    per_page: "20",
    page: String(page || 1),
    state: "open",
    sort: filters.sort === "oldest" ? "created" : (filters.sort === "votes" ? "reactions-+1" : "created"),
    direction: filters.sort === "oldest" ? "asc" : "desc",
  });
  if (filters.labels) params.set("labels", filters.labels);

  var cacheKey = "polis_cache_" + params.toString();
  var cached = sessionStorage.getItem(cacheKey);
  var cacheTime = sessionStorage.getItem(cacheKey + "_t");

  // Return cached if fresh (<5 min)
  if (cached && cacheTime && (Date.now() - parseInt(cacheTime)) < 300000) {
    return JSON.parse(cached);
  }

  var res = await apiCall(repoUrl() + "/issues?" + params.toString());
  var issues = await res.json();

  // Filter out PRs
  issues = issues.filter(function(i) { return !i.pull_request; });

  // Cache
  sessionStorage.setItem(cacheKey, JSON.stringify(issues));
  sessionStorage.setItem(cacheKey + "_t", String(Date.now()));

  return issues;
}

async function createTicket(data) {
  // Phase 2 stub: PoW
  var powProof = POLIS_CONFIG.pow && POLIS_CONFIG.pow.enabled
    ? { nonce: null, difficulty: POLIS_CONFIG.pow.difficulty } // TODO: await computePoW(...)
    : { nonce: null, difficulty: null };

  // Phase 3 stub: Nullifier
  var identity = window.__EKKLESIA_MOD01_LOADED__
    ? { nullifier: null, signature: null, publicKey: null } // TODO: await signWithEkklesia(...)
    : { nullifier: null, signature: null, publicKey: null };

  var meta = {
    polis_version: "1.0",
    category: data.category,
    submitted_at: Date.now(),
    submitter_pubkey: identity.publicKey,
    pow_nonce: powProof.nonce,
    pow_difficulty: powProof.difficulty,
    nullifier: identity.nullifier,
    client_lang: polisLang,
  };

  var body = "<!-- POLIS_META\n" + JSON.stringify(meta, null, 2) + "\n-->\n\n"
    + "## " + (polisLang === "el" ? "Περιγραφή" : "Description") + "\n\n"
    + data.description + "\n\n"
    + "---\n"
    + "*Submitted via [POLIS](https://ekklesia.gr/tickets/index.html) — Community Ticket System for [εκκλησία](https://ekklesia.gr)*";

  // Check account age
  var labels = ["status:pending", "category:" + data.category];
  if (polisUser) {
    var accountAge = (Date.now() - new Date(polisUser.created_at).getTime()) / 86400000;
    if (accountAge >= POLIS_CONFIG.moderation.newAccountAgeDays) {
      labels[0] = "status:pending"; // Still starts pending, community promotes
    }
  }

  var res = await apiCall(repoUrl() + "/issues", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: "[POLIS] " + data.title,
      body: body,
      labels: labels,
    }),
  });

  return await res.json();
}

async function getTicketDetail(number) {
  var res = await apiCall(repoUrl() + "/issues/" + number);
  return await res.json();
}

async function getComments(number, page) {
  var res = await apiCall(repoUrl() + "/issues/" + number + "/comments?per_page=5&page=" + (page || 1));
  return await res.json();
}

// ─── Votes ───────────────────────────────────────────────────────────────────

async function castVote(issueNumber) {
  var res = await apiCall(repoUrl() + "/issues/" + issueNumber + "/reactions", {
    method: "POST",
    headers: { "Content-Type": "application/json", "Accept": "application/vnd.github.squirrel-girl-preview+json" },
    body: JSON.stringify({ content: "+1" }),
  });
  var data = await res.json();
  polisMyVotes[issueNumber] = data.id;
  return data;
}

async function removeVote(issueNumber) {
  var reactionId = polisMyVotes[issueNumber];
  if (!reactionId) return;
  await apiCall(repoUrl() + "/issues/" + issueNumber + "/reactions/" + reactionId, {
    method: "DELETE",
    headers: { "Accept": "application/vnd.github.squirrel-girl-preview+json" },
  });
  delete polisMyVotes[issueNumber];
}

async function loadMyVotes(issueNumbers) {
  if (!isLoggedIn() || !polisUser) return;
  // Load reactions for visible issues to check if user already voted
  for (var i = 0; i < issueNumbers.length; i++) {
    try {
      var res = await apiCall(
        repoUrl() + "/issues/" + issueNumbers[i] + "/reactions?per_page=100",
        { headers: { "Accept": "application/vnd.github.squirrel-girl-preview+json" } }
      );
      var reactions = await res.json();
      for (var j = 0; j < reactions.length; j++) {
        if (reactions[j].user.id === polisUser.id && reactions[j].content === "+1") {
          polisMyVotes[issueNumbers[i]] = reactions[j].id;
          break;
        }
      }
    } catch (e) { /* skip */ }
  }
}

// ─── Claim ───────────────────────────────────────────────────────────────────

async function claimTicket(issueNumber) {
  // Add comment
  await apiCall(repoUrl() + "/issues/" + issueNumber + "/comments", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ body: "🙋 **Claimed by @" + polisUser.login + "** via POLIS" }),
  });
  // Add label (requires push access — may fail for non-collaborators)
  try {
    await apiCall(repoUrl() + "/issues/" + issueNumber + "/labels", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ labels: ["status:claimed"] }),
    });
  } catch (e) { /* non-collaborator, label not added — ok */ }
}

async function flagAsSpam(issueNumber) {
  await apiCall(repoUrl() + "/issues/" + issueNumber + "/comments", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ body: "/polis spam" }),
  });
}

// ─── UI Rendering ────────────────────────────────────────────────────────────

function renderAuthStatus() {
  var container = document.getElementById("authStatus");
  if (!container) return;
  if (polisUser) {
    container.innerHTML = '<div class="auth-status">'
      + '<img src="' + polisUser.avatar_url + '&s=56" class="auth-avatar" alt=""/>'
      + '<span style="font-size:0.8rem;font-weight:600;color:white">' + polisUser.login + '</span>'
      + '<button class="btn-logout" onclick="logout()">↪</button>'
      + '</div>';
  } else {
    container.innerHTML = '<button class="btn-login" onclick="login()">' + t("loginGitHub") + '</button>';
  }
}

function renderTicketCard(issue) {
  var status = ticketStatus(issue);
  var cat = ticketCategory(issue);
  var votes = ticketVotes(issue);
  var voted = !!polisMyVotes[issue.number];
  var selected = polisSelectedTicket && polisSelectedTicket.number === issue.number;

  var catBadge = cat ? '<span class="category-badge" style="background:' + cat.color + '">' + (polisLang === "el" ? cat.el : cat.en) + '</span>' : '';
  var statusClass = "status-" + status;
  var statusText = t("status" + status.charAt(0).toUpperCase() + status.slice(1));

  return '<div class="ticket-card' + (selected ? ' selected' : '') + '" onclick="selectTicket(' + issue.number + ')">'
    + '<div class="ticket-vote">'
    + '<button class="vote-btn' + (voted ? ' voted' : '') + '" onclick="event.stopPropagation();toggleVote(' + issue.number + ')" title="' + t("vote") + '">▲</button>'
    + '<span class="vote-count">' + votes + '</span>'
    + '</div>'
    + '<div class="ticket-body">'
    + '<span class="ticket-id">POL-' + String(issue.number).padStart(3, "0") + '</span>'
    + '<div class="ticket-title">' + escapeHtml(issue.title.replace("[POLIS] ", "")) + '</div>'
    + '<div class="ticket-meta">'
    + catBadge
    + '<span class="status-pill ' + statusClass + '">' + statusText + '</span>'
    + '<span class="ticket-time">' + formatTimeAgo(issue.created_at) + '</span>'
    + '<span class="ticket-comments">💬 ' + issue.comments + '</span>'
    + '</div></div></div>';
}

function renderTicketList() {
  var container = document.getElementById("ticketList");
  if (!container) return;
  if (!polisTickets.length) {
    container.innerHTML = '<div class="empty-state"><div class="icon">📋</div><p>' + t("noTickets") + '</p></div>';
    return;
  }
  container.innerHTML = polisTickets.map(renderTicketCard).join("");
}

function renderSkeletons() {
  var container = document.getElementById("ticketList");
  if (!container) return;
  container.innerHTML = Array(5).fill('<div class="skeleton skeleton-card"></div>').join("");
}

async function renderDetail(issue) {
  var panel = document.getElementById("detailPanel");
  if (!panel) return;
  if (!issue) {
    panel.innerHTML = '<div class="detail-empty"><p>' + t("noTickets") + '</p></div>';
    return;
  }

  var status = ticketStatus(issue);
  var cat = ticketCategory(issue);
  var votes = ticketVotes(issue);
  var voted = !!polisMyVotes[issue.number];
  var desc = parseTicketDescription(issue.body);
  var maxVotes = 20; // for heat bar
  var heatPct = Math.min(100, Math.round((votes / maxVotes) * 100));

  var html = '<div class="ticket-id">POL-' + String(issue.number).padStart(3, "0") + '</div>'
    + '<div class="detail-title">' + escapeHtml(issue.title.replace("[POLIS] ", "")) + '</div>'
    + '<div class="ticket-meta" style="margin-bottom:1rem">'
    + (cat ? '<span class="category-badge" style="background:' + cat.color + '">' + (polisLang === "el" ? cat.el : cat.en) + '</span>' : '')
    + '<span class="status-pill status-' + status + '">' + t("status" + status.charAt(0).toUpperCase() + status.slice(1)) + '</span>'
    + '<span class="ticket-time">' + formatTimeAgo(issue.created_at) + '</span>'
    + '</div>'
    + '<div class="detail-desc">' + escapeHtml(desc) + '</div>'
    + '<div class="heat-bar-wrap"><div class="heat-bar-label">' + t("communityHeat") + ' (' + votes + ')</div>'
    + '<div class="heat-bar"><div class="heat-fill" style="width:' + heatPct + '%"></div></div></div>'
    + '<div class="detail-actions">'
    + '<button class="btn-vote-large' + (voted ? ' voted' : '') + '" onclick="toggleVote(' + issue.number + ')">'
    + (voted ? '✓ ' + t("voted") : '▲ ' + t("vote"))
    + '</button>'
    + (status === "open" ? '<button class="btn-claim" onclick="doClaim(' + issue.number + ')">🙋 ' + t("claim") + '</button>' : '')
    + '</div>'
    + '<a href="' + issue.html_url + '" target="_blank" class="github-link">' + t("viewOnGitHub") + ' ↗</a>';

  panel.innerHTML = html;

  // Load comments
  try {
    var comments = await getComments(issue.number);
    if (comments.length) {
      var actHtml = '<div class="activity-feed"><div style="font-size:0.8rem;font-weight:800;margin-bottom:0.5rem">' + t("recentActivity") + '</div>';
      comments.slice(0, 5).forEach(function(c) {
        actHtml += '<div class="activity-item"><span class="activity-user">' + c.user.login + '</span> '
          + '<span class="activity-time">' + formatTimeAgo(c.created_at) + '</span>'
          + '<div style="font-size:0.78rem;color:#64748b;margin-top:0.2rem">' + escapeHtml(c.body.substring(0, 150)) + '</div></div>';
      });
      actHtml += '</div>';
      panel.innerHTML += actHtml;
    }
  } catch (e) { /* ok */ }
}

function renderStats() {
  var open = 0, claimed = 0, resolved = 0;
  polisTickets.forEach(function(t) {
    var s = ticketStatus(t);
    if (s === "open") open++;
    else if (s === "claimed") claimed++;
    else if (s === "resolved") resolved++;
  });
  var el = document.getElementById("polisStats");
  if (el) {
    el.innerHTML = '<span>Open <strong>' + open + '</strong></span>'
      + '<span>Claimed <strong>' + claimed + '</strong></span>'
      + '<span>Resolved <strong>' + resolved + '</strong></span>';
  }
}

// ─── Actions ─────────────────────────────────────────────────────────────────

async function selectTicket(number) {
  var issue = polisTickets.find(function(t) { return t.number === number; });
  if (!issue) {
    issue = await getTicketDetail(number);
  }
  polisSelectedTicket = issue;
  renderTicketList();
  if (window.innerWidth <= 1024) {
    renderMobileDetail(issue);
  } else {
    renderDetail(issue);
  }
}

function closeMobileDetail() {
  document.getElementById("polisMobileModal").classList.remove("open");
}

async function renderMobileDetail(issue) {
  var body = document.getElementById("mobileDetailBody");
  if (!body || !issue) return;
  // Temporarily swap detailPanel to mobile body
  var desktopPanel = document.getElementById("detailPanel");
  var originalParent = desktopPanel.parentNode;
  body.innerHTML = "";
  body.appendChild(desktopPanel);
  await renderDetail(issue);
  document.getElementById("polisMobileModal").classList.add("open");
  // Restore desktop panel on close (handled by closeMobileDetail)
}

async function toggleVote(number) {
  if (!isLoggedIn()) { login(); return; }
  if (polisMyVotes[number]) {
    await removeVote(number);
  } else {
    await castVote(number);
  }
  // Refresh ticket
  var issue = await getTicketDetail(number);
  var idx = polisTickets.findIndex(function(t) { return t.number === number; });
  if (idx >= 0) polisTickets[idx] = issue;
  if (polisSelectedTicket && polisSelectedTicket.number === number) polisSelectedTicket = issue;
  renderTicketList();
  renderDetail(polisSelectedTicket);
}

async function doClaim(number) {
  if (!isLoggedIn()) { login(); return; }
  await claimTicket(number);
  var issue = await getTicketDetail(number);
  var idx = polisTickets.findIndex(function(t) { return t.number === number; });
  if (idx >= 0) polisTickets[idx] = issue;
  polisSelectedTicket = issue;
  renderTicketList();
  renderDetail(issue);
}

async function loadAndRender(filters) {
  renderSkeletons();
  try {
    polisTickets = await loadTickets(polisPage, filters);
    if (isLoggedIn() && polisUser) {
      await loadMyVotes(polisTickets.map(function(t) { return t.number; }));
    }
    renderTicketList();
    renderStats();
  } catch (e) {
    var container = document.getElementById("ticketList");
    if (container) {
      container.innerHTML = '<div class="empty-state"><div class="icon">⚠️</div><p>' + e.message + '</p>'
        + '<button class="btn-load-more" onclick="loadAndRender()" style="margin-top:1rem">' + t("loadMore") + '</button></div>';
    }
  }
}

// ─── Modal ───────────────────────────────────────────────────────────────────

function openNewTicketModal() {
  if (!isLoggedIn()) { login(); return; }
  document.getElementById("ticketModal").classList.add("open");
}

function closeTicketModal() {
  document.getElementById("ticketModal").classList.remove("open");
  document.getElementById("ticketForm").reset();
  document.getElementById("submitSuccess").style.display = "none";
  document.getElementById("ticketFormFields").style.display = "block";
}

async function submitTicketForm(e) {
  e.preventDefault();
  var titleEl = document.getElementById("ticketTitle");
  var catEl = document.getElementById("ticketCategory");
  var descEl = document.getElementById("ticketDesc");
  var submitBtn = document.getElementById("ticketSubmitBtn");

  // Validate
  if (titleEl.value.length > 120) { return; }
  if (descEl.value.length < 30) { return; }

  submitBtn.disabled = true;
  submitBtn.textContent = t("submitting");

  try {
    var created = await createTicket({
      title: titleEl.value,
      category: catEl.value,
      description: descEl.value,
    });

    document.getElementById("ticketFormFields").style.display = "none";
    var success = document.getElementById("submitSuccess");
    success.style.display = "block";
    success.innerHTML = '<div class="success-msg"><h4>✅ ' + t("successSubmit") + '</h4>'
      + '<a href="' + created.html_url + '" target="_blank">' + t("viewOnGitHub") + ' ↗</a></div>';

    // Refresh list
    polisPage = 1;
    loadAndRender();
  } catch (err) {
    alert(err.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = t("submitTicket");
  }
}

// ─── Utilities ───────────────────────────────────────────────────────────────

function escapeHtml(str) {
  var div = document.createElement("div");
  div.textContent = str || "";
  return div.innerHTML;
}

// ─── Init ────────────────────────────────────────────────────────────────────

async function initPolis() {
  await initAuth();
  await loadAndRender();
}
