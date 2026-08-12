#!/bin/bash
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
cd /c/Users/Asad/mac-sku-prices || exit 1
curl -s -m 30 -A "$UA" -L "https://www.apple.com/fi/shop/buy-mac/mac-mini" -o apple_mini.html -w "mini HTTP:%{http_code} SIZE:%{size_download}\n"
curl -s -m 30 -A "$UA" -L "https://www.apple.com/fi/shop/buy-mac/mac-studio" -o apple_studio.html -w "studio HTTP:%{http_code} SIZE:%{size_download}\n"
echo "--- mini price mentions ---"
grep -oE '"price":"[^"]{1,12}"' apple_mini.html | sort -u | head -20
grep -oE 'alv\.?[^<]{0,20}' apple_mini.html | head -5
echo "--- studio price mentions ---"
grep -oE '"price":"[^"]{1,12}"' apple_studio.html | sort -u | head -20
