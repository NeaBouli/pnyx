
  (async function() {
    var params = new URLSearchParams(window.location.search);
    var code = params.get("code");
    var state = params.get("state");
    var errorParam = params.get("error");

    // Handle GitHub error redirect
    if (errorParam) {
      showError("GitHub: " + (params.get("error_description") || errorParam));
      return;
    }

    // Validate code
    if (!code) {
      showError("Δεν βρέθηκε κωδικός αυθεντικοποίησης.");
      return;
    }

    // CSRF: validate state
    var savedState = sessionStorage.getItem("polis_oauth_state");
    if (!savedState || savedState !== state) {
      showError("Σφάλμα ασφαλείας (state mismatch). Δοκιμάστε ξανά.");
      return;
    }

    // Exchange code for token via Cloudflare Worker
    try {
      var redirectUri = window.location.origin + POLIS_CONFIG.oauth.callbackPath;
      var res = await fetch(POLIS_CONFIG.oauth.workerUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: code, redirect_uri: redirectUri }),
      });

      if (!res.ok) {
        var errData = await res.json().catch(function() { return {}; });
        throw new Error(errData.error || "HTTP " + res.status);
      }

      var data = await res.json();

      if (!data.access_token) {
        throw new Error(data.error || "Δεν επιστράφηκε token.");
      }

      // Store token in sessionStorage ONLY
      sessionStorage.setItem("polis_token", data.access_token);
      sessionStorage.removeItem("polis_oauth_state");

      // Redirect back
      var returnTo = sessionStorage.getItem("polis_return_to") || "../index.html";
      sessionStorage.removeItem("polis_return_to");
      window.location.href = returnTo;

    } catch (err) {
      showError(err.message || "Σφάλμα ανταλλαγής token.");
    }

    function showError(msg) {
      if (!["spinner", "title", "message", "error", "retryLink"].every(function(id) { return document.getElementById(id); })) return;
      document.getElementById("spinner").style.display = "none";
      document.getElementById("title").textContent = "Σφάλμα";
      document.getElementById("message").style.display = "none";
      document.getElementById("error").textContent = msg;
      document.getElementById("error").style.display = "block";
      document.getElementById("retryLink").style.display = "block";
    }
  })();
  