// Phase B: auth-state-aware ticket guard (replaces old desktop blanket block)
function showPhaseBModal() {
  document.getElementById("phaseBModal").style.display = "flex";
  return false;
}
// Called by the CSP listener: keep the auth guard in the same event path as
// opening the modal, including controls inserted after DOMContentLoaded.
function requestNewTicket(event) {
  var hasGitHub = !!sessionStorage.getItem("polis_token");
  var hasQR = !!sessionStorage.getItem("polis_nullifier");
  if (!hasGitHub) {
    event.preventDefault();
    if (typeof login === "function") login();
    return false;
  }
  if (!hasQR) {
    event.preventDefault();
    sessionStorage.setItem("polis_pending_action", "new-ticket");
    if (typeof openQRLogin === "function") openQRLogin();
    return false;
  }
  return openNewTicketModal();
}
