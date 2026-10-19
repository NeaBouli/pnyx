
var currentLang = "el";
function toggleLang() {
  currentLang = currentLang === "el" ? "en" : "el";
  if (document.getElementById("langBtn")) document.getElementById("langBtn").textContent = currentLang === "el" ? "EN" : "ΕΛ";
  document.querySelectorAll("[data-el]").forEach(function(el) {
    var t = el.getAttribute("data-" + currentLang);
    if (t) el.innerHTML = t;
  });
}
function toggleSection(el) {
  var isOpen = el.classList.toggle("open");
  el.setAttribute("aria-expanded", String(isOpen));
}
document.querySelectorAll(".roadmap-section").forEach(function(section) {
  section.setAttribute("role", "button");
  section.setAttribute("tabindex", "0");
  section.setAttribute("aria-expanded", String(section.classList.contains("open")));
  section.addEventListener("keydown", function(event) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      toggleSection(section);
    }
  });
});
var obs = new IntersectionObserver(function(entries) {
  entries.forEach(function(e) { if (e.isIntersecting) e.target.classList.add("visible"); });
}, { threshold: 0.1 });
document.querySelectorAll(".fade-in").forEach(function(el) { obs.observe(el); });
