
// @ai-anchor INVOICE_AMPEL_TIMER
(function() {
  // ═══════════════════════════════════════════════════════════
  // CONFIG — fetched live from /api/v1/payments/status
  // Fallback values used until first API response arrives
  // ═══════════════════════════════════════════════════════════
  var SERVER_COST_PER_MONTH = 10;
  var SERVER_START_DATE = new Date("2026-04-16T00:00:00");
  var DOMAIN_EXPIRY = new Date("2028-03-29T00:00:00");
  var DOMAIN_YELLOW_DAYS = 365;
  var DOMAIN_RED_DAYS = 183;
  var AUTO_RECOVERY_TOKENS_PER_RUN = 0;
  var AUTO_RECOVERY_TOKEN_COST_EUR = 0;
  var AUTO_RECOVERY_ALLOWED_RUNBOOKS = 1;
  var AUTO_RECOVERY_PROOF_WAIT_SECONDS = 30;

  // Live data from API (updated by fetchPaymentStatus)
  var liveServerData = null, liveDomainData = null;
  var serverDataState = "loading", domainDataState = "loading";
  var liveReserveData = null, reserveDataState = "loading";

  function validFundingAccount(acct) {
    return acct && acct.available !== false && ["received", "cost_total", "balance"].every(function(key) {
      return typeof acct[key] === "number" && isFinite(acct[key]);
    });
  }

  function updateReserveTile() {
    var val = document.getElementById("rReserveVal");
    var na = document.getElementById("rUnavailable");
    if (!val) return;
    if (liveReserveData !== null) {
      val.textContent = liveReserveData.toLocaleString("el-GR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + "\u20AC";
    } else {
      // Unknown is not zero: never show a balance we did not receive.
      val.textContent = "\u2014";
    }
    if (na) {
      na.style.display = reserveDataState === "ready" ? "none" : "";
      na.textContent = reserveDataState === "loading" ? t("Φόρτωση οικονομικών στοιχείων…", "Loading funding data…") : liveReserveData !== null ? t("Τελευταία έγκυρα στοιχεία — η ενημέρωση δεν είναι διαθέσιμη", "Last valid data — update unavailable") : t("Τα στοιχεία δεν είναι διαθέσιμα αυτή τη στιγμή", "Data currently unavailable");
    }
  }
  function fetchPaymentStatus() {
    fetch("https://api.ekklesia.gr/api/v1/payments/status")
      .then(function(r) { if (!r.ok) throw new Error("status " + r.status); return r.json(); })
      .then(function(data) {
        var serverOK = data && data.available !== false && validFundingAccount(data.server);
        var domainOK = data && data.available !== false && validFundingAccount(data.domain);
        var expiry = domainOK && data.domain.expires;
        if (expiry !== undefined && expiry !== false) {
          var parsedExpiry = typeof expiry === "string" && /^\d{4}-\d{2}-\d{2}$/.test(expiry) ? new Date(expiry + "T00:00:00Z") : null;
          if (!parsedExpiry || !isFinite(parsedExpiry.getTime()) || parsedExpiry.toISOString().slice(0, 10) !== expiry) domainOK = false;
        }
        serverDataState = serverOK ? "ready" : liveServerData ? "stale" : "unavailable";
        domainDataState = domainOK ? "ready" : liveDomainData ? "stale" : "unavailable";
        if (serverOK) liveServerData = data.server;
        if (domainOK) { liveDomainData = data.domain; if (expiry) DOMAIN_EXPIRY = new Date(expiry + "T00:00:00"); }
        var reserveOK = data && data.available !== false && typeof data.reserve === "number" && isFinite(data.reserve);
        reserveDataState = reserveOK ? "ready" : liveReserveData !== null ? "stale" : "unavailable";
        if (reserveOK) liveReserveData = data.reserve;
        updateServerTile();
        updateDomainTile();
        updateReserveTile();
      })
      .catch(function() {
        serverDataState = liveServerData ? "stale" : "unavailable";
        domainDataState = liveDomainData ? "stale" : "unavailable";
        reserveDataState = liveReserveData !== null ? "stale" : "unavailable";
        updateServerTile(); updateDomainTile(); updateReserveTile();
      });
  }
  var AR_WARN_THRESHOLD = 1.0;  // AR — yellow below this
  var AR_CRIT_THRESHOLD = 0.1;  // AR — red below this

  // ═══════════════════════════════════════════════════════════
  // HELPERS
  // ═══════════════════════════════════════════════════════════
  // Bilingual text helper — uses global currentLang from toggle
  function t(el, en) { return (typeof currentLang !== "undefined" && currentLang === "en") ? en : el; }

  function updateAutoRecoveryTransparency() {
    var tokenEl = document.getElementById("autoRecoveryTokens");
    var costEl = document.getElementById("autoRecoveryCost");
    var runbookEl = document.getElementById("autoRecoveryRunbooks");
    var waitEl = document.getElementById("autoRecoveryWait");
    var formulaEl = document.getElementById("autoRecoveryFormula");
    var summaryEl = document.getElementById("tranRecoveryTokens");
    if (tokenEl) tokenEl.textContent = AUTO_RECOVERY_TOKENS_PER_RUN.toLocaleString("el-GR");
    if (costEl) costEl.textContent = AUTO_RECOVERY_TOKEN_COST_EUR.toLocaleString("el-GR", { minimumFractionDigits: 0, maximumFractionDigits: 4 }) + "\u20AC";
    if (runbookEl) runbookEl.textContent = String(AUTO_RECOVERY_ALLOWED_RUNBOOKS);
    if (waitEl) waitEl.textContent = AUTO_RECOVERY_PROOF_WAIT_SECONDS + "s";
    if (summaryEl) summaryEl.textContent = AUTO_RECOVERY_TOKENS_PER_RUN.toLocaleString("el-GR");
    if (formulaEl) {
      formulaEl.textContent = t(
        "Υπολογισμός: " + AUTO_RECOVERY_TOKENS_PER_RUN + " AI tokens/run × allowlisted T1V runbook = " + AUTO_RECOVERY_TOKEN_COST_EUR + "\u20AC token κόστος",
        "Calculation: " + AUTO_RECOVERY_TOKENS_PER_RUN + " AI tokens/run × allowlisted T1V runbook = " + AUTO_RECOVERY_TOKEN_COST_EUR + "\u20AC token cost"
      );
    }
  }

  function setMirrorStatus(status, latencyMs) {
    var row = document.getElementById("mirrorSandboxRow");
    var dot = document.getElementById("mirrorSandboxDot");
    var text = document.getElementById("mirrorSandboxText");
    var label = "";
    var color = "#64748b";
    if (!row || !dot || !text) return;

    row.className = "mirror-row";
    dot.className = "mirror-dot";

    if (status === "online") {
      row.classList.add("mirror-row-online");
      dot.classList.add("mirror-dot-online");
      color = "#166534";
      label = t("read-only", "read-only");
      if (typeof latencyMs === "number") label += " · " + latencyMs + "ms";
    } else if (status === "degraded") {
      row.classList.add("mirror-row-degraded");
      dot.classList.add("mirror-dot-degraded");
      color = "#92400e";
      label = t("Μερική διαταραχή", "Partial disruption");
    } else {
      row.classList.add("mirror-row-offline");
      dot.classList.add("mirror-dot-offline");
      color = "#991b1b";
      label = t("Offline", "Offline");
    }

    text.textContent = label;
    document.getElementById("m1").style.color = color;
  }

  function fetchMirrorStatus() {
    fetch("https://api.ekklesia.gr/api/v1/public/mirrors/status", { cache: "no-store" })
      .then(function(r) {
        if (!r.ok) throw new Error("mirror status http " + r.status);
        return r.json();
      })
      .then(function(d) {
        var mirror = d.mirrors && d.mirrors[0];
        setMirrorStatus(mirror && mirror.status ? mirror.status : "offline", mirror ? mirror.latency_ms : null);
      })
      .catch(function() {
        setMirrorStatus("offline", null);
      });
  }

  function fmt(ms) {
    if (ms <= 0) return "00:00:00:00";
    var s=Math.floor(ms/1000),m=Math.floor(s/60);s%=60;
    var h=Math.floor(m/60);m%=60;
    var d=Math.floor(h/24);h%=24;
    return d+t("ημ ","d ")+pad(h)+":"+pad(m)+":"+pad(s);
  }
  function pad(n){return String(n).padStart(2,"0");}
  function eur(n){return n.toFixed(2).replace(".",",")+"\u20AC";}

  // ═══════════════════════════════════════════════════════════
  // SERVER SOLL/IST ACCOUNTING (data from API)
  // ═══════════════════════════════════════════════════════════
  function updateServerTile() {
    var acct = liveServerData;
    var hint = document.getElementById("sDataHint");
    if (hint) { hint.style.display = serverDataState === "ready" ? "none" : ""; hint.textContent = serverDataState === "loading" ? t("Φόρτωση οικονομικών στοιχείων…", "Loading funding data…") : acct ? t("Τελευταία έγκυρα στοιχεία — η ενημέρωση δεν είναι διαθέσιμη", "Last valid data — update unavailable") : t("Τα στοιχεία δεν είναι διαθέσιμα αυτή τη στιγμή", "Data currently unavailable"); }
    if (!acct) {
      ["sReceived", "sCost", "sBalanceVal", "sTimer", "sDue", "sTsub"].forEach(function(id) { var el = document.getElementById(id); if (el) el.textContent = "—"; });
      document.getElementById("sBalance").className = "fc-acct-total";
      document.getElementById("sBadge").textContent = serverDataState === "loading" ? t("ΦΟΡΤΩΣΗ", "LOADING") : t("ΜΗ ΔΙΑΘΕΣΙΜΟ", "UNAVAILABLE");
      document.getElementById("sTboxLabel").textContent = t("Αναμονή στοιχείων", "Waiting for data");
      ["sGreen", "sYellow", "sRed"].forEach(function(id) { document.getElementById(id).style.display = "none"; });
      return;
    }
    // Next due: start + months_elapsed months
    var monthsElapsed = typeof acct.months_elapsed === "number" && isFinite(acct.months_elapsed) && acct.months_elapsed > 0 && acct.months_elapsed <= 1200 ? acct.months_elapsed : Math.max(1, Math.ceil((new Date() - SERVER_START_DATE) / (30.44*86400000)));
    var nextDue = new Date(SERVER_START_DATE);
    nextDue.setMonth(nextDue.getMonth() + monthsElapsed);
    var now = new Date();
    var ms = nextDue - now;
    var days = Math.ceil(ms / 86400000);

    // Update accounting display
    var recEl = document.getElementById("sReceived");
    var costEl = document.getElementById("sCost");
    var balEl = document.getElementById("sBalanceVal");
    var balRow = document.getElementById("sBalance");
    if (recEl) { recEl.textContent = eur(acct.received); recEl.style.color = "#166534"; }
    if (costEl) { costEl.textContent = "-" + eur(acct.cost_total); costEl.style.color = "#dc2626"; }
    if (balEl) balEl.textContent = (acct.balance < 0 ? "-" : "") + eur(Math.abs(acct.balance || 0));
    if (balRow) {
      balRow.className = "fc-acct-total " + (acct.balance > 0 ? "positive" : acct.balance < 0 ? "negative" : "zero");
    }

    // Timer
    var timer = document.getElementById("sTimer");
    if (timer) timer.textContent = fmt(Math.max(0, ms));

    // Ampel logic based on balance
    var card = document.getElementById("sCard");
    var badge = document.getElementById("sBadge");
    var green = document.getElementById("sGreen");
    var yell = document.getElementById("sYellow");
    var red = document.getElementById("sRed");
    var tbox = document.getElementById("sTbox");
    var tsub = document.getElementById("sTsub");
    if (tsub) tsub.textContent = t("ημ · ώ · λ · δ", "d · h · m · s");
    var tboxLabel = document.getElementById("sTboxLabel");
    var sDue = document.getElementById("sDue");

    if (acct.balance < 0) {
      // RED — negative balance, pulsing
      card.className = "fc pulse-red";
      card.style.borderColor = "#ef4444";
      badge.style.background = "#ef4444";
      badge.textContent = t("ΧΡΕΙΑΖΕΤΑΙ ΧΡΗΜΑΤΟΔΟΤΗΣΗ","NEEDS FUNDING");
      if (tbox) { tbox.style.background = "#fef2f2"; }
      if (timer) timer.style.color = "#dc2626";
      if (tsub) { tsub.style.color = "#dc2626"; tsub.textContent = Math.abs(days) + t(" ημ. εκκρεμότητα"," days overdue"); }
      if (tboxLabel) { tboxLabel.textContent = t("Κρίσιμο — χρειάζεται δωρεά","Critical — donation needed"); tboxLabel.style.color = "#dc2626"; }
      if (sDue) { sDue.textContent = t("Χρειάζεται χρηματοδότηση","Needs funding"); sDue.style.color = "#dc2626"; }
      if (green) green.style.display = "none";
      if (yell) yell.style.display = "none";
      if (red) red.style.display = "block";
    } else if (acct.balance === 0 || days <= 5) {
      // YELLOW — balance zero or approaching due
      card.className = "fc";
      card.style.borderColor = "#fde047";
      badge.style.background = "#f59e0b";
      badge.textContent = t("ΠΡΟΣΟΧΗ","ATTENTION");
      if (tbox) { tbox.style.background = "#fefce8"; }
      if (timer) timer.style.color = "#92400e";
      if (tsub) tsub.style.color = "#92400e";
      if (tboxLabel) { tboxLabel.textContent = t("Χρόνος μέχρι χρέωση","Time until charge"); tboxLabel.style.color = "#92400e"; }
      if (sDue) { sDue.textContent = t("Υπόλοιπο: ","Balance: ") + eur(acct.balance); sDue.style.color = "#92400e"; }
      if (green) green.style.display = "none";
      if (yell) yell.style.display = "block";
      if (red) red.style.display = "none";
    } else {
      // GREEN — balance positive
      card.className = "fc";
      card.style.borderColor = "#86efac";
      badge.style.background = "#22c55e";
      badge.textContent = t("ΕΝΕΡΓΟ","ACTIVE");
      if (tbox) { tbox.style.background = "#f0fdf4"; }
      if (timer) timer.style.color = "#166534";
      if (tsub) tsub.style.color = "#166534";
      if (tboxLabel) { tboxLabel.textContent = t("Χρόνος μέχρι χρέωση","Time until charge"); tboxLabel.style.color = "#166534"; }
      if (sDue) { sDue.textContent = t("Ενεργός — ","Active — ") + eur(acct.balance) + t(" υπόλοιπο"," balance"); sDue.style.color = "#166534"; }
      if (green) green.style.display = "block";
      if (yell) yell.style.display = "none";
      if (red) red.style.display = "none";
    }
  }

  // ═══════════════════════════════════════════════════════════
  // DOMAIN SOLL/IST (gelb < 1 Jahr, rot < 6 Monate, pulsing when expired)
  // ═══════════════════════════════════════════════════════════
  function updateDomainTile() {
    var now = new Date(), ms = DOMAIN_EXPIRY - now, days = Math.ceil(ms / 86400000);
    var acct = liveDomainData;
    var hint = document.getElementById("dDataHint");
    if (hint) { hint.style.display = domainDataState === "ready" ? "none" : ""; hint.textContent = domainDataState === "loading" ? t("Φόρτωση οικονομικών στοιχείων…", "Loading funding data…") : acct ? t("Τελευταία έγκυρα στοιχεία — η ενημέρωση δεν είναι διαθέσιμη", "Last valid data — update unavailable") : t("Τα στοιχεία δεν είναι διαθέσιμα αυτή τη στιγμή", "Data currently unavailable"); }
    if (!acct) {
      ["dReceived", "dCost", "dBalanceVal", "dTimer", "dTsub"].forEach(function(id) { var el = document.getElementById(id); if (el) el.textContent = "—"; });
      document.getElementById("dBalance").className = "fc-acct-total";
      document.getElementById("dBadge").textContent = domainDataState === "loading" ? t("ΦΟΡΤΩΣΗ", "LOADING") : t("ΜΗ ΔΙΑΘΕΣΙΜΟ", "UNAVAILABLE");
      document.getElementById("dTboxLabel").textContent = t("Αναμονή στοιχείων", "Waiting for data");
      ["dGreen", "dYellow", "dRed"].forEach(function(id) { document.getElementById(id).style.display = "none"; });
      return;
    }

    // Accounting display
    var recEl = document.getElementById("dReceived");
    var costEl = document.getElementById("dCost");
    var balEl = document.getElementById("dBalanceVal");
    var balRow = document.getElementById("dBalance");
    if (recEl) { recEl.textContent = eur(acct.received); recEl.style.color = "#166534"; }
    if (costEl) { costEl.textContent = "-" + eur(acct.cost_total); costEl.style.color = "#dc2626"; }
    if (balEl) balEl.textContent = (acct.balance < 0 ? "-" : "") + eur(Math.abs(acct.balance || 0));
    if (balRow) balRow.className = "fc-acct-total " + (acct.balance > 0 ? "positive" : acct.balance < 0 ? "negative" : "zero");

    // Timer
    var timer = document.getElementById("dTimer");
    if (timer) timer.textContent = fmt(Math.max(0, ms));

    var card = document.getElementById("dCard");
    var badge = document.getElementById("dBadge");
    var green = document.getElementById("dGreen");
    var yell = document.getElementById("dYellow");
    var red = document.getElementById("dRed");
    var tbox = document.getElementById("dTbox");
    var tsub = document.getElementById("dTsub");
    if (tsub) tsub.textContent = t("ημ · ώ · λ · δ", "d · h · m · s");
    var tboxLabel = document.getElementById("dTboxLabel");
    if (!card) return;

    if (days <= 0) {
      // EXPIRED — pulsing red
      card.className = "fc pulse-red"; card.style.borderColor = "#ef4444";
      badge.style.background = "#ef4444"; badge.textContent = t("ΛΗΓΜΕΝΟ","EXPIRED");
      if (tbox) tbox.style.background = "#fef2f2";
      if (timer) { timer.style.color = "#dc2626"; timer.textContent = t("ΛΗΓΜΕΝΟ","EXPIRED"); }
      if (tsub) { tsub.style.color = "#dc2626"; tsub.textContent = Math.abs(days) + t(" ημ. εκπρόθεσμο"," days overdue"); }
      if (tboxLabel) { tboxLabel.textContent = t("Domain έχει λήξει!","Domain has expired!"); tboxLabel.style.color = "#dc2626"; }
      if (green) green.style.display = "none"; if (yell) yell.style.display = "none"; if (red) red.style.display = "block";
    } else if (days <= DOMAIN_RED_DAYS) {
      // RED — < 6 months, pulsing
      card.className = "fc pulse-red"; card.style.borderColor = "#ef4444";
      badge.style.background = "#ef4444"; badge.textContent = t("ΕΠΕΙΓΟΝ","URGENT");
      if (tbox) tbox.style.background = "#fef2f2";
      if (timer) timer.style.color = "#dc2626";
      if (tsub) tsub.style.color = "#dc2626";
      if (tboxLabel) { tboxLabel.textContent = t("Χρόνος μέχρι λήξη","Time until expiry"); tboxLabel.style.color = "#dc2626"; }
      if (green) green.style.display = "none"; if (yell) yell.style.display = "none"; if (red) red.style.display = "block";
    } else if (days <= DOMAIN_YELLOW_DAYS) {
      // YELLOW — < 1 year
      card.className = "fc"; card.style.borderColor = "#fde047";
      badge.style.background = "#f59e0b"; badge.textContent = t("ΑΝΑΝΕΩΣΗ","RENEWAL");
      if (tbox) tbox.style.background = "#fefce8";
      if (timer) timer.style.color = "#92400e"; if (tsub) tsub.style.color = "#92400e";
      if (tboxLabel) { tboxLabel.textContent = t("Χρόνος μέχρι ανανέωση","Time until renewal"); tboxLabel.style.color = "#92400e"; }
      if (green) green.style.display = "none"; if (yell) yell.style.display = "block"; if (red) red.style.display = "none";
    } else {
      // GREEN — > 1 year remaining
      card.className = "fc"; card.style.borderColor = "#86efac";
      badge.style.background = "#22c55e"; badge.textContent = t("ΕΞΟΦΛΗΜΕΝΟ","PAID");
      if (tbox) tbox.style.background = "#f0fdf4";
      if (timer) timer.style.color = "#166534"; if (tsub) tsub.style.color = "#166534";
      if (tboxLabel) { tboxLabel.textContent = t("Χρόνος μέχρι ανανέωση","Time until renewal"); tboxLabel.style.color = "#166534"; }
      if (green) green.style.display = "block"; if (yell) yell.style.display = "none"; if (red) red.style.display = "none";
    }
  }

  // ═══════════════════════════════════════════════════════════
  // ARWEAVE LIVE BALANCE
  // ═══════════════════════════════════════════════════════════
  var arLastBalance = null;
  var arLastPrice = null;

  function fetchArweaveBalance() {
    fetch("https://api.ekklesia.gr/api/v1/arweave/status")
      .then(function(r) { return r.json(); })
      .then(function(data) {
        arLastBalance = typeof data.balance_ar === "number" ? data.balance_ar : null;
        updateArweaveTile();
      })
      .catch(function() {
        var el = document.getElementById("arBalance");
        if (el) el.textContent = "Offline";
      });
  }

  function fetchArweavePrice() {
    fetch("https://api.coingecko.com/api/v3/simple/price?ids=arweave&vs_currencies=usd")
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (data && data.arweave) arLastPrice = data.arweave.usd;
        updateArweaveTile();
      })
      .catch(function() { /* price unavailable, show AR only */ });
  }

  function updateArweaveTile() {
    var balEl = document.getElementById("arBalance");
    var usdEl = document.getElementById("arBalanceUsd");
    var statusEl = document.getElementById("arStatusText");
    var card = document.getElementById("arCard");
    var badge = document.getElementById("arBadge");
    var statusBox = document.getElementById("arStatus");

    if (arLastBalance === null) return;

    if (balEl) balEl.textContent = arLastBalance.toFixed(4) + " AR";
    if (usdEl && arLastPrice) usdEl.textContent = "≈ $" + (arLastBalance * arLastPrice).toFixed(4);

    // Ampel
    if (arLastBalance < AR_CRIT_THRESHOLD) {
      // RED
      if (card) { card.className = "fc pulse-red"; card.style.borderColor = "#ef4444"; }
      if (badge) { badge.style.background = "#ef4444"; badge.textContent = t("ΚΡΙΣΙΜΟ","CRITICAL"); }
      if (statusBox) { statusBox.style.background = "#fef2f2"; statusBox.style.color = "#dc2626"; }
      if (statusEl) statusEl.textContent = t("Κρίσιμο υπόλοιπο — χρειάζεται AR","Critical balance — AR needed");
    } else if (arLastBalance < AR_WARN_THRESHOLD) {
      // YELLOW
      if (card) { card.className = "fc"; card.style.borderColor = "#fde047"; }
      if (badge) { badge.style.background = "#f59e0b"; badge.textContent = t("ΧΑΜΗΛΟ","LOW"); }
      if (statusBox) { statusBox.style.background = "#fefce8"; statusBox.style.color = "#92400e"; }
      if (statusEl) statusEl.textContent = t("Χαμηλό υπόλοιπο — σκεφτείτε δωρεά AR","Low balance — consider donating AR");
    } else {
      // GREEN
      if (card) { card.className = "fc"; card.style.borderColor = "#86efac"; }
      if (badge) { badge.style.background = "#22c55e"; badge.textContent = t("ΕΝΕΡΓΟ","ACTIVE"); }
      if (statusBox) { statusBox.style.background = "#f0fdf4"; statusBox.style.color = "#166534"; }
      if (statusEl) statusEl.textContent = t("Wallet ενεργό — ","Wallet active — ") + arLastBalance.toFixed(2) + " AR";
    }
  }

  // ═══════════════════════════════════════════════════════════
  // HLR LIVE STATUS (TABBED PRIMARY/FALLBACK) — grobes, datensparsames Schema
  // ═══════════════════════════════════════════════════════════
  var HLR_LEVEL_PCT = { high: 100, medium: 60, low: 25, empty: 0 };
  var hlrActiveTab = "primary";

  function switchHlrTab(tab) {
    hlrActiveTab = tab;
    var pp = document.getElementById("hlrPanelPrimary");
    var pf = document.getElementById("hlrPanelFallback");
    var bp = document.getElementById("hlrTabPrimary");
    var bf = document.getElementById("hlrTabFallback");
    if (tab === "primary") {
      if (pp) pp.style.display = "";
      if (pf) pf.style.display = "none";
      if (bp) { bp.style.border = "2px solid #3b82f6"; bp.style.background = "#eff6ff"; bp.style.color = "#1d4ed8"; }
      if (bf) { bf.style.border = "2px solid #e2e8f0"; bf.style.background = "white"; bf.style.color = "var(--gray-500)"; }
    } else {
      if (pp) pp.style.display = "none";
      if (pf) pf.style.display = "";
      if (bf) { bf.style.border = "2px solid #3b82f6"; bf.style.background = "#eff6ff"; bf.style.color = "#1d4ed8"; }
      if (bp) { bp.style.border = "2px solid #e2e8f0"; bp.style.background = "white"; bp.style.color = "var(--gray-500)"; }
    }
  }

  function fetchHlrCredits() {
    fetch("https://api.ekklesia.gr/api/v1/identity/hlr/credits")
      .then(function(r) { return r.json(); })
      .then(function(data) { updateHlrTile(data); })
      .catch(function() {
        var st = document.getElementById("hlrStatusText");
        if (st) st.textContent = t("API εκτός σύνδεσης — δεδομένα μη διαθέσιμα","API offline — data unavailable");
      });
  }

  function hlrLevelLabel(level) {
    if (level === "high") return t("Πλήρως διαθέσιμο","Fully available");
    if (level === "medium") return t("Επαρκές απόθεμα","Sufficient reserve");
    if (level === "low") return t("Χαμηλό απόθεμα","Low reserve");
    return t("Εξαντλήθηκε","Depleted");
  }

  function updateHlrProvider(prefix, pData) {
    var level = pData.level || "empty";
    var status = pData.status || "critical";
    var pct = HLR_LEVEL_PCT[level] !== undefined ? HLR_LEVEL_PCT[level] : 0;

    var remEl = document.getElementById(prefix + "Remaining");
    var balRow = document.getElementById(prefix + "Balance");
    var bar = document.getElementById(prefix + "Bar");
    var barLabel = document.getElementById(prefix + "BarLabel");
    var statusBox = document.getElementById(prefix + "StatusBox");
    var statusText = document.getElementById(prefix + "StatusText");

    if (remEl) remEl.textContent = hlrLevelLabel(level);
    if (balRow) balRow.className = "fc-acct-total " + (status === "ok" ? "positive" : status === "low" ? "zero" : "negative");
    if (bar) bar.style.width = pct + "%";
    if (barLabel) barLabel.textContent = hlrLevelLabel(level);

    if (status === "critical") {
      if (bar) bar.style.background = "#ef4444";
      if (statusBox) { statusBox.style.background = "#fef2f2"; statusBox.style.color = "#dc2626"; }
      if (statusText) statusText.textContent = t("Κρίσιμο — σχεδόν εξαντλημένο","Critical — almost depleted");
    } else if (status === "low") {
      if (bar) bar.style.background = "#f59e0b";
      if (statusBox) { statusBox.style.background = "#fefce8"; statusBox.style.color = "#92400e"; }
      if (statusText) statusText.textContent = t("Χαμηλό απόθεμα — παρακολουθείται","Low reserve — monitored");
    } else {
      if (bar) bar.style.background = "#22c55e";
      if (statusBox) { statusBox.style.background = "#f0fdf4"; statusBox.style.color = "#166534"; }
      if (statusText) statusText.textContent = t("Διαθέσιμο για επαληθεύσεις","Available for verifications");
    }
  }

  function updateHlrTile(data) {
    // Primary tab
    var primary = data.primary || {};
    updateHlrProvider("hlr", primary);

    // Fallback tab
    var fb = data.fallback || {};
    if (fb.status !== undefined) {
      updateHlrProvider("hlrFb", fb);
    }

    // Card-level badge: use active-path status
    var card = document.getElementById("hlrCard");
    var badge = document.getElementById("hlrBadge");
    var activeStatus = data.status || primary.status || "critical";

    if (activeStatus === "critical") {
      if (card) { card.className = "fc pulse-red"; card.style.borderColor = "#ef4444"; }
      if (badge) { badge.style.background = "#ef4444"; badge.textContent = t("ΚΡΙΣΙΜΟ","CRITICAL"); }
    } else if (activeStatus === "low") {
      if (card) { card.className = "fc"; card.style.borderColor = "#fde047"; }
      if (badge) { badge.style.background = "#f59e0b"; badge.textContent = t("ΧΑΜΗΛΟ","LOW"); }
    } else {
      if (card) { card.className = "fc"; card.style.borderColor = "#86efac"; }
      if (badge) { badge.style.background = "#22c55e"; badge.textContent = t("ΕΝΕΡΓΟ","ACTIVE"); }
    }

    // Failover notice (generisch — kein Grund, keine Provider-Details)
    var notice = document.getElementById("hlrFailoverNotice");
    var noticeText = document.getElementById("hlrFailoverText");
    if (data.failover_active) {
      if (notice) notice.style.display = "";
      if (noticeText) noticeText.textContent = t(
        "Auto-Failover ενεργό — εφεδρική παροχή σε χρήση",
        "Auto-Failover active — backup service in use"
      );
    } else {
      if (notice) notice.style.display = "none";
    }
  }

    // NEWSLETTER LIVE STATS
  // ═══════════════════════════════════════════════════════════
  function fetchNewsletterStats() {
    fetch("https://api.ekklesia.gr/api/v1/newsletter/stats")
      .then(function(r) { return r.json(); })
      .then(function(d) {
        var plan = document.getElementById("nlPlan");
        var sent = document.getElementById("nlSent");
        var subs = document.getElementById("nlSubs");
        var cost = document.getElementById("nlCost");
        var bar = document.getElementById("nlBar");
        var barLabel = document.getElementById("nlBarLabel");
        var card = document.getElementById("nlCard");
        var badge = document.getElementById("nlBadge");
        var statusBox = document.getElementById("nlStatus");
        var statusText = document.getElementById("nlStatusText");

        if (plan) plan.textContent = d.plan || "Free";
        if (sent) sent.textContent = (d.emails_sent_month || 0).toLocaleString() + " / " + (d.monthly_limit || 9000).toLocaleString();
        if (subs) subs.textContent = d.subscribers || 0;
        if (cost) { cost.textContent = (d.monthly_cost_eur || 0) + "\u20AC"; cost.style.color = d.monthly_cost_eur > 0 ? "#dc2626" : "#166534"; }
        var pct = d.usage_percent || 0;
        if (bar) bar.style.width = pct + "%";
        if (barLabel) barLabel.textContent = pct + t("% χρήση","% usage");

        if (d.status === "paid") {
          if (card) { card.className = "fc pulse-red"; card.style.borderColor = "#ef4444"; }
          if (badge) { badge.style.background = "#ef4444"; badge.textContent = t("ΠΛΗΡΩΜΕΝΟ","PAID"); }
          if (bar) bar.style.background = "#ef4444";
          if (statusBox) { statusBox.style.background = "#fef2f2"; statusBox.style.color = "#dc2626"; }
          if (statusText) statusText.textContent = t("Πληρωμένο πρόγραμμα — ","Paid plan — ") + d.monthly_cost_eur + "\u20AC/" + t("μήνα","month");
        } else if (d.status === "warning") {
          if (card) { card.className = "fc"; card.style.borderColor = "#fde047"; }
          if (badge) { badge.style.background = "#f59e0b"; badge.textContent = t("ΠΡΟΣΟΧΗ","ATTENTION"); }
          if (bar) bar.style.background = "#f59e0b";
          if (statusBox) { statusBox.style.background = "#fefce8"; statusBox.style.color = "#92400e"; }
          if (statusText) statusText.textContent = t("Πλησιάζει το όριο","Approaching limit");
        } else {
          if (card) { card.className = "fc"; card.style.borderColor = "#86efac"; }
          if (badge) { badge.style.background = "#22c55e"; badge.textContent = t("ΕΝΕΡΓΟ","ACTIVE"); }
          if (bar) bar.style.background = "#22c55e";
          if (statusBox) { statusBox.style.background = "#f0fdf4"; statusBox.style.color = "#166534"; }
          if (statusText) statusText.textContent = t("Free plan — ","Free plan — ") + (d.subscribers || 0) + t(" εγγεγραμμένοι"," subscribers");
        }
      })
      .catch(function() {
        var st = document.getElementById("nlStatusText");
        if (st) st.textContent = t("Μη διαθέσιμο","Unavailable");
      });
  }

  // ═══════════════════════════════════════════════════════════
  // TICK — runs every second
  // ═══════════════════════════════════════════════════════════
  function tick() {
    updateServerTile();
    updateDomainTile();
    updateReserveTile();
    updateAutoRecoveryTransparency();
  }

  // Init
  document.addEventListener("community-language-change", tick);
  tick();
  setInterval(tick, 1000);

  // Fetch live data
  fetchPaymentStatus();
  fetchMirrorStatus();
  fetchArweaveBalance();
  fetchArweavePrice();
  fetchHlrCredits();
  fetchNewsletterStats();
  setInterval(fetchPaymentStatus, 60000);    // Server/Domain balances every 60s
  setInterval(fetchMirrorStatus, 30000);     // Mirror health every 30s
  setInterval(fetchArweaveBalance, 60000);   // AR balance every 60s
  setInterval(fetchArweavePrice, 300000);    // AR price every 5min
  setInterval(fetchHlrCredits, 30000);       // HLR credits every 30s
  setInterval(fetchNewsletterStats, 60000);  // Newsletter stats every 60s

  // Transparenz Live-Daten
  function fetchTransparency() {
    fetch("https://api.ekklesia.gr/api/v1/payments/public/finance")
      .then(function(r) { return r.json(); })
      .then(function(d) {
        var hlrEl = document.getElementById("tranHlr");
        var runEl = document.getElementById("tranRunway");
        var donEl = document.getElementById("tranDonations");
        if (hlrEl && d.hlr_verifikationen_moeglich != null) hlrEl.textContent = d.hlr_verifikationen_moeglich.toLocaleString("el-GR");
        if (runEl && d.server_gedeckt_monate != null) runEl.textContent = d.server_gedeckt_monate;
        if (donEl && d.spenden_gesamt != null) donEl.textContent = d.spenden_gesamt;
      })
      .catch(function() {});
  }
  fetchTransparency();
  setInterval(fetchTransparency, 60000);

  // DeepL usage + billing cycle (resets on 26th of each month, started 26.04.2026)
  function deeplBillingCycle() {
    var now = new Date();
    var resetDay = 26;
    var startY = now.getFullYear(), startM = now.getMonth();
    // Current period start: 26th of this month or last month
    if (now.getDate() < resetDay) { startM--; if (startM < 0) { startM = 11; startY--; } }
    var periodStart = new Date(startY, startM, resetDay);
    var nextM = startM + 1, nextY = startY;
    if (nextM > 11) { nextM = 0; nextY++; }
    var periodEnd = new Date(nextY, nextM, resetDay);
    var daysLeft = Math.ceil((periodEnd - now) / 86400000);
    var fmt = function(d) { return d.getDate().toString().padStart(2,"0") + "." + (d.getMonth()+1).toString().padStart(2,"0") + "." + d.getFullYear(); };
    return { start: fmt(periodStart), end: fmt(periodEnd), daysLeft: daysLeft };
  }
  function fetchDeeplUsage() {
    var cycle = deeplBillingCycle();
    var per = document.getElementById("deeplPeriod");
    if (per) per.textContent = cycle.start + " — " + cycle.end;
    var days = document.getElementById("deeplDays");
    if (days) days.textContent = cycle.daysLeft + " " + (currentLang === "en" ? "days" : "ημέρες");
    fetch("https://api.ekklesia.gr/api/v1/public/deepl/usage")
      .then(function(r) { return r.json(); })
      .then(function(d) {
        if (!d.available) return;
        var used = d.character_count || 0;
        var limit = d.character_limit || 500000;
        var pct = Math.round(used / limit * 100);
        var el = document.getElementById("deeplUsed");
        if (el) el.textContent = used.toLocaleString() + " / " + limit.toLocaleString();
        var lim = document.getElementById("deeplLimit");
        if (lim) lim.innerHTML = limit.toLocaleString() + " <span>" + (currentLang === "en" ? "chars/month" : "χαρ./μήνα") + "</span>";
        var bar = document.getElementById("deeplBar");
        if (bar) { bar.style.width = pct + "%"; bar.style.background = pct > 80 ? "#ef4444" : pct > 50 ? "#f59e0b" : "#22c55e"; }
        var lbl = document.getElementById("deeplBarLabel");
        if (lbl) lbl.textContent = pct + "% " + (currentLang === "en" ? "usage" : "χρήση");
      }).catch(function() {});
  }
  fetchDeeplUsage();
  setInterval(fetchDeeplUsage, 60000);

  // Claude AI Status
  function fetchClaudeStatus() {
    fetch("https://api.ekklesia.gr/api/v1/claude/budget")
      .then(function(r){return r.json()})
      .then(function(d){
        var today=document.getElementById("claudeToday");
        if(today) today.textContent=(d.tokens_today || 0).toLocaleString()+" tokens";
        var month=document.getElementById("claudeMonth");
        if(month) month.textContent=(d.tokens_month || 0).toLocaleString()+" tokens";
        var analysis=document.getElementById("claudeAnalysis");
        if(analysis) analysis.textContent=(d.analysis_tokens_month || 0).toLocaleString()+" tokens";
        var cost=document.getElementById("claudeCost");
        if(cost) {
          var costVal = d.estimated_cost_usd_month;
          cost.textContent = costVal != null ? "$" + Number(costVal).toFixed(4) : (currentLang==="en" ? "usage only" : "μόνο χρήση");
        }
        var model=document.getElementById("claudeModel");
        if(model) model.textContent="V-Labs Artificial Systems · vlabs.gr";
        var card=document.getElementById("claudeCard");
        var badge=document.getElementById("claudeBadge");
        var status=document.getElementById("claudeStatus");
        var btn=document.getElementById("claudeDonateBtn");
        if(d.is_active){
          if(card)card.style.borderColor="#86efac";
          if(badge){badge.style.background="#22c55e";badge.textContent=currentLang==="en"?"ACTIVE":"ΕΝΕΡΓΟ";}
          if(status){status.style.background="#f0fdf4";status.style.color="#166534";status.innerHTML="✅ "+(currentLang==="en"?"AI active — chat + bill analysis":"AI ενεργή — chat + ανάλυση νόμων");}
          if(btn)btn.style.display="none";
        } else {
          if(card)card.style.borderColor="#fca5a5";
          if(badge){badge.style.background="#ef4444";badge.textContent=currentLang==="en"?"INACTIVE":"ΑΝΕΝΕΡΓΟ";}
          if(status){status.style.background="#fef2f2";status.style.color="#991b1b";status.innerHTML="⚠️ "+(currentLang==="en"?"Credits depleted":"Τα credits εξαντλήθηκαν");}
          if(btn)btn.style.display="block";
        }
      }).catch(function(){});
  }
  fetchClaudeStatus();
  setInterval(fetchClaudeStatus, 30000);
})();
