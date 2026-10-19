
var currentFilter = "ALL";
var filters = [
  {key:"ALL", label:"Όλα"},
  {key:"ACTIVE", label:"Ενεργά"},
  {key:"WINDOW_24H", label:"24ω"},
  {key:"OPEN_END", label:"Αρχείο"},
  {key:"ANNOUNCED", label:"Ανακοινώθηκε"}
];

function renderFilters() {
  var html = "";
  filters.forEach(function(f) {
    html += '<button class="filter-btn' + (currentFilter === f.key ? ' active' : '') + '" data-csp-click="demo-filter" data-value="' + f.key + '">' + f.label + ' (' + (f.key === "ALL" ? DEMO_BILLS.length : DEMO_BILLS.filter(function(b){return b.status===f.key}).length) + ')</button>';
  });
  document.getElementById("filters").innerHTML = html;
}

function setFilter(f) { currentFilter = f; renderFilters(); renderBills(); }

function renderBills() {
  var bills = currentFilter === "ALL" ? DEMO_BILLS : DEMO_BILLS.filter(function(b) { return b.status === currentFilter; });
  var html = "";
  bills.forEach(function(b) {
    var s = DEMO_STATUS[b.status] || DEMO_STATUS.ACTIVE;
    var total = b.total_votes || 1;
    var yesPct = Math.round(b.yes_count / total * 100);
    var noPct = Math.round(b.no_count / total * 100);
    var absPct = 100 - yesPct - noPct;
    var userVote = demoGetVote(b.id);
    var votable = b.status === "ACTIVE" || b.status === "WINDOW_24H";

    html += '<div class="bill-card">';
    html += '<div class="bill-header"><span class="badge" style="background:' + s.bg + ';color:' + s.color + '">' + s.el + '</span><span class="bill-id">' + b.id + '</span></div>';
    html += '<div class="bill-title">' + b.title_el + '</div>';
    if (b.pill_el) html += '<div class="bill-pill">' + b.pill_el + '</div>';
    if (b.categories) { html += '<div class="categories">'; b.categories.forEach(function(c) { html += '<span class="cat-tag">' + c + '</span>'; }); html += '</div>'; }

    // Results bar
    if (b.total_votes > 0) {
      html += '<div class="bar-wrap"><div class="bar-yes" style="width:' + Math.max(yesPct,3) + '%">' + yesPct + '%</div><div class="bar-no" style="width:' + Math.max(noPct,3) + '%">' + noPct + '%</div>' + (absPct > 2 ? '<div class="bar-abs" style="width:' + absPct + '%"></div>' : '') + '</div>';
      html += '<div class="votes-info">' + b.total_votes.toLocaleString() + ' ψήφοι · ΝΑΙ ' + b.yes_count + ' · ΟΧΙ ' + b.no_count + ' · ΑΠΟΧΗ ' + b.abstain_count + '</div>';
    }

    // Vote buttons or voted message
    if (votable && !userVote) {
      html += '<div class="vote-buttons">';
      html += '<button class="vote-btn yes" data-csp-click="demo-vote" data-bill="' + b.id + '" data-choice="YES">ΝΑΙ</button>';
      html += '<button class="vote-btn no" data-csp-click="demo-vote" data-bill="' + b.id + '" data-choice="NO">ΟΧΙ</button>';
      html += '<button class="vote-btn abs" data-csp-click="demo-vote" data-bill="' + b.id + '" data-choice="ABSTAIN">ΑΠΟΧΗ</button>';
      html += '</div>';
      html += '<div class="info-hint">ℹ️ Σε μια πραγματική node, η ψήφος υπογράφεται κρυπτογραφικά με Ed25519 και αποστέλλεται στον server με ψευδώνυμο κωδικό, χωρίς όνομα ή τηλέφωνο.</div>';
    } else if (userVote) {
      html += '<div class="voted-msg">✅ Έχετε ψηφίσει: ' + userVote + ' (demo — αποθηκευμένο τοπικά)</div>';
    }

    // Consensus slider for OPEN_END
    if (b.status === "OPEN_END") {
      var userCons = demoGetConsensus(b.id);
      html += '<div class="consensus-wrap"><h4>⚖️ Κλίμακα Συναίνεσης</h4>';
      if (b.consensus_score !== null) {
        html += '<div class="votes-info">Τρέχον σκορ: ' + (b.consensus_score > 0 ? '+' : '') + b.consensus_score.toFixed(1) + ' (' + b.consensus_count + ' ψήφοι)</div>';
      }
      if (!userCons) {
        html += '<div class="consensus-labels"><span>Αντίσταση -5</span><span>Ουδέτερο</span><span>Συναίνεση +5</span></div>';
        html += '<input type="range" min="-5" max="5" value="0" step="1" id="slider_' + b.id + '" style="width:100%;margin:8px 0" data-csp-input="demo-score" data-bill="' + b.id + '">';
        html += '<div class="consensus-score" id="sv_' + b.id + '">0</div>';
        html += '<button class="consensus-btn" data-csp-click="demo-consensus" data-bill="' + b.id + '">Υποβολή Βαθμολογίας</button>';
        html += '<div class="info-hint">ℹ️ Η κλίμακα συναίνεσης επιτρέπει στους πολίτες να εκφράσουν πόσο συμφωνούν με την απόφαση μετά την ψηφοφορία.</div>';
      } else {
        html += '<div class="voted-msg">⚖️ Βαθμολογία: ' + (userCons > 0 ? '+' : '') + userCons + ' (demo)</div>';
      }
      html += '</div>';
    }

    // Arweave
    if (b.arweave_tx_id) {
      html += '<div class="arweave-badge" title="Demo — Σε πραγματική node αυτό θα ήταν σύνδεσμος στο Arweave blockchain">⛓ Arweave: ' + b.arweave_tx_id.substring(0, 16) + '… (demo)</div>';
      html += '<div class="info-hint">ℹ️ Σε πραγματική node, αυτός ο σύνδεσμος οδηγεί στο Arweave blockchain όπου τα αποτελέσματα είναι μόνιμα αποθηκευμένα.</div>';
    }

    html += '</div>';
  });
  document.getElementById("billsList").innerHTML = html || '<p style="color:var(--gray-400);text-align:center;padding:40px">Δεν βρέθηκαν ψηφοφορίες σε αυτό το φίλτρο</p>';
}

function castVote(billId, choice) {
  demoSetVote(billId, choice);
  renderBills();
}

function castConsensus(billId) {
  var val = document.getElementById("slider_" + billId).value;
  demoSetConsensus(billId, val);
  renderBills();
}

if (document.getElementById("filters") && document.getElementById("billsList") && typeof DEMO_BILLS !== "undefined") {
  renderFilters();
  renderBills();
}
