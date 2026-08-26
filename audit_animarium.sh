#!/usr/bin/env bash
# audit_animarium.sh — public-release audit for ~/progetti/animarium (read-only, changes nothing)
# usage:  cd ~/progetti/animarium && bash audit_animarium.sh > audit_animarium_$(date +%Y%m%d).txt 2>&1
set -u
echo "== repo: $(git rev-parse --show-toplevel)  HEAD: $(git rev-parse --short HEAD)  branch: $(git branch --show-current)"
echo "== remote:"; git remote -v | sed 's/^/   /'

echo; echo "== 1. blobs > 2 MB anywhere in history (viewer repo: threshold lower than GSP)"
git rev-list --objects --all \
 | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' \
 | awk '$1=="blob" && $3>2000000 {printf "%8.1f MB  %s\n",$3/1e6,$4}' | sort -rn | head -40

echo; echo "== 2. generated products ever committed (bundle, deploy, dist, parquet, per-comune json, node_modules)"
git log --all --name-only --pretty=format: \
 | grep -Ei '^(bundle|deploy|dist|build|public/dati|node_modules)/|\.(parquet|csv|env|pem|key|sqlite|duckdb)$|comuni/[0-9]{6}/' \
 | sort -u | head -80

echo; echo "== 3. currently tracked files under bundle/ deploy/ dist/ (should be empty)"
git ls-files bundle deploy dist build 2>/dev/null | head -40

echo; echo "== 4. secrets: Cloudflare / wrangler / API tokens (grep fallback if gitleaks absent)"
if command -v gitleaks >/dev/null; then gitleaks detect --source . --log-opts='--all' --no-banner || true
else git grep -nEi 'CLOUDFLARE|CF_API|wrangler|account_id|api[_-]?key|token|secret|password|sk-or-|sk-ant-' \
       -- ':!*.md' ':!*.lock' ':!package-lock.json' | head -40; fi
echo "-- files that look like config with credentials:"
git ls-files | grep -Ei '(^|/)(\.env|wrangler\.toml|\.dev\.vars|secrets?\.[a-z]+)$' | head

echo; echo "== 5. absolute / personal paths and sys.path hacks in tracked code"
git grep -nE '/home/[a-z]+/|/mnt/c/Users/|C:\\\\Users|~/progetti' -- ':!*.md' | head -40
echo "-- sys.path manipulation (should be gone after the pyproject dependency on gsp):"
git grep -nE 'sys\.path\.(insert|append)' -- '*.py' | head

echo; echo "== 6. python entry points and their gsp imports"
for f in $(git ls-files '*.py'); do
  printf "%6d  %-45s imports: %s\n" "$(wc -l <"$f")" "$f" "$(grep -oE 'from gsp[.a-z_]* import [A-Za-z_, ]+|import gsp[.a-z_]*' "$f" | tr '\n' ';' | cut -c1-90)"
done

echo; echo "== 7. the --pubblico blocker: where the bundle is written and whether esporta_pubblico is called"
git grep -nE 'esporta_pubblico|campione\(|--pubblico|to_parquet|write_parquet|to_parquet\(' -- '*.py' '*.sh' | head -30

echo; echo "== 8. front-end: dependency and deploy files"
for f in package.json wrangler.toml index.html vite.config.* ; do
  ls $f 2>/dev/null | sed 's/^/   ok   /'; done
[ -f package.json ] && { echo "-- deps:"; python3 -c "import json;d=json.load(open('package.json'));print('   ',list((d.get('dependencies') or {}).keys()));print('   dev',list((d.get('devDependencies') or {}).keys()))"; }
echo "-- CDN / external script URLs in html/js:"
git grep -hoE 'https?://[a-zA-Z0-9./_-]+\.(js|wasm|css)' -- '*.html' '*.js' | sort -u | head -20

echo; echo "== 9. what a fresh clone can rebuild without GSP data: files read from outside the repo"
git grep -nE '\.\./gsp|progetti/gsp|GSP_ROOT|/data/comuni' -- '*.py' '*.js' '*.sh' | head -20

echo; echo "== 10. licence / readme / citation"
for f in LICENSE LICENSE.md README.md CITATION.cff pyproject.toml; do
  [ -e "$f" ] && echo "  ok   $f" || echo "  MISSING $f"; done
echo; echo "== 11. tracked file inventory by top-level dir"
git ls-files | awk -F/ '{print (NF>1?$1"/":".")}' | sort | uniq -c | sort -rn
echo; echo "== done"
