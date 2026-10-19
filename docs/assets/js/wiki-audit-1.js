
var _privacyHtml='<h2 style="margin-top:0">Πολιτική Απορρήτου</h2><p><a href="privacy.html" style="display:inline-block;padding:0.6rem 1.5rem;background:#2563eb;color:#fff;border-radius:0.5rem;text-decoration:none;font-weight:700;font-size:0.9rem">Πλήρης Πολιτική Απορρήτου →</a></p>';
var _deleteHtml='<h2 style="margin-top:0">Διαγραφή Λογαριασμού</h2><p><a href="delete-account.html" style="display:inline-block;padding:0.6rem 1.5rem;background:#ef4444;color:#fff;border-radius:0.5rem;text-decoration:none;font-weight:700;font-size:0.9rem">Αναλυτικές Οδηγίες Διαγραφής →</a></p>';
function openLegalModal(t){document.getElementById("legalContent").innerHTML=t==="privacy"?_privacyHtml:_deleteHtml;document.getElementById("legalModal").style.display="flex"}
function closeLegalModal(){document.getElementById("legalModal").style.display="none"}
document.addEventListener("keydown",function(e){if(e.key==="Escape")closeLegalModal()});
