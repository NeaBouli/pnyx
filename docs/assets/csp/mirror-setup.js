
var currentLang="el";
function toggleLang(){currentLang=currentLang==="el"?"en":"el";document.querySelectorAll("[data-el]").forEach(function(el){var t=el.getAttribute("data-"+currentLang);if(t)el.innerHTML=t;})}
// Mirror status check (future: fetch from API)
// For now: static "available"
