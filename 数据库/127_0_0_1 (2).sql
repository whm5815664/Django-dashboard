-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- 主机： 127.0.0.1:3306
-- 生成日期： 2026-02-03 02:51:34
-- 服务器版本： 9.1.0
-- PHP 版本： 8.3.14

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- 数据库： `web_database`
--
CREATE DATABASE IF NOT EXISTS `web_database` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `web_database`;

-- --------------------------------------------------------

--
-- 表的结构 `base`
--

DROP TABLE IF EXISTS `base`;
CREATE TABLE IF NOT EXISTS `base` (
  `base_id` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '主键',
  `base_name` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '基地名称',
  `province_name` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '外键',
  `city_name` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `longitude` double NOT NULL COMMENT '经度（定位用）',
  `latitude` double NOT NULL COMMENT '纬度（定位用）',
  `base_description` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '简洁',
  `base_pic` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '基地图片预览'
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='产业基地信息';

--
-- 转存表中的数据 `base`
--

INSERT INTO `base` (`base_id`, `base_name`, `province_name`, `city_name`, `longitude`, `latitude`, `base_description`, `base_pic`) VALUES
('001', '柑橘冷库', '湖北', '武汉', 114.367824, 30.471571, '测试', '001.jpg'),
('HB001', '湖北基地2', '湖北', '武汉', 113.300499, 30.670329, '测试用地2', 'HBHB001.jpg');

-- --------------------------------------------------------

--
-- 表的结构 `devices`
--

DROP TABLE IF EXISTS `devices`;
CREATE TABLE IF NOT EXISTS `devices` (
  `id` bigint UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
  `device_name` varchar(64) NOT NULL COMMENT '设备名',
  `device_code` varchar(64) DEFAULT NULL COMMENT '设备编号/编码',
  `base_id` bigint UNSIGNED DEFAULT NULL COMMENT '所属冷库ID',
  `longitude` decimal(10,6) DEFAULT NULL COMMENT '经度',
  `latitude` decimal(10,6) DEFAULT NULL COMMENT '纬度',
  `location` varchar(255) DEFAULT NULL COMMENT '位置信息(例如: 一楼北侧/货架A3)',
  `status` enum('online','offline','alarm') NOT NULL DEFAULT 'offline' COMMENT '在线状态',
  `last_report_time` datetime DEFAULT NULL COMMENT '最后上报时间',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_device_name` (`device_name`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='设备表（仅存设备名）';

--
-- 转存表中的数据 `devices`
--

INSERT INTO `devices` (`id`, `device_name`, `device_code`, `base_id`, `longitude`, `latitude`, `location`, `status`, `last_report_time`, `created_at`, `updated_at`) VALUES
(1, 'sensor_readings1', '1', 1, 113.356700, 30.469600, '湖北武汉', 'online', '2026-01-27 09:59:15', '2026-01-12 16:00:00', '2026-01-27 10:42:26');

-- --------------------------------------------------------

--
-- 表的结构 `screen_citrus`
--

DROP TABLE IF EXISTS `screen_citrus`;
CREATE TABLE IF NOT EXISTS `screen_citrus` (
  `area` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL,
  `value` int NOT NULL
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- 转存表中的数据 `screen_citrus`
--

INSERT INTO `screen_citrus` (`area`, `value`) VALUES
('北京', 0),
('天津', 0),
('上海', 12),
('重庆', 320),
('河北', 0),
('河南', 5),
('云南', 136),
('辽宁', 0),
('海南', 260),
('湖北', 150);

-- --------------------------------------------------------

--
-- 表的结构 `screen_citrusvariety_production_history_area`
--

DROP TABLE IF EXISTS `screen_citrusvariety_production_history_area`;
CREATE TABLE IF NOT EXISTS `screen_citrusvariety_production_history_area` (
  `date` date NOT NULL,
  `variety` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL,
  `production_volume` float NOT NULL,
  `area` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='柑橘不同品种的月度累计产量(地区分区)';

--
-- 转存表中的数据 `screen_citrusvariety_production_history_area`
--

INSERT INTO `screen_citrusvariety_production_history_area` (`date`, `variety`, `production_volume`, `area`) VALUES
('2018-12-31', '温州蜜柑', 196, '湖北'),
('2018-12-31', '橙类', 87, '湖北'),
('2018-12-31', '椪柑', 43, '湖北'),
('2018-12-31', '其他', 9, '湖北'),
('2019-12-31', '秭归柑橘', 60, '湖北'),
('2019-12-31', '晚熟柑橘', 12.5, '湖北'),
('2019-12-31', '伦晚脐橙', 8, '湖北'),
('2019-12-31', '红肉脐橙', 2.5, '湖北'),
('2020-12-31', '温州蜜柑', 231.62, '湖北'),
('2020-12-31', '橙类', 93.75, '湖北'),
('2020-12-31', '椪柑', 34.12, '湖北'),
('2020-12-31', '杂柑、柚类等', 10.17, '湖北');

-- --------------------------------------------------------

--
-- 表的结构 `screen_citrus_production_history`
--

DROP TABLE IF EXISTS `screen_citrus_production_history`;
CREATE TABLE IF NOT EXISTS `screen_citrus_production_history` (
  `year` int NOT NULL,
  `production_volume` int NOT NULL
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- 转存表中的数据 `screen_citrus_production_history`
--

INSERT INTO `screen_citrus_production_history` (`year`, `production_volume`) VALUES
(2025, 1643),
(2024, 962),
(2023, 1548),
(2022, 1846),
(2021, 500);

-- --------------------------------------------------------

--
-- 表的结构 `screen_citrus_production_history_area`
--

DROP TABLE IF EXISTS `screen_citrus_production_history_area`;
CREATE TABLE IF NOT EXISTS `screen_citrus_production_history_area` (
  `date` date NOT NULL,
  `production_volume` double NOT NULL,
  `area` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- 转存表中的数据 `screen_citrus_production_history_area`
--

INSERT INTO `screen_citrus_production_history_area` (`date`, `production_volume`, `area`) VALUES
('2024-12-31', 589, '湖北'),
('2023-12-31', 571, '湖北'),
('2022-12-31', 540.82, '湖北'),
('2021-12-01', 509.96, '湖北'),
('2020-12-31', 495.17, '湖北'),
('2019-12-01', 490.92, '湖北'),
('2018-12-31', 465.9, '湖北'),
('2016-12-31', 534.55, '湖北'),
('2017-12-31', 532.57, '湖北');

-- --------------------------------------------------------

--
-- 表的结构 `sensor_readings1`
--

DROP TABLE IF EXISTS `sensor_readings1`;
CREATE TABLE IF NOT EXISTS `sensor_readings1` (
  `id` bigint UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '自增主键',
  `collected_at` datetime NOT NULL COMMENT '采集时间',
  `temperature` decimal(6,2) DEFAULT NULL COMMENT '温度(℃)',
  `humidity` decimal(6,2) DEFAULT NULL COMMENT '湿度(%)',
  `co2_ppm` int DEFAULT NULL COMMENT 'CO2(ppm)',
  `h2_ppm` int DEFAULT NULL COMMENT 'H2(ppm)',
  `co_ppm` int DEFAULT NULL COMMENT 'CO(ppm)',
  `c2h5oh` decimal(10,3) DEFAULT NULL COMMENT 'C2H5OH',
  `voc` decimal(10,3) DEFAULT NULL COMMENT 'VOC',
  `o2` decimal(10,3) DEFAULT NULL COMMENT 'O2',
  `c2h4` decimal(10,3) DEFAULT NULL COMMENT 'C2H4',
  `image_path` varchar(255) DEFAULT NULL COMMENT '图片相对路径',
  PRIMARY KEY (`id`),
  KEY `idx_collected_at` (`collected_at`)
) ENGINE=InnoDB AUTO_INCREMENT=33 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='传感器采集数据';

--
-- 转存表中的数据 `sensor_readings1`
--

INSERT INTO `sensor_readings1` (`id`, `collected_at`, `temperature`, `humidity`, `co2_ppm`, `h2_ppm`, `co_ppm`, `c2h5oh`, `voc`, `o2`, `c2h4`, `image_path`) VALUES
(1, '2025-10-01 00:00:00', 26.93, 72.85, 395, 14, 0, 0.286, 5.338, 20.900, 21.270, '1/2/2025-10-01 11:28:34.jpg'),
(2, '2025-10-02 00:00:00', 26.96, 72.57, 394, 13, 0, 0.289, 5.267, 11.600, 20.940, '1/2/2025-10-01 11:28:44.jpg'),
(3, '2025-10-03 00:00:00', 26.96, 72.40, 394, 13, 0, 0.290, 5.204, 15.700, 20.580, '1/2/2025-10-01 11:28:54.jpg'),
(4, '2025-10-04 00:00:00', 26.96, 72.28, 393, 14, 0, 0.273, 5.123, 17.200, 20.210, '1/2/2025-10-01 11:29:04.jpg'),
(5, '2025-10-05 00:00:00', 26.96, 72.22, 390, 14, 0, 0.248, 5.025, 17.600, 19.830, '1/2/2025-10-01 11:29:14.jpg'),
(6, '2025-10-06 00:00:00', 26.94, 72.19, 387, 14, 0, 0.223, 4.934, 17.700, 19.390, '1/2/2025-10-01 11:29:24.jpg'),
(7, '2025-10-07 00:00:00', 26.94, 72.12, 383, 14, 0, 0.183, 4.787, 17.800, 18.700, '1/2/2025-10-01 11:29:39.jpg'),
(8, '2025-10-08 00:00:00', 26.96, 72.17, 382, 14, 0, 0.159, 4.686, 17.900, 18.220, '1/2/2025-10-01 11:29:49.jpg'),
(9, '2025-10-09 00:00:00', 26.97, 72.14, 381, 14, 0, 0.137, 4.588, 18.000, 17.800, '1/2/2025-10-01 11:29:59.jpg'),
(10, '2025-10-10 00:00:00', 26.94, 72.09, 380, 14, 0, 0.116, 4.497, 18.000, 17.450, '1/2/2025-10-01 11:30:09.jpg'),
(11, '2025-10-11 00:00:00', 26.93, 72.08, 380, 13, 0, 0.096, 4.414, 18.000, 17.180, '1/2/2025-10-01 11:30:19.jpg'),
(12, '2025-10-12 00:00:00', 26.94, 72.10, 384, 13, 0, 0.078, 4.338, 18.100, 16.520, '1/2/2025-10-01 11:30:29.jpg'),
(13, '2025-10-13 00:00:00', 26.94, 72.16, 405, 13, 0, 0.071, 4.234, 18.100, 16.090, '1/2/2025-10-01 11:30:39.jpg'),
(14, '2025-10-14 00:00:00', 26.96, 72.19, 423, 13, 0, 0.064, 4.146, 18.200, 15.690, '1/2/2025-10-01 11:30:49.jpg'),
(15, '2025-10-15 00:00:00', 26.96, 72.22, 441, 13, 0, 0.057, 4.075, 18.200, 15.260, '1/2/2025-10-01 11:30:59.jpg'),
(16, '2025-10-16 00:00:00', 26.97, 72.24, 445, 13, 0, 0.053, 4.040, 19.800, 15.100, '1/2/2025-10-01 11:31:04.jpg'),
(17, '2025-10-17 00:00:00', 26.94, 72.70, 450, 13, 0, 0.044, 3.967, 30.000, 14.870, '1/2/2025-10-01 11:31:14.jpg'),
(18, '2025-10-18 00:00:00', 26.96, 72.86, 454, 12, 0, 0.037, 3.881, 23.600, 14.290, '1/2/2025-10-01 11:31:24.jpg'),
(19, '2025-10-19 00:00:00', 26.96, 72.95, 458, 12, 0, 0.036, 3.808, 22.500, 13.800, '1/2/2025-10-01 11:31:37.jpg'),
(20, '2025-10-20 00:00:00', 26.93, 73.01, 460, 12, 0, 0.035, 3.752, 22.300, 13.570, '1/2/2025-10-01 11:31:47.jpg'),
(21, '2025-10-21 00:00:00', 26.97, 73.01, 462, 12, 0, 0.034, 3.692, 22.200, 13.280, '1/2/2025-10-01 11:31:57.jpg'),
(22, '2025-10-22 00:00:00', 26.96, 72.99, 464, 12, 0, 0.033, 3.646, 22.200, 13.020, '1/2/2025-10-01 11:32:07.jpg'),
(23, '2025-10-23 00:00:00', 26.96, 73.04, 466, 12, 0, 0.033, 3.606, 22.100, 12.800, '1/2/2025-10-01 11:32:17.jpg'),
(24, '2025-10-24 00:00:00', 26.98, 73.04, 466, 12, 0, 0.033, 3.570, 22.100, 12.590, '1/2/2025-10-01 11:32:27.jpg'),
(25, '2025-10-25 00:00:00', 26.98, 73.02, 467, 12, 0, 0.033, 3.505, 22.100, 12.160, '1/2/2025-10-01 11:32:43.jpg'),
(26, '2025-10-26 00:00:00', 26.97, 73.05, 467, 12, 0, 0.034, 3.462, 22.100, 11.970, '1/2/2025-10-01 11:32:53.jpg'),
(27, '2025-10-27 00:00:00', 26.98, 73.04, 467, 12, 0, 0.034, 3.421, 22.100, 11.790, '1/2/2025-10-01 11:33:03.jpg'),
(28, '2025-10-28 00:00:00', 26.97, 73.03, 467, 12, 0, 0.035, 3.386, 22.100, 11.640, '1/2/2025-10-01 11:33:13.jpg'),
(29, '2025-10-29 00:00:00', 26.97, 73.03, 467, 12, 0, 0.036, 3.346, 22.000, 11.490, '1/2/2025-10-01 11:33:23.jpg'),
(30, '2025-10-30 00:00:00', 27.00, 73.06, 466, 10, 0, 0.036, 3.315, 22.000, 11.260, '1/2/2025-10-01 11:33:33.jpg'),
(31, '2025-10-31 00:00:00', 26.98, 72.99, 466, 12, 0, 0.037, 3.285, 22.000, 11.130, '1/2/2025-10-01 11:33:43.jpg'),
(32, '2025-11-01 00:00:00', 26.97, 73.03, 466, 12, 0, 0.038, 3.257, 21.900, 11.000, '1/2/2025-10-01 11:33:53.jpg');

-- --------------------------------------------------------

--
-- 表的结构 `users`
--

DROP TABLE IF EXISTS `users`;
CREATE TABLE IF NOT EXISTS `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `email` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=MyISAM AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- 转存表中的数据 `users`
--

INSERT INTO `users` (`id`, `name`, `email`) VALUES
(1, 'Alice', 'alice@example.com'),
(2, 'Bob', 'bob@example.com');
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
