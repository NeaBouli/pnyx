(function () {
  var lang = "el";
  var button = document.getElementById("langBtn");
  button.addEventListener("click", function () {
    lang = lang === "el" ? "en" : "el";
    document.documentElement.lang = lang;
    document.documentElement.dataset.lang = lang;
    document.getElementById("elContent").hidden = lang !== "el";
    document.getElementById("enContent").hidden = lang !== "en";
    document.querySelectorAll("[data-el]").forEach(function (element) {
      element.textContent = element.getAttribute("data-" + lang);
    });
    button.textContent = lang === "el" ? "EN" : "ΕΛ";
  });
}());
