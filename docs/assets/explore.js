// Explorer page: player table, player comparison, league tables and season awards.
(async function () {
  const S = window.SITE;
  S.initThemeToggle();
  const d = await S.load(['players', 'teams', 'best_xi', 'meta']);
  const fmt = S.fmtNum;
  const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const label = (s) => (s.includes('-') ? s.slice(0, 4) + '–' + s.slice(-2) : s);
  const opts = (vals, sel) => vals.map(([v, l]) => `<option value="${esc(v)}"${v === sel ? ' selected' : ''}>${esc(l)}</option>`).join('');
  const SHORT = { Goalkeeper: 'GK', 'Centre-back': 'CB', 'Full-back': 'FB', 'Central midfielder': 'CM', 'Attacking midfielder / winger': 'AM/W', Striker: 'ST' };
  const POS = ['Goalkeeper', 'Centre-back', 'Full-back', 'Central midfielder', 'Attacking midfielder / winger', 'Striker'];

  // ---- tabs
  document.querySelectorAll('.tabs button').forEach((b) => b.addEventListener('click', () => {
    document.querySelectorAll('.tabs button').forEach((x) => x.setAttribute('aria-selected', String(x === b)));
    document.querySelectorAll('.panel').forEach((p) => { p.hidden = p.id !== 'panel-' + b.dataset.tab; });
    window.dispatchEvent(new Event('resize'));
  }));

  // ---- players table
  const seasons = [...new Set(d.players.map((p) => p.season))].sort();
  document.getElementById('p-season').innerHTML = opts([['all', 'All seasons'], ...seasons.slice().reverse().map((s) => [s, label(s)])], seasons[seasons.length - 2]);
  document.getElementById('p-pos').innerHTML = opts([['all', 'All positions'], ...POS.map((p) => [p, p])], 'all');
  const COLS = [
    ['player', 'Player'], ['season', 'Season'], ['team', 'Club'], ['position_group', 'Position'], ['minutes', 'Min'],
    ['score', 'Score'], ['goals', 'Goals'], ['assists', 'Assists'], ['np_goals_p90', 'NP goals'], ['npxg_p90', 'NP xG'],
    ['xa_p90', 'xA'], ['conversion_pct', 'Conv %'], ['chances_created_p90', 'Chances'], ['dribbles_p90', 'Dribbles'],
    ['passes_p90', 'Passes'], ['pass_pct', 'Pass %'], ['tackles_p90', 'Tackles'], ['interceptions_p90', 'Int'],
    ['clearances_p90', 'Clear'], ['aerial_pct', 'Aerial %'], ['save_pct', 'Save %'], ['fk_goals', 'FK goals'],
  ];
  let sortKey = 'score', sortDir = -1;
  function drawPlayers() {
    const season = document.getElementById('p-season').value;
    const pos = document.getElementById('p-pos').value;
    const min = +document.getElementById('p-min').value;
    const nat = document.getElementById('p-nat').value;
    const q = document.getElementById('p-search').value.trim().toLowerCase();
    let rows = d.players.filter((p) => (season === 'all' || p.season === season) && (pos === 'all' || p.position_group === pos)
      && p.minutes >= min && (nat === 'all' || (nat === 'ind') === !!p.is_indian)
      && (!q || (p.player + ' ' + p.team).toLowerCase().includes(q)));
    rows.sort((a, b) => {
      const x = a[sortKey], y = b[sortKey];
      if (x == null) return 1; if (y == null) return -1;
      return (typeof x === 'string' ? x.localeCompare(y) : x - y) * sortDir;
    });
    document.getElementById('p-count').textContent = `${rows.length.toLocaleString()} player seasons`;
    const head = '<tr>' + COLS.map(([k, l]) => `<th data-sort="${k}">${l}${k === sortKey ? (sortDir < 0 ? ' ↓' : ' ↑') : ''}</th>`).join('') + '</tr>';
    const body = rows.slice(0, 300).map((p) => '<tr>' + COLS.map(([k]) => {
      const v = p[k];
      if (k === 'season') return `<td>${label(v)}</td>`;
      if (k === 'player') return `<td><b>${esc(v)}</b></td>`;
      if (k === 'position_group') return `<td>${esc(SHORT[v] || '–')}</td>`;
      if (typeof v === 'number') return `<td>${fmt(v, k.endsWith('_pct') || k === 'score' ? 0 : 2)}</td>`;
      return `<td>${esc(v ?? '–')}</td>`;
    }).join('') + '</tr>').join('');
    document.getElementById('t-players').innerHTML = `<thead>${head}</thead><tbody>${body}</tbody>`;
  }
  document.getElementById('t-players').addEventListener('click', (e) => {
    const th = e.target.closest('th[data-sort]'); if (!th) return;
    const k = th.dataset.sort;
    sortDir = k === sortKey ? -sortDir : (['player', 'team', 'season', 'position_group'].includes(k) ? 1 : -1);
    sortKey = k; drawPlayers();
  });
  ['p-season', 'p-pos', 'p-min', 'p-nat', 'p-search'].forEach((id) => document.getElementById(id).addEventListener('input', drawPlayers));
  drawPlayers();

  // ---- compare (career totals since 2019-20, weighted by minutes)
  const SUM = ['minutes', 'goals', 'assists', 'xg', 'xa'];
  const RATE = ['np_goals_p90', 'npxg_p90', 'xa_p90', 'shots_p90', 'chances_created_p90', 'dribbles_p90', 'passes_p90', 'pass_pct',
    'tackles_p90', 'interceptions_p90', 'clearances_p90', 'blocks_p90', 'recoveries_p90', 'aerial_pct', 'conversion_pct', 'save_pct', 'saves_p90'];
  const careers = {};
  d.players.forEach((p) => {
    const c = careers[p.player_id] || (careers[p.player_id] = { player: p.player, position_group: p.position_group, teams: new Set(), _w: {} });
    c.teams.add(p.team);
    SUM.forEach((k) => { c[k] = (c[k] || 0) + (p[k] || 0); });
    RATE.forEach((k) => { if (p[k] != null) { c._w[k] = (c._w[k] || 0) + p.minutes; c[k] = (c[k] || 0) + p[k] * p.minutes; } });
  });
  Object.values(careers).forEach((c) => RATE.forEach((k) => { c[k] = c._w[k] ? c[k] / c._w[k] : null; }));
  const names = Object.values(careers).filter((c) => c.minutes >= 900).sort((a, b) => b.minutes - a.minutes);
  document.getElementById('player-list').innerHTML = names.map((c) => `<option value="${esc(c.player)}">`).join('');
  const STATS = {
    Goalkeeper: [['save_pct', 'Save %'], ['saves_p90', 'Saves'], ['passes_p90', 'Passes'], ['pass_pct', 'Pass %'], ['recoveries_p90', 'Recoveries']],
    default: [['np_goals_p90', 'NP goals'], ['npxg_p90', 'NP xG'], ['xa_p90', 'xA'], ['shots_p90', 'Shots'], ['conversion_pct', 'Conversion %'],
      ['chances_created_p90', 'Chances created'], ['dribbles_p90', 'Dribbles'], ['passes_p90', 'Passes'], ['pass_pct', 'Pass %'],
      ['tackles_p90', 'Tackles'], ['interceptions_p90', 'Interceptions'], ['clearances_p90', 'Clearances'], ['aerial_pct', 'Aerial %']],
  };
  function pctile(pool, key, v) {
    const vals = pool.map((c) => c[key]).filter((x) => x != null);
    if (v == null || !vals.length) return null;
    return Math.round(100 * vals.filter((x) => x <= v).length / vals.length);
  }
  const find = (name) => names.find((c) => c.player.toLowerCase() === name.trim().toLowerCase());
  document.getElementById('c-a').value = 'Sunil Chhetri';
  document.getElementById('c-b').value = 'Roy Krishna';
  let chart = null;
  function drawCompare() {
    const a = find(document.getElementById('c-a').value), b = find(document.getElementById('c-b').value);
    if (!a) return;
    const pool = names.filter((c) => c.position_group === a.position_group && c.minutes >= 1800);
    const stats = STATS[a.position_group] || STATS.default;
    const players = [a, b].filter(Boolean);
    document.getElementById('c-title').textContent = players.map((p) => `${p.player} (${fmt(p.minutes)} min)`).join(' vs ');
    const build = (t) => Object.assign(S.base(t, { tooltip: Object.assign(S.base(t).tooltip, { axisPointer: { type: 'shadow' },
      formatter: (ps) => `<b>${ps[0].name}</b><br>` + ps.map((p) => `${p.marker} ${esc(p.seriesName)}: ${fmt(players[p.seriesIndex][stats[p.dataIndex][0]], 2)} (${p.value}th pct)`).join('<br>') }) }), {
      grid: { left: 8, right: 24, top: 36, bottom: 8, containLabel: true },
      yAxis: Object.assign(S.axisStyle(t, { splitLine: { show: false } }), { type: 'category', inverse: true, data: stats.map((s) => s[1]), axisLabel: { color: t.ink2, fontSize: 12 } }),
      xAxis: Object.assign(S.axisStyle(t), { type: 'value', min: 0, max: 100 }),
      series: players.map((p, i) => ({ type: 'bar', name: p.player, barMaxWidth: 10, barGap: '30%',
        data: stats.map(([k]) => pctile(pool, k, p[k])), itemStyle: { color: t.series[i], borderRadius: [0, 4, 4, 0] } })),
    });
    if (!chart) chart = S.make('c-compare', build); else S.rebuild(chart, build);
  }
  ['c-a', 'c-b'].forEach((id) => document.getElementById(id).addEventListener('change', drawCompare));
  drawCompare();

  // ---- tables
  const tSeasons = [...new Set(d.teams.map((t) => t.season))].sort();
  document.getElementById('t-season').innerHTML = opts(tSeasons.slice().reverse().map((s) => [s, label(s)]), tSeasons[tSeasons.length - 2]);
  function drawTable() {
    const s = document.getElementById('t-season').value;
    const rows = d.teams.filter((t) => t.season === s).sort((a, b) => a.position - b.position);
    const cols = [['position', '#'], ['team', 'Club'], ['played', 'P'], ['wins', 'W'], ['draws', 'D'], ['goals_for', 'GF'], ['goals_against', 'GA'],
      ['goal_diff', 'GD'], ['points', 'Pts'], ['xg', 'xG'], ['xga', 'xGA'], ['possession', 'Poss %'], ['shots_per_match', 'Shots'], ['passes_per_match', 'Passes']];
    document.getElementById('t-table').innerHTML = '<thead><tr>' + cols.map(([, l]) => `<th>${l}</th>`).join('') + '</tr></thead><tbody>' +
      rows.map((r) => '<tr>' + cols.map(([k]) => {
        if (k === 'team') return `<td style="text-align:left"><b>${esc(r.team)}</b>${r.won_final ? ' <span class="champ">Champion</span>' : ''}</td>`;
        return `<td>${fmt(r[k], k === 'xg' || k === 'xga' ? 1 : 0)}</td>`;
      }).join('') + '</tr>').join('') + '</tbody>';
  }
  document.getElementById('t-season').addEventListener('input', drawTable);
  drawTable();

  const clubs = [...new Set(d.teams.map((t) => t.team))].sort();
  document.getElementById('t-team').innerHTML = opts(clubs.map((c) => [c, c]), 'Mohun Bagan SG');
  let ptsChart = null, xgChart = null;
  function drawTeam() {
    const club = document.getElementById('t-team').value;
    const rows = d.teams.filter((t) => t.team === club).sort((a, b) => a.season.localeCompare(b.season));
    const league = tSeasons.map((s) => { const r = d.teams.filter((t) => t.season === s); return r.reduce((a, x) => a + x.points, 0) / r.reduce((a, x) => a + x.played, 0); });
    const ptsBuild = (t) => Object.assign(S.base(t), {
      xAxis: Object.assign(S.axisStyle(t), { type: 'category', data: tSeasons.map(label) }),
      yAxis: Object.assign(S.axisStyle(t), { type: 'value', min: 0 }),
      tooltip: Object.assign(S.base(t).tooltip, { valueFormatter: (v) => fmt(v, 2) }),
      series: [
        { type: 'line', name: club, data: tSeasons.map((s) => { const r = rows.find((x) => x.season === s); return r ? r.points_per_match : null; }),
          symbolSize: 8, lineStyle: { width: 2, color: t.series[0] }, itemStyle: { color: t.series[0] } },
        { type: 'line', name: 'League average', data: league, symbol: 'none', lineStyle: { width: 2, type: 'dashed', color: t.muted }, itemStyle: { color: t.muted } },
      ],
    });
    const xr = rows.filter((r) => r.xg != null);
    const xgBuild = (t) => Object.assign(S.base(t), {
      xAxis: Object.assign(S.axisStyle(t), { type: 'category', data: xr.map((r) => r.label) }),
      yAxis: Object.assign(S.axisStyle(t), { type: 'value', min: 0 }),
      tooltip: Object.assign(S.base(t).tooltip, { valueFormatter: (v) => fmt(v, 2) }),
      series: [['xG for', 'xg', 0], ['xG against', 'xga', 1]].map(([n, k, i]) => ({ type: 'line', name: n, data: xr.map((r) => r[k] / r.played),
        symbolSize: 8, lineStyle: { width: 2, color: t.series[i] }, itemStyle: { color: t.series[i] } })),
    });
    if (!ptsChart) { ptsChart = S.make('c-team-pts', ptsBuild); xgChart = S.make('c-team-xg', xgBuild); }
    else { S.rebuild(ptsChart, ptsBuild); S.rebuild(xgChart, xgBuild); }
  }
  document.getElementById('t-team').addEventListener('input', drawTeam);
  drawTeam();

  // ---- best by season
  const bs = d.best_xi.by_season;
  const sSeasons = [...new Set(bs.map((x) => x.season))].sort();
  document.getElementById('s-season').innerHTML = opts(sSeasons.slice().reverse().map((s) => [s, label(s)]), sSeasons[sSeasons.length - 2]);
  function drawSeason() {
    const s = document.getElementById('s-season').value;
    document.getElementById('s-grid').innerHTML = bs.filter((x) => x.season === s).map((x) => `<div class="card"><h3>${esc(x.position)}</h3>
      <table class="data"><tbody>${x.top.map((p, i) => `<tr><td>${i + 1}. <b>${esc(p.player)}</b> <span class="legend-note">${esc(p.team)}</span></td><td>${fmt(p.score, 0)}</td></tr>`).join('') || '<tr><td class="legend-note">No qualified players</td></tr>'}</tbody></table></div>`).join('');
  }
  document.getElementById('s-season').addEventListener('input', drawSeason);
  drawSeason();
})();
