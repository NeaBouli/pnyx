
// Democracy Cycle Animation — 6 Phasen (#356)
// Runs only while the #demo fold is open: closing stops it, reopening restarts at
// phase 01. Pause/play is user-controlled; reduced motion starts paused (static).
(function() {
  var PHASE_MS = 2000, HOLD_MS = 3000;
  var section = document.getElementById("demo");
  var reduceQuery = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;
  var timer = null, step = -1, paused = reducedMotion();

  function reducedMotion() { return !!(reduceQuery && reduceQuery.matches); }
  function setLiveText(id, elText, enText) {
    var node=document.getElementById(id);
    if(!node) return;
    node.setAttribute("data-el", elText);
    node.setAttribute("data-en", enText);
    node.textContent=currentLang==="en"?enText:elText;
  }
  function clearResultData() {
    var ry=document.getElementById("resultYes"); if(ry) ry.style.width="0";
    var rn=document.getElementById("resultNo"); if(rn) rn.style.width="0";
    var yb=document.getElementById("yesBar"); if(yb) yb.style.width="0";
    var nb=document.getElementById("noBar"); if(nb) nb.style.width="0";
    setLiveText("resultParticipation","Συμμετοχή στην πλατφόρμα: —","Platform participation: —");
  }
  function renderLiveResult(data) {
    var total=data.total_votes == null ? null : Number(data.total_votes);
    var STATUS={
      ANNOUNCED:["Ανακοίνωση","Announced"],
      ACTIVE:["Ενεργό · ψηφοφορία ανοιχτή","Active · voting open"],
      WINDOW_24H:["Παράθυρο 24 ωρών","24-hour window"],
      PARLIAMENT_VOTED:["Ψηφίστηκε στη Βουλή","Voted in Parliament"],
      OPEN_END:["Αρχείο · Open End","Archive · Open End"]
    };
    var status=STATUS[data.status]||["Άγνωστη","Unknown"];
    var statusEl="Κατάσταση νομοσχεδίου · "+status[0];
    var statusEn="Bill status · "+status[1];
    var totalEl=total == null ? "—" : total.toLocaleString("el-GR")+(total===1?" ψήφος":" ψήφοι");
    var totalEn=total == null ? "—" : total.toLocaleString("en-US")+(total===1?" vote":" votes");
    var yes=data.yes_pct == null ? null : Math.max(0,Math.min(100,Number(data.yes_pct)));
    var no=data.no_pct == null ? null : Math.max(0,Math.min(100,Number(data.no_pct)));
    var abstain=data.abstain_pct == null ? null : Math.max(0,Math.min(100,Number(data.abstain_pct)));
    var titleEl=data.title_el||data.bill_id;
    var titleEn=data.title_en||titleEl;
    var majorityEl="Πλειοψηφία: ΑΠΟΧΗ";
    var majorityEn="Majority: ABSTAIN";
    if(yes==null||no==null||abstain==null) { majorityEl="Πλειοψηφία: —"; majorityEn="Majority: —"; }
    else if(yes>=no&&yes>=abstain) { majorityEl="Πλειοψηφία: ΥΠΕΡ"; majorityEn="Majority: YES"; }
    else if(no>=yes&&no>=abstain) { majorityEl="Πλειοψηφία: ΚΑΤΑ"; majorityEn="Majority: NO"; }
    var electorate=9810040;
    var participation=total/electorate*100;
    setLiveText("latestBillTitle",titleEl,titleEn);
    setLiveText("latestBillStatus",statusEl,statusEn);
    setLiveText("demoYesLabel",(yes==null?"—":yes+"%")+" Υπέρ",(yes==null?"—":yes+"%")+" Yes");
    setLiveText("demoNoLabel",(no==null?"—":no+"%")+" Κατά",(no==null?"—":no+"%")+" No");
    setLiveText("resultTotal",totalEl,totalEn);
    setLiveText("resultParticipation",total==null?"Συμμετοχή στην πλατφόρμα: —":"Συμμετοχή στην πλατφόρμα: "+participation.toFixed(4)+"% ("+total.toLocaleString("el-GR")+" / 9.810.040)",total==null?"Platform participation: —":"Platform participation: "+participation.toFixed(4)+"% ("+total.toLocaleString("en-US")+" / 9,810,040)");
    setLiveText("resultYesLabel",(yes==null?"—":yes+"%")+" Υπέρ",(yes==null?"—":yes+"%")+" Yes");
    setLiveText("resultNoLabel",(no==null?"—":no+"%")+" Κατά",(no==null?"—":no+"%")+" No");
    setLiveText("resultMajority",majorityEl,majorityEn);
  }
  function fillResultData() {
    var live=window._liveResult;
    if(!live||!live.bill_id||live.yes_pct==null||live.no_pct==null||Number(live.total_votes)<1) {
      clearResultData();
      return;
    }
    var ry=document.getElementById("resultYes"); if(ry) ry.style.width=live.yes_pct+"%";
    var rn=document.getElementById("resultNo"); if(rn) rn.style.width=live.no_pct+"%";
    var yb=document.getElementById("yesBar"); if(yb) yb.style.width=live.yes_pct+"%";
    var nb=document.getElementById("noBar"); if(nb) nb.style.width=live.no_pct+"%";
  }

  function phases() {
    return section ? Array.prototype.slice.call(section.querySelectorAll("#cyclePhases > .demo-box")) : [];
  }
  function foldOpen() {
    var fold = section && section.querySelector("details.pnx2-fold");
    return fold ? fold.open : true;
  }
  function showPhase(index) {
    phases().forEach(function(el, i) {
      el.classList.toggle("active", i === index);
      if (i === index) el.setAttribute("aria-current", "step"); else el.removeAttribute("aria-current");
    });
    step = index;
  }
  function stopCycle() { if (timer) { clearTimeout(timer); timer = null; } }
  function runCycle() {
    stopCycle();
    if (step < 0) showPhase(0);
    var last = phases().length - 1;
    timer = setTimeout(function() {
      timer = null;
      showPhase(step >= last ? 0 : step + 1);
      runCycle();
    }, step >= last ? HOLD_MS : PHASE_MS);
  }
  function sync() {
    var open = foldOpen();
    if (!open) showPhase(-1);
    if (open && !paused) runCycle(); else stopCycle();
    var btn = document.getElementById("cycleToggle");
    if (btn) btn.setAttribute("data-state", paused ? "paused" : "playing");
    setLiveText("cycleToggleText", paused ? "Αναπαραγωγή" : "Παύση", paused ? "Play" : "Pause");
  }
  function initCycle() {
    var fold = section && section.querySelector("details.pnx2-fold");
    if (fold) fold.addEventListener("toggle", function() {
      // Reopening restarts at phase 01 unless the visitor prefers reduced motion.
      if (fold.open) { paused = reducedMotion(); showPhase(-1); }
      sync();
    });
    var btn = document.getElementById("cycleToggle");
    if (btn) btn.addEventListener("click", function() { paused = !paused; sync(); });
    if (reduceQuery) {
      var onReduce = function() { if (reducedMotion()) paused = true; sync(); };
      if (reduceQuery.addEventListener) reduceQuery.addEventListener("change", onReduce);
      else if (reduceQuery.addListener) reduceQuery.addListener(onReduce);
    }
    sync();
  }
  // landing-folds.js (deferred) builds the <details> before DOMContentLoaded.
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initCycle);
  else initCycle();

  // Load the real latest result; empty and unavailable states never show numbers.
  fetch("https://api.ekklesia.gr/api/v1/vote/results/latest")
    .then(function(r){ if(!r.ok) throw new Error("HTTP "+r.status); return r.json(); })
    .then(function(data){
      if(!data||!data.bill_id||(data.total_votes!=null&&data.total_votes<1)) return;
      window._liveResult=data;
      renderLiveResult(data);
      fillResultData();
    }).catch(function(){
      setLiveText("latestBillStatus","Τα ζωντανά δεδομένα δεν είναι διαθέσιμα αυτή τη στιγμή.","Live data is currently unavailable.");
    });
})();

// Ticker — live bills from API, fallback to static HTML
(function() {
  var lang = document.documentElement.lang || "el";
  var STATUS_BADGE = {
    ACTIVE:    { el: "Βουλή · Ανοιχτή", en: "Parliament · Active", cls: "badge-green" },
    ANNOUNCED: { el: "Βουλή · Ανακοινώθηκε", en: "Parliament · Announced", cls: "badge-yellow" },
    WINDOW_24H:{ el: "Βουλή · 24ω", en: "Parliament · 24h", cls: "badge-yellow" },
    OPEN_END:  { el: "Αποτέλεσμα", en: "Result", cls: "badge-blue" },
    PARLIAMENT_VOTED: { el: "Ψηφίστηκε", en: "Voted", cls: "badge-blue" }
  };

  function billCard(b, cssClass) {
    var s = STATUS_BADGE[b.status] || STATUS_BADGE.ACTIVE;
    var title = (lang === "en" && b.title_en) ? b.title_en : b.title_el;
    var badge = lang === "en" ? s.en : s.el;
    var a = document.createElement("a");
    a.href = "https://ekklesia.gr/" + lang + "/bills/" + (b.bill_id || b.id);
    a.className = "t-card " + cssClass;
    var hasAggregates = b.total_votes !== null && b.total_votes !== undefined && Number.isFinite(Number(b.total_votes));
    var total = hasAggregates ? Number(b.total_votes).toLocaleString(lang === "en" ? "en-US" : "el-GR") : null;
    var hasShares = hasAggregates && b.yes_pct != null;
    var yesPct = hasShares ? Number(b.yes_pct) : null;
    var meta = hasAggregates
      ? total + " " + (lang === "en" ? "votes" : "ψήφοι")
      : (b.suppressed ? "—" : (lang === "en" ? "Open for voting" : "Ανοιχτή για ψήφο"));
    var result = hasShares
      ? yesPct + "% " + (lang === "en" ? "Yes" : "Υπέρ")
      : (b.suppressed ? "—" : (lang === "en" ? "View bill details" : "Προβολή νομοσχεδίου"));
    a.innerHTML =
      '<span class="t-badge ' + s.cls + '">' + escapeHtml(badge) + '</span>' +
      '<span class="t-title">' + escapeHtml(title || "") + '</span>' +
      '<span class="t-meta">' + escapeHtml(meta) + '</span>' +
      (hasShares ? '<div class="t-bar"><div class="t-fill" style="width:' + Math.max(0, Math.min(100, yesPct)) + '%"></div></div>' : '') +
      '<div class="t-converge">' + escapeHtml(result) + '</div>';
    return a;
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, function(ch) {
      return {"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch];
    });
  }

  function emptyCard(cssClass, titleEl, titleEn, textEl, textEn) {
    var card = document.createElement("div");
    card.className = "t-card " + cssClass + " t-empty visible";
    card.innerHTML = '<strong>' + escapeHtml(lang === "en" ? titleEn : titleEl) + '</strong>' +
      '<span>' + escapeHtml(lang === "en" ? textEn : textEl) + '</span>';
    return card;
  }

  function startCycle(trackId, interval) {
    var track = document.getElementById(trackId);
    if (!track) return;
    var cards = track.querySelectorAll(".t-card");
    if (!cards.length) return;
    var cur = 0;
    function show(i) {
      cards.forEach(function(c) { c.classList.remove("visible"); });
      cur = i % cards.length;
      cards[cur].classList.add("visible");
    }
    show(0);
    if (cards.length > 1) setInterval(function() { show(cur + 1); }, interval);
  }

  function populateTrack(trackId, bills, cssClass) {
    var track = document.getElementById(trackId);
    if (!track || !bills.length) return;
    track.innerHTML = "";
    bills.forEach(function(b) { track.appendChild(billCard(b, cssClass)); });
  }

  function populateEmpty(trackId, cssClass, titleEl, titleEn, textEl, textEn) {
    var track = document.getElementById(trackId);
    if (!track) return;
    track.innerHTML = "";
    track.appendChild(emptyCard(cssClass, titleEl, titleEn, textEl, textEn));
  }

  function shuffle(arr) {
    for (var i = arr.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = arr[i]; arr[i] = arr[j]; arr[j] = tmp;
    }
    return arr;
  }

  function fetchJson(url, fallback) {
    return fetch(url)
      .then(function(r) {
        if (!r.ok) throw new Error("request failed");
        return r.json();
      })
      .catch(function() { return fallback; });
  }

  Promise.all([
    fetchJson("https://api.ekklesia.gr/api/v1/vote/results/in-progress", { bills: [] }),
    fetchJson("https://api.ekklesia.gr/api/v1/bills?status=WINDOW_24H&limit=10", [])
  ])
    .then(function(payloads) {
      var resultData = payloads[0];
      var publicWindowBills = Array.isArray(payloads[1]) ? payloads[1] : [];
      var bills = resultData && Array.isArray(resultData.bills) ? resultData.bills.slice() : [];
      var knownBillIds = {};
      bills.forEach(function(b) { knownBillIds[b.bill_id || b.id] = true; });
      publicWindowBills.forEach(function(b) {
        var billId = b.bill_id || b.id;
        var hasOfficialSource = Boolean(b.parliament_url || b.diavgeia_ada);
        if (!billId || !hasOfficialSource || knownBillIds[billId]) return;
        knownBillIds[billId] = true;
        bills.push({
          bill_id: billId,
          title_el: b.title_el,
          title_en: b.title_en,
          status: "WINDOW_24H",
          governance_level: b.governance_level,
          total_votes: null
        });
      });
      if (!bills.length) throw new Error("empty");
      var active = bills.filter(function(b) { return b.status === "ACTIVE" || b.status === "WINDOW_24H"; });
      var window24 = bills.filter(function(b) { return b.status === "WINDOW_24H"; });
      var finished = bills.filter(function(b) { return b.status === "OPEN_END" || b.status === "PARLIAMENT_VOTED"; });
      var t1Bills = shuffle(active).slice(0, 5);
      var t2Bills = shuffle(window24).slice(0, 5);
      var t3Bills = shuffle(finished).slice(0, 5);
      if (t1Bills.length) populateTrack("t1", t1Bills, "al");
      else populateEmpty("t1", "al", "Σύντομα πραγματικά δεδομένα", "Real data soon", "Καμία τρέχουσα ψηφοφορία δεν έχει περάσει ακόμη το όριο συμμετοχής.", "No current vote has passed the participation threshold yet.");
      if (t2Bills.length) populateTrack("t2", t2Bills, "rc");
      else populateEmpty("t2", "rc", "Καμία ψηφοφορία 24ω πάνω από το όριο", "No 24h vote above threshold", "Θα εμφανιστεί αυτόματα όταν υπάρξουν αρκετές πραγματικές ψήφοι.", "It will appear automatically after enough real votes.");
      if (t3Bills.length) populateTrack("t3", t3Bills, "rs");
      else populateEmpty("t3", "rs", "Αποτελέσματα όταν υπάρχουν αρκετές ψήφοι", "Results after enough votes", "Δεν προβάλλονται δοκιμαστικοί αριθμοί.", "No demo numbers are shown.");
      startCycle("t1", 3000);
      startCycle("t2", 3500);
      startCycle("t3", 4000);
    })
    .catch(function() {
      populateEmpty("t1", "al", "Σύντομα πραγματικά δεδομένα", "Real data soon", "Θα εμφανιστούν ψηφοφορίες όταν περάσουν το όριο συμμετοχής.", "Votes appear after they pass the participation threshold.");
      populateEmpty("t2", "rc", "Καμία ψηφοφορία πάνω από το όριο", "No vote above threshold", "Μόνο πραγματικές, συγκεντρωτικές ψήφοι εμφανίζονται εδώ.", "Only real aggregated votes appear here.");
      populateEmpty("t3", "rs", "Αποτελέσματα όταν υπάρχουν αρκετές ψήφοι", "Results after enough votes", "Δεν προβάλλονται δοκιμαστικοί αριθμοί.", "No demo numbers are shown.");
      startCycle("t1", 3000);
      startCycle("t2", 3500);
      startCycle("t3", 4000);
    });
})();

// Contact form
document.addEventListener("DOMContentLoaded", function() {
  var form = document.getElementById("contactForm");
  if (!form) return;
  form.addEventListener("submit", function(e) {
    e.preventDefault();
    var name = document.getElementById("cName").value;
    var email = document.getElementById("cEmail").value;
    var msg = document.getElementById("cMsg").value;
    var subject = encodeURIComponent("Ekklesia.gr — " + name);
    var body = encodeURIComponent(msg + "\n\nFrom: " + name + " (" + email + ")");
    window.location.href = "mailto:kaspartisan@proton.me?subject=" + subject + "&body=" + body;
  });
});

// Landing Ticket Tab Switcher
function switchContactTab(mode) {
  document.getElementById("contactMode").style.display = mode === "contact" ? "block" : "none";
  document.getElementById("ticketMode").style.display = mode === "ticket" ? "block" : "none";
  document.getElementById("tabContact").style.background = mode === "contact" ? "#2563eb" : "white";
  document.getElementById("tabContact").style.color = mode === "contact" ? "white" : "#334155";
  document.getElementById("tabContact").style.borderColor = mode === "contact" ? "#2563eb" : "#e2e8f0";
  document.getElementById("tabTicket").style.background = mode === "ticket" ? "#2563eb" : "white";
  document.getElementById("tabTicket").style.color = mode === "ticket" ? "white" : "#334155";
  document.getElementById("tabTicket").style.borderColor = mode === "ticket" ? "#2563eb" : "#e2e8f0";
  if (mode === "ticket") checkTicketAuth();
}

