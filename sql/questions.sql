-- 五个业务问题。
-- 格式：每条查询以 "-- name: 标题" 开头，后面的注释行会被忽略。
-- 想加问题？照着复制一段就行，pipeline 会自动发现并跑。

-- name: 各区均价与房源数
-- 说明: 哪个区最贵、哪个区房源最多——这是看城市房价结构的第一步
SELECT district              AS 区域,
       COUNT(*)              AS 房源数,
       ROUND(AVG(unit_price), 0) AS 均价,
       ROUND(MIN(unit_price), 0) AS 最低价,
       ROUND(MAX(unit_price), 0) AS 最高价
FROM listings
GROUP BY district
ORDER BY 均价 DESC;

-- name: 面积段与均价
-- 说明: 小户型单价高还是大户型高？这条会告诉你
SELECT CASE
           WHEN area_m2 < 60  THEN '60㎡以下'
           WHEN area_m2 < 90  THEN '60-90㎡'
           WHEN area_m2 < 120 THEN '90-120㎡'
           ELSE '120㎡以上'
       END                   AS 面积段,
       COUNT(*)              AS 房源数,
       ROUND(AVG(unit_price), 0) AS 均价,
       ROUND(AVG(area_m2), 1)    AS 平均面积
FROM listings
GROUP BY 面积段
ORDER BY MIN(area_m2);

-- name: 楼层高低对单价的影响
-- 说明: 顶楼、一楼通常便宜，这条用数据验证一下
SELECT COALESCE(NULLIF(floor, ''), '未标注') AS 楼层,
       COUNT(*)              AS 房源数,
       ROUND(AVG(unit_price), 0) AS 均价
FROM listings
GROUP BY 楼层
ORDER BY 均价 DESC;

-- name: 房龄与均价
-- 说明: 新房溢价有多少？按房龄分段看更清楚
SELECT CASE
           WHEN 2026 - build_year <= 5  THEN '5 年内'
           WHEN 2026 - build_year <= 10 THEN '6-10 年'
           WHEN 2026 - build_year <= 20 THEN '11-20 年'
           ELSE '20 年以上'
       END                   AS 房龄段,
       COUNT(*)              AS 房源数,
       ROUND(AVG(unit_price), 0) AS 均价
FROM listings
WHERE build_year IS NOT NULL AND build_year > 0
GROUP BY 房龄段
ORDER BY MIN(build_year) DESC;

-- name: 挂牌量最多的小区
-- 说明: 挂牌量大 = 换手率高，这类小区通常更好出手
SELECT community   AS 小区,
       district    AS 区域,
       COUNT(*)    AS 挂牌数,
       ROUND(AVG(unit_price), 0) AS 均价,
       ROUND(AVG(area_m2), 1)    AS 平均面积
FROM listings
WHERE community IS NOT NULL AND community <> ''
GROUP BY community, district
ORDER BY 挂牌数 DESC, 均价 DESC
LIMIT 10;
