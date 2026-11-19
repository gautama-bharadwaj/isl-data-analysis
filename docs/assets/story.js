// Report page: reads docs/data/*.json and draws every chart and table.
(async function () {
  const S = window.SITE;
  S.initThemeToggle();
  const d = await S.load(['seasons', 'teams', 'best_xi', 'positions', 'leaderboards', 'meta', 'set_play', 'attendance']);
  const seasons = d.seasons;
  const labels = seasons.map((s) => s.label);
  const fmt = S.fmtNum;
  const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const shortTeams = (t) => String(t || '').split(', ').slice(-2).join(', ');

  document.getElementById('generated').textContent = 'Data up to ' + d.meta.generated + '.';

  // ---- hero tiles
  const goals = d.leaderboards.goals_all_time;
  const titles = {};
  d.teams.filter((t) => t.won_final).forEach((t) => { titles[t.team] = (titles[t.team] || 0) + 1; });
  const [topClub, topTitles] = Object.entries(titles).sort((a, b) => b[1] - a[1])[0];
  const totalMatches = seasons.reduce((a, s) => a + s.matches, 0);
  const totalGoals = seasons.reduce((a, s) => a + s.goals, 0);
  document.getElementById('hero-tiles').innerHTML = [
    ['Matches', fmt(totalMatches), '13 seasons, 2014 to 2026–27'],
    ['Goals', fmt(totalGoals), fmt(totalGoals / totalMatches, 2) + ' per match'],
    ['All-time top scorer', esc(goals[0].player), `<b>${goals[0].goals}</b> goals`],
    ['Most titles', esc(topClub), `<b>${topTitles}</b> ISL Cups`],
  ].map(([l, v, s]) => `<div class="tile"><div class="label">${l}</div><div class="value" style="font-size:${String(v).length > 10 ? 24 : 34}px">${v}</div><div class="delta">${s}</div></div>`).join('');

  // ---- goals per match
  S.make('c-goals', (t) => Object.assign(S.base(t, { legend: { show: false } }), {
    xAxis: Object.assign(S.axisStyle(t), { type: 'category', data: labels }),
    yAxis: Object.assign(S.axisStyle(t), { type: 'value', min: 0 }),
    series: [{ type: 'bar', data: seasons.map((s) => s.goals_per_match), barMaxWidth: 22,
      itemStyle: { color: t.series[0], borderRadius: [4, 4, 0, 0] }, name: 'Goals per match' }],
  }));
  S.tableView('c-goals', ['Season', 'Matches', 'Goals per match'], seasons.map((s) => [s.label, s.matches, s.goals_per_match]), (v, i) => (i === 2 ? fmt(v, 2) : fmt(v)));

  const shotSeasons = seasons.filter((s) => s.conversion_pct != null);
  S.make('c-conversion', (t) => Object.assign(S.base(t, { legend: { show: false } }), {
    xAxis: Object.assign(S.axisStyle(t), { type: 'category', data: shotSeasons.map((s) => s.label) }),
    yAxis: Object.assign(S.axisStyle(t), { type: 'value', min: 8, axisLabel: { color: t.muted, fontSize: 11, formatter: '{value}%' } }),
    series: [{ type: 'line', name: 'Conversion %', data: shotSeasons.map((s) => s.conversion_pct), symbolSize: 8,
      lineStyle: { width: 2, color: t.series[0] }, itemStyle: { color: t.series[0] } }],
  }));
  S.tableView('c-conversion', ['Season', 'Shots per match', 'On target per match', 'Conversion %'],
    shotSeasons.map((s) => [s.label, s.shots_per_match, s.on_target_per_match, s.conversion_pct]));

  // ---- results
  const bubble = seasons.find((s) => s.season === '2020-2021');
  document.getElementById('bubble-home').textContent = Math.round(bubble.home_win_pct) + '%';
  document.getElementById('bubble-draw').textContent = Math.round(bubble.draw_pct) + '%';
  S.make('c-results', (t) => Object.assign(S.base(t, { tooltip: Object.assign(S.base(t).tooltip, { axisPointer: { type: 'shadow' }, valueFormatter: (v) => fmt(v) + '%' }) }), {
    xAxis: Object.assign(S.axisStyle(t), { type: 'category', data: labels }),
    yAxis: Object.assign(S.axisStyle(t), { type: 'value', max: 100, axisLabel: { color: t.muted, fontSize: 11, formatter: '{value}%' } }),
    series: [
      ['Home win', 'home_win_pct', t.series[0]], ['Draw', 'draw_pct', t.axis], ['Away win', 'away_win_pct', t.series[1]],
    ].map(([name, key, color], i) => ({
      type: 'bar', stack: 'r', name, data: seasons.map((s) => s[key]), barMaxWidth: 34,
      itemStyle: { color, borderColor: t.surface, borderWidth: 1, borderRadius: i === 2 ? [4, 4, 0, 0] : 0 },
      markArea: i === 0 ? { silent: true, itemStyle: { color: 'transparent', borderColor: t.muted, borderType: 'dashed', borderWidth: 1 },
        label: { color: t.ink2, fontSize: 11, position: 'top', formatter: 'Closed doors, Goa' },
        data: [[{ xAxis: '2020–21' }, { xAxis: '2020–21' }]] } : undefined,
    })),
  }));
  S.tableView('c-results', ['Season', 'Home win %', 'Draw %', 'Away win %'], seasons.map((s) => [s.label, s.home_win_pct, s.draw_pct, s.away_win_pct]));

  // ---- goal types
  const xgSeasons = seasons.filter((s) => s.set_piece_goal_pct != null);
  S.make('c-goaltypes', (t) => Object.assign(S.base(t, { tooltip: Object.assign(S.base(t).tooltip, { valueFormatter: (v) => fmt(v) + '%' }) }), {
    xAxis: Object.assign(S.axisStyle(t), { type: 'category', data: xgSeasons.map((s) => s.label) }),
    yAxis: Object.assign(S.axisStyle(t), { type: 'value', min: 0, axisLabel: { color: t.muted, fontSize: 11, formatter: '{value}%' } }),
    series: [['Set pieces', 'set_piece_goal_pct'], ['Headers', 'header_goal_pct'], ['Penalties', 'penalty_goal_pct']].map(([name, key], i) => ({
      type: 'line', name, data: xgSeasons.map((s) => s[key]), symbolSize: 8,
      lineStyle: { width: 2, color: t.series[i] }, itemStyle: { color: t.series[i] },
      endLabel: { show: true, formatter: name, color: t.ink2, fontSize: 11 },
    })),
    grid: { left: 8, right: 70, top: 60, bottom: 8, containLabel: true },
  }));
  S.tableView('c-goaltypes', ['Season', 'Set pieces %', 'Headers %', 'Penalties %', 'From outside the box %', 'Direct free kicks'],
    xgSeasons.map((s) => [s.label, s.set_piece_goal_pct, s.header_goal_pct, s.penalty_goal_pct, s.outside_box_goal_pct, s.direct_free_kick_goals]));

  const indSeasons = seasons.filter((s) => s.indian_minutes_pct != null);
  S.make('c-indian', (t) => Object.assign(S.base(t, { legend: { show: false } }), {
    xAxis: Object.assign(S.axisStyle(t), { type: 'category', data: indSeasons.map((s) => s.label) }),
    yAxis: Object.assign(S.axisStyle(t), { type: 'value', min: 50, max: 80, axisLabel: { color: t.muted, fontSize: 11, formatter: '{value}%' } }),
    series: [{ type: 'line', name: 'Indian share of minutes', data: indSeasons.map((s) => s.indian_minutes_pct), symbolSize: 8,
      lineStyle: { width: 2, color: t.series[2] }, itemStyle: { color: t.series[2] } }],
  }));
  S.tableView('c-indian', ['Season', 'Indian share of minutes %'], indSeasons.map((s) => [s.label, s.indian_minutes_pct]));

  // ---- set plays
  const sp = d.set_play;
  document.querySelectorAll('.sp-first').forEach((e) => { e.textContent = sp.first_season; });
  const peak = sp.by_season.reduce((a, b) => (b.set_play_pct > a.set_play_pct ? b : a));
  document.getElementById('sp-peak').textContent = `${peak.label} (${Math.round(peak.set_play_pct)}%)`;
  const typeColor = (t, name) => ({ 'Open play': t.series[0], Corners: t.series[1], 'Free kicks': t.series[2], 'Throw-ins': t.series[3],
    Penalties: t.series[4], 'Own goals': t.axis })[name];
  const pctOf = (row, name, total) => (100 * (row.counts[name] || 0)) / total;
  S.make('c-setplay', (t) => Object.assign(S.base(t, { tooltip: Object.assign(S.base(t).tooltip, { axisPointer: { type: 'shadow' },
    formatter: (ps) => `<b>${ps[0].name}</b> · ${sp.by_season[ps[0].dataIndex].goals} goals<br>` + ps.slice().reverse().map((p) => `${p.marker} ${p.seriesName}: ${fmt(p.value, 1)}% (${sp.by_season[p.dataIndex].counts[p.seriesName]})`).join('<br>') }) }), {
    grid: { left: 8, right: 16, top: 70, bottom: 8, containLabel: true },
    xAxis: Object.assign(S.axisStyle(t), { type: 'category', data: sp.by_season.map((x) => x.label) }),
    yAxis: Object.assign(S.axisStyle(t), { type: 'value', max: 100, axisLabel: { color: t.muted, fontSize: 11, formatter: '{value}%' } }),
    series: sp.types.map((name, i) => ({
      type: 'bar', stack: 'g', name, barMaxWidth: 40, data: sp.by_season.map((x) => pctOf(x, name, x.goals)),
      itemStyle: { color: typeColor(t, name), borderColor: t.surface, borderWidth: 1, borderRadius: i === sp.types.length - 1 ? [4, 4, 0, 0] : 0 },
      label: i === sp.types.length - 1 ? { show: true, position: 'top', color: t.ink2, fontSize: 11,
        formatter: (p) => `Set plays ${Math.round(sp.by_season[p.dataIndex].set_play_pct)}%` } : undefined,
    })),
  }));
  S.tableView('c-setplay', ['Season', 'Goals', ...sp.types, 'Set plays + penalties %'],
    sp.by_season.map((x) => [x.label, x.goals, ...sp.types.map((n) => x.counts[n]), x.set_play_pct]));

  const clubTypes = sp.types.filter((n) => n !== 'Own goals');
  S.make('c-setplay-club', (t) => Object.assign(S.base(t, { tooltip: Object.assign(S.base(t).tooltip, { axisPointer: { type: 'shadow' },
    formatter: (ps) => `<b>${esc(ps[0].name)}</b> · ${sp.by_club[ps[0].dataIndex].goals} goals<br>` + ps.map((p) => `${p.marker} ${p.seriesName}: ${fmt(p.value, 1)}%`).join('<br>') }) }), {
    grid: { left: 8, right: 16, top: 36, bottom: 8, containLabel: true },
    yAxis: Object.assign(S.axisStyle(t, { splitLine: { show: false } }), { type: 'category', inverse: true, data: sp.by_club.map((c) => c.team), axisLabel: { color: t.ink2, fontSize: 12 } }),
    xAxis: Object.assign(S.axisStyle(t), { type: 'value', max: 100, axisLabel: { color: t.muted, fontSize: 11, formatter: '{value}%' } }),
    series: clubTypes.map((name, i) => ({ type: 'bar', stack: 'c', name, barMaxWidth: 16,
      data: sp.by_club.map((c) => pctOf(c, name, c.goals)),
      itemStyle: { color: typeColor(t, name), borderColor: t.surface, borderWidth: 1, borderRadius: i === clubTypes.length - 1 ? [0, 4, 4, 0] : 0 } })),
  }));
  S.tableView('c-setplay-club', ['Club', 'Goals', ...clubTypes, 'Set plays + penalties %'],
    sp.by_club.map((c) => [c.team, c.goals, ...clubTypes.map((n) => c.counts[n]), c.set_play_pct]));

  // ---- champions table
  const bySeason = {};
  d.teams.forEach((t) => { (bySeason[t.season] = bySeason[t.season] || []).push(t); });
  let doubles = 0;
  const champRows = Object.keys(bySeason).sort().map((s) => {
    const rows = bySeason[s];
    const leader = rows.find((r) => r.position === 1);
    const champ = rows.find((r) => r.won_final);
    if (champ && champ.team === leader.team) doubles += 1;
    const inProgress = s === seasons[seasons.length - 1].season;
    return `<tr><td>${esc(leader.label)}</td><td style="text-align:left">${esc(leader.team)}${inProgress ? ' <span class="legend-note">(in progress)</span>' : ''}</td>
      <td>${leader.points} pts from ${leader.played}</td>
      <td style="text-align:left">${champ ? `<span class="${champ.team === leader.team ? 'champ' : ''}">${esc(champ.team)}</span>` : '<span class="legend-note">No final</span>'}</td></tr>`;
  });
  document.getElementById('t-champions').innerHTML = '<thead><tr><th>Season</th><th style="text-align:left">Table leader</th><th>Record</th><th style="text-align:left">Champion</th></tr></thead><tbody>' + champRows.join('') + '</tbody>';
  document.getElementById('double-count').textContent = ({ 0: 'never', 1: 'once', 2: 'twice' })[doubles] || doubles + ' times';

  // ---- xG difference vs points
  const xgTeams = d.teams.filter((t) => t.xg != null && t.played >= 10);
  S.make('c-xgpts', (t) => Object.assign(S.base(t, { tooltip: {
    trigger: 'item', backgroundColor: t.surface, borderColor: t.axis, textStyle: { color: t.ink, fontSize: 12 }, confine: true,
    formatter: (p) => `<b>${esc(p.data.team)}</b> ${esc(p.data.label)}<br>${fmt(p.data.value[1], 2)} points per match<br>xG difference ${fmt(p.data.value[0], 2)} per match` } }), {
    grid: { left: 8, right: 24, top: 40, bottom: 30, containLabel: true },
    xAxis: Object.assign(S.axisStyle(t), { type: 'value', name: 'xG difference per match', nameLocation: 'middle', nameGap: 28 }),
    yAxis: Object.assign(S.axisStyle(t), { type: 'value', name: 'Points per match', nameLocation: 'end' }),
    series: [['Other clubs', false, 0], ['Champion', true, 1]].map(([name, won, i]) => ({
      type: 'scatter', name, symbolSize: 10,
      data: xgTeams.filter((x) => !!x.won_final === won).map((x) => ({ value: [x.xg_diff / x.played, x.points_per_match], team: x.team, label: x.label })),
      itemStyle: { color: t.series[i], borderColor: t.surface, borderWidth: 2 } })),
  }));
  S.tableView('c-xgpts', ['Season', 'Club', 'Points per match', 'xG for', 'xG against', 'Champion'],
    xgTeams.map((x) => [x.label, x.team, x.points_per_match, x.xg, x.xga, x.won_final ? 'Yes' : '']), (v, i) => (i === 2 ? fmt(v, 2) : fmt(v)));

  // ---- crowds
  const att = d.attendance;
  const attSeasons = att.by_season;
  const withAvg = attSeasons.filter((x) => x.average != null);
  const top = withAvg.reduce((a, b) => (b.average > a.average ? b : a));
  const lastFull = withAvg.filter((x) => x.season !== seasons[seasons.length - 1].season).slice(-1)[0];
  document.getElementById('att-peak').textContent = fmt(Math.round(top.average / 100) * 100);
  document.getElementById('att-peak-season').textContent = top.label;
  document.getElementById('att-latest').textContent = fmt(Math.round(lastFull.average / 100) * 100);
  document.getElementById('att-latest-season').textContent = lastFull.label;
  document.getElementById('att-top').textContent = fmt(att.biggest_crowds[0].attendance);
  S.make('c-att-season', (t) => Object.assign(S.base(t, { tooltip: Object.assign(S.base(t).tooltip, { axisPointer: { type: 'shadow' },
    formatter: (ps) => { const x = attSeasons[ps[0].dataIndex]; return `<b>${x.label}</b><br>` + (x.status === 'closed_doors' ? 'Behind closed doors' : x.average == null ? 'No data' : `${fmt(x.average)} average (${x.source})`); } }) }), {
    legend: { show: false },
    xAxis: Object.assign(S.axisStyle(t), { type: 'category', data: attSeasons.map((x) => (x.status === 'closed_doors' ? x.label + '\nno fans' : x.label)) }),
    yAxis: Object.assign(S.axisStyle(t), { type: 'value', min: 0 }),
    grid: { left: 8, right: 16, top: 30, bottom: 8, containLabel: true },
    series: [{ type: 'bar', name: 'Average crowd', barMaxWidth: 28,
      data: attSeasons.map((x) => ({ value: x.average, itemStyle: { color: x.source === 'Wikipedia' ? t.seq[1] : t.series[0] } })),
      itemStyle: { borderRadius: [4, 4, 0, 0] } }],
  }));
  S.tableView('c-att-season', ['Season', 'Average crowd', 'Source', 'Highest'], attSeasons.map((x) => [x.label,
    x.status === 'closed_doors' ? 'Closed doors' : x.average, x.source || '', x.highest || '']));

  const clubs = att.by_club;
  S.make('c-att-club', (t) => Object.assign(S.base(t, { legend: { show: false }, tooltip: Object.assign(S.base(t).tooltip, { axisPointer: { type: 'shadow' }, valueFormatter: (v) => fmt(v) }) }), {
    grid: { left: 8, right: 56, top: 8, bottom: 8, containLabel: true },
    yAxis: Object.assign(S.axisStyle(t, { splitLine: { show: false } }), { type: 'category', inverse: true, data: clubs.map((c) => c.team), axisLabel: { color: t.ink2, fontSize: 12 } }),
    xAxis: Object.assign(S.axisStyle(t), { type: 'value' }),
    series: [{ type: 'bar', name: 'Average home crowd', data: clubs.map((c) => c.average_all), barMaxWidth: 14,
      itemStyle: { color: t.series[0], borderRadius: [0, 4, 4, 0] },
      label: { show: true, position: 'right', color: t.ink2, fontSize: 11, formatter: (p) => fmt(p.value) } }],
  }));
  S.tableView('c-att-club', ['Club', 'Average home crowd', ...attSeasons.filter((x) => x.source === 'FotMob').map((x) => x.label)],
    clubs.map((c) => [c.team, c.average_all, ...attSeasons.filter((x) => x.source === 'FotMob').map((x) => (c.seasons.find((y) => y.season === x.season) || {}).average ?? '')]));

  const stads = att.by_stadium;
  S.make('c-att-stadium', (t) => Object.assign(S.base(t, { legend: { show: false }, tooltip: Object.assign(S.base(t).tooltip, { axisPointer: { type: 'shadow' },
    formatter: (ps) => { const x = stads[ps[0].dataIndex]; return `<b>${esc(x.stadium)}</b><br>Average ${fmt(Math.round(x.average))} over ${x.matches} matches<br>Highest ${fmt(x.highest)}<br>Main tenants: ${esc(x.clubs)}`; } }) }), {
    grid: { left: 8, right: 56, top: 8, bottom: 8, containLabel: true },
    xAxis: Object.assign(S.axisStyle(t), { type: 'value', splitNumber: 3 }),
    yAxis: Object.assign(S.axisStyle(t, { splitLine: { show: false } }), { type: 'category', inverse: true, data: stads.map((x) => x.stadium.replace('Jawaharlal Nehru Stadium', 'JN Stadium').replace(' (VYBK)', '')), axisLabel: { color: t.ink2, fontSize: 12, width: 220, overflow: 'truncate' } }),
    series: [{ type: 'bar', name: 'Average crowd', data: stads.map((x) => Math.round(x.average)), barMaxWidth: 14,
      itemStyle: { color: t.series[0], borderRadius: [0, 4, 4, 0] },
      label: { show: true, position: 'right', color: t.ink2, fontSize: 11, formatter: (p) => fmt(p.value) } }],
  }));
  S.tableView('c-att-stadium', ['Stadium', 'Matches', 'Average', 'Highest', 'Main tenants'], stads.map((x) => [x.stadium, x.matches, Math.round(x.average), x.highest, x.clubs]));

  const sel = document.getElementById('att-club-select');
  sel.innerHTML = clubs.map((c) => `<option>${esc(c.team)}</option>`).join('');
  let trend = null;
  const drawTrend = () => {
    const c = clubs.find((x) => x.team === sel.value);
    document.getElementById('att-club-title').textContent = `${c.team}: average home crowd by season`;
    const build = (t) => Object.assign(S.base(t, { legend: { show: false }, tooltip: Object.assign(S.base(t).tooltip, { axisPointer: { type: 'shadow' }, valueFormatter: (v) => fmt(v) }) }), {
      grid: { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
      xAxis: Object.assign(S.axisStyle(t), { type: 'category', data: c.seasons.map((x) => x.label) }),
      yAxis: Object.assign(S.axisStyle(t), { type: 'value', min: 0 }),
      series: [{ type: 'bar', name: 'Average home crowd', data: c.seasons.map((x) => x.average), barMaxWidth: 28, itemStyle: { color: t.series[0], borderRadius: [4, 4, 0, 0] } }],
    });
    if (!trend) trend = S.make('c-att-trend', build); else S.rebuild(trend, build);
  };
  sel.addEventListener('input', drawTrend);
  drawTrend();
  document.getElementById('t-crowds').innerHTML = '<thead><tr><th style="text-align:left">Match</th><th>Season</th><th>Crowd</th></tr></thead><tbody>' +
    att.biggest_crowds.map((x) => `<tr><td style="text-align:left">${esc(x.home)} v ${esc(x.away)}<br><span class="legend-note">${esc(x.stadium)}</span></td><td>${esc(x.season)}</td><td>${fmt(x.attendance)}</td></tr>`).join('') + '</tbody>';

  // ---- best XI
  const rows433 = [['Striker'], ['Attacking midfielder / winger', 'Attacking midfielder / winger'],
    ['Central midfielder', 'Central midfielder', 'Central midfielder'], ['Full-back', 'Centre-back', 'Centre-back', 'Full-back'], ['Goalkeeper']];
  function drawXI(key) {
    const pool = d.best_xi[key].slice();
    const take = (pos) => { const i = pool.findIndex((p) => p.position === pos); return i < 0 ? null : pool.splice(i, 1)[0]; };
    const pitch = document.getElementById('pitch');
    pitch.style.gridTemplateRows = 'repeat(5, 1fr)';
    pitch.innerHTML = rows433.map((line) => '<div class="line">' + line.map((pos) => {
      const p = take(pos);
      if (!p) return '<div class="slot"></div>';
      return `<div class="slot" title="${esc(pos)}"><div class="dot">${Math.round(p.score)}</div><div class="name">${esc(p.player)}</div>
        <div class="meta">${esc(shortTeams(p.teams))}<br>${fmt(p.minutes)} min</div></div>`;
    }).join('') + '</div>').join('');
  }
  drawXI('all_time');
  document.querySelectorAll('[data-xi]').forEach((b) => b.addEventListener('click', () => {
    document.querySelectorAll('[data-xi]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    drawXI(b.dataset.xi);
  }));

  // ---- positions
  const posNames = Object.keys(d.positions);
  const tabs = document.getElementById('pos-tabs');
  tabs.innerHTML = posNames.map((p, i) => `<button role="tab" aria-selected="${i === 0}" data-pos="${esc(p)}">${esc(p.replace(' / winger', ' / W'))}</button>`).join('');
  const pctClass = (v) => (v >= 80 ? 'hi' : v >= 40 ? 'mid' : 'lo');
  function drawPos(pos) {
    const metrics = d.meta.metrics[pos];
    const info = d.positions[pos];
    document.getElementById('pos-sub').textContent = `${info.qualified} qualified players with 2,000+ minutes since 2019–20. Percentiles: 100 = best at the position.`;
    const head = '<tr><th>#</th><th style="text-align:left">Player</th><th>Score</th>' + metrics.map((m) => `<th title="${esc(m.label)}">${esc(m.label.replace(/ \(.*\)$/, '').replace(' compared with an average keeper', '').replace(' per 90', '/90'))}</th>`).join('') + '<th>Minutes</th></tr>';
    const body = info.players.slice(0, 10).map((p, i) => `<tr><td>${i + 1}</td>
      <td style="text-align:left"><b>${esc(p.player)}</b><br><span class="legend-note">${esc(p.country || '')} · ${esc(shortTeams(p.teams))}</span></td>
      <td><div class="bar-cell"><b>${fmt(p.score, 0)}</b><span class="bar" style="width:${Math.round(p.score * 0.6)}px"></span></div></td>
      ${metrics.map((m) => { const v = p['pct_' + m.stat]; return `<td title="${esc(m.label)}: ${fmt(p[m.stat], 2)}"><span class="pct ${pctClass(v)}">${fmt(v, 0)}</span></td>`; }).join('')}
      <td>${fmt(p.minutes)}</td></tr>`).join('');
    document.getElementById('t-pos').innerHTML = `<thead>${head}</thead><tbody>${body}</tbody>`;
    document.getElementById('pos-weights').innerHTML = metrics.map((m) => `<li>${esc(m.label)}: weight ${m.weight}</li>`).join('');
  }
  drawPos(posNames[0]);
  tabs.addEventListener('click', (e) => {
    const b = e.target.closest('button'); if (!b) return;
    tabs.querySelectorAll('button').forEach((x) => x.setAttribute('aria-selected', String(x === b)));
    drawPos(b.dataset.pos);
  });

  // ---- leaderboards
  const hbar = (id, rows, series, opts = {}) => S.make(id, (t) => Object.assign(S.base(t, {
    legend: series.length > 1 ? S.base(t).legend : { show: false },
    tooltip: Object.assign(S.base(t).tooltip, { axisPointer: { type: 'shadow' } }) }), {
    grid: { left: 8, right: 40, top: series.length > 1 ? 36 : 8, bottom: 8, containLabel: true },
    yAxis: Object.assign(S.axisStyle(t, { splitLine: { show: false } }), { type: 'category', inverse: true, data: rows.map((r) => r.player), axisLabel: { color: t.ink2, fontSize: 12 } }),
    xAxis: Object.assign(S.axisStyle(t), { type: 'value', show: opts.showX !== false }),
    series: series.map((s, i) => ({ type: 'bar', name: s.name, stack: opts.stack ? 'x' : undefined, data: rows.map(s.value), barMaxWidth: 14,
      itemStyle: { color: s.color ? s.color(t) : t.series[i], borderColor: t.surface, borderWidth: opts.stack ? 1 : 0,
        borderRadius: opts.stack ? (i === series.length - 1 ? [0, 4, 4, 0] : 0) : opts.diverge ? 4 : [0, 4, 4, 0] },
      label: i === series.length - 1 && opts.total ? { show: true, position: 'right', color: t.ink2, fontSize: 11, formatter: (p) => opts.total(rows[p.dataIndex]) } : undefined })),
  }));

  const top15 = goals.slice(0, 15);
  hbar('c-scorers', top15, [
    { name: 'Open play and set pieces', value: (r) => r.goals - r.penalties },
    { name: 'Penalties', value: (r) => r.penalties },
  ], { stack: true, total: (r) => r.goals });
  S.tableView('c-scorers', ['Player', 'Goals', 'Penalties', 'Seasons', 'Clubs'], goals.map((r) => [r.player, r.goals, r.penalties, r.seasons, r.teams]));

  const fin = d.leaderboards.overperformers.slice(0, 8).concat(d.leaderboards.underperformers.slice(0, 7).reverse());
  hbar('c-finishing', fin, [{ name: 'Goals minus xG', value: (r) => r.goals_minus_xg,
    color: (t) => (p) => (p.value >= 0 ? t.series[0] : t.series[1]) }], { diverge: true });
  S.tableView('c-finishing', ['Player', 'Goals', 'xG', 'Goals minus xG'], fin.map((r) => [r.player, r.goals_in_xg_matches, r.xg, r.goals_minus_xg]));

  const fk = d.leaderboards.free_kick_goals.filter((r) => r.fk_goals >= 2);
  hbar('c-freekicks', fk, [{ name: 'Free-kick goals', value: (r) => r.fk_goals }], { total: (r) => `${r.fk_goals} from ${r.fk_shots} shots` });
  S.tableView('c-freekicks', ['Player', 'Free-kick goals', 'Free-kick shots', 'Free-kick xG'], d.leaderboards.free_kick_goals.map((r) => [r.player, r.fk_goals, r.fk_shots, r.fk_xg]));

  const gk = d.leaderboards.goals_prevented.slice(0, 10);
  hbar('c-keepers', gk, [{ name: 'Goals prevented', value: (r) => r.goals_prevented,
    color: (t) => (p) => (p.value >= 0 ? t.series[0] : t.series[1]) }], { diverge: true });
  S.tableView('c-keepers', ['Keeper', 'Goals prevented', 'Per 90', 'Save %', 'Minutes'], gk.map((r) => [r.player, r.goals_prevented, r.goals_prevented_p90, r.save_pct, r.minutes]), (v, i) => (i === 2 ? fmt(v, 2) : fmt(v)));
})();
