-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- 主机： 127.0.0.1:3306
-- 生成日期： 2026-04-12 08:07:14
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
  `base_id` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '主键',
  `base_name` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '基地名称',
  `province_name` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '外键',
  `city_name` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `longitude` double NOT NULL COMMENT '经度（定位用）',
  `latitude` double NOT NULL COMMENT '纬度（定位用）',
  `base_description` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '简洁',
  `base_pic` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '基地图片预览'
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='产业基地信息';

--
-- 转存表中的数据 `base`
--

INSERT INTO `base` (`base_id`, `base_name`, `province_name`, `city_name`, `longitude`, `latitude`, `base_description`, `base_pic`) VALUES
('HB001', '柑橘冷库', '湖北省', '武汉市', 114.367824, 30.471571, '测试', '001.jpg'),
('HB002', '湖北基地2', '湖北省', '黄冈市', 114.913376, 30.648698, 'ces1', 'HB002.jpg');

-- --------------------------------------------------------

--
-- 表的结构 `labdataset_dataset`
--

DROP TABLE IF EXISTS `labdataset_dataset`;
CREATE TABLE IF NOT EXISTS `labdataset_dataset` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(200) CHARACTER SET utf8mb3 COLLATE utf8mb3_general_ci NOT NULL,
  `description` longtext CHARACTER SET utf8mb3 COLLATE utf8mb3_general_ci NOT NULL,
  `cover` varchar(1024) CHARACTER SET utf8mb3 COLLATE utf8mb3_general_ci NOT NULL,
  `creator` varchar(200) CHARACTER SET utf8mb3 COLLATE utf8mb3_general_ci NOT NULL,
  `size` bigint NOT NULL,
  `file_count` int NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `data_format` varchar(64) CHARACTER SET utf8mb3 COLLATE utf8mb3_general_ci NOT NULL,
  `storage_url` varchar(1024) CHARACTER SET utf8mb3 COLLATE utf8mb3_general_ci NOT NULL,
  PRIMARY KEY (`id`) USING BTREE
) ENGINE=InnoDB AUTO_INCREMENT=25 DEFAULT CHARSET=utf8mb3 ROW_FORMAT=DYNAMIC;

--
-- 转存表中的数据 `labdataset_dataset`
--

INSERT INTO `labdataset_dataset` (`id`, `name`, `description`, `cover`, `creator`, `size`, `file_count`, `created_at`, `updated_at`, `data_format`, `storage_url`) VALUES
(1, '玉米病害数据集', '复杂背景下的玉米大斑病、锈病、灰叶病自建数据集（共4189张图像）', '1.jpg', '王晗铭', 0, 4189, '2026-01-29 16:04:13.000000', '2026-01-29 16:04:13.000000', '图像', '237服务器: /data_1/whm24/玉米病害数据集'),
(2, 'NeRF合成数据集', 'NeRF标准数据集，含8个不同对象', '2.jpg', '王晗铭', 0, 0, '2026-01-29 16:04:13.000000', '2026-01-29 16:04:13.000000', '图像, 位姿', '237服务器: /data_1/whm24/NeRF_原始数据集'),
(3, '柑橘品种光谱数据', '85个品种的柑橘光谱数据，共计1000条数据', '3.jpg', '温馨龙', 0, 1000, '2026-01-29 16:04:13.000000', '2026-01-29 16:04:13.000000', 'NIRS', '238服务器: /data/home/wxl22/Regression_of_Chunjian/0219.csv'),
(4, '春见柑橘光谱数据', '3个产区的春见柑橘光谱数据，光谱采集时的俯视、侧视rgb图像、手持拍摄图像，及其对应的可溶性固体含量标签，共计500条数据', '4.jpg', '温馨龙', 0, 500, '2026-01-29 16:04:13.000000', '2026-01-29 16:04:13.000000', 'NIRS, 图像', '线下'),
(5, '不同品种柑橘光谱数据', '50个品种柑橘的光谱数据及其对应的可溶性固体含量、酸等多种内品质种类数据，共计1200条数据', '5.jpg', '温馨龙', 0, 1200, '2026-01-29 16:04:13.000000', '2026-01-29 16:04:13.000000', 'NIRS', '线下'),
(6, '柑橘侵染数据', '含细菌、霉菌、脱霉金杆等10+组数据，每组700+条数据', '6.jpg', '武永辉', 0, 0, '2026-01-29 16:04:13.000000', '2026-01-29 16:04:13.000000', '结构化数据, 图像', '已上传一组数据在237服务器 /data_1/wyh22 目录下，仅供4月现场参会相关人员参考');

