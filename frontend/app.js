const DEFAULT_PLAYER_NAMES = ["FrangGabriel", "레온하트 네리아"];
const FIELD_NAMES = ["TOP", "MIDDLE", "BOTTOM"];

const DEFAULT_SERVER =
  window.TIKATUKA_SERVER_URL ||
  (window.location.protocol === "file:" ? "http://161.33.14.219" : window.location.origin);

const state = {
  serverUrl: DEFAULT_SERVER.replace(/\/$/, ""),
  clientId: getClientId(),
  ws: null,
  snapshot: null,
  roomCode: null,
  leaving: false,
};

const fx = {
  seenEvents: new Set(),
  rollingIds: new Set(),
  popIds: new Set(),
  flickingIds: new Set(),
  shieldBlockIds: new Set(),
  discardIds: new Set(),
  flickFields: new Set(),
  shieldFields: new Set(),
  ghosts: [],
  startBanner: null,
  lockUntil: 0,
};

const els = {
  lobby: document.querySelector("#lobby"),
  gameShell: document.querySelector("#game-shell"),
  lobbyStatus: document.querySelector("#lobby-status"),
  nicknameInput: document.querySelector("#nickname-input"),
  createRoom: document.querySelector("#create-room-button"),
  joinForm: document.querySelector("#join-form"),
  roomCodeInput: document.querySelector("#room-code-input"),
  roomCode: document.querySelector("#room-code"),
  copyRoom: document.querySelector("#copy-room-button"),
  connectionStatus: document.querySelector("#connection-status"),
  leave: document.querySelector("#leave-button"),
  restart: document.querySelector("#restart-button"),
  resultBanner: document.querySelector("#result-banner"),
  resultWinnerText: document.querySelector("#result-winner-text"),
  startBanner: document.querySelector("#start-banner"),
  startBannerText: document.querySelector("#start-banner-text"),
  rolloffNames: [
    document.querySelector("#rolloff-name-0"),
    document.querySelector("#rolloff-name-1"),
  ],
  rolloffDice: [
    document.querySelector("#rolloff-die-0"),
    document.querySelector("#rolloff-die-1"),
  ],
  eventLog: document.querySelector("#event-log"),
  playerNames: [
    document.querySelector("#player-name-0"),
    document.querySelector("#player-name-1"),
  ],
  trayControls: [
    document.querySelector("#tray-controls-0"),
    document.querySelector("#tray-controls-1"),
  ],
};

function getClientId() {
  const key = "tikatuka.clientId";
  const existing = localStorage.getItem(key);
  if (existing) return existing;
  const created =
    crypto.randomUUID?.() ||
    `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  localStorage.setItem(key, created);
  return created;
}

function getNickname() {
  const nickname = els.nicknameInput.value.trim().replace(/\s+/g, " ");
  if (!nickname) {
    setStatus("사용할 닉네임을 입력해주세요.");
    els.nicknameInput.focus();
    return null;
  }
  const clipped = nickname.slice(0, 16);
  localStorage.setItem("tikatuka.nickname", clipped);
  els.nicknameInput.value = clipped;
  return clipped;
}

function playerName(index) {
  return state.snapshot?.room.players?.[index]?.name || DEFAULT_PLAYER_NAMES[index] || "플레이어";
}

function setRoomMode(inRoom) {
  document.body.classList.toggle("in-room", inRoom);
  els.lobby.hidden = inRoom;
  els.gameShell.hidden = !inRoom;
}

function clearFx() {
  fx.seenEvents.clear();
  fx.rollingIds.clear();
  fx.popIds.clear();
  fx.flickingIds.clear();
  fx.shieldBlockIds.clear();
  fx.discardIds.clear();
  fx.flickFields.clear();
  fx.shieldFields.clear();
  fx.ghosts = [];
  fx.startBanner = null;
  fx.lockUntil = 0;
}

function apiUrl(path) {
  return `${state.serverUrl}${path}`;
}

function wsUrl(path) {
  const base = state.serverUrl.replace(/^http:/, "ws:").replace(/^https:/, "wss:");
  return `${base}${path}`;
}

function setStatus(message) {
  els.lobbyStatus.textContent = message;
  els.connectionStatus.textContent = message;
}

async function createRoom() {
  if (!getNickname()) return;
  setStatus("방 만드는 중...");
  const response = await fetch(apiUrl("/api/rooms"), { method: "POST" });
  if (!response.ok) throw new Error(await response.text());
  const data = await response.json();
  await connectRoom(data.code, { skipCheck: true });
}

async function connectRoom(code, options = {}) {
  const nickname = getNickname();
  if (!nickname) return;
  const roomCode = String(code || "").replace(/\D/g, "").padStart(4, "0").slice(-4);
  if (!/^\d{4}$/.test(roomCode)) {
    setStatus("방 번호는 4자리 숫자여야 합니다.");
    return;
  }

  if (!options.skipCheck) {
    const exists = await checkRoomExists(roomCode);
    if (!exists) return;
  }

  if (state.ws) state.ws.close();
  clearFx();
  state.leaving = false;
  state.roomCode = roomCode;
  els.roomCode.textContent = roomCode;
  setRoomMode(true);
  setStatus(`${roomCode} 방에 연결 중...`);

  const socket = new WebSocket(
    wsUrl(
      `/ws/${roomCode}?client_id=${encodeURIComponent(state.clientId)}&nickname=${encodeURIComponent(
        nickname,
      )}`,
    ),
  );
  state.ws = socket;

  socket.addEventListener("open", () => {
    setStatus("서버에 연결됨");
  });

  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.type === "snapshot") {
      state.snapshot = message;
      render();
    } else if (message.type === "error") {
      setStatus(message.message);
    } else if (message.type === "room_closed") {
      returnToLobby(message.message || "방이 종료되었습니다.");
    }
  });

  socket.addEventListener("close", () => {
    if (state.leaving) {
      state.leaving = false;
      return;
    }
    setStatus("연결이 끊겼습니다. 새로고침하거나 다시 입장해주세요.");
  });

  socket.addEventListener("error", () => {
    setStatus("WebSocket 연결 오류");
  });
}

async function checkRoomExists(roomCode) {
  setStatus("방 확인 중...");
  try {
    const response = await fetch(apiUrl(`/api/rooms/${roomCode}`), { method: "GET" });
    if (response.status === 404) {
      setStatus("없는 방 번호입니다.");
      return false;
    }
    if (!response.ok) {
      setStatus("방 번호 확인에 실패했습니다.");
      return false;
    }
    return true;
  } catch {
    setStatus("서버와 연결할 수 없습니다.");
    return false;
  }
}

function returnToLobby(message) {
  state.leaving = true;
  if (state.ws) state.ws.close();
  state.ws = null;
  state.snapshot = null;
  state.roomCode = null;
  clearFx();
  setRoomMode(false);
  setStatus(message);
}

function sendAction(action, payload = {}) {
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
    setStatus("서버와 연결되어 있지 않습니다.");
    return;
  }
  if (!isMyTurn()) {
    setStatus("아직 내 차례가 아닙니다.");
    return;
  }
  if (isFxLocked()) {
    setStatus("주사위 연출 중입니다.");
    return;
  }
  state.ws.send(JSON.stringify({ type: "action", action, ...payload }));
}

function sendRestart() {
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) return;
  state.ws.send(JSON.stringify({ type: "restart" }));
}

function render() {
  const snapshot = state.snapshot;
  if (!snapshot) return;
  processFx(snapshot);
  const { room, game, you } = snapshot;
  els.roomCode.textContent = room.code;

  const meText =
    you.player === null || you.player === undefined
      ? "관전 중"
      : `${playerName(you.player)}로 플레이 중`;
  const waitText = room.started ? phaseText(game) : "상대 입장 대기 중";
  setStatus(`${meText} · ${waitText}`);

  for (let player = 0; player < 2; player += 1) {
    const card = document.querySelector(`#player-card-${player}`);
    const playerState = document.querySelector(`#player-state-${player}`);
    const roomPlayer = room.players[player];
    els.playerNames[player].textContent = roomPlayer.name;
    card.classList.toggle(
      "is-turn",
      room.started && game.currentPlayer === player && game.phase !== "game_over",
    );
    playerState.textContent = `${player === 0 ? "초록" : "빨강"} 진영 · ${
      roomPlayer.connected ? "접속 중" : roomPlayer.occupied ? "재접속 대기" : "빈자리"
    }`;
  }

  renderBoard(game);
  renderTrays(game, you);
  renderControls(room, game, you);
  renderResult(game, you);
  renderStartBanner(room);
  renderLog(snapshot.log || []);
}

function processFx(snapshot) {
  const events = [...(snapshot.log || [])].reverse();
  for (const event of events) {
    const key = eventKey(event);
    if (fx.seenEvents.has(key)) continue;
    fx.seenEvents.add(key);
    triggerFx(event, snapshot);
  }

  if (fx.seenEvents.size > 240) {
    fx.seenEvents = new Set([...fx.seenEvents].slice(-120));
  }
}

function eventKey(event) {
  return `${event.ts ?? ""}:${event.type}:${JSON.stringify(event)}`;
}

function triggerFx(event, snapshot) {
  if (event.type === "first_player_rolloff") {
    const duration = 2200;
    fx.startBanner = {
      rolls: event.rolls,
      winner: event.winner,
      until: Date.now() + duration,
    };
    lockFor(duration - 300);
    window.setTimeout(render, duration);
    return;
  }

  if (event.type === "die_rolled") {
    pulseSet(fx.rollingIds, [event.die?.id], 720);
    lockFor(520);
    return;
  }

  if (event.type === "hand_trick") {
    pulseSet(fx.popIds, [event.kept?.id], 360);
    pulseSet(fx.rollingIds, [event.rerolled?.id], 720);
    lockFor(520);
    return;
  }

  if (event.type === "die_selected") {
    pulseSet(
      fx.discardIds,
      (event.discarded || []).map((die) => die.id),
      420,
    );
    lockFor(280);
    return;
  }

  if (event.type === "hold") {
    pulseSet(
      fx.discardIds,
      (event.discarded || []).map((die) => die.id),
      420,
    );
    lockFor(280);
    return;
  }

  if (event.type === "normal_die_placed") {
    pulseSet(fx.popIds, [event.die?.id], 360);
    return;
  }

  if (event.type === "bonus_die_placed") {
    pulseSet(fx.popIds, [event.die?.id], 360);
    return;
  }

  if (event.type === "egg_flick") {
    const opponent = 1 - event.player;
    addGhost(event.placedDie, event.player, event.field, [
      "striking",
      event.player === 0 ? "strike-right" : "strike-left",
    ]);
    for (const die of event.opponentDiceRemoved || []) {
      addGhost(die, opponent, event.field, ["flicking"]);
    }
    pulseSet(
      fx.shieldBlockIds,
      (event.shieldedDiceBlocked || []).map((die) => die.id),
      760,
    );
    pulseSet(fx.rollingIds, [event.bonusDie?.id], 720);
    pulseFields(fx.flickFields, [`${event.player}:${event.field}`, `${opponent}:${event.field}`], 700);
    if ((event.shieldedDiceBlocked || []).length) {
      pulseFields(fx.shieldFields, [`${opponent}:${event.field}`], 760);
    }
    lockFor(820);
    return;
  }

  if (event.type === "shield_only_match") {
    const opponent = 1 - event.player;
    const ids = snapshot.game.boards[opponent][event.field]
      .filter((die) => die.value === event.value && die.shield)
      .map((die) => die.id);
    pulseSet(fx.shieldBlockIds, ids, 760);
    pulseFields(fx.shieldFields, [`${opponent}:${event.field}`], 760);
    lockFor(480);
  }
}

function pulseSet(set, ids, duration) {
  const validIds = ids.filter((id) => id !== undefined && id !== null);
  if (!validIds.length) return;
  for (const id of validIds) set.add(id);
  window.setTimeout(() => {
    for (const id of validIds) set.delete(id);
    render();
  }, duration);
}

