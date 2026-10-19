
(function(){
  var QUAD_EL = {
    center: "Κέντρο", libertarian_left: "Ελευθ. Αριστερά",
    libertarian_right: "Ελευθ. Δεξιά", authoritarian_left: "Αυτ. Αριστερά",
    authoritarian_right: "Αυτ. Δεξιά"
  };
  var QUAD_EN = {
    center: "Center", libertarian_left: "Lib. Left",
    libertarian_right: "Lib. Right", authoritarian_left: "Auth. Left",
    authoritarian_right: "Auth. Right"
  };
  function fetchCPLM() {
    fetch("https://api.ekklesia.gr/api/v1/cplm/aggregate")
      .then(function(r){return r.json()})
      .then(function(d){
        var dot = document.getElementById("cplmDot");
        var arrow = document.getElementById("cplmArrow");
        var xEl = document.getElementById("cplmX");
        var yEl = document.getElementById("cplmY");
        var vEl = document.getElementById("cplmVoters");
        var qEl = document.getElementById("cplmQuadrant");
        if (arrow) arrow.setAttribute("opacity", "0");
        var fallback = document.getElementById("cplmFallback");
        if (fallback) fallback.style.opacity = "0";
        if (d.suppressed || !Number.isFinite(d.x) || !Number.isFinite(d.y)) {
          if (dot) dot.setAttribute("visibility", "hidden");
          [xEl, yEl, vEl, qEl].forEach(function(el) {
            if (el) el.textContent = "—";
          });
          if (qEl) {
            qEl.setAttribute("data-el", "—");
            qEl.setAttribute("data-en", "—");
          }
          return;
        }
        if (dot) dot.setAttribute("visibility", "visible");
        // Map X/Y from [-10,+10] to [0,280]
        var px = 140 + (d.x / 10) * 140;
        var py = 140 - (d.y / 10) * 140;
        if (dot) { dot.setAttribute("cx", px); dot.setAttribute("cy", py); }
        if (xEl) xEl.textContent = d.x.toFixed(2);
        if (yEl) yEl.textContent = d.y.toFixed(2);
        if (vEl) vEl.textContent = Number.isFinite(d.total_voters) ? d.total_voters.toLocaleString() : "—";
        var lang = typeof currentLang !== "undefined" ? currentLang : "el";
        if (qEl) {
          var quadEl = QUAD_EL[d.quadrant] || d.quadrant || "";
          var quadEn = QUAD_EN[d.quadrant] || d.quadrant || "";
          qEl.setAttribute("data-el", quadEl);
          qEl.setAttribute("data-en", quadEn);
          qEl.textContent = lang === "en" ? quadEn : quadEl;
        }
        // Trend arrow
        if (arrow && d.trend && (Math.abs(d.trend.x_delta) > 0.001 || Math.abs(d.trend.y_delta) > 0.001)) {
          var ax = px + (d.trend.x_delta / 10) * 280;
          var ay = py - (d.trend.y_delta / 10) * 280;
          arrow.setAttribute("x1", px); arrow.setAttribute("y1", py);
          arrow.setAttribute("x2", ax); arrow.setAttribute("y2", ay);
          arrow.setAttribute("opacity", "0.6");
        }

      })
      .catch(function(){});
  }
  fetchCPLM();
  setInterval(fetchCPLM, 60000);
})();
