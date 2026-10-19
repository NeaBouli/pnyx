
async function submitNewsletter(e) {
  e.preventDefault();
  var btn = document.getElementById("nlBtn");
  var msg = document.getElementById("nlMsg");
  btn.disabled = true; btn.textContent = "...";
  try {
    var r = await fetch("https://api.ekklesia.gr/api/v1/newsletter/subscribe", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        email: document.getElementById("nlEmail").value,
        subscriber_type: document.getElementById("nlType").value,
        frequency: document.querySelector('input[name="freq"]:checked').value,
        language: document.querySelector('input[name="lang"]:checked').value,
        topic_active_votes: document.getElementById("nlVotes").checked,
        topic_vote_results: document.getElementById("nlResults").checked,
        topic_new_proposals: document.getElementById("nlProposals").checked,
        topic_system_news: document.getElementById("nlSystem").checked,
        topic_breaking_news: document.getElementById("nlBreaking").checked,
      })
    });
    var d = await r.json();
    msg.style.display = "block";
    if (d.success) {
      msg.style.background = "#052e16"; msg.style.color = "#22c55e";
      msg.textContent = d.message;
    } else {
      msg.style.background = "#450a0a"; msg.style.color = "#ef4444";
      msg.textContent = d.detail || d.message || "Error";
    }
  } catch(err) {
    msg.style.display = "block"; msg.style.background = "#450a0a"; msg.style.color = "#ef4444";
    msg.textContent = "Network error";
  }
  btn.disabled = false; btn.textContent = "📬 Εγγραφή";
}
