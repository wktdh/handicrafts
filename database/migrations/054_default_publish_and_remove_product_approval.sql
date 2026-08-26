-- 卖家作品默认审核通过；历史等待人工审核的作品不再保留为待通过状态。
UPDATE products
SET moderation_status = 'approved',
    moderation_reason = NULL,
    moderated_at = CURRENT_TIMESTAMP
WHERE moderation_status = 'pending';

UPDATE governance_tasks
SET status = 'completed',
    completed_at = CURRENT_TIMESTAMP
WHERE task_type = 'product_moderation' AND status IN ('pending', 'in_progress');
