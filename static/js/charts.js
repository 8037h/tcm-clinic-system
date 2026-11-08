(function () {
  const dataNode = document.getElementById('chart-data');
  if (!dataNode) return;
  const data = JSON.parse(dataNode.textContent);
  if (typeof echarts === 'undefined') {
    document.querySelectorAll('.chart').forEach(node => { node.textContent = '图表资源加载失败，请刷新页面。'; });
    return;
  }
  const charts = [];
  const palette = ['#287b52', '#6ebd82', '#e4a85d', '#7096cb', '#a47fbc', '#cc766e'];
  function draw(id, option) {
    const node = document.getElementById(id);
    if (!node) return;
    const chart = echarts.init(node, null, { renderer: 'svg' });
    chart.setOption({ color: palette, tooltip: { trigger: 'axis' }, grid: { left: 42, right: 22, top: 25, bottom: 45, containLabel: true }, ...option });
    charts.push(chart);
  }
  draw('chart-trend', {
    xAxis: { type: 'category', data: data.dates, axisLabel: { formatter: value => value.slice(5) } },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{ name: '接诊数', type: 'line', smooth: true, data: data.seven_day_counts, areaStyle: { opacity: .12 } }]
  });
  draw('chart-departments', {
    xAxis: { type: 'category', data: data.departments, axisLabel: { interval: 0, rotate: 25 } },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{ name: '接诊数', type: 'bar', data: data.department_counts, barMaxWidth: 42 }]
  });
  draw('chart-statuses', {
    tooltip: { trigger: 'item' }, legend: { bottom: 0 },
    series: [{ name: '接诊状态', type: 'pie', radius: ['38%', '68%'], data: data.statuses, label: { formatter: '{b}: {c}' } }]
  });
  draw('chart-doctors', {
    xAxis: { type: 'value', minInterval: 1 },
    yAxis: { type: 'category', data: data.doctor_names.slice().reverse() },
    series: [{ name: '接诊数', type: 'bar', data: data.doctor_counts.slice().reverse(), barMaxWidth: 24 }]
  });
  draw('chart-performance', {
    xAxis: { type: 'value' },
    yAxis: { type: 'category', data: data.performance_names.slice().reverse() },
    series: [{ name: '绩效总分', type: 'bar', data: data.performance_scores.slice().reverse(), barMaxWidth: 24 }]
  });
  window.addEventListener('resize', () => charts.forEach(chart => chart.resize()));
  window.addEventListener('beforeprint', () => charts.forEach(chart => chart.resize()));
})();
