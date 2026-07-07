/**
 * 全国省份气象地图 - ECharts + china.js GeoJSON
 * 依赖: echarts, china.js (registerMap "china")
 */
(function (root) {
  "use strict";

  var WeatherProvinceMap = {
    chart: null,
    weatherData: {},
    overviewList: [],
    currentLayer: "temperature",
    selectedProvince: "",
    onProvinceSelect: null,

    LAYERS: {
      temperature: {
        label: "温度",
        field: "value",
        unit: "°C",
        visualMap: {
          min: -15,
          max: 38,
          text: ["高温", "低温"],
          inRange: { color: ["#1e3a8a", "#2563eb", "#22c55e", "#eab308", "#ef4444"] },
        },
      },
      humidity: {
        label: "湿度",
        field: "humidity",
        unit: "%",
        visualMap: {
          min: 30,
          max: 95,
          text: ["高湿", "低湿"],
          inRange: { color: ["#fef3c7", "#86efac", "#38bdf8", "#2563eb", "#1e3a8a"] },
        },
      },
      rainfall: {
        label: "降雨",
        field: "rainfall",
        unit: "mm",
        tooltipNote: "24小时预报降水",
        visualMap: {
          min: 0,
          max: 20,
          text: ["多雨", "少雨"],
          inRange: { color: ["#f0f9ff", "#bae6fd", "#38bdf8", "#0284c7", "#1e3a8a"] },
        },
      },
    },

    init: function (containerId, options) {
      options = options || {};
      var el = document.getElementById(containerId);
      if (!el || !root.echarts) return null;

      this.chart = root.echarts.init(el);
      this.onProvinceSelect = options.onProvinceSelect || null;
      this._bindEvents();
      this._renderEmpty();
      return this;
    },

    _bindEvents: function () {
      var self = this;
      this.chart.on("click", function (params) {
        if (params.componentType !== "series" || !params.name) return;
        var name = self._normalizeName(params.name);
        self.selectProvince(name);
        if (typeof self.onProvinceSelect === "function") {
          self.onProvinceSelect(name);
        }
      });
      root.addEventListener("resize", function () {
        self.chart && self.chart.resize();
      });
    },

    _normalizeName: function (name) {
      if (!name) return "";
      return String(name).trim().replace(/(省|市|自治区|特别行政区)$/, "");
    },

    _renderEmpty: function () {
      this.chart.setOption(this._buildOption([]), true);
    },

    updateMapData: function (list) {
      this.overviewList = list || [];
      var map = {};
      (this.overviewList || []).forEach(function (item) {
        map[item.name] = item;
      });
      this.weatherData = map;
      this._applyLayer();
    },

    setLayer: function (layer) {
      if (!this.LAYERS[layer]) return;
      this.currentLayer = layer;
      this._applyLayer();
    },

    _getLayerValue: function (item, layer) {
      var cfg = this.LAYERS[layer || this.currentLayer];
      if (!item || !cfg) return 0;
      var val = item[cfg.field];
      return val != null ? val : 0;
    },

    _applyLayer: function () {
      var self = this;
      var layer = this.currentLayer;
      var cfg = this.LAYERS[layer];
      var seriesData = (this.overviewList || []).map(function (item) {
        return { name: item.name, value: self._getLayerValue(item, layer) };
      });
      this.chart.setOption(this._buildOption(seriesData, layer), true);
      if (this.selectedProvince) {
        this.selectProvince(this.selectedProvince);
      }
    },

    selectProvince: function (provinceName) {
      this.selectedProvince = provinceName;
      this.chart.dispatchAction({ type: "downplay", seriesIndex: 0 });
      this.chart.dispatchAction({
        type: "highlight",
        seriesIndex: 0,
        name: provinceName,
      });
    },

    _buildOption: function (seriesData, layer) {
      layer = layer || this.currentLayer;
      var cfg = this.LAYERS[layer];
      var vm = cfg.visualMap;
      return {
        backgroundColor: "transparent",
        tooltip: {
          trigger: "item",
          backgroundColor: "rgba(7,15,26,.92)",
          borderColor: "rgba(52,211,255,.35)",
          textStyle: { color: "#d7e6ff", fontSize: 13 },
          formatter: function (params) {
            var name = params.name || "";
            var info = WeatherProvinceMap.weatherData[name];
            if (!info) {
              return name + "<br/>暂无数据";
            }
            var activeLayer = WeatherProvinceMap.currentLayer;
            var layerVal = WeatherProvinceMap._getLayerValue(info, activeLayer);
            var layerCfg = WeatherProvinceMap.LAYERS[activeLayer];
            var iconHtml = info.icon_url
              ? '<img src="' + info.icon_url + '" style="width:36px;height:36px;vertical-align:middle;margin-right:6px;" />'
              : "";
            var layerNote = layerCfg.tooltipNote ? "（" + layerCfg.tooltipNote + "）" : "";
            return (
              iconHtml +
              "<b>" + name + "</b><br/>" +
              layerCfg.label + layerNote + ": <b style='color:#34d399'>" + layerVal + layerCfg.unit + "</b><br/>" +
              "温度: " + info.value + "°C<br/>" +
              "湿度: " + info.humidity + "%<br/>" +
              "24h降雨: " + (info.rainfall != null ? info.rainfall : 0) + " mm<br/>" +
              "天气: " + (info.description || "—")
            );
          },
        },
        visualMap: {
          show: true,
          left: 16,
          bottom: 24,
          min: vm.min,
          max: vm.max,
          text: vm.text,
          realtime: true,
          calculable: true,
          inRange: vm.inRange,
          textStyle: { color: "#8fb1d4", fontSize: 11 },
          itemWidth: 12,
          itemHeight: 80,
        },
        series: [
          {
            name: "省份" + cfg.label,
            type: "map",
            map: "china",
            roam: true,
            zoom: 1.15,
            scaleLimit: { min: 0.8, max: 3 },
            label: {
              show: true,
              color: "#c8dff5",
              fontSize: 10,
            },
            emphasis: {
              label: { show: true, color: "#fff", fontWeight: "bold", fontSize: 12 },
              itemStyle: { areaColor: "#f59e0b", borderColor: "#fff", borderWidth: 1.5 },
            },
            itemStyle: {
              areaColor: "rgba(34,70,168,.55)",
              borderColor: "rgba(52,211,255,.45)",
              borderWidth: 0.8,
            },
            data: seriesData,
          },
        ],
      };
    },

    resize: function () {
      this.chart && this.chart.resize();
    },
  };

  root.WeatherProvinceMap = WeatherProvinceMap;
})(window);
