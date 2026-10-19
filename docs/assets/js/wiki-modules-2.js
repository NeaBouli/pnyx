
var currentLang = "el";
function toggleLang() {
  currentLang = currentLang === "el" ? "en" : "el";
  if (document.getElementById("langBtn")) document.getElementById("langBtn").textContent = currentLang === "el" ? "EN" : "ΕΛ";
  document.querySelectorAll("[data-el]").forEach(function(el) {
    var t = el.getAttribute("data-" + currentLang);
    if (t) el.innerHTML = t;
  });
  if (typeof refreshHealthLabels === "function") refreshHealthLabels();
}
var obs = new IntersectionObserver(function(entries) {
  entries.forEach(function(e) { if (e.isIntersecting) e.target.classList.add("visible"); });
}, { threshold: 0.1 });
document.querySelectorAll(".fade-in").forEach(function(el) { obs.observe(el); });

// Live module health status polling (every 30s)
// MOD-24 (CPLM) and MOD-02b have no matching health scope: they stay neutral.
var refreshHealthLabels;
(function() {
  var MOD_DOT_MAP = {
    "MOD-01":"dot-mod01","MOD-02":"dot-mod02","MOD-03":"dot-mod03",
    "MOD-04":"dot-mod04","MOD-05":"dot-mod05","MOD-06":"dot-mod06",
    "MOD-07":"dot-mod07","MOD-08":"dot-mod08","MOD-09":"dot-mod09",
    "MOD-10":"dot-mod10","MOD-11":"dot-mod11","MOD-12":"dot-mod12",
    "MOD-14":"dot-mod14","MOD-15":"dot-mod15","MOD-16":"dot-mod16",
    "MOD-19":"dot-mod19","MOD-20":"dot-mod20",
    "MOD-21":"dot-mod21","MOD-22":"dot-mod22","MOD-23":"dot-mod23",
    "MOD-25":"dot-mod25"
  };
  var UNMAPPED_DOTS = ["dot-mod02b","dot-mod24"];
  var STATUS_CLASS = {ok:"dot-active",degraded:"dot-degraded",error:"dot-error",deferred:"dot-planned",disabled:"dot-planned",unknown:"dot-unknown"};
  var STATUS_LABEL = {
    ok:{el:"Κατάσταση: λειτουργεί",en:"Status: operational"},
    degraded:{el:"Κατάσταση: μειωμένη λειτουργία",en:"Status: degraded"},
    error:{el:"Κατάσταση: σφάλμα",en:"Status: error"},
    deferred:{el:"Κατάσταση: σε αναμονή",en:"Status: deferred"},
    disabled:{el:"Κατάσταση: απενεργοποιημένο",en:"Status: disabled"},
    unknown:{el:"Κατάσταση: άγνωστη",en:"Status: unknown"}
  };
  var ALL_CLASSES = ["dot-active","dot-inactive","dot-planned","dot-error","dot-degraded","dot-unknown"];
  function label(el) {
    var st = el.getAttribute("data-health") || "unknown";
    var t = STATUS_LABEL[st][currentLang] || STATUS_LABEL[st].el;
    el.setAttribute("role","img");
    el.setAttribute("title",t);
    el.setAttribute("aria-label",t);
  }
  function setStatus(el, st) {
    if (!STATUS_CLASS.hasOwnProperty(st)) st = "unknown";
    ALL_CLASSES.forEach(function(c){ el.classList.remove(c); });
    el.classList.add(STATUS_CLASS[st]);
    el.setAttribute("data-health", st);
    label(el);
    var row=el.closest("tr");
    if(row){
      row.style.background=(st==="error")?"#fff1f2":(st==="degraded")?"#fffbeb":"";
      row.style.borderLeft=(st==="error")?"3px solid #ef4444":(st==="degraded")?"3px solid #f59e0b":"";
    }
  }
  function eachDot(fn) {
    Object.keys(MOD_DOT_MAP).forEach(function(modId){
      var el=document.getElementById(MOD_DOT_MAP[modId]);
      if(el) fn(modId, el);
    });
  }
  // Failed refresh: never keep green as current health; planned (deferred/disabled) stays planned.
  function markUnknown() {
    eachDot(function(modId, el){
      if(el.getAttribute("data-health")!=="deferred" && el.getAttribute("data-health")!=="disabled") setStatus(el,"unknown");
    });
  }
  refreshHealthLabels = function() {
    eachDot(function(modId, el){ if(el.hasAttribute("data-health")) label(el); });
    UNMAPPED_DOTS.forEach(function(id){ var el=document.getElementById(id); if(el) label(el); });
  };
  UNMAPPED_DOTS.forEach(function(id){ var el=document.getElementById(id); if(el) setStatus(el,"unknown"); });
  eachDot(function(modId, el){ setStatus(el, el.classList.contains("dot-planned") ? "deferred" : "unknown"); });
  function pollHealth() {
    fetch("https://api.ekklesia.gr/api/v1/health/modules")
      .then(function(r){ if(!r.ok) throw new Error("http"); return r.json(); })
      .then(function(d){
        var mods = d && d.modules;
        if(!mods || typeof mods!=="object" || Array.isArray(mods)) { markUnknown(); return; }
        eachDot(function(modId, el){
          var info = mods[modId];
          var st = (info && typeof info==="object" && typeof info.status==="string") ? info.status : "unknown";
          setStatus(el, st);
        });
      }).catch(markUnknown);
  }
  pollHealth();
  setInterval(pollHealth, 30000);
})();