function pulseFields(set, keys, duration) {
  for (const key of keys) set.add(key);
  window.setTimeout(() => {
    for (const key of keys) set.delete(key);
    render();
  }, duration);
}

function addGhost(die, player, field, extraClasses = ["flicking"]) {
  if (!die) return;
  const key = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  fx.ghosts.push({ key, die, player, field, extraClasses });
  window.setTimeout(() => {
    fx.ghosts = fx.ghosts.filter((ghost) => ghost.key !== key);
    render();
  }, 620);
}

function lockFor(duration) {
  const until = Date.now() + duration;
  fx.lockUntil = Math.max(fx.lockUntil, until);
  window.setTimeout(() => {
    if (!isFxLocked()) render();
  }, duration + 30);
}

function phaseText(game) {
  if (game.phase === "place_normal") return `${playerName(game.currentPlayer)} 배치 차례`;
  if (game.phase === "select_die") return `${playerName(game.currentPlayer)} 주사위 선택`;
  if (game.phase === "place_bonus") return `${playerName(game.currentPlayer)} 보너스 배치`;
  if (game.phase === "game_over") return "게임 종료";
  return "자동 굴림";
}

function renderBoard(game) {
  for (let field = 0; field < 3; field += 1) {
    const scores = [game.scores[0][field], game.scores[1][field]];
    const scoreEl = document.querySelector(`#score-${field}`);
    scoreEl.querySelector(".score-left").textContent = scores[0];
    scoreEl.querySelector(".score-right").textContent = scores[1];
    const arrow = scoreEl.querySelector(".arrow");
    arrow.classList.toggle("left", scores[0] > scores[1]);
    arrow.classList.toggle("right", scores[1] > scores[0]);
    arrow.textContent = scores[0] === scores[1] ? "–" : scores[0] > scores[1] ? "◀" : "▶";

    for (let player = 0; player < 2; player += 1) {
      const fieldEl = document.querySelector(
        `.field[data-player="${player}"][data-field="${field}"]`,
      );
      const logicalDice = game.boards[player][field];
      const visualDice = player === 0 ? [...logicalDice].reverse() : logicalDice;
      fieldEl.innerHTML = renderFieldDice(visualDice) + renderGhostDice(player, field);
      fieldEl.classList.toggle("legal", isFieldLegal(player, field));
      fieldEl.classList.toggle("flick-hit", fx.flickFields.has(`${player}:${field}`));
      fieldEl.classList.toggle("shield-hit", fx.shieldFields.has(`${player}:${field}`));
    }
  }
}

function renderTrays(game) {
  for (let player = 0; player < 2; player += 1) {
    const tray = document.querySelector(`#tray-${player}`);
    const dice = [];
    if (game.currentPlayer === player && game.phase !== "game_over") {
      if (game.phase === "select_die") dice.push(...game.rolledDice);
      if ((game.phase === "place_normal" || game.phase === "place_bonus") && game.heldDie) {
        dice.push(game.heldDie);
      }
    }
    tray.innerHTML = dice
      .map((die, index) =>
        renderDie(die, {
          clickable: isMyTurn() && game.phase === "select_die",
          selectIndex: index,
        }),
      )
      .join("");
  }
}

function renderControls(room, game, you) {
  for (let player = 0; player < 2; player += 1) {
    const isCurrent = room.started && you.player === player && game.currentPlayer === player;
    const canTrick =
      isCurrent &&
      game.phase === "place_normal" &&
      !game.handTrickUsed[player] &&
      !game.result &&
      !isFxLocked();
    const canHold =
      isCurrent &&
      ["place_normal", "select_die"].includes(game.phase) &&
      !game.result &&
      !isFxLocked();
    els.trayControls[player].innerHTML = `
      <button class="tray-action" data-action="trick" data-player="${player}" ${
        canTrick ? "" : "disabled"
      }>타짜의 손놀림</button>
      <button class="tray-action danger" data-action="hold" data-player="${player}" ${
        canHold ? "" : "disabled"
      }>홀드</button>
    `;
  }
}

