(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();
  var green = style.getPropertyValue('--green').trim();
  var amber = style.getPropertyValue('--amber').trim();
  var red = style.getPropertyValue('--red').trim();

  // --- Chart 1: IR Comparison across portfolio sizes ---
  var chart1 = echarts.init(document.getElementById('chart-ir-comparison'), null, { renderer: 'svg' });
  chart1.setOption({
    title: { text: '信息比率 (IR) 对比', left: 'center', textStyle: { fontSize: 14, color: ink } },
    tooltip: { trigger: 'axis', appendToBody: true, axisPointer: { type: 'shadow' } },
    legend: { data: ['n5 (5只持仓)', 'n10 (10只持仓)', 'n30 (30只持仓)'], bottom: 0, textStyle: { color: muted, fontSize: 11 } },
    grid: { left: 50, right: 20, top: 40, bottom: 50 },
    xAxis: {
      type: 'category',
      data: ['冠军', '亚军', '第3名', '第4名', '第5名', '第6名', '第7名', '第8名', '第9名', '第10名'],
      axisLabel: { color: muted, fontSize: 11 },
      axisLine: { lineStyle: { color: rule } }
    },
    yAxis: {
      type: 'value',
      name: 'IR',
      nameTextStyle: { color: muted, fontSize: 11 },
      axisLabel: { color: muted, fontSize: 11 },
      splitLine: { lineStyle: { color: rule } }
    },
    series: [
      {
        name: 'n5 (5只持仓)',
        type: 'bar',
        data: [1.384, 0.938, 0.862, 0.801, 0.800, 0.740, 0.724, 0.508],
        itemStyle: { color: accent2, borderRadius: [3, 3, 0, 0] },
        barWidth: '20%'
      },
      {
        name: 'n10 (10只持仓)',
        type: 'bar',
        data: [1.370, 1.366, 1.188, 1.156, 1.084, 1.067, 1.052, 1.006, 0.991, 0.980],
        itemStyle: { color: accent, borderRadius: [3, 3, 0, 0] },
        barWidth: '20%'
      },
      {
        name: 'n30 (30只持仓)',
        type: 'bar',
        data: [1.088, 1.074, 1.004, 0.989, 0.967, 0.960, 0.958, 0.858, 0.804, 0.790],
        itemStyle: { color: green, borderRadius: [3, 3, 0, 0] },
        barWidth: '20%'
      }
    ],
    animation: false
  });
  window.addEventListener('resize', function() { chart1.resize(); });

  // --- Chart 2: n10 IR vs MDD Scatter ---
  var chart2 = echarts.init(document.getElementById('chart-scatter'), null, { renderer: 'svg' });
  chart2.setOption({
    title: { text: 'n10 策略: IR vs MDD (气泡大小=OOS收益)', left: 'center', textStyle: { fontSize: 14, color: ink } },
    tooltip: {
      trigger: 'item',
      appendToBody: true,
      formatter: function(p) {
        return p.data.name + '<br/>IR: ' + p.data.value[0] + '<br/>MDD: ' + p.data.value[1] + '%<br/>OOS: +' + p.data.value[2] + '%';
      }
    },
    grid: { left: 60, right: 30, top: 40, bottom: 50 },
    xAxis: {
      type: 'value',
      name: '信息比率 IR',
      nameLocation: 'middle',
      nameGap: 30,
      nameTextStyle: { color: muted, fontSize: 11 },
      axisLabel: { color: muted, fontSize: 11 },
      splitLine: { lineStyle: { color: rule } },
      min: 0.4
    },
    yAxis: {
      type: 'value',
      name: '最大回撤 MDD (%)',
      nameLocation: 'middle',
      nameGap: 40,
      nameTextStyle: { color: muted, fontSize: 11 },
      axisLabel: { color: muted, fontSize: 11 },
      splitLine: { lineStyle: { color: rule } }
    },
    series: [{
      type: 'scatter',
      symbolSize: function(data) { return Math.max(8, Math.sqrt(data[2]) * 1.5); },
      data: [
        { name: 'dd3_rsv7_ret20', value: [1.370, 22.3, 345.4], itemStyle: { color: accent } },
        { name: 'dd3_rsv9_ret20', value: [1.366, 22.3, 358.1], itemStyle: { color: accent } },
        { name: 'dd3_rsv6_ret20', value: [1.188, 28.4, 292.2], itemStyle: { color: accent } },
        { name: 'dd3_rsv14_ret20', value: [1.156, 28.5, 321.5], itemStyle: { color: accent } },
        { name: 'rsv9_ret20', value: [1.084, 23.4, 290.6], itemStyle: { color: accent, opacity: 0.7 } },
        { name: 'rsv7_ret20', value: [1.067, 25.6, 260.3], itemStyle: { color: accent, opacity: 0.7 } },
        { name: 'bollpb5_ret20', value: [0.980, 21.5, 252.8], itemStyle: { color: '#db2777' } },
        { name: 'dd3_mfi7_ret20', value: [0.949, 33.5, 220.6], itemStyle: { color: green } },
        { name: 'dd3_mfi10_ret20', value: [0.891, 40.5, 202.7], itemStyle: { color: green } },
        { name: 'dd3_obv10_ret20', value: [0.878, 35.9, 201.3], itemStyle: { color: '#7c3aed' } },
        { name: 'dd3_mfi_ret20', value: [0.773, 26.8, 161.1], itemStyle: { color: green } },
        { name: 'dd3_rsv7_rsi7_ret20', value: [0.650, 34.2, 119.2], itemStyle: { color: amber } },
        { name: 'obv10_ret20', value: [0.615, 41.3, 146.5], itemStyle: { color: '#7c3aed', opacity: 0.7 } },
        { name: 'obv_ret20', value: [0.552, 32.2, 121.1], itemStyle: { color: '#7c3aed', opacity: 0.7 } }
      ],
      label: {
        show: true,
        position: 'right',
        formatter: function(p) { return p.data.name; },
        fontSize: 9,
        color: muted
      },
      animation: false
    }],
    animation: false
  });
  window.addEventListener('resize', function() { chart2.resize(); });
})();
