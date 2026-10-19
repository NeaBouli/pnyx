
var currentLang = "el";
function toggleLang() {
  currentLang = currentLang === "el" ? "en" : "el";
  document.getElementById("langBtn").textContent = currentLang === "el" ? "EN" : "ΕΛ";
  document.querySelectorAll("[data-el]").forEach(function(el) {
    var t = el.getAttribute("data-" + currentLang);
    if (t) el.innerHTML = t;
  });
}
var obs = new IntersectionObserver(function(entries) {
  entries.forEach(function(e) { if (e.isIntersecting) e.target.classList.add("visible"); });
}, { threshold: 0.1 });
document.querySelectorAll(".fade-in").forEach(function(el) { obs.observe(el); });