function renderResult(game, you) {
  if (!game.result) {
    els.resultBanner.hidden = true;
    return;
  }
  els.resultWinnerText.textContent =
    game.result.winner === null ? "무승부!" : `${playerName(game.result.winner)} 승리!`;
  els.restart.disabled = you.player !== 0;
  els.resultBanner.hidden = false;
}

function renderStartBanner(room) {
  const banner = fx.startBanner;
  if (!banner || Date.now() > banner.until) {
    els.startBanner.hidden = true;
    return;
  }

  for (let player = 0; player < 2; player += 1) {
    els.rolloffNames[player].textContent = room.players[player]?.name || DEFAULT_PLAYER_NAMES[player];
    els.rolloffDice[player].innerHTML = renderDie(
      {
        id: `rolloff-${player}-${banner.rolls[player]}`,
        value: banner.rolls[player],
        shield: false,
        owner: player,
      },
      { extraClasses: ["rolling"] },
    );
  }
  els.startBannerText.textContent = `${playerName(banner.winner)} 선공!`;
  els.startBanner.hidden = false;
}

function renderLog(log) {
  els.eventLog.innerHTML = log
    .slice(0, 10)
    .map((event) => `<li>${escapeHtml(eventText(event))}</li>`)
    .join("");
}

function eventText(event) {
  if (event.type === "room_started") return "상대가 입장했습니다. 게임 시작!";
  if (event.type === "first_player_rolloff") {
    return `선공 결정 · ${playerName(0)} ${event.rolls[0]} : ${playerName(1)} ${event.rolls[1]} · ${playerName(event.winner)} 선공`;
  }
  if (event.type === "die_rolled") {
    return `${playerName(event.player)} 자동 굴림 · ${dieText(event.die)}${
      event.openingShield ? " · 개막 실드" : ""
    }`;
  }
  if (event.type === "hand_trick") {
    return `${playerName(event.player)} 타짜의 손놀림 · ${event.kept.value} 킵, ${event.rerolled.value} 획득`;
  }
  if (event.type === "die_selected") {
    return `${playerName(event.player)} ${event.selected.value} 선택`;
  }
  if (event.type === "normal_die_placed") {
    return `${playerName(event.player)} ${FIELD_NAMES[event.field]}에 ${event.die.value} 배치`;
  }
  if (event.type === "egg_flick") {
    return `알까기! ${playerName(event.player)} ${event.value} · 상대 ${event.opponentDiceRemoved.length}개 제거`;
  }
  if (event.type === "shield_only_match") {
    return `실드 방어 · ${event.value}은 제거되지 않았습니다`;
  }
  if (event.type === "bonus_die_placed") {
    return `${playerName(event.player)} 보너스 실드 ${event.die.value} → ${playerName(event.targetPlayer)} ${FIELD_NAMES[event.field]}`;
  }
  if (event.type === "hold") {
    return `${playerName(event.player)} 홀드`;
  }
  if (event.type === "turn_passed") {
    return `${playerName(event.player)} 턴 패스`;
  }
  if (event.type === "game_finished") {
    const winner = event.result.winner;
    return winner === null ? "게임 종료 · 무승부" : `게임 종료 · ${playerName(winner)} 승리`;
  }
  if (event.type === "game_reset") return "새 게임 시작";
  return event.type;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => {
    const map = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;",
    };
    return map[char];
  });
}

function isMyTurn() {
  const snapshot = state.snapshot;
  if (!snapshot?.room.started) return false;
  return snapshot.you.player === snapshot.game.currentPlayer && snapshot.game.phase !== "game_over";
}

function isFxLocked() {
  return Date.now() < fx.lockUntil;
}

function isFieldLegal(player, field) {
  const snapshot = state.snapshot;
  if (!snapshot || !isMyTurn()) return false;
  if (isFxLocked()) return false;
  const { game } = snapshot;
  if (game.phase === "place_normal") {
    return player === game.currentPlayer && game.boards[player][field].length < 3;
  }
  if (game.phase === "place_bonus") {
    return game.boards[player][field].length < 3;
  }
  return false;
}

