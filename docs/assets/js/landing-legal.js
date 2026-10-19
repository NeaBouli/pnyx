
var _privacyHtml='<h2 style="margin-top:0">Πολιτική Απορρήτου / Privacy Policy</h2>'
+'<p><strong>Τι ΔΕΝ αποθηκεύουμε:</strong> Αριθμό κινητού, Private Key, IP μαζί με την ψήφο, Ηλικία, Φύλο.</p>'
+'<p>Οι μετρητές ορίων αιτημάτων χρησιμοποιούν ημερήσια HMAC αναγνωριστικά IP και λήγουν. Τα access logs μπορεί να περιέχουν την IP και εναλλάσσονται βάσει μεγέθους, χωρίς σταθερό όριο χρόνου διατήρησης.</p>'
+'<p><strong>Τι αποθηκεύουμε:</strong> Argon2id v2 identity hash και SHA256 compatibility anchor, Public Key (Ed25519), Ψήφοι (ψευδώνυμα YES/NO/ABSTAIN, συνδεδεμένες με nullifier — όχι με όνομα ή αριθμό τηλεφώνου).</p>'
+'<p><strong>k-Anonymity:</strong> Δημογραφικά μόνο όταν k ≥ 10 ψήφοι.</p>'
+'<p><strong>GDPR:</strong> Servers στην Ευρώπη (Hetzner). Ελαχιστοποίηση δεδομένων· τα ψευδώνυμα δεδομένα παραμένουν προσωπικά δεδομένα. Δεν αποτελεί βεβαίωση νομικής συμμόρφωσης.</p>'
+'<p><strong>Arweave:</strong> Κανονικές ψήφοι: μόνο συγκεντρωτικά αποτελέσματα, χωρίς ατομικές ψήφους ή Public Keys. ZK ψήφοι (σε παύση): ατομικές επιλογές με ZK απόδειξη, χωρίς ταυτότητα.</p>'
+'<hr style="border:none;border-top:1px solid #e2e8f0;margin:1.5rem 0">'
+'<h3>Όροι Χρήσης / Terms of Use</h3>'
+'<p>Η πλατφόρμα ekklesia.gr είναι ένα ανοιχτού κώδικα, κοινοτικό έργο (MIT License). Η πλατφόρμα δεν αποτελεί κρατική υπηρεσία και οι ψηφοφορίες δεν έχουν νομική δεσμευτικότητα.</p>'
+'<p>Πηγαίος κώδικας: <a href="https://github.com/NeaBouli/pnyx" target="_blank" style="color:#2563eb">github.com/NeaBouli/pnyx</a></p>'
+'<p style="margin-top:1.5rem"><a href="wiki/privacy.html" style="display:inline-block;padding:0.6rem 1.5rem;background:#2563eb;color:#fff;border-radius:0.5rem;text-decoration:none;font-weight:700;font-size:0.9rem">Πλήρης Πολιτική Απορρήτου →</a></p>';
var _deleteHtml='<h2 style="margin-top:0">Διαγραφή Λογαριασμού / Delete Account</h2>'
+'<p>Το ekklesia.gr δεν δημιουργεί παραδοσιακό λογαριασμό. Δεν υπάρχει email, κωδικός ή username.</p>'
+'<h3>Βήμα 1 — Απεγκατάσταση</h3>'
+'<p>Απεγκαταστήστε την εφαρμογή. Διαγράφονται αμέσως: Private Key, Nullifier Root, όλα τα τοπικά δεδομένα.</p>'
+'<h3>Βήμα 2 — Server</h3>'
+'<p>Ο server διατηρεί τον ψευδώνυμο κωδικό (nullifier), το δημόσιο κλειδί και τις ψήφους. Η απεγκατάσταση δεν διαγράφει αυτά τα δεδομένα.</p>'
+'<h3>Βήμα 3 — Επανεγγραφή</h3>'
+'<p>Η ανάκληση απενεργοποιεί το παλιό κλειδί. Με νέα επαλήθευση το κλειδί αντικαθίσταται· ο nullifier και οι προηγούμενες ψήφοι παραμένουν.</p>'
+'<p style="margin-top:1.5rem"><a href="wiki/delete-account.html" style="display:inline-block;padding:0.6rem 1.5rem;background:#ef4444;color:#fff;border-radius:0.5rem;text-decoration:none;font-weight:700;font-size:0.9rem">Αναλυτικές Οδηγίες Διαγραφής →</a></p>';
function openLegalModal(type){var m=document.getElementById("legalModal");document.getElementById("legalContent").innerHTML=type==="privacy"?_privacyHtml:_deleteHtml;m.style.display="flex"}
function closeLegalModal(){document.getElementById("legalModal").style.display="none"}
document.addEventListener("keydown",function(e){if(e.key==="Escape")closeLegalModal()});
