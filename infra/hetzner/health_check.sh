#!/bin/bash
SERVER=${1:-"localhost"}
echo "=== Ekklesia.gr Health Check ==="
echo "--- API ---"
curl -sf "https://api.ekklesia.gr/health" && echo " ✅ API OK" || echo " ❌ API DOWN"
echo "--- Web ---"
curl -sf "https://ekklesia.gr" > /dev/null && echo " ✅ Web OK" || echo " ❌ Web DOWN"
echo "--- SSL ---"
echo | openssl s_client -connect ekklesia.gr:443 2>/dev/null | openssl x509 -noout -dates 2>/dev/null && echo " ✅ SSL OK" || echo " ❌ SSL Issue"