function renderFieldDice(dice) {
  const parts = [];
  let index = 0;
  while (index < dice.length) {
    let end = index + 1;
    while (end < dice.length && dice[end].value === dice[index].value) end += 1;
    const group = dice.slice(index, end);
    if (group.length >= 2) {
      const type = group.length === 3 ? "triple" : "double";
      parts.push(`
        <span class="combo-group ${type}-group" aria-label="${type} combo">
          ${group.map((die) => renderDie(die)).join('<span class="combo-link" aria-hidden="true"></span>')}
        </span>
      `);
    } else {
      parts.push(renderDie(group[0]));
    }
    index = end;
  }
  return parts.join("");
}

function renderGhostDice(player, field) {
  return fx.ghosts
    .filter((ghost) => ghost.player === player && ghost.field === field)
    .map((ghost) => renderDie(ghost.die, { extraClasses: ghost.extraClasses }))
    .join("");
}

function renderDie(die, options = {}) {
  const owner = die.owner ?? 0;
  const classes = ["die", `player-${owner}`];
  if (options.extraClasses) classes.push(...options.extraClasses);
  if (die.shield) classes.push("shield");
  if (options.clickable) classes.push("clickable");
  if (fx.rollingIds.has(die.id)) classes.push("rolling");
  if (fx.popIds.has(die.id)) classes.push("pop");
  if (fx.flickingIds.has(die.id)) classes.push("flicking");
  if (fx.shieldBlockIds.has(die.id)) classes.push("shield-block");
  if (fx.discardIds.has(die.id)) classes.push("discard");
  const attrs = [
    `class="${classes.join(" ")}"`,
    `data-die-id="${die.id}"`,
    `aria-label="${dieText(die)} 주사위"`,
  ];
  if (options.clickable) attrs.push(`data-select-index="${options.selectIndex}"`);
  return `<button ${attrs.join(" ")}>${pipsMarkup(die.value)}</button>`;
}

function dieText(die) {
  return `${die.value}${die.shield ? " 실드" : ""}`;
}

function pipsMarkup(value) {
  const map = {
    1: ["c"],
    2: ["tl", "br"],
    3: ["tl", "c", "br"],
    4: ["tl", "tr", "bl", "br"],
    5: ["tl", "tr", "c", "bl", "br"],
    6: ["tl", "tr", "ml", "mr", "bl", "br"],
  };
  return `<span class="pips">${map[value]
    .map((position) => `<span class="pip ${position}"></span>`)
    .join("")}</span>`;
}

els.createRoom.addEventListener("click", () => {
  createRoom().catch((error) => setStatus(`방 생성 실패: ${error.message}`));
});

els.joinForm.addEventListener("submit", (event) => {
  event.preventDefault();
  connectRoom(els.roomCodeInput.value).catch((error) =>
    setStatus(`입장 실패: ${error.message}`),
  );
});

els.copyRoom.addEventListener("click", () => {
  navigator.clipboard?.writeText(state.roomCode || "");
  setStatus("방 번호를 복사했습니다.");
});

els.leave.addEventListener("click", () => {
  returnToLobby("로비로 돌아왔습니다.");
});

els.restart.addEventListener("click", sendRestart);

document.addEventListener("click", (event) => {
  const actionButton = event.target.closest("[data-action]");
  if (actionButton) {
    const action = actionButton.dataset.action;
    if (action === "trick") sendAction("use_hand_trick");
    if (action === "hold") sendAction("hold");
    return;
  }

  const selectableDie = event.target.closest("[data-select-index]");
  if (selectableDie) {
    sendAction("select_die", { index: Number(selectableDie.dataset.selectIndex) });
    return;
  }

  const field = event.target.closest(".field[data-player][data-field]");
  if (field) {
    const player = Number(field.dataset.player);
    const fieldIndex = Number(field.dataset.field);
    if (!isFieldLegal(player, fieldIndex)) return;
    const phase = state.snapshot.game.phase;
    if (phase === "place_normal") sendAction("place_normal", { field: fieldIndex });
    if (phase === "place_bonus") {
      sendAction("place_bonus", { targetPlayer: player, field: fieldIndex });
    }
  }
});

els.nicknameInput.value = localStorage.getItem("tikatuka.nickname") || "";
setRoomMode(false);
setStatus("");
