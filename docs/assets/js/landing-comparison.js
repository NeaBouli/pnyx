
(function(){
  var ELECTORATE = 9810040; // Εκλογικό Σώμα Ελλάδας 2023 (ΥΠΕΣ)
  var representationRequestId = 0;

  function renderBillComparison(parliamentPct, citizenPct, billId) {
    var available = Number.isFinite(parliamentPct) && Number.isFinite(citizenPct) && parliamentPct >= 0 && parliamentPct <= 100 && citizenPct >= 0 && citizenPct <= 100;
    var lang = typeof currentLang !== "undefined" ? currentLang : "el";
    function text(id, el, en) {
      var node = document.getElementById(id);
      if (!node) return;
      node.setAttribute("data-el", el);
      node.setAttribute("data-en", en);
      node.textContent = lang === "en" ? en : el;
    }
    [["repParliament", parliamentPct], ["repCitizen", citizenPct]].forEach(function(item) {
      var fill = document.getElementById(item[0] + "Fill");
      if (fill) fill.style.width = (available ? item[1] : 0) + "%";
      text(item[0] + "Value", available ? item[1].toFixed(2).replace(".", ",") + "% Υπέρ" : "—", available ? item[1].toFixed(2) + "% YES" : "—");
    });
    text("repComparisonNote",
      (available ? "Ίδιο νομοσχέδιο: " + billId + ". " : "Δεν υπάρχουν διαθέσιμα έγκυρα συγκρίσιμα δεδομένα για το ίδιο νομοσχέδιο. ") + "Ποσοστό Υπέρ των καταγεγραμμένων κομματικών θέσεων έναντι όλων των ψήφων της πλατφόρμας. Όχι ποσοστό βουλευτών ή επίσημα επιβεβαιωμένη απόφαση.",
      (available ? "Same bill: " + billId + ". " : "Valid comparable data for the same bill is unavailable. ") + "YES share of reported party positions versus all platform votes. Not MP percentages or an officially confirmed decision.");
  }

  function fetchBillComparison(billId, requestId) {
    if (typeof billId !== "string" || !billId.trim() || billId.length > 50) return;
    fetch("https://api.ekklesia.gr/api/v1/public/bills/" + encodeURIComponent(billId) + "/results")
      .then(function(r){ if (!r.ok) throw new Error("Bill results unavailable"); return r.json(); })
      .then(function(d){
        if (requestId !== representationRequestId) return;
        if (!d || d.bill_id !== billId || (d.status !== "PARLIAMENT_VOTED" && d.status !== "OPEN_END") || d.results_hidden !== false) throw new Error("Bill results are not public and closed");
        var counts = d.citizen_votes;
        var parties = d.parliament_votes;
        if (!counts || typeof counts !== "object" || Array.isArray(counts) || !parties || typeof parties !== "object" || Array.isArray(parties)) throw new Error("Comparison data missing");
        var fields = ["yes", "no", "abstain", "unknown", "total"];
        if (!fields.every(function(key){ return Number.isSafeInteger(counts[key]) && counts[key] >= 0; }) || counts.total === 0) throw new Error("Invalid vote counts");
        var sum = counts.yes + counts.no + counts.abstain + counts.unknown;
        if (!Number.isSafeInteger(sum) || sum !== counts.total) throw new Error("Vote totals disagree");
        var keys = Object.keys(parties);
        var positions = Object.values(parties);
        var known = ["YES", "ΝΑΙ", "NO", "ΟΧΙ", "ABSTAIN", "ΠΑΡΩΝ", "ΑΠΟΧΗ"];
        if (!keys.length || !keys.every(function(key){ return !!key.trim(); }) || !positions.every(function(position){ return typeof position === "string" && known.indexOf(position) !== -1; })) throw new Error("Party positions unavailable");
        var yes = positions.filter(function(position){ return position === "YES" || position === "ΝΑΙ"; }).length;
        renderBillComparison(yes / positions.length * 100, counts.yes / counts.total * 100, billId);
      })
      .catch(function(){ if (requestId === representationRequestId) renderBillComparison(null, null); });
  }

  function repColor(pct) {
    // Text-safe shades: the score is also rendered as coloured text.
    if (pct < 25) return "#dc2626";
    if (pct < 50) return "#c2410c";
    if (pct < 75) return "#a16207";
    if (pct < 90) return "#15803d";
    return "#1d4ed8";
  }

  function setMood(score) {
    var mouth = document.getElementById("moodMouth");
    var status = document.getElementById("moodStatus");
    if (!mouth || !status) return;
    var el = "Αναμονή πραγματικών δεδομένων. Ο δείκτης ενεργοποιείται μόλις υπάρξουν αρκετά συγκρίσιμα δεδομένα.";
    var en = "Waiting for real data. The indicator activates once sufficient comparable data is available.";
    var path = "M36 80 L84 80";
    if (Number.isFinite(score)) {
      if (score >= 50) {
        path = "M36 74 Q60 96 84 74";
        el = "Η Βουλή αντιπροσωπεύει τη γνώμη των πολιτών στο " + score + "%.";
        en = "Parliament represents citizen opinion at " + score + "%.";
      } else if (score < 45) {
        path = "M36 88 Q60 66 84 88";
        el = "Αντιπροσωπευτικότητα " + score + "%: απόκλιση από τη γνώμη των πολιτών.";
        en = "Representativeness " + score + "%: divergence from citizen opinion.";
      } else {
        el = "Οριακή αντιπροσωπευτικότητα: " + score + "%.";
        en = "Marginal representativeness: " + score + "%.";
      }
    }
    mouth.setAttribute("d", path);
    status.setAttribute("data-el", el);
    status.setAttribute("data-en", en);
    var lang = typeof currentLang !== "undefined" ? currentLang : "el";
    var newText = lang === "en" ? en : el;
    if (status.textContent !== newText) status.textContent = newText;
  }

  function fetchRepresentation() {
    var requestId = ++representationRequestId;
    renderBillComparison(null, null);
    fetch("https://api.ekklesia.gr/api/v1/analytics/representation")
      .then(function(r){ if (!r.ok) throw new Error("Representation unavailable"); return r.json(); })
      .then(function(d){
        if (requestId !== representationRequestId) return;
        fetchBillComparison(d && d.last_bill && d.last_bill.bill_id, requestId);
        var score = d.cumulative_representation;
        var scoreEl = document.getElementById("repScore");
        var divEl = document.getElementById("repDivergence");
        var billsEl = document.getElementById("repBills");
        var votesEl = document.getElementById("repVotes");
        var lastBill = document.getElementById("repLastBill");
        var lastTitle = document.getElementById("repLastTitle");
        var lastStats = document.getElementById("repLastStats");
        var noData = document.getElementById("repNoData");
        var t1 = document.getElementById("tier1Score");
        var t2 = document.getElementById("tier2Score");
        var t3 = document.getElementById("tier3Score");
        var heroT1 = document.getElementById("heroTier1");
        var heroT2 = document.getElementById("heroTier2");
        var heroT3 = document.getElementById("heroTier3");

        var totalVotes = d.total_citizen_votes || 0;
        var avgDiv = d.cumulative_divergence || 0;
        var bills = d.bills_analyzed || 0;

        // These fields compare Parliament with citizens. Fail closed until
        // the API has at least one analyzed bill and a cumulative score.
        if (bills < 1 || score === null || score === undefined || !Number.isFinite(Number(score))) {
          setMood(null);
          if (scoreEl) scoreEl.textContent = "—";
          if (divEl) divEl.textContent = "—";
          if (billsEl) billsEl.textContent = "—";
          if (votesEl) votesEl.textContent = "—";
          if (t1) t1.textContent = "—";
          if (t2) t2.textContent = "—";
          if (t3) { t3.textContent = "—"; t3.style.color = ""; }
          if (heroT1) heroT1.textContent = "—";
          if (heroT2) heroT2.textContent = "—";
          if (heroT3) heroT3.textContent = "—";
          if (lastBill) lastBill.style.display = "none";
          if (noData) noData.style.display = "inline";
          return;
        }

        // Tier 1: Raw platform
        var rawPct = (totalVotes / ELECTORATE) * 100;
        var rawLabel = rawPct < 0.001 ? "0%" : rawPct.toFixed(rawPct < 1 ? 3 : 1) + "%";
        if (t1) t1.textContent = rawLabel;
        if (heroT1) heroT1.textContent = rawLabel;

        // Tier 2: Weighted (Jackman MRP correction)
        var corrected = rawPct / 0.65; // voluntary participation bias
        var avgBillsPerVoter = bills > 0 ? Math.min(totalVotes / Math.max(1, bills), 5) / 5 : 0;
        var weighted = corrected * (1 + avgBillsPerVoter * 0.3);
        weighted = Math.min(100, weighted);
        var weightedLabel = weighted < 0.001 ? "0%" : weighted.toFixed(weighted < 1 ? 3 : 1) + "%";
        if (t2) t2.textContent = weightedLabel;
        if (heroT2) heroT2.textContent = weightedLabel;

        // Tier 3: CRI composite is meaningful only with real representation data.
        var quantityScore = Math.min(1, rawPct / 1); // normalize: 1% = max
        var qualityScore = score / 100; // representation = 1-divergence
        var diversityScore = 0.5; // neutral until demographic data available
        var cri = Math.round((0.4 * quantityScore + 0.3 * qualityScore + 0.3 * diversityScore) * 100);
        if (t3) { t3.textContent = cri + "/100"; t3.style.color = repColor(cri); }
        if (heroT3) heroT3.textContent = cri + "/100";

        if (noData) noData.style.display = "none";
        var pct = Math.min(100, Math.max(0, score));
        setMood(pct);
        var col = repColor(pct);
        if (scoreEl) { scoreEl.textContent = pct + "%"; scoreEl.style.color = col; }
        if (divEl) divEl.textContent = avgDiv + "%";
        if (billsEl) billsEl.textContent = bills;
        if (votesEl) votesEl.textContent = totalVotes.toLocaleString();

        if (d.last_bill && lastBill) {
          lastBill.style.display = "block";
          if (lastTitle) lastTitle.textContent = d.last_bill.title_el;
          var attribution = document.getElementById("repLastTitleAttribution");
          if (attribution && window.EmbedUI) {
            attribution.replaceChildren();
            EmbedUI.parliamentAttribution(attribution, d.last_bill, document.documentElement.lang !== "en");
          }
          if (lastStats) lastStats.textContent = d.last_bill.citizen_votes + " ψήφοι · Απόκλιση " + d.last_bill.divergence + "% · Αντιπρ. " + d.last_bill.representation + "%";
        }
      })
      .catch(function(){ if (requestId === representationRequestId) { setMood(null); renderBillComparison(null, null); } });
  }
  fetchRepresentation();
  setInterval(fetchRepresentation, 60000);
})();
