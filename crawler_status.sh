#!/bin/zsh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATABASE="$PROJECT_DIR/MetadataCrawler/data.db"
KEYWORDS="$PROJECT_DIR/wechat_miniapps_keywords.txt"

if [[ ! -f "$DATABASE" ]]; then
  echo "Database non trovato: $DATABASE"
  exit 1
fi

if pgrep -f "MetadataCrawler/pixel_batch_crawler.py" >/dev/null 2>&1; then
  echo "Crawler: ATTIVO"
else
  echo "Crawler: FERMO"
fi

sqlite3 "$DATABASE" <<'SQL'
SELECT 'Mini App uniche: ' || count(*) FROM miniapps;
SELECT 'Keyword completate: ' || count(*) FROM query_queue WHERE status = 'done';
SELECT 'Keyword in esecuzione: ' || count(*) FROM query_queue WHERE status = 'running';
SELECT 'Keyword in coda: ' || count(*) FROM query_queue WHERE status = 'pending';
SELECT 'Ultima ricerca: ' || query || ' (offset ' || offset || ', ' || item_count || ' risultati, ' || searched_at || ')'
FROM searches ORDER BY searched_at DESC LIMIT 1;
SQL

if [[ -f "$KEYWORDS" ]]; then
  echo "Keyword nel TXT: $(wc -l < "$KEYWORDS" | tr -d ' ')"
fi
