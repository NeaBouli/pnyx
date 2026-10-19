
// Populate category sidebar + select
var catSidebar = document.getElementById("categorySidebar");
var catSelect = document.getElementById("ticketCategory");
POLIS_CONFIG.categories.forEach(function(cat) {
  catSidebar.innerHTML += '<div class="sidebar-option" data-csp-click="filter-category" data-value="category:' + cat.id + '">' + (polisLang === "el" ? cat.el : cat.en) + '</div>';
  var opt = document.createElement("option");
  opt.value = cat.id;
  opt.textContent = polisLang === "el" ? cat.el : cat.en;
  catSelect.appendChild(opt);
});

// Filter state
var currentFilters = { labels: "", sort: "newest" };

function filterByStatus(el, label) {
  el.parentElement.querySelectorAll(".sidebar-option").forEach(function(o) { o.classList.remove("active"); });
  el.classList.add("active");
  // Combine with category filter
  var parts = [];
  if (label) parts.push(label);
  if (currentFilters._cat) parts.push(currentFilters._cat);
  currentFilters.labels = parts.join(",");
  polisPage = 1;
  loadAndRender(currentFilters);
}

function filterByCat(el, label) {
  el.parentElement.querySelectorAll(".sidebar-option").forEach(function(o) { o.classList.remove("active"); });
  el.classList.add("active");
  currentFilters._cat = label;
  // Combine with status filter
  var parts = [];
  if (currentFilters._status) parts.push(currentFilters._status);
  if (label) parts.push(label);
  currentFilters.labels = parts.join(",");
  polisPage = 1;
  loadAndRender(currentFilters);
}

function sortBy(el, sort) {
  el.parentElement.querySelectorAll(".sidebar-option").forEach(function(o) { o.classList.remove("active"); });
  el.classList.add("active");
  currentFilters.sort = sort;
  polisPage = 1;
  loadAndRender(currentFilters);
}

async function loadMoreTickets() {
  polisPage++;
  var more = await loadTickets(polisPage, currentFilters);
  polisTickets = polisTickets.concat(more);
  renderTicketList();
}

// Init
initPolis();

// ── QR-Code Browser Login ────────────────────────────────────────────────
var qrSessionId = null;
var qrPollTimer = null;

var _qrStrings = {
  el: { title: "Σύνδεση με εφαρμογή εκκλησία", scan: "Σαρώστε τον κωδικό QR με την εφαρμογή", loading: "Φόρτωση...", waiting: "Αναμονή σάρωσης...", cancel: "Ακύρωση", error: "Σφάλμα φόρτωσης", success: "✓ Επαληθεύτηκε!", expired: "Η σύνδεση έληξε" },
  en: { title: "Login with ekklesia App", scan: "Scan the QR code with the app", loading: "Loading...", waiting: "Waiting for app scan...", cancel: "Cancel", error: "Loading error", success: "✓ Authenticated!", expired: "Session expired" }
};
function _qr(key) { return (_qrStrings[polisLang] || _qrStrings.el)[key] || key; }

function openQRLogin() {
  // Create modal
  var overlay = document.createElement("div");
  overlay.id = "qrOverlay";
  overlay.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:9999;display:flex;align-items:center;justify-content:center";
  overlay.innerHTML = '<div style="background:#fff;border-radius:16px;padding:24px;max-width:340px;text-align:center">' +
    '<h3 style="margin:0 0 8px;font-size:16px;color:#1e293b">' + _qr("title") + '</h3>' +
    '<p style="font-size:12px;color:#64748b;margin:0 0 16px">' + _qr("scan") + '</p>' +
    '<div id="qrCodeBox" style="background:#f8fafc;border:2px dashed #e2e8f0;border-radius:12px;padding:24px;margin-bottom:12px;min-height:200px;display:flex;align-items:center;justify-content:center">' +
    '<span style="color:#94a3b8">' + _qr("loading") + '</span></div>' +
    '<p id="qrStatus" style="font-size:12px;color:#64748b;margin:0 0 12px">' + _qr("waiting") + '</p>' +
    '<button data-csp-click="close-qr-login" style="padding:8px 20px;background:#f1f5f9;border:1px solid #e2e8f0;border-radius:8px;font-size:13px;cursor:pointer">' + _qr("cancel") + '</button>' +
    '</div>';
  document.body.appendChild(overlay);

  // Fetch session
  fetch("https://api.ekklesia.gr/api/v1/polis/qr-session")
    .then(function(r){return r.json()})
    .then(function(d){
      qrSessionId = d.session_id;
      var box = document.getElementById("qrCodeBox");
      if (box) {
        // Generate QR using simple SVG (no library needed)
        box.innerHTML = '<div style="padding:16px;background:#fff;border-radius:8px;border:1px solid #e2e8f0">' +
          '<img src="https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=' + encodeURIComponent(d.qr_data) + '" width="200" height="200" alt="QR"/>' +
          '</div><p style="font-size:10px;color:#94a3b8;margin:8px 0 0">TTL: 5 min</p>';
      }
      // Start polling
      qrPollTimer = setInterval(pollQRSession, 2000);
    })
    .catch(function(){
      var box = document.getElementById("qrCodeBox");
      if (box) box.innerHTML = '<span style="color:#ef4444">' + _qr("error") + '</span>';
    });
}

function pollQRSession() {
  if (!qrSessionId) return;
  fetch("https://api.ekklesia.gr/api/v1/polis/qr-session/" + qrSessionId)
    .then(function(r){return r.json()})
    .then(function(d){
      var st = document.getElementById("qrStatus");
      if (d.status === "authenticated") {
        if (st) st.innerHTML = '<span style="color:#22c55e;font-weight:700">' + _qr("success") + '</span>';
        clearInterval(qrPollTimer);
        // Store auth in session
        sessionStorage.setItem("polis_nullifier", d.nullifier_hash || "");
        sessionStorage.setItem("polis_pubkey", d.public_key_hex || "");
        setTimeout(function(){
          closeQRLogin();
          // Check pending action
          var pending = sessionStorage.getItem("polis_pending_action");
          sessionStorage.removeItem("polis_pending_action");
          if (pending === "new-ticket" && typeof openNewTicketModal === "function") {
            updateQRVerifiedStatus();
            openNewTicketModal();
          } else {
            location.reload();
          }
        }, 1500);
      } else if (d.status === "expired") {
        if (st) st.innerHTML = '<span style="color:#ef4444">' + _qr("expired") + '</span>';
        clearInterval(qrPollTimer);
      }
    }).catch(function(){});
}

function updateQRVerifiedStatus() {
  var badge = document.getElementById("qrVerifiedBadge");
  var btn = document.getElementById("qrLoginBtn");
  var verified = !!sessionStorage.getItem("polis_nullifier");
  if (badge) badge.style.display = verified ? "inline" : "none";
  if (btn) btn.style.display = verified ? "none" : "inline-block";
}
document.addEventListener("DOMContentLoaded", updateQRVerifiedStatus);

function closeQRLogin() {
  clearInterval(qrPollTimer);
  qrSessionId = null;
  var ov = document.getElementById("qrOverlay");
  if (ov) ov.remove();
}
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    closeQRLogin();
    var pb = document.getElementById('phaseBModal');
    if (pb) pb.style.display = 'none';
  }
});
