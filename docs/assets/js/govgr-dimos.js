
var currentLang = "el";
function toggleLang() {
  currentLang = currentLang === "el" ? "en" : "el";
  document.getElementById("langBtn").textContent = currentLang === "el" ? "EN" : "ΕΛ";
  document.querySelectorAll("[data-el]").forEach(function(el) {
    var t = el.getAttribute("data-" + currentLang);
    if (t) el.innerHTML = t;
  });
}

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
  var fd = new FormData(e.target);
  var status = document.getElementById("ngoStatus");
  var btn = document.getElementById("ngoBtn");
  var fileInput = e.target.querySelector('input[type="file"]');

  // Validate file size (max 5MB) and type
  if (fileInput && fileInput.files.length > 0) {
    var file = fileInput.files[0];
    var allowedTypes = ['application/pdf','application/msword','application/vnd.openxmlformats-officedocument.wordprocessingml.document','application/vnd.oasis.opendocument.text','text/plain','image/png','image/jpeg'];
    if (file.size > 5 * 1024 * 1024) {
      status.style.display = "block";
      status.style.background = "#fee2e2";
      status.style.color = "#991b1b";
      status.innerHTML = currentLang === "el" ? "Το αρχείο υπερβαίνει τα 5MB." : "File exceeds 5MB limit.";
      return;
    }
    if (!allowedTypes.includes(file.type)) {
      status.style.display = "block";
      status.style.background = "#fee2e2";
      status.style.color = "#991b1b";
      status.innerHTML = currentLang === "el" ? "Μη αποδεκτός τύπος αρχείου." : "Invalid file type.";
      return;
    }
  }

  btn.disabled = true;
  btn.textContent = "...";

  fetch("https://api.ekklesia.gr/api/v1/contact/ngo", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      subject: fd.get("subject"),
      first_name: fd.get("first_name"),
      last_name: fd.get("last_name"),
      email: fd.get("email"),
      phone: fd.get("phone") || "",
      org: fd.get("org") || "",
      position: fd.get("position") || "",
      region: fd.get("region") || "",
      message: fd.get("message") || "",
      consent: e.target.querySelector('input[name="consent"]').checked
    })
  }).then(function(r) {
    if (r.ok) {
      status.style.display = "block";
      status.style.background = "#dcfce7";
      status.style.color = "#166534";
      status.innerHTML = currentLang === "el"
        ? "<div style='font-size:1.5rem;margin-bottom:0.5rem'>✅</div><strong>Το μήνυμά σας εστάλη επιτυχώς!</strong><br/><span style='font-size:0.82rem;color:#22863a'>Κάποιος από την ομάδα ανάπτυξης θα επικοινωνήσει μαζί σας.</span>"
        : "<div style='font-size:1.5rem;margin-bottom:0.5rem'>✅</div><strong>Your message was sent successfully!</strong><br/><span style='font-size:0.82rem;color:#22863a'>Someone from the development team will contact you.</span>";
      e.target.style.display = "none";
    } else { throw new Error(); }
  }).catch(function() {
    status.style.display = "block";
    status.style.background = "#fee2e2";
    status.style.color = "#991b1b";
    status.innerHTML = currentLang === "el" ? "Σφάλμα. Δοκιμάστε ξανά." : "Error. Please try again.";
  }).finally(function() {
    btn.disabled = false;
    btn.textContent = currentLang === "el" ? "Αποστολή" : "Send";
  });
}

// Fade-in observer
var obs = new IntersectionObserver(function(entries) {
  entries.forEach(function(e) { if (e.isIntersecting) e.target.classList.add("visible"); });
}, { threshold: 0.1 });
document.querySelectorAll(".fade-in").forEach(function(el) { obs.observe(el); });
