
var currentLang = "el";
function toggleLang() {
  currentLang = currentLang === "el" ? "en" : "el";
  document.documentElement.lang = currentLang;
  if (document.getElementById("langBtn")) document.getElementById("langBtn").textContent = currentLang === "el" ? "EN" : "ΕΛ";
  document.querySelectorAll("[data-el]").forEach(function(el) {
    var t = el.getAttribute("data-" + currentLang);
    if (t) el.innerHTML = t;
  });
}
var obs = new IntersectionObserver(function(entries) {
  entries.forEach(function(e) { if (e.isIntersecting) e.target.classList.add("visible"); });
}, { threshold: 0.1 });
document.querySelectorAll(".fade-in").forEach(function(el) { obs.observe(el); });
// Horizontal arrow scrolling is not native for focused regions in every engine.
document.querySelector(".code-block")?.addEventListener("keydown", function(e) {
  if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey ||
      (e.key !== "ArrowLeft" && e.key !== "ArrowRight") ||
      this.scrollWidth <= this.clientWidth) return;
  e.preventDefault();
  this.scrollLeft += e.key === "ArrowRight" ? 40 : -40;
});
