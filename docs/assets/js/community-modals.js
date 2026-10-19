
// NGO Contact Modal
function openNgoModal() {
  var m = document.getElementById("ngoModal");
  m.style.display = "flex";
  document.getElementById("ngoForm").reset();
  document.getElementById("ngoStatus").style.display = "none";
}
function closeNgoModal() { document.getElementById("ngoModal").style.display = "none"; }
document.getElementById("ngoModal").addEventListener("click", function(e) { if (e.target === this) closeNgoModal(); });

function submitNgoForm(e) {
  e.preventDefault();
  var form = document.getElementById("ngoForm");
  var btn = document.getElementById("ngoSubmitBtn");
  var status = document.getElementById("ngoStatus");
  var data = { org: form.org.value, name: form.name.value, email: form.email.value, message: form.message.value };
  btn.disabled = true;
  btn.textContent = (typeof currentLang !== "undefined" && currentLang === "en") ? "Sending..." : "Αποστολή...";
  fetch("https://api.ekklesia.gr/api/v1/contact/ngo", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data)
  }).then(function(r) {
    if (!r.ok) return r.json().then(function(d) { throw new Error(d.detail || "Error"); });
    return r.json();
  }).then(function() {
    status.style.display = "block";
    status.style.color = "#166534";
    status.textContent = (typeof currentLang !== "undefined" && currentLang === "en") ? "Sent successfully!" : "Εστάλη επιτυχώς!";
    btn.textContent = "✅";
    setTimeout(closeNgoModal, 2000);
  }).catch(function(err) {
    status.style.display = "block";
    status.style.color = "#dc2626";
    status.textContent = err.message || "Error";
    btn.disabled = false;
    btn.textContent = (typeof currentLang !== "undefined" && currentLang === "en") ? "Send" : "Αποστολή";
  });
}

// Share Popup
var shareTextEl = "Η φωνή σου μετράει. Ψήφισε για πραγματικά νομοσχέδια στο ekklesia.gr 🏛️ #εκκλησία #δημοκρατία";
var shareTextEn = "Your voice matters. Vote on real legislation at ekklesia.gr 🏛️ #ekklesia #democracy";
var shareUrl = "https://ekklesia.gr";

function getShareText() { return (typeof currentLang !== "undefined" && currentLang === "en") ? shareTextEn : shareTextEl; }

function openSharePopup() {
  var txt = encodeURIComponent(getShareText());
  var url = encodeURIComponent(shareUrl);
  document.getElementById("shareTwitter").href = "https://twitter.com/intent/tweet?text=" + txt + "&url=" + url;
  document.getElementById("shareFacebook").href = "https://www.facebook.com/sharer/sharer.php?u=" + url;
  document.getElementById("shareWhatsApp").href = "https://wa.me/?text=" + txt + "%20" + url;
  document.getElementById("shareEmail").href = "mailto:?subject=" + encodeURIComponent("ekklesia.gr") + "&body=" + txt + "%0A" + url;
  document.getElementById("shareTelegram").href = "https://t.me/share/url?url=" + url + "&text=" + txt;
  document.getElementById("copyLinkBtn").innerHTML = '<span style="font-size:1.1rem">🔗</span> <span>' + ((typeof currentLang !== "undefined" && currentLang === "en") ? "Copy Link" : "Αντιγραφή Συνδέσμου") + '</span>';
  document.getElementById("sharePopup").style.display = "flex";
}
function closeSharePopup() { document.getElementById("sharePopup").style.display = "none"; }
document.getElementById("sharePopup").addEventListener("click", function(e) { if (e.target === this) closeSharePopup(); });

function copyShareLink() {
  navigator.clipboard.writeText(shareUrl).then(function() {
    var btn = document.getElementById("copyLinkBtn");
    btn.innerHTML = '<span style="font-size:1.1rem">🔗</span> <span style="color:#166534">✓ ' + ((typeof currentLang !== "undefined" && currentLang === "en") ? "Copied!" : "Αντιγράφηκε!") + '</span>';
    setTimeout(function() {
      btn.innerHTML = '<span style="font-size:1.1rem">🔗</span> <span>' + ((typeof currentLang !== "undefined" && currentLang === "en") ? "Copy Link" : "Αντιγραφή Συνδέσμου") + '</span>';
    }, 2000);
  });
}
