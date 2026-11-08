const apiUrl = window.location.origin;

const brandTitle = document.getElementById("brandTitle");
const seasonNameEl = document.getElementById("seasonName");
const seasonInput = document.getElementById("seasonInput");
const groupSelect = document.getElementById("groupSelect");
const seasonSelect = document.getElementById("seasonSelect");
const newGroupBtn = document.getElementById("newGroupBtn");
const newSeasonBtn = document.getElementById("newSeasonBtn");
const groupGate = document.getElementById("groupGate");
const appShell = document.getElementById("appShell");
const groupGateList = document.getElementById("groupGateList");
const newGroupNameInput = document.getElementById("newGroupName");
const newGroupPasswordInput = document.getElementById("newGroupPassword");
const createGroupGateBtn = document.getElementById("createGroupGateBtn");
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
const shareTeamsBtn = document.getElementById("shareTeamsBtn");

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

function showAppShell(show) {
  appShell.classList.toggle("hidden", !show);
  groupGate.classList.toggle("hidden", show);
}

function renderGroupGate(groups) {
  if (!groups.length) {
    groupGateList.innerHTML = '<div class="group-gate-empty">Todavía no hay grupos.</div>';
    return;
  }

  groupGateList.innerHTML = groups
    .map(
      (group) => `
        <button class="group-gate-item" type="button" data-group-id="${group.id}">
          <span>${group.name}</span>
          <small>${group.has_password ? "Protegido con contraseña" : "Acceso libre"}</small>
        </button>
      `
    )
    .join("");

  groupGateList.querySelectorAll(".group-gate-item").forEach((button) => {
    button.addEventListener("click", async () => {
      const groupId = Number(button.dataset.groupId);
      const group = groups.find((item) => item.id === groupId);
      if (!group) return;

      if (group.has_password) {
        const password = window.prompt(`Ingresá la contraseña de "${group.name}"`);
        if (password === null) return;

        try {
          await fetchJson(`${apiUrl}/groups/login`, {
            method: "POST",
            body: JSON.stringify({ group_id: groupId, password }),
          });
        } catch (error) {
          alert(error.message);
          return;
        }
      } else {
        try {
          await fetchJson(`${apiUrl}/config`, {
            method: "POST",
            body: JSON.stringify({ current_group_id: groupId }),
          });
        } catch (error) {
          alert(error.message);
          return;
        }
      }

      showAppShell(true);
      loadData();
    });
  });
}

function renderGroups(groups, selectedGroupId) {
  if (!groups.length) {
    groupSelect.innerHTML = '<option value="">Sin grupos</option>';
    return;
  }

  groupSelect.innerHTML = groups
    .map((group) => `<option value="${group.id}">${group.name}</option>`)
    .join("");
  groupSelect.value = String(selectedGroupId ?? groups[0].id);
}

function renderSeasons(seasons, selectedSeasonId) {
  if (!seasons.length) {
    seasonSelect.innerHTML = '<option value="">Sin temporadas</option>';
    return;
  }

  seasonSelect.innerHTML = seasons
    .map((season) => `<option value="${season.id}">${season.name}</option>`)
    .join("");
  seasonSelect.value = String(selectedSeasonId ?? seasons[0].id);
}