function polisLogin() {
  var state = crypto.randomUUID();
  sessionStorage.setItem("polis_oauth_state", state);
  sessionStorage.setItem("polis_return_to", window.location.href + "#contact");
  // Use config if available, fallback to placeholder
  var clientId = "Ov23lifSswjpPlnYF6UK";
  var callbackPath = "/tickets/auth/callback.html";
  var params = new URLSearchParams({ client_id: clientId, redirect_uri: window.location.origin + callbackPath, scope: "public_repo", state: state });
  window.location.href = "https://github.com/login/oauth/authorize?" + params.toString();
}

// Only accept https GitHub avatar URLs; returns "" for anything else.
function ticketAvatarUrl(raw, size) {
  try {
    var url = new URL(String(raw || ""));
    if (url.protocol !== "https:" || url.hostname !== "avatars.githubusercontent.com") return "";
    url.searchParams.set("s", String(size));
    return url.toString();
  } catch (e) {
    return "";
  }
}

function checkTicketAuth() {
  var token = sessionStorage.getItem("polis_token");
  if (token) {
    document.getElementById("ticketLoginPrompt").style.display = "none";
    document.getElementById("ticketFormLanding").style.display = "block";
    // Fetch user info
    fetch("https://api.github.com/user", { headers: { Authorization: "Bearer " + token } })
      .then(function(r) { return r.json(); })
      .then(function(u) {
        // Remote GitHub fields go through DOM properties, never through HTML parsing.
        var info = document.getElementById("ticketUserInfo");
        var nodes = [];
        var avatarUrl = ticketAvatarUrl(u && u.avatar_url, 40);
        if (avatarUrl) {
          var img = document.createElement("img");
          img.src = avatarUrl;
          img.style.cssText = "width:28px;height:28px;border-radius:50%";
          nodes.push(img);
        }
        var name = document.createElement("span");
        name.style.cssText = "font-weight:700;font-size:0.85rem";
        name.textContent = (u && u.login) || "";
        nodes.push(name);
        var logoutBtn = document.createElement("button");
        logoutBtn.type = "button";
        logoutBtn.textContent = "Logout";
        logoutBtn.style.cssText = "margin-left:auto;background:none;border:1px solid #e2e8f0;border-radius:0.3rem;padding:0.15rem 0.5rem;font-size:0.7rem;cursor:pointer";
        logoutBtn.onclick = function() { sessionStorage.removeItem("polis_token"); checkTicketAuth(); };
        nodes.push(logoutBtn);
        info.replaceChildren.apply(info, nodes);
      });
  } else {
    document.getElementById("ticketLoginPrompt").style.display = "block";
    document.getElementById("ticketFormLanding").style.display = "none";
  }
}

