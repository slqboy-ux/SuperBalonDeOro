const apiUrl = "http://localhost:8000";

const brandTitle = document.getElementById("brandTitle");
const seasonNameEl = document.getElementById("seasonName");
const seasonInput = document.getElementById("seasonInput");
const taglineEl = document.getElementById("tagline");
const bulkPlayersInput = document.getElementById("bulkPlayersInput");
const playerNameInput = document.getElementById("playerName");
const playerList = document.getElementById("playerList");
const teamList = document.getElementById("teamList");
const teamSizeInput = document.getElementById("teamSize");
const standingsBody = document.getElementById("standingsBody");
const matchList = document.getElementById("matchList");
const homeTeamSelect = document.getElementById("homeTeamSelect");
const awayTeamSelect = document.getElementById("awayTeamSelect");
const totalPlayersEl = document.getElementById("totalPlayers");
const totalTeamsEl = document.getElementById("totalTeams");
const totalMatchesEl = document.getElementById("totalMatches");
const championNameEl = document.getElementById("championName");

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Hubo un error");
  }

  return response.json();
}

function renderPlayers(players) {
  if (!players.length) {
    playerList.innerHTML = "<li>No hay jugadores todavía.</li>";
    return;
  }

  playerList.innerHTML = players
    .map((player) => `<li>${player.name}</li>`)
    .join("");
}

function renderTeams(teams) {
  if (!teams.length) {
    teamList.innerHTML = "<p class='empty-state'>Aún no hay equipos armados.</p>";
    return;
  }

  teamList.innerHTML = teams
    .map(
      (team) => `
        <div class="team-card">
          <strong>${team.name}</strong>
          <div class="members">${team.players.map((p) => p.name).join(", ") || "Sin jugadores"}</div>
        </div>
      `
    )
    .join("");
}

function renderMatches(matches) {
  if (!matches.length) {
    matchList.innerHTML = "<li>No hay resultados cargados todavía.</li>";
    return;
  }

  matchList.innerHTML = matches
    .map(
      (match) => `
        <li>
          ${match.home_name} ${match.home_goals} - ${match.away_goals} ${match.away_name}
        </li>
      `
    )
    .join("");
}

function renderStandings(standings) {
  if (!standings.length) {
    standingsBody.innerHTML = "<tr><td colspan='10'>Sin resultados todavía</td></tr>";
    return;
  }

  standingsBody.innerHTML = standings
    .map(
      (player) => `
        <tr>
          <td>${player.position}</td>
          <td>${player.player_name}</td>
          <td>${player.played}</td>
          <td>${player.wins}</td>
          <td>${player.draws}</td>
          <td>${player.losses}</td>
          <td>${player.goals_for}</td>
          <td>${player.goals_against}</td>
          <td>${player.goal_difference}</td>
          <td>${player.points}</td>
        </tr>
      `
    )
    .join("");
}

function populateTeamSelects(teams) {
  const options = teams
    .map((team) => `<option value="${team.id}">${team.name}</option>`)
    .join("");

  homeTeamSelect.innerHTML = options;
  awayTeamSelect.innerHTML = options;

  if (teams.length > 1) {
    homeTeamSelect.value = String(teams[0].id);
    awayTeamSelect.value = String(teams[1].id);
  }
}

async function loadData() {
  try {
    const [config, players, teams, matches, standings, summary] = await Promise.all([
      fetchJson(`${apiUrl}/config`),
      fetchJson(`${apiUrl}/players`),
      fetchJson(`${apiUrl}/teams`),
      fetchJson(`${apiUrl}/matches`),
      fetchJson(`${apiUrl}/standings`),
      fetchJson(`${apiUrl}/summary`),
    ]);

    brandTitle.textContent = config.brand;
    seasonNameEl.textContent = config.season_name;
    seasonInput.value = config.season_name;
    taglineEl.textContent = config.tagline || "Armá equipos, jugá cada fecha y definí al campeón sin planilla.";
    totalPlayersEl.textContent = String(summary.total_players ?? players.length);
    totalTeamsEl.textContent = String(summary.total_teams ?? teams.length);
    totalMatchesEl.textContent = String(summary.total_matches ?? matches.length);
    championNameEl.textContent = summary.champion ? summary.champion.player_name : "Sin resultados";

    renderPlayers(players);
    renderTeams(teams);
    populateTeamSelects(teams);
    renderMatches(matches);
    renderStandings(standings);
  } catch (error) {
    console.error(error);
    playerList.innerHTML = "<li>No se pudo conectar con la API.</li>";
  }
}

