(function () {
  function foldBody(body, heading, className) {
    if (!body || !heading) return null;
    var details = document.createElement("details");
    details.className = "pnx2-fold " + (className || "");
    var summary = document.createElement("summary");
    summary.className = "pnx2-fold-summary";
    summary.appendChild(heading);
    details.appendChild(summary);
    Array.from(body.childNodes).forEach(function (node) { details.appendChild(node); });
    body.appendChild(details);
    return details;
  }

  function foldSection(id) {
    var section = document.getElementById(id);
    if (!section) return;
    var body = section.querySelector(":scope > .section-inner") ||
      (id === "notice" ? section.querySelector(":scope > div") : null) || section;
    var heading = body.querySelector(":scope > h2, :scope > h3, :scope > .demo-title");
    foldBody(body, heading);
  }

  function init() {
    ["how", "demo", "forum", "roadmap", "wiki-section", "notice", "contact"].forEach(foldSection);

    var transparency = document.getElementById("transparency");
    if (transparency) foldBody(transparency, transparency.querySelector(":scope > h2"));

    var features = document.querySelector("#features > .section-inner");
    if (features) {
      var featureHeading = features.querySelector(":scope > .section-title");
      var featureGrid = features.querySelector(":scope > .features-grid");
      if (featureHeading && featureGrid) {
        var featureFold = document.createElement("details");
        featureFold.className = "pnx2-fold pnx2-features-fold";
        var featureSummary = document.createElement("summary");
        featureSummary.className = "pnx2-fold-summary";
        featureSummary.appendChild(featureHeading);
        featureFold.appendChild(featureSummary);
        featureFold.appendChild(featureGrid);
        features.insertBefore(featureFold, document.getElementById("representative"));
      }
    }

    var representative = document.getElementById("representative");
    var representativeHeading = representative && representative.querySelector("h3");
    if (representative && representativeHeading) {
      var representativeFold = document.createElement("details");
      representativeFold.className = "pnx2-fold pnx2-representative-fold";
      var representativeSummary = document.createElement("summary");
      representativeSummary.className = "pnx2-fold-summary";
      representativeSummary.appendChild(representativeHeading);
      var representativeBody = document.createElement("div");
      representativeBody.className = "pnx2-representative-body";
      Array.from(representative.childNodes).forEach(function (node) { representativeBody.appendChild(node); });
      representativeFold.appendChild(representativeSummary);
      representativeFold.appendChild(representativeBody);
      representative.appendChild(representativeFold);
    }

    function openHashTarget() {
      var id;
      try { id = decodeURIComponent(window.location.hash.slice(1)); } catch (_) { return; }
      if (!id) return;
      var target = document.getElementById(id);
      if (!target) return;
      var details = id === "features"
        ? target.querySelector(".pnx2-features-fold")
        : target.closest("details");
      if (!details) {
        var fold = target.querySelector(".pnx2-fold");
        if (fold && fold.closest("[id]") === target) details = fold;
      }
      if (details) {
        details.open = true;
        // T-383: defer scroll until the browser has laid out the newly-opened fold,
        // otherwise scrollIntoView may land under the sticky header.
        requestAnimationFrame(function () {
          target.scrollIntoView({ block: "start" });
        });
      }
    }

    window.addEventListener("hashchange", openHashTarget);
    document.addEventListener("click", function (event) {
      var link = event.target.closest("a[href^='#']");
      if (link) window.requestAnimationFrame(openHashTarget);
    });
    openHashTarget();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
