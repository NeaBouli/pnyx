
      function switchHlrTab(tab) {
        var pp = document.getElementById("hlrPanelPrimary");
        var pf = document.getElementById("hlrPanelFallback");
        var bp = document.getElementById("hlrTabPrimary");
        var bf = document.getElementById("hlrTabFallback");
        if (tab === "primary") {
          if (pp) pp.style.display = "";
          if (pf) pf.style.display = "none";
          if (bp) { bp.style.border = "2px solid #3b82f6"; bp.style.background = "#eff6ff"; bp.style.color = "#1d4ed8"; }
          if (bf) { bf.style.border = "2px solid #e2e8f0"; bf.style.background = "white"; bf.style.color = "#6b7280"; }
        } else {
          if (pp) pp.style.display = "none";
          if (pf) pf.style.display = "";
          if (bf) { bf.style.border = "2px solid #3b82f6"; bf.style.background = "#eff6ff"; bf.style.color = "#1d4ed8"; }
          if (bp) { bp.style.border = "2px solid #e2e8f0"; bp.style.background = "white"; bp.style.color = "#6b7280"; }
        }
      }
      