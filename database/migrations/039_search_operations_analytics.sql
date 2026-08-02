CREATE INDEX IF NOT EXISTS idx_search_query_metrics_created_at
  ON search_query_metrics(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_search_query_metrics_zero_results
  ON search_query_metrics(result_count, created_at DESC);