async function addPlayer() {
  const name = playerNameInput.value.trim();
  if (!name) return;

  try {
    await fetchJson(`${apiUrl}/players`, {
      method: "POST",
      body: JSON.stringify({ name }),
    });
    playerNameInput.value = "";
    loadData();
  } catch (error) {
    alert(error.message);
  }
}

function parseBulkPlayers(rawText) {
  const lines = rawText
    .split(/\r?\n/)
    .flatMap((line) => line.split(/[;,]/))
    .map((entry) => entry.trim())
    .filter(Boolean)
    .filter((entry) => !/^(?:reenv|forward|fwd)/i.test(entry))
    .map((entry) => entry.replace(/^\s*(?:[-*•]|\d+[.)]|[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+[.)])\s*/i, ""))
    .map((entry) => entry.replace(/^\s*[-*•]\s*/, ""))
    .map((entry) => entry.trim())
    .filter(Boolean);

  return [...new Set(lines)];
}

async function bulkAddPlayers() {
  const rawText = (bulkPlayersInput.value || "").trim();
  if (!rawText) return;

  const names = parseBulkPlayers(rawText);
  if (!names.length) return;

  try {
    await Promise.all(
      names.map((name) =>
        fetchJson(`${apiUrl}/players`, {
          method: "POST",
          body: JSON.stringify({ name }),
        })
      )
    );

    bulkPlayersInput.value = "";
    loadData();
  } catch (error) {
    alert(error.message);
  }
}

async function copyPlayerList() {
  try {
    const players = await fetchJson(`${apiUrl}/players`);
    const text = players.map((player) => player.name).join("\n");
    await navigator.clipboard.writeText(text);
    alert("Lista de jugadores copiada para WhatsApp.");
  } catch (error) {
    alert("No se pudo copiar la lista.");
  }
}

async function generateTeams() {
  const teamSize = Number(teamSizeInput.value || 2);

  try {
    await fetchJson(`${apiUrl}/teams/generate`, {
      method: "POST",
      body: JSON.stringify({ team_size: teamSize }),
    });
    loadData();
  } catch (error) {
    alert(error.message);
  }
}

async function saveMatch() {
  const homeTeamId = Number(homeTeamSelect.value);
  const awayTeamId = Number(awayTeamSelect.value);
  const homeGoals = Number(document.getElementById("homeGoals").value || 0);
  const awayGoals = Number(document.getElementById("awayGoals").value || 0);

  if (homeTeamId === awayTeamId) {
    alert("Elegí dos equipos distintos.");
    return;
  }

  try {
    await fetchJson(`${apiUrl}/matches`, {
      method: "POST",
      body: JSON.stringify({
        home_team_id: homeTeamId,
        away_team_id: awayTeamId,
        home_goals: homeGoals,
        away_goals: awayGoals,
      }),
    });

    document.getElementById("homeGoals").value = 0;
    document.getElementById("awayGoals").value = 0;
    loadData();
  } catch (error) {
    alert(error.message);
  }
}

async function resetData() {
  const confirmed = window.confirm("Se borrarán jugadores, equipos y partidos. ¿Continuás?");
  if (!confirmed) return;

  try {
    await fetchJson(`${apiUrl}/players`, {
      method: "DELETE",
    });
    loadData();
  } catch (error) {
    alert(error.message);
  }
}

document.getElementById("addPlayerBtn").addEventListener("click", addPlayer);
document.getElementById("bulkAddPlayersBtn").addEventListener("click", bulkAddPlayers);
document.getElementById("copyPlayersBtn").addEventListener("click", copyPlayerList);
document.getElementById("generateTeamsBtn").addEventListener("click", generateTeams);
document.getElementById("saveMatchBtn").addEventListener("click", saveMatch);
document.getElementById("resetBtn").addEventListener("click", resetData);
document.getElementById("saveSeasonBtn").addEventListener("click", async () => {
  const newSeason = seasonInput.value.trim();
  if (!newSeason) return;

  try {
    await fetchJson(`${apiUrl}/config`, {
      method: "POST",
      body: JSON.stringify({ season_name: newSeason }),
    });
    loadData();
  } catch (error) {
    alert(error.message);
  }
});

playerNameInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") addPlayer();
});

loadData();
