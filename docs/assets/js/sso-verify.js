
(function () {
  'use strict';

  var API_BASE = 'https://api.ekklesia.gr/api/v1';
  var LOCALSTORAGE_KEY = 'ekklesia_private_key';
  var LOCALSTORAGE_PUBKEY = 'ekklesia_public_key';

  // ─── URL params from SSO redirect ───
  var params = new URLSearchParams(window.location.search);
  var nonce = params.get('nonce');
  var returnUrl = params.get('return_url');

  // ─── State management ───
  function showState(id) {
    var states = document.querySelectorAll('.state');
    for (var i = 0; i < states.length; i++) {
      states[i].classList.remove('active');
    }
    document.getElementById('state-' + id).classList.add('active');
  }

  function showError(msg) {
    document.getElementById('error-detail').textContent = msg;
    showState('error');
  }

  // ─── Validate nonce + return_url ───
  if (!nonce || !returnUrl) {
    showState('error');
    document.getElementById('error-detail').textContent =
      'Μη έγκυρος σύνδεσμος — λείπουν παράμετροι nonce/return_url.';
    return;
  }

  // ─── Check for stored private key ───
  var privateKeyHex = localStorage.getItem(LOCALSTORAGE_KEY);
  var publicKeyHex = localStorage.getItem(LOCALSTORAGE_PUBKEY);

  if (!privateKeyHex || !publicKeyHex) {
    // No key — show QR / registration prompt
    showState('nokey');
    return;
  }

  // ─── Key exists — authenticate automatically ───
  authenticate(publicKeyHex);

  function authenticate(pubKeyHex) {
    // Redirect to Next.js SSO-Verify which has Ed25519 signing capability
    var nextUrl = 'https://ekklesia.gr/el/sso-verify?nonce=' +
      encodeURIComponent(nonce) + '&return_url=' + encodeURIComponent(returnUrl);
    window.location.href = nextUrl;
    return;

    // Legacy code below — kept for reference but never reached
    showState('verifying');

    var body = JSON.stringify({
      nonce: nonce,
      public_key_hex: pubKeyHex
    });

    fetch(API_BASE + '/sso/discourse/callback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body,
      redirect: 'manual'
    })
      .then(function (res) {
        // API returns 307 redirect to Discourse
        if (res.type === 'opaqueredirect' || res.status === 307 || res.status === 302) {
          var location = res.headers.get('Location');
          if (location) {
            showState('success');
            setTimeout(function () { window.location.href = location; }, 600);
            return;
          }
        }

        // API returns 200 with redirect URL in body
        if (res.ok) {
          return res.json().then(function (data) {
            if (data.redirect_url) {
              showState('success');
              setTimeout(function () { window.location.href = data.redirect_url; }, 600);
            } else {
              showError('Δεν ελήφθη URL ανακατεύθυνσης.');
            }
          });
        }

        // Error responses
        if (res.status === 404) {
          showError('Η ταυτότητα δεν βρέθηκε. Ολοκληρώστε πρώτα την εγγραφή στο ekklesia.gr.');
          return;
        }
        if (res.status === 410) {
          showError('Η σύνδεση έληξε. Επιστρέψτε στο forum και δοκιμάστε ξανά.');
          return;
        }

        return res.text().then(function (text) {
          var detail;
          try { detail = JSON.parse(text).detail; } catch (e) { detail = text; }
          showError(detail || 'Σφάλμα ' + res.status);
        });
      })
      .catch(function (err) {
        showError('Αδυναμία σύνδεσης: ' + err.message);
      });
  }

  // ─── Retry button ───
  window.retryAuth = function () {
    var pk = localStorage.getItem(LOCALSTORAGE_PUBKEY);
    if (!pk) {
      showState('nokey');
      return;
    }
    authenticate(pk);
  };
})();