-- --------------------------------------------------------

--
-- 表的结构 `labdataset_tag`
--

DROP TABLE IF EXISTS `labdataset_tag`;
CREATE TABLE IF NOT EXISTS `labdataset_tag` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(64) CHARACTER SET utf8mb3 COLLATE utf8mb3_general_ci NOT NULL,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE KEY `name` (`name`) USING BTREE
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb3 ROW_FORMAT=DYNAMIC;

--
-- 转存表中的数据 `labdataset_tag`
--

INSERT INTO `labdataset_tag` (`id`, `name`) VALUES
(3, 'NIRS'),
(2, '位姿'),
(1, '图像'),
(4, '结构化数据'),
(5, '音频');

-- --------------------------------------------------------

--
-- 表的结构 `screen_citrus`
--

DROP TABLE IF EXISTS `screen_citrus`;
CREATE TABLE IF NOT EXISTS `screen_citrus` (
  `area` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `value` int NOT NULL
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- 转存表中的数据 `screen_citrus`
--

INSERT INTO `screen_citrus` (`area`, `value`) VALUES
('湖北省', 10),
('上海市', 20),
('贵州省', 12),
('四川省', 60),
('北京市', 2),
('江苏省', 21);

-- --------------------------------------------------------

--
-- 表的结构 `screen_citrusvariety_production_history_area`
--

DROP TABLE IF EXISTS `screen_citrusvariety_production_history_area`;
CREATE TABLE IF NOT EXISTS `screen_citrusvariety_production_history_area` (
  `date` date NOT NULL,
  `variety` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `production_volume` float NOT NULL,
  `area` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='柑橘不同品种的月度累计产量(地区分区)';

--
-- 转存表中的数据 `screen_citrusvariety_production_history_area`
--

INSERT INTO `screen_citrusvariety_production_history_area` (`date`, `variety`, `production_volume`, `area`) VALUES
('2018-12-31', '温州蜜柑', 196, '湖北省'),
('2018-12-31', '橙类', 87, '湖北省'),
('2018-12-31', '椪柑', 43, '湖北省'),
('2018-12-31', '其他', 9, '湖北省'),
('2019-12-31', '秭归柑橘', 60, '湖北省'),
('2019-12-31', '晚熟柑橘', 12.5, '湖北省'),
('2019-12-31', '伦晚脐橙', 8, '湖北省'),
('2019-12-31', '红肉脐橙', 2.5, '湖北省'),
('2020-12-31', '温州蜜柑', 231.62, '湖北省'),
('2020-12-31', '橙类', 93.75, '湖北省'),
('2020-12-31', '椪柑', 34.12, '湖北省'),
('2020-12-31', '杂柑、柚类等', 10.17, '湖北省');

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
  `area` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- 转存表中的数据 `screen_citrus_production_history_area`
--

INSERT INTO `screen_citrus_production_history_area` (`date`, `production_volume`, `area`) VALUES
('2024-12-31', 589, '湖北省'),
('2023-12-31', 571, '湖北省'),
('2022-12-31', 540.82, '湖北省'),
('2021-12-01', 509.96, '湖北省'),
('2020-12-31', 495.17, '湖北省'),
('2019-12-01', 490.92, '湖北省'),
('2018-12-31', 465.9, '湖北省'),
('2016-12-31', 534.55, '湖北省'),
('2017-12-31', 532.57, '湖北省');
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
