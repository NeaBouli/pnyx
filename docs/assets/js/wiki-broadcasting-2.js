
var currentLang="el";function toggleLang(){currentLang=currentLang==="el"?"en":"el";if (document.getElementById("langBtn")) document.getElementById("langBtn").textContent=currentLang==="el"?"EN":"ΕΛ";document.querySelectorAll("[data-el]").forEach(function(el){var t=el.getAttribute("data-"+currentLang);if(t)el.innerHTML=t;})}
