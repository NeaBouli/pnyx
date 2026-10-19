
(function () {
  var lang = "el";
  var button = document.getElementById("langBtn");
  if (!button) return;
  button.addEventListener("click", function () {
    lang = lang === "el" ? "en" : "el";
    document.documentElement.lang = lang;
    document.documentElement.dataset.lang = lang;
    var elContent = document.getElementById("elContent");
    if (elContent) elContent.hidden = lang !== "el";
    var enContent = document.getElementById("enContent");
    if (enContent) enContent.hidden = lang !== "en";
    document.querySelectorAll("[data-el]").forEach(function (element) {
      element.textContent = element.getAttribute("data-" + lang);
    });
    button.textContent = lang === "el" ? "EN" : "ΕΛ";
  });
}());
