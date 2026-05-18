// Demo-Node Daten — hardcoded, kein Backend nötig
var DEMO_BILLS = [
  {
    id: "DEMO-001",
    title_el: "Νέος Ποδηλατόδρομος στην Κεντρική Οδό",
    pill_el: "Πρόταση για κατασκευή ποδηλατόδρομου 2.5km στην κεντρική οδό του δήμου",
    status: "ACTIVE",
    governance_level: "MUNICIPAL",
    categories: ["Υποδομές"],
    submitted_date: "2026-04-15",
    parliament_vote_date: "2026-06-01",
    yes_count: 847, no_count: 234, abstain_count: 43,
    total_votes: 1124,
    consensus_score: null, consensus_count: 0,
    arweave_tx_id: null, forum_topic_id: 201
  },
  {
    id: "DEMO-002",
    title_el: "Αναδιαμόρφωση Κεντρικής Πλατείας",
    pill_el: "Ανακατασκευή με νέα παιδική χαρά, χώρους πρασίνου και πεζόδρομο",
    status: "WINDOW_24H",
    governance_level: "MUNICIPAL",
    categories: ["Περιβάλλον", "Υποδομές"],
    submitted_date: "2026-03-20",
    parliament_vote_date: "2026-05-19",
    yes_count: 1243, no_count: 567, abstain_count: 89,
    total_votes: 1899,
    consensus_score: null, consensus_count: 0,
    arweave_tx_id: null, forum_topic_id: 202
  },
  {
    id: "DEMO-003",
    title_el: "Τιμολόγιο Δημοτικών Υπηρεσιών 2026",
    pill_el: "Αναθεώρηση τιμολογίου καθαριότητας, ύδρευσης και αποχέτευσης",
    status: "OPEN_END",
    governance_level: "MUNICIPAL",
    categories: ["Οικονομικά"],
    submitted_date: "2026-01-10",
    parliament_vote_date: "2026-03-15",
    yes_count: 432, no_count: 891, abstain_count: 156,
    total_votes: 1479,
    consensus_score: -1.8, consensus_count: 312,
    arweave_tx_id: "DEMO-ARCHIVE-3a8f9b2c4d5e6f",
    forum_topic_id: 203,
    parliament_result: {"\u039d\u0394": "\u039d\u0391\u0399", "\u03a3\u03a5\u03a1\u0399\u0396\u0391": "\u039f\u03a7\u0399", "\u03a0\u0391\u03a3\u039f\u039a": "\u039d\u0391\u0399", "\u039a\u039a\u0395": "\u039f\u03a7\u0399"}
  },
  {
    id: "DEMO-004",
    title_el: "Κατασκευή Νέου Βρεφονηπιακού Σταθμού",
    pill_el: "Δημιουργία σύγχρονου βρεφονηπιακού σταθμού 120 θέσεων στην περιοχή Λιβαδειά",
    status: "ANNOUNCED",
    governance_level: "MUNICIPAL",
    categories: ["Παιδεία"],
    submitted_date: "2026-05-10",
    parliament_vote_date: null,
    yes_count: 0, no_count: 0, abstain_count: 0,
    total_votes: 0,
    consensus_score: null, consensus_count: 0,
    arweave_tx_id: null, forum_topic_id: null
  }
];

var DEMO_STATUS = {
  ACTIVE:           {el: "Ενεργή", color: "#22c55e", bg: "#dcfce7"},
  WINDOW_24H:       {el: "24ω Παράθυρο", color: "#f59e0b", bg: "#fef3c7"},
  ANNOUNCED:        {el: "Ανακοινώθηκε", color: "#64748b", bg: "#f1f5f9"},
  PARLIAMENT_VOTED: {el: "Ψηφίστηκε", color: "#2563eb", bg: "#dbeafe"},
  OPEN_END:         {el: "Αρχείο", color: "#7c3aed", bg: "#ede9fe"}
};

function demoGetVote(billId) { return localStorage.getItem("demo_vote_" + billId); }
function demoSetVote(billId, choice) { localStorage.setItem("demo_vote_" + billId, choice); }
function demoGetConsensus(billId) { return localStorage.getItem("demo_consensus_" + billId); }
function demoSetConsensus(billId, score) { localStorage.setItem("demo_consensus_" + billId, score); }
