
var currentLang = "el";
function toggleLang() {
  currentLang = currentLang === "el" ? "en" : "el";
  document.documentElement.lang = currentLang;
  if (document.getElementById("langBtn")) document.getElementById("langBtn").textContent = currentLang === "el" ? "EN" : "ΕΛ";
  document.querySelectorAll("[data-el]").forEach(function(el) {
    var t = el.getAttribute("data-" + currentLang);
    if (t) el.innerHTML = t;
  });
  document.dispatchEvent(new Event("community-language-change"));
}
var obs = new IntersectionObserver(function(entries) {
  entries.forEach(function(e) { if (e.isIntersecting) e.target.classList.add("visible"); });
}, { threshold: 0.1 });
document.querySelectorAll(".fade-in").forEach(function(el) { obs.observe(el); });
