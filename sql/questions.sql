-- name: 长春最新快照
-- 说明: 最新月份长春新房和二手房的环比、同比、年内累计指数。
WITH latest AS (SELECT MAX(month) AS month FROM housing_index)
SELECT
    h.month,
    h.market,
    ROUND(h.mom_index, 1) AS mom_index,
    ROUND(h.yoy_index, 1) AS yoy_index,
    ROUND(h.ytd_index, 1) AS ytd_index
FROM housing_index AS h
JOIN latest AS l ON h.month = l.month
WHERE h.city = '长春'
ORDER BY h.market;

-- name: 长春近 12 个月走势
-- 说明: 用窗口起点把最近 12 个月的新房/二手房指数并排列出。
WITH latest AS (SELECT MAX(month) AS month FROM housing_index),
start AS (
    SELECT strftime('%Y-%m', date(MAX(month) || '-01', '-11 months')) AS month
    FROM latest
)
SELECT
    h.month,
    h.market,
    ROUND(h.mom_index, 1) AS mom_index,
    ROUND(h.yoy_index, 1) AS yoy_index,
    ROUND(h.ytd_index, 1) AS ytd_index
FROM housing_index AS h
JOIN start AS s ON h.month >= s.month
WHERE h.city = '长春'
ORDER BY h.month, h.market;

-- name: 全国 70 城同比排名
-- 说明: 最新月份各城市同比排名；报告只需要头尾和长春。
WITH latest AS (SELECT MAX(month) AS month FROM housing_index),
ranked AS (
    SELECT
        h.month,
        h.market,
        h.city,
        h.yoy_index,
        RANK() OVER (PARTITION BY h.market ORDER BY h.yoy_index DESC) AS yoy_rank,
        COUNT(*) OVER (PARTITION BY h.market) AS city_count
    FROM housing_index AS h
    JOIN latest AS l ON h.month = l.month
),
selected AS (
    SELECT * FROM ranked
    WHERE city = '长春' OR yoy_rank <= 5 OR yoy_rank >= city_count - 4
)
SELECT
    market,
    yoy_rank,
    city,
    ROUND(yoy_index, 1) AS yoy_index,
    city_count
FROM selected
ORDER BY market, yoy_rank, city;

-- name: 长春与同类城市对比
-- 说明: 最新月份长春、东北城市和部分一线/新一线城市的同比指数。
WITH latest AS (SELECT MAX(month) AS month FROM housing_index)
SELECT
    h.city,
    h.market,
    ROUND(h.yoy_index, 1) AS yoy_index,
    ROUND(h.mom_index, 1) AS mom_index
FROM housing_index AS h
JOIN latest AS l ON h.month = l.month
WHERE h.city IN ('长春', '沈阳', '哈尔滨', '大连', '北京', '上海', '广州', '深圳', '杭州', '成都')
ORDER BY h.market, h.yoy_index DESC;

-- name: 新房与二手房同比价差
-- 说明: 长春最近 12 个月，新房同比减二手房同比，看走势分化。
WITH latest AS (SELECT MAX(month) AS month FROM housing_index),
pivot AS (
    SELECT
        month,
        MAX(CASE WHEN market = 'new' THEN yoy_index END) AS new_yoy,
        MAX(CASE WHEN market = 'second_hand' THEN yoy_index END) AS second_hand_yoy
    FROM housing_index
    WHERE city = '长春'
    GROUP BY month
)
SELECT
    month,
    ROUND(new_yoy, 1) AS new_yoy,
    ROUND(second_hand_yoy, 1) AS second_hand_yoy,
    ROUND(new_yoy - second_hand_yoy, 1) AS yoy_spread
FROM pivot
ORDER BY month DESC
LIMIT 12;