async function loadData() {
  try {
    const [config, groups, seasons, players, teams, matches, standings, summary] = await Promise.all([
      fetchJson(`${apiUrl}/config`),
      fetchJson(`${apiUrl}/groups`),
      fetchJson(`${apiUrl}/seasons`),
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

    renderGroupGate(groups);
    renderGroups(groups, config.current_group_id);
    renderSeasons(seasons, config.current_season_id);
    renderPlayers(players);
    renderTeams(teams);
    populateTeamSelects(teams);
    renderMatches(matches);
    renderStandings(standings);
    shareTeamsBtn.disabled = teams.length === 0;
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

function buildTeamsShareText(teams) {
  const season = seasonNameEl.textContent || "Temporada";
  const lines = [
    `${season}`,
    "",
    "Equipos armados:",
    ...teams.map((team, index) => `${index + 1}. ${team.name}: ${team.players.map((player) => player.name).join(", ") || "Sin jugadores"}`),
    "",
    "Compartido desde SUPERBALON DE ORO",
  ];
  return lines.join("\n");
}

async function shareTeamsOnWhatsapp() {
  try {
    const teams = await fetchJson(`${apiUrl}/teams`);
    if (!teams.length) {
      alert("Primero armá los equipos para compartirlos.");
      return;
    }

    const text = encodeURIComponent(buildTeamsShareText(teams));
    window.open(`https://wa.me/?text=${text}`, "_blank");
  } catch (error) {
    alert("No se pudieron compartir los equipos.");
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

async function createGroup() {
  const name = window.prompt("Nombre del grupo", "Mi grupo");
  if (!name) return;

  const password = window.prompt("Contraseña del grupo (opcional)", "");
  if (password === null) return;

  try {
    const response = await fetchJson(`${apiUrl}/groups`, {
      method: "POST",
      body: JSON.stringify({ name, password }),
    });
    if (response.has_password) {
      const enteredPassword = window.prompt(`Ingresá la contraseña para entrar a "${response.name}"`);
      if (enteredPassword === null) return;
      await fetchJson(`${apiUrl}/groups/login`, {
        method: "POST",
        body: JSON.stringify({ group_id: response.id, password: enteredPassword }),
      });
    }
    showAppShell(true);
    loadData();
  } catch (error) {
    alert(error.message);
  }
}

async function createGroupFromGate() {
  const name = newGroupNameInput.value.trim();
  const password = newGroupPasswordInput.value.trim();
  if (!name) {
    alert("Poné un nombre para el grupo.");
    return;
  }

  try {
    const response = await fetchJson(`${apiUrl}/groups`, {
      method: "POST",
      body: JSON.stringify({ name, password }),
    });
    if (response.has_password) {
      await fetchJson(`${apiUrl}/groups/login`, {
        method: "POST",
        body: JSON.stringify({ group_id: response.id, password }),
      });
    }
    newGroupNameInput.value = "";
    newGroupPasswordInput.value = "";
    showAppShell(true);
    loadData();
  } catch (error) {
    alert(error.message);
  }
}

async function createSeason() {
  const selectedGroupId = Number(groupSelect.value);
  const name = window.prompt("Nombre de la temporada", "Primer Temporada");
  if (!name) return;

  try {
    await fetchJson(`${apiUrl}/seasons`, {
      method: "POST",
      body: JSON.stringify({
        group_id: selectedGroupId || undefined,
        name,
      }),
    });
    loadData();
  } catch (error) {
    alert(error.message);
  }
}

async function changeCurrentGroup() {
  const groupId = Number(groupSelect.value);
  if (!groupId) return;

  try {
    await fetchJson(`${apiUrl}/config`, {
      method: "POST",
      body: JSON.stringify({ current_group_id: groupId }),
    });
    loadData();
  } catch (error) {
    alert(error.message);
  }
}

async function changeCurrentSeason() {
  const seasonId = Number(seasonSelect.value);
  if (!seasonId) return;

  try {
    await fetchJson(`${apiUrl}/config`, {
      method: "POST",
      body: JSON.stringify({ current_season_id: seasonId }),
    });
    loadData();
  } catch (error) {
    alert(error.message);
  }
}

async function clearPlayersList() {
  const confirmed = window.confirm("Se van a borrar todos los jugadores, equipos y partidos de la temporada actual. ¿Continuás?");
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

async function resetData() {
  const confirmed = window.confirm("Se reiniciará la temporada completa. Se borrarán jugadores, equipos y partidos y no habrá forma de recuperar la información. ¿Continuás?");
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
document.getElementById("shareTeamsBtn").addEventListener("click", shareTeamsOnWhatsapp);
document.getElementById("saveMatchBtn").addEventListener("click", saveMatch);
document.getElementById("clearPlayersBtn").addEventListener("click", clearPlayersList);
document.getElementById("resetBtn").addEventListener("click", resetData);
groupSelect.addEventListener("change", changeCurrentGroup);
seasonSelect.addEventListener("change", changeCurrentSeason);
newGroupBtn.addEventListener("click", createGroup);
newSeasonBtn.addEventListener("click", createSeason);
createGroupGateBtn.addEventListener("click", createGroupFromGate);
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

(async function bootstrap() {
  try {
    const groups = await fetchJson(`${apiUrl}/groups`);
    renderGroupGate(groups);
    const config = await fetchJson(`${apiUrl}/config`);
    if (config.current_group_id) {
      showAppShell(true);
      await loadData();
      return;
    }
    showAppShell(false);
  } catch (error) {
    console.error(error);
    showAppShell(false);
  }
})();