async function submitLandingTicket(e) {
  e.preventDefault();
  var btn = document.getElementById("ltSubmitBtn");
  btn.disabled = true; btn.textContent = "...";
  var token = sessionStorage.getItem("polis_token");
  var title = document.getElementById("ltTitle").value;
  var cat = document.getElementById("ltCategory").value;
  var desc = document.getElementById("ltDesc").value;
  var meta = { polis_version: "1.0", category: cat, submitted_at: Date.now(), submitter_pubkey: null, pow_nonce: null, pow_difficulty: null, nullifier: null, client_lang: currentLang || "el" };
  var body = "<!-- POLIS_META\n" + JSON.stringify(meta, null, 2) + "\n-->\n\n## Περιγραφή\n\n" + desc + "\n\n---\n*Submitted via POLIS*";
  try {
    var res = await fetch("https://api.github.com/repos/NeaBouli/pnyx-community/issues", {
      method: "POST",
      headers: { Authorization: "Bearer " + token, "Content-Type": "application/json", Accept: "application/vnd.github.v3+json" },
      body: JSON.stringify({ title: "[POLIS] " + title, body: body, labels: ["status:pending", "category:" + cat] })
    });
    var issue = await res.json();
    document.getElementById("ticketFormLanding").style.display = "none";
    document.getElementById("ltSuccess").style.display = "block";
    document.getElementById("ltSuccess").innerHTML = '<div style="background:#f0fdf4;border:2px solid #86efac;border-radius:0.75rem;padding:1.5rem;text-align:center"><h4 style="color:#166534;font-weight:900">✅ Ticket υποβλήθηκε!</h4><a href="' + issue.html_url + '" target="_blank" style="color:#2563eb;font-weight:700">Δείτε στο GitHub ↗</a></div>';
  } catch (err) { alert(err.message); }
  btn.disabled = false; btn.textContent = "Υποβολή Ticket";
}

// Auto-check auth on load (if returning from OAuth)
if (window.location.hash === "#contact" && sessionStorage.getItem("polis_token")) {
  setTimeout(function() { switchContactTab("ticket"); }, 500);
}

