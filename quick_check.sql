-- Check sofas by source in Railway database
SELECT
    source_website,
    COUNT(*) as sofa_count
FROM products
WHERE is_available = true
AND (
    name ~* '\ysofa\y' OR
    name ~* '\ycouch\y' OR
    name ~* '\ysectional\y' OR
    name ~* '\yloveseat\y'
)
GROUP BY source_website
ORDER BY sofa_count DESC;

-- Total sofas
SELECT COUNT(*) as total_sofas
FROM products
WHERE is_available = true
AND (
    name ~* '\ysofa\y' OR
    name ~* '\ycouch\y' OR
    name ~* '\ysectional\y' OR
    name ~* '\yloveseat\y'
);
