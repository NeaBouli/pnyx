
  (function(){
    fetch("https://api.ekklesia.gr/api/v1/public/stats").then(function(r){return r.json()}).then(function(d){
      var s=d.stats||{};
      document.getElementById("ss-parliament").textContent=s.parliament_bills||0;
      document.getElementById("ss-diavgeia").textContent=s.diavgeia_bills||0;
      document.getElementById("ss-votes").textContent=s.total_votes == null ? "—" : s.total_votes;
      document.getElementById("ss-arweave").textContent=s.arweave_archived||0;
      document.getElementById("ss-archived").textContent=s.archived_bills||0;
      document.getElementById("ss-forum").textContent=s.forum_topics||0;
    }).catch(function(){});
    fetch("https://api.ekklesia.gr/api/v1/public/scraper/status").then(function(r){return r.json()}).then(function(d){
      document.getElementById("ss-balance").textContent=d.arweave_balance_ar?d.arweave_balance_ar.toFixed(2):"—";
      var last=d.parliament_scraper&&d.parliament_scraper.last_success;
      if(last){
        var age=(Date.now()-new Date(last).getTime())/3600000;
        if(age<24){document.getElementById("ss-indicator").textContent="🟢";document.getElementById("ss-label").textContent="Ενεργό"}
        else if(age<72){document.getElementById("ss-indicator").textContent="🟡";document.getElementById("ss-label").textContent="Καθυστέρηση"}
        else{document.getElementById("ss-indicator").textContent="🔴";document.getElementById("ss-label").textContent="Ανενεργό"}
      }
    }).catch(function(){});
  })();
  