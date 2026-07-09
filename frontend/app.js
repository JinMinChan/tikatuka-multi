const DEFAULT_PLAYER_NAMES = ["FrangGabriel", "레온하트 네리아"];
const SOUND_FILES = {
  roll: "./sound_samples/roll.m4a",
  place: "./sound_samples/place.m4a",
  egg: "./sound_samples/egg.m4a",
};

const IS_MOBILE_DEMO = new URLSearchParams(window.location.search).get("demo") === "mobile";
const MOBILE_STAGE_WIDTH = 390;
const MOBILE_STAGE_HEIGHT = 844;
const EMOTICONS = [
  { id: "gogo", label: "가자" },
  { id: "lol", label: "웃음" },
  { id: "sad", label: "슬픔" },
  { id: "stop", label: "멈춰" },
  { id: "what", label: "뭐야" },
  { id: "whatwhat", label: "뭐뭐" },
];

const IS_LOCAL_STATIC_SERVER =
  ["localhost", "127.0.0.1"].includes(window.location.hostname) &&
  ["5173", "5174"].includes(window.location.port);
const DEFAULT_SERVER =
  window.TIKATUKA_SERVER_URL ||
  (window.location.protocol === "file:"
    ? "http://tikatuka.duckdns.org"
    : IS_LOCAL_STATIC_SERVER
      ? "http://127.0.0.1:8000"
      : window.location.origin);

const state = {
  serverUrl: DEFAULT_SERVER.replace(/\/$/, ""),
  clientId: getClientId(),
  ws: null,
  snapshot: null,
  snapshotReceivedAt: 0,
  connectedAt: 0,
  awaitingFirstSnapshot: false,
  status: null,
  roomCode: null,
  leaving: false,
  leaveReserved: false,
  leaveAutoTimer: null,
  statusRefreshInFlight: false,
  actionPending: false,
  lastTimeoutCheckAt: 0,
  emoticonPickerPlayer: null,
  waitingEmoticonPickerOpen: false,
  streamerQueueOpen: false,
};

const soundState = {
  enabled: localStorage.getItem("tikatuka.soundEnabled") !== "false",
  volume: Math.min(1, Math.max(0, Number(localStorage.getItem("tikatuka.soundVolume") || 0.72))),
  unlocked: false,
  pools: {},
};

const fx = {
  seenEvents: new Set(),
  dieRects: new Map(),
  trayDieRects: new Map(),
  rollingIds: new Set(),
  popIds: new Set(),
  flickingIds: new Set(),
  shieldBlockIds: new Set(),
  discardIds: new Set(),
  flickFields: new Set(),
  shieldFields: new Set(),
  ghosts: [],
  startBanner: null,
  rollDelayUntil: 0,
  animatingUntil: 0,
  lockUntil: 0,
  renderTimer: null,
};

const els = {
  lobby: document.querySelector("#lobby"),
  gameShell: document.querySelector("#game-shell"),
  lobbyStatus: document.querySelector("#lobby-status"),
  onlineUsers: document.querySelector("#online-users"),
  myRating: document.querySelector("#my-rating"),
  leaderboard: document.querySelector("#leaderboard"),
  nicknameInput: document.querySelector("#nickname-input"),
  randomMatch: document.querySelector("#random-match-button"),
  createRoom: document.querySelector("#create-room-button"),
  createStreamerRoom: document.querySelector("#create-streamer-room-button"),
  streamerQueueLimit: document.querySelector("#streamer-queue-limit"),
  joinForm: document.querySelector("#join-form"),
  roomCodeInput: document.querySelector("#room-code-input"),
  roomCode: document.querySelector("#room-code"),
  copyRoom: document.querySelector("#copy-room-button"),
  connectionStatus: document.querySelector("#connection-status"),
  friendlyRecord: document.querySelector("#friendly-record"),
  friendlyRecordScore: document.querySelector("#friendly-record-score"),
  leave: document.querySelector("#leave-button"),
  restart: document.querySelector("#restart-button"),
  kickOpponent: document.querySelector("#kick-opponent-button"),
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
  turnClockValues: [
    document.querySelector("#turn-clock-0"),
    document.querySelector("#turn-clock-1"),
  ],
  totalClockValues: [
    document.querySelector("#total-clock-0"),
    document.querySelector("#total-clock-1"),
  ],
  turnClockPanels: [
    document.querySelector("#turn-clock-panel-0"),
    document.querySelector("#turn-clock-panel-1"),
  ],
  totalClockPanels: [
    document.querySelector("#total-clock-panel-0"),
    document.querySelector("#total-clock-panel-1"),
  ],
  playerNames: [
    document.querySelector("#player-name-0"),
    document.querySelector("#player-name-1"),
  ],
  soundToggle: document.querySelector("#sound-toggle"),
  soundVolume: document.querySelector("#sound-volume"),
  trayControls: [
    document.querySelector("#tray-controls-0"),
    document.querySelector("#tray-controls-1"),
  ],
  streamerQueuePanel: document.querySelector("#streamer-queue-panel"),
  streamerQueueCount: document.querySelector("#streamer-queue-count"),
  streamerQueueList: document.querySelector("#streamer-queue-list"),
  streamerQueueToggle: document.querySelector("#streamer-queue-toggle"),
  streamerQueueToggleCount: document.querySelector("#streamer-queue-toggle-count"),
  waitingEmoticonControl: document.querySelector("#waiting-emoticon-control"),
  waitingEmoticonStage: document.querySelector("#waiting-emoticon-stage"),
  mobile: {
    roomCode: document.querySelector("#mobile-room-code"),
    friendlyRecord: document.querySelector("#mobile-friendly-record"),
    friendlyRecordScore: document.querySelector("#mobile-friendly-record-score"),
    opponentCard: document.querySelector("#mobile-opponent-card"),
    myCard: document.querySelector("#mobile-my-card"),
    opponentAvatar: document.querySelector("#mobile-opponent-avatar"),
    myAvatar: document.querySelector("#mobile-my-avatar"),
    opponentName: document.querySelector("#mobile-opponent-name"),
    myName: document.querySelector("#mobile-my-name"),
    opponentState: document.querySelector("#mobile-opponent-state"),
    myState: document.querySelector("#mobile-my-state"),
    opponentBoard: document.querySelector("#mobile-opponent-board"),
    scoreGrid: document.querySelector("#mobile-score-grid"),
    myBoard: document.querySelector("#mobile-my-board"),
    tray: document.querySelector("#mobile-tray"),
    actionRow: document.querySelector("#mobile-action-row"),
    myTurnClock: document.querySelector("#mobile-my-turn-clock"),
    myTotalClock: document.querySelector("#mobile-my-total-clock"),
    opponentTurnClock: document.querySelector("#mobile-opponent-turn-clock"),
    opponentTotalClock: document.querySelector("#mobile-opponent-total-clock"),
    myTurnClockPanel: document.querySelector("#mobile-my-turn-clock-panel"),
    myTotalClockPanel: document.querySelector("#mobile-my-total-clock-panel"),
    opponentTurnClockPanel: document.querySelector("#mobile-opponent-turn-clock-panel"),
    opponentTotalClockPanel: document.querySelector("#mobile-opponent-total-clock-panel"),
    leave: document.querySelector("#mobile-leave-button"),
    resultBanner: document.querySelector("#mobile-result-banner"),
    resultWinnerText: document.querySelector("#mobile-result-winner-text"),
    restart: document.querySelector("#mobile-restart-button"),
    kickOpponent: document.querySelector("#mobile-kick-opponent-button"),
    resultLeave: document.querySelector("#mobile-result-leave-button"),
    waitingEmoticonStage: document.querySelector("#mobile-waiting-emoticon-stage"),
  },
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
  if (!inRoom) {
    document.body.classList.remove("streamer-room");
    state.streamerQueueOpen = false;
  }
  els.lobby.hidden = inRoom;
  els.gameShell.hidden = !inRoom;
  updateMobileStageScale();
}

function updateMobileStageScale() {
  const viewport = window.visualViewport;
  const widthCandidates = [
    viewport?.width,
    window.innerWidth,
    document.documentElement.clientWidth,
    window.outerWidth,
  ].filter((value) => Number.isFinite(value) && value > 0);
  const heightCandidates = [
    viewport?.height,
    window.innerHeight,
    document.documentElement.clientHeight,
    window.outerHeight,
  ].filter((value) => Number.isFinite(value) && value > 0);
  const width = Math.min(...widthCandidates);
  const height = Math.min(...heightCandidates);
  const offsetLeft = viewport?.offsetLeft || 0;
  const offsetTop = viewport?.offsetTop || 0;
  const scale = Math.min(width / MOBILE_STAGE_WIDTH, height / MOBILE_STAGE_HEIGHT);
  const measuredClientWidth =
    document.documentElement.clientWidth ||
    document.body?.clientWidth ||
    window.innerWidth ||
    width;
  const layoutWidth = Math.min(width, measuredClientWidth);
  const maxStageWidth =
    layoutWidth <= MOBILE_STAGE_WIDTH + 4 ? MOBILE_STAGE_WIDTH : Math.min(430, width / scale);
  const stageWidth = Math.min(Math.max(MOBILE_STAGE_WIDTH, width / scale), maxStageWidth);
  const centerX = offsetLeft + width / 2;
  document.documentElement.style.setProperty("--mobile-stage-scale", String(scale));
  document.documentElement.style.setProperty("--mobile-stage-width", `${stageWidth}px`);
  document.documentElement.style.setProperty("--mobile-viewport-width", `${width}px`);
  document.documentElement.style.setProperty("--mobile-viewport-height", `${height}px`);
  document.documentElement.style.setProperty("--mobile-viewport-left", `${offsetLeft}px`);
  document.documentElement.style.setProperty("--mobile-viewport-top", `${offsetTop}px`);
  document.documentElement.style.setProperty("--mobile-viewport-center-x", `${centerX}px`);
}

function setupSound() {
  soundState.pools = Object.fromEntries(
    Object.entries(SOUND_FILES).map(([name, src]) => [
      name,
      Array.from({ length: 4 }, () => {
        const audio = new Audio(src);
        audio.preload = "auto";
        audio.volume = effectiveSoundVolume();
        return audio;
      }),
    ]),
  );
  renderSoundControls();
}

function effectiveSoundVolume() {
  return soundState.enabled ? soundState.volume : 0;
}

function renderSoundControls() {
  if (!els.soundToggle || !els.soundVolume) return;
  els.soundVolume.value = String(Math.round(soundState.volume * 100));
  els.soundToggle.textContent = soundState.enabled && soundState.volume > 0 ? "🔊" : "🔇";
  els.soundToggle.setAttribute(
    "aria-label",
    soundState.enabled ? "효과음 끄기" : "효과음 켜기",
  );
  for (const pool of Object.values(soundState.pools)) {
    for (const audio of pool) {
      audio.volume = effectiveSoundVolume();
    }
  }
}

async function unlockSound() {
  if (soundState.unlocked) return;
  soundState.unlocked = true;
  const warmups = Object.values(soundState.pools)
    .map((pool) => pool[0])
    .filter(Boolean)
    .map(async (audio) => {
      const previousMuted = audio.muted;
      audio.muted = true;
      try {
        await audio.play();
        audio.pause();
        audio.currentTime = 0;
      } catch {
        // 브라우저가 아직 막으면 실제 게임 클릭 이후 다시 play()에서 시도한다.
      } finally {
        audio.muted = previousMuted;
      }
    });
  await Promise.allSettled(warmups);
}

function setSoundEnabled(enabled) {
  soundState.enabled = enabled;
  localStorage.setItem("tikatuka.soundEnabled", String(enabled));
  renderSoundControls();
}

function setSoundVolume(value) {
  soundState.volume = Math.min(1, Math.max(0, Number(value) / 100));
  if (soundState.volume > 0 && !soundState.enabled) {
    soundState.enabled = true;
    localStorage.setItem("tikatuka.soundEnabled", "true");
  }
  localStorage.setItem("tikatuka.soundVolume", String(soundState.volume));
  renderSoundControls();
}

function isSoundAllowed() {
  return document.body.classList.contains("in-room") && soundState.enabled && soundState.volume > 0;
}

function playSound(name, delay = 0) {
  if (delay > 0) {
    window.setTimeout(() => playSound(name), delay);
    return;
  }
  if (!isSoundAllowed()) return;
  const pool = soundState.pools[name] || [];
  const audio = pool.find((item) => item.paused || item.ended) || pool[0]?.cloneNode(true);
  if (!audio) return;
  audio.volume = effectiveSoundVolume();
  audio.currentTime = 0;
  audio.play().catch(() => {
    // 사용자가 아직 오디오를 허용하지 않은 상황이면 조용히 무시한다.
  });
}

function clearFx() {
  fx.seenEvents.clear();
  fx.dieRects.clear();
  fx.trayDieRects.clear();
  fx.rollingIds.clear();
  fx.popIds.clear();
  fx.flickingIds.clear();
  fx.shieldBlockIds.clear();
  fx.discardIds.clear();
  fx.flickFields.clear();
  fx.shieldFields.clear();
  fx.ghosts = [];
  document.querySelectorAll(".strike-flyer-shell").forEach((element) => element.remove());
  document.querySelectorAll(".emoticon-burst").forEach((element) => element.remove());
  document.querySelectorAll(".waiting-emoticon-burst").forEach((element) => element.remove());
  document
    .querySelectorAll(".mobile-player-card.has-emoticon")
    .forEach((element) => element.classList.remove("has-emoticon"));
  fx.startBanner = null;
  fx.rollDelayUntil = 0;
  fx.animatingUntil = 0;
  fx.lockUntil = 0;
  if (fx.renderTimer) window.clearTimeout(fx.renderTimer);
  fx.renderTimer = null;
  state.waitingEmoticonPickerOpen = false;
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
  unlockSound();
  if (!getNickname()) return;
  setStatus("방 만드는 중...");
  const response = await fetch(apiUrl("/api/rooms"), { method: "POST" });
  if (!response.ok) throw new Error(await response.text());
  const data = await response.json();
  await connectRoom(data.code, { skipCheck: true });
}

async function createStreamerRoom() {
  unlockSound();
  if (!getNickname()) return;
  const queueLimit = Number(els.streamerQueueLimit?.value || 1);
  setStatus("방송인 모드 방 만드는 중...");
  const response = await fetch(apiUrl("/api/streamer-rooms"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      queueLimit,
      clientId: state.clientId,
      nickname: els.nicknameInput.value,
    }),
  });
  if (!response.ok) throw new Error(await response.text());
  const data = await response.json();
  await connectRoom(data.code, { skipCheck: true });
}

async function randomMatch() {
  unlockSound();
  const nickname = getNickname();
  if (!nickname) return;
  setStatus("랜덤 매칭 찾는 중...");
  const response = await fetch(apiUrl("/api/random-match"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ clientId: state.clientId, nickname }),
  });
  if (!response.ok) throw new Error(await response.text());
  const data = await response.json();
  setStatus(data.matched ? "랜덤 상대를 찾았습니다." : "랜덤 상대를 기다리는 중...");
  await connectRoom(data.code, { skipCheck: true });
}

async function connectRoom(code, options = {}) {
  unlockSound();
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
  state.leaveReserved = false;
  state.actionPending = false;
  if (state.leaveAutoTimer) window.clearTimeout(state.leaveAutoTimer);
  state.leaveAutoTimer = null;
  state.roomCode = roomCode;
  state.connectedAt = Date.now() / 1000;
  state.awaitingFirstSnapshot = true;
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
      state.actionPending = false;
      state.snapshot = message;
      state.snapshotReceivedAt = Date.now();
      primeExistingFxEvents(message);
      requestRender();
    } else if (message.type === "error") {
      state.actionPending = false;
      setStatus(message.message);
    } else if (message.type === "room_closed") {
      state.actionPending = false;
      returnToLobby(message.message || "방이 종료되었습니다.");
    }
  });

  socket.addEventListener("close", () => {
    state.actionPending = false;
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

function shouldRefreshStatus() {
  return !document.hidden && !document.body.classList.contains("in-room");
}

async function refreshStatus() {
  if (!shouldRefreshStatus() || state.statusRefreshInFlight) return;
  state.statusRefreshInFlight = true;
  try {
    const response = await fetch(apiUrl("/api/heartbeat"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        clientId: state.clientId,
        nickname: els.nicknameInput.value,
      }),
    });
    if (!response.ok) return;
    state.status = await response.json();
    renderLobbyStatus();
  } catch {
    // 로컬 프론트만 띄운 상태에서는 백엔드가 없을 수 있다.
  } finally {
    state.statusRefreshInFlight = false;
  }
}

function renderLobbyStatus() {
  const onlineUsers = state.status?.onlineUsers ?? 0;
  const stats = state.status?.stats || { score: 0, wins: 0, losses: 0, streak: 0 };
  const leaderboard = state.status?.leaderboard || [];
  els.onlineUsers.textContent = `접속 ${onlineUsers}명`;
  els.myRating.innerHTML = `
    <strong>${stats.score}점</strong>
    <span>${stats.wins}승 / ${stats.losses}패</span>
  `;
  els.leaderboard.innerHTML = leaderboard.length
    ? leaderboard
        .map(
          (entry, index) => `
            <li class="${entry.clientId === state.clientId ? "is-me" : ""}">
              <span class="rank-no">${index + 1}</span>
              <strong>${escapeHtml(entry.name || "플레이어")}</strong>
              <em>${entry.score}점</em>
              <small>${entry.wins}승/${entry.losses}패</small>
            </li>
          `,
        )
        .join("")
    : `<li class="empty-ranking">아직 랭킹 기록이 없습니다.</li>`;
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

async function copyRoomCode() {
  const roomCode = state.roomCode || "";
  if (!roomCode) {
    setStatus("복사할 방 번호가 없습니다.");
    return;
  }
  try {
    let copied = false;
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(roomCode);
        copied = true;
      } catch {
        copied = false;
      }
    }
    if (!copied) copied = legacyCopyText(roomCode);
    if (!copied) throw new Error("copy command failed");
    setStatus(`방 번호 ${roomCode} 복사 완료`);
  } catch {
    setStatus("방 번호를 복사하지 못했습니다. 직접 입력해주세요.");
  }
}

function legacyCopyText(text) {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.append(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  textarea.remove();
  return copied;
}

function returnToLobby(message) {
  state.leaving = true;
  state.leaveReserved = false;
  if (state.leaveAutoTimer) window.clearTimeout(state.leaveAutoTimer);
  state.leaveAutoTimer = null;
  if (state.ws) state.ws.close();
  state.ws = null;
  state.snapshot = null;
  state.roomCode = null;
  state.awaitingFirstSnapshot = false;
  state.actionPending = false;
  state.emoticonPickerPlayer = null;
  clearFx();
  setRoomMode(false);
  setStatus(message);
  refreshStatus();
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
  if (state.actionPending) {
    setStatus("이전 행동을 처리 중입니다.");
    return;
  }
  state.actionPending = true;
  state.ws.send(JSON.stringify({ type: "action", action, ...payload }));
}

function sendRestart() {
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) return;
  state.ws.send(JSON.stringify({ type: "restart" }));
}

function sendReady() {
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) return;
  state.ws.send(JSON.stringify({ type: "ready" }));
}

function sendKickOpponent() {
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) return;
  state.ws.send(JSON.stringify({ type: "kick_opponent" }));
}

function sendEmoticon(emoticon) {
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
    setStatus("서버와 연결되어 있지 않습니다.");
    return;
  }
  state.ws.send(JSON.stringify({ type: "emoticon", emoticon }));
}

function sendWaitingEmoticon(emoticon) {
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
    setStatus("서버와 연결되어 있지 않습니다.");
    return;
  }
  state.ws.send(JSON.stringify({ type: "waiting_emoticon", emoticon }));
}

function sendTimeoutCheck() {
  const snapshot = state.snapshot;
  if (!snapshot || !state.ws || state.ws.readyState !== WebSocket.OPEN) return;
  const { room, game } = snapshot;
  if (!room.started || game.result || room.clockPlayer === null || room.clockPlayer === undefined) return;
  if (clockValues(room.clockPlayer).total > 0) return;
  if (Date.now() - state.lastTimeoutCheckAt < 1200) return;
  state.lastTimeoutCheckAt = Date.now();
  state.ws.send(JSON.stringify({ type: "timeout_check" }));
}

function render() {
  const snapshot = state.snapshot;
  if (!snapshot) return;
  const { room, game, you } = snapshot;
  document.body.classList.toggle("streamer-room", Boolean(room.streamerMode));
  if (els.waitingEmoticonStage) {
    els.waitingEmoticonStage.hidden = !room.streamerMode;
  }
  if (els.mobile.waitingEmoticonStage) {
    els.mobile.waitingEmoticonStage.hidden = !room.streamerMode;
  }
  processFx(snapshot);
  els.roomCode.textContent = room.randomMatch ? "랜덤 매칭" : room.code;
  els.copyRoom.hidden = Boolean(room.randomMatch);

  const meText =
    you.queuePosition
      ? `대기 ${you.queuePosition}번으로 관전 중`
      : you.player === null || you.player === undefined
        ? "관전 중"
      : `${playerName(you.player)}로 플레이 중`;
  const waitText = room.started
    ? phaseText(game)
    : room.streamerMode && room.players[1]?.occupied
      ? "방송인의 준비를 기다리는 중"
      : "상대 입장 대기 중";
  setStatus(
    state.leaveReserved && room.started && !game.result
      ? "나가기 예약중 · 승패가 결정되면 로비로 이동합니다."
      : `${meText} · ${waitText}`,
  );

  for (let player = 0; player < 2; player += 1) {
    const card = document.querySelector(`#player-card-${player}`);
    const playerState = document.querySelector(`#player-state-${player}`);
    const roomPlayer = room.players[player];
    els.playerNames[player].innerHTML = renderPlayerNameWithRank(roomPlayer);
    card.classList.toggle(
      "is-turn",
      room.started && game.currentPlayer === player && game.phase !== "game_over",
    );
    playerState.innerHTML = renderPlayerStateLine(room, roomPlayer);
  }

  renderBoard(game);
  renderTrays(game, you);
  renderControls(room, game, you);
  renderResult(room, game, you);
  renderClocks(room, game);
  renderMobile(room, game, you);
  renderStartBanner(room);
  renderLeaveButtons(room, game);
  renderStreamerQueue(room, you);
  renderFriendlyRecord(room);
  maybeAutoLeaveAfterResult(game);
  rememberDieRects();
}

function renderFriendlyRecord(room) {
  const isFriendlyMatch = !room.randomMatch && Boolean(room.players?.[1]?.occupied);
  const score = Array.isArray(room.friendlyScore) ? room.friendlyScore : [0, 0];
  const scoreText = `${Number(score[0]) || 0} : ${Number(score[1]) || 0}`;
  for (const [record, scoreElement] of [
    [els.friendlyRecord, els.friendlyRecordScore],
    [els.mobile.friendlyRecord, els.mobile.friendlyRecordScore],
  ]) {
    if (!record || !scoreElement) continue;
    record.hidden = !isFriendlyMatch;
    if (isFriendlyMatch) scoreElement.textContent = scoreText;
  }
}

function renderPlayerStateLine(room, roomPlayer) {
  const statsLine = renderPlayerStatLine(roomPlayer?.stats);
  if (
    !room.streamerMode ||
    room.started ||
    !roomPlayer?.occupied ||
    roomPlayer.index !== 0
  ) {
    return statsLine;
  }
  const readyLine = roomPlayer.ready
    ? '<span class="ready-state">준비 완료</span>'
    : '<span class="waiting-state">준비 전</span>';
  return statsLine ? `${statsLine} · ${readyLine}` : readyLine;
}

function renderPlayerStatLine(stats) {
  if (!stats) return "";
  const record = `${stats.wins}승 / ${stats.losses}패`;
  if (stats.streak > 0) {
    return `${record} · <span class="streak-win">${stats.streak}연승 중</span>`;
  }
  if (stats.streak < 0) {
    return `${record} · <span class="streak-loss">${Math.abs(stats.streak)}연패 중</span>`;
  }
  return record;
}

function renderPlayerNameWithRank(roomPlayer) {
  const name = escapeHtml(roomPlayer?.name || "플레이어");
  return `${name}${rankBadge(roomPlayer?.stats)}`;
}

function rankBadge(stats) {
  const rank = Number(stats?.rank);
  if (!Number.isInteger(rank) || rank < 1 || rank > 20) return "";
  return `<span class="rank-badge" aria-label="랭킹 ${rank}위">TOP ${rank}</span>`;
}

function requestRender() {
  if (Date.now() < fx.animatingUntil) {
    scheduleFxRender();
    return;
  }
  render();
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

function primeExistingFxEvents(snapshot) {
  if (!state.awaitingFirstSnapshot) return;
  state.awaitingFirstSnapshot = false;
  const cutoff = state.connectedAt - 0.25;
  for (const event of snapshot.log || []) {
    const eventTime = Number(event.ts || 0);
    if (eventTime > 0 && eventTime < cutoff) {
      fx.seenEvents.add(eventKey(event));
    }
  }
}

function eventKey(event) {
  return `${event.ts ?? ""}:${event.type}:${JSON.stringify(event)}`;
}

function triggerFx(event, snapshot) {
  if (event.type === "first_player_rolloff") {
    const duration = 3600;
    fx.startBanner = {
      key: `${event.ts ?? Date.now()}:${event.rolls.join("-")}:${event.winner}`,
      rolls: event.rolls,
      winner: event.winner,
      until: Date.now() + duration,
    };
    fx.rollDelayUntil = fx.startBanner.until - 300;
    playSound("roll");
    markAnimation(duration);
    lockFor(duration - 300);
    const bannerKey = fx.startBanner.key;
    window.setTimeout(() => {
      if (els.startBanner && fx.startBanner?.key === bannerKey) {
        els.startBanner.hidden = true;
      }
    }, duration);
    return;
  }

  if (event.type === "die_rolled") {
    const delay = Math.max(0, fx.rollDelayUntil - Date.now());
    playSound("roll", delay);
    delayedPulseSet(fx.rollingIds, [event.die?.id], 720, delay);
    lockFor(delay + 520);
    return;
  }

  if (event.type === "hand_trick") {
    playSound("roll");
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
    if (!hasPairedEggFlick(event, snapshot)) playSound("place");
    pulseSet(fx.popIds, [event.die?.id], 360);
    return;
  }

  if (event.type === "bonus_die_placed") {
    playSound("place");
    pulseSet(fx.popIds, [event.die?.id], 360);
    return;
  }

  if (event.type === "egg_flick") {
    const opponent = 1 - event.player;
    playSound("egg");
    addStrikeFlyer(event.placedDie, event.player, opponent, event.field, event.opponentDiceRemoved);
    for (const die of event.opponentDiceRemoved || []) {
      addGhost(die, opponent, event.field, ["victim-flick"]);
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
    return;
  }

  if (event.type === "emoticon") {
    showEmoticon(event.player, event.emoticon);
    return;
  }

  if (event.type === "waiting_emoticon") {
    showWaitingEmoticon(event);
    return;
  }
}

function hasPairedEggFlick(event, snapshot) {
  return (snapshot.log || []).some(
    (candidate) =>
      candidate.type === "egg_flick" &&
      candidate.ts === event.ts &&
      candidate.placedDie?.id === event.die?.id,
  );
}

function pulseSet(set, ids, duration) {
  const validIds = ids.filter((id) => id !== undefined && id !== null);
  if (!validIds.length) return;
  for (const id of validIds) set.add(id);
  markAnimation(duration);
  window.setTimeout(() => {
    for (const id of validIds) set.delete(id);
    scheduleFxRender();
  }, duration);
}

function delayedPulseSet(set, ids, duration, delay = 0) {
  if (delay <= 0) {
    pulseSet(set, ids, duration);
    return;
  }
  window.setTimeout(() => {
    pulseSet(set, ids, duration);
    render();
  }, delay);
}

function pulseFields(set, keys, duration) {
  for (const key of keys) set.add(key);
  markAnimation(duration);
  window.setTimeout(() => {
    for (const key of keys) set.delete(key);
    scheduleFxRender();
  }, duration);
}

function addGhost(die, player, field, extraClasses = ["flicking"]) {
  if (!die) return;
  const key = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  fx.ghosts.push({ key, die, player, field, extraClasses });
  markAnimation(620);
  window.setTimeout(() => {
    fx.ghosts = fx.ghosts.filter((ghost) => ghost.key !== key);
    scheduleFxRender();
  }, 620);
}

function addStrikeFlyer(die, player, opponent, field, removedDice = []) {
  if (!die) return;
  const table = document.querySelector(".table");
  if (!table) return;

  const tableRect = table.getBoundingClientRect();
  const sourceRect = findStrikeSourceRect(player, die);
  const targetRect = findStrikeTargetRect(opponent, field, removedDice);
  if (!sourceRect || !targetRect) {
    addGhost(die, player, field, [
      "striking",
      player === 0 ? "strike-right" : "strike-left",
    ]);
    return;
  }

  const fromX = sourceRect.left + sourceRect.width / 2 - tableRect.left;
  const fromY = sourceRect.top + sourceRect.height / 2 - tableRect.top;
  const toX = targetRect.left + targetRect.width / 2 - tableRect.left;
  const toY = targetRect.top + targetRect.height / 2 - tableRect.top;
  const midX = fromX + (toX - fromX) * 0.58;
  const midY = fromY + (toY - fromY) * 0.58;
  const duration = 820;

  const shell = document.createElement("div");
  shell.className = `strike-flyer-shell ${player === 0 ? "fly-right" : "fly-left"}`;
  shell.style.setProperty("--from-x", `${fromX}px`);
  shell.style.setProperty("--from-y", `${fromY}px`);
  shell.style.setProperty("--mid-x", `${midX}px`);
  shell.style.setProperty("--mid-y", `${midY}px`);
  shell.style.setProperty("--to-x", `${toX}px`);
  shell.style.setProperty("--to-y", `${toY}px`);
  shell.innerHTML = renderDie(die, {
    extraClasses: ["strike-fly-die"],
    ownerOverride: mobileOwnerOverride(die, player),
  });
  table.append(shell);

  markAnimation(duration);
  window.setTimeout(() => {
    shell.remove();
    scheduleFxRender();
  }, duration);
}

function showEmoticon(player, emoticon) {
  if (!EMOTICONS.some((item) => item.id === emoticon)) return;
  if (isMobileRoomView()) {
    showMobileEmoticon(player, emoticon);
    return;
  }
  showPcEmoticon(player, emoticon);
}

function showWaitingEmoticon(event) {
  if (!state.snapshot?.room?.streamerMode) return;
  if (!EMOTICONS.some((item) => item.id === event.emoticon)) return;
  const stage = isMobileRoomView()
    ? els.mobile.waitingEmoticonStage
    : els.waitingEmoticonStage;
  if (!stage || stage.hidden) return;
  const image = emoticonImage(event.emoticon, ["waiting-emoticon-burst"]);
  const imageSize = 64;
  const inset = 6;
  const maxX = Math.max(0, stage.clientWidth - imageSize - inset * 2);
  const maxY = Math.max(0, stage.clientHeight - imageSize - inset * 2);
  image.style.left = `${inset + Math.random() * maxX}px`;
  image.style.top = `${inset + Math.random() * maxY}px`;
  image.title = event.name || "대기자";
  stage.append(image);
  window.setTimeout(() => image.remove(), 2200);
}

function showMobileEmoticon(player, emoticon) {
  const me = state.snapshot?.you?.player;
  const card = player === me ? els.mobile.myCard : els.mobile.opponentCard;
  if (!card) return;
  card.querySelectorAll(".mobile-card-emoticon").forEach((element) => element.remove());
  card.classList.add("has-emoticon");
  const image = emoticonImage(emoticon, ["emoticon-burst", "mobile-card-emoticon"]);
  card.append(image);
  window.setTimeout(() => {
    image.remove();
    card.classList.remove("has-emoticon");
  }, 2200);
}

function showPcEmoticon(player, emoticon) {
  const table = document.querySelector(".table");
  const target = firstVisible(`.field[data-player="${player}"][data-field="0"]`);
  if (!table || !target) return;
  table
    .querySelectorAll(`.pc-emoticon-burst[data-emoticon-player="${player}"]`)
    .forEach((element) => element.remove());
  const tableRect = table.getBoundingClientRect();
  const targetRect = target.getBoundingClientRect();
  const image = emoticonImage(emoticon, ["emoticon-burst", "pc-emoticon-burst"]);
  image.dataset.emoticonPlayer = String(player);
  image.style.left = `${targetRect.left + targetRect.width / 2 - tableRect.left}px`;
  image.style.top = `${targetRect.top - tableRect.top - 10}px`;
  table.append(image);
  window.setTimeout(() => image.remove(), 2200);
}

function emoticonImage(emoticon, classes = []) {
  const image = document.createElement("img");
  image.className = classes.join(" ");
  image.src = emoticonUrl(emoticon);
  image.alt = "";
  image.draggable = false;
  image.setAttribute("aria-hidden", "true");
  return image;
}

function emoticonUrl(emoticon) {
  return `./emoticon/${encodeURIComponent(emoticon)}.png`;
}

function isVisibleElement(element) {
  return Boolean(
    element &&
      element.getClientRects().length &&
      window.getComputedStyle(element).visibility !== "hidden",
  );
}

function firstVisible(selector) {
  return [...document.querySelectorAll(selector)].find(isVisibleElement) || null;
}

function rectSnapshot(element) {
  const rect = element.getBoundingClientRect();
  return {
    left: rect.left,
    top: rect.top,
    width: rect.width,
    height: rect.height,
    right: rect.right,
    bottom: rect.bottom,
  };
}

function findStrikeSourceRect(player, die) {
  const exactDie = firstVisible(
    `#tray-${player} .die[data-die-id="${die.id}"], #mobile-tray .die[data-die-id="${die.id}"]`,
  );
  if (exactDie) return exactDie.getBoundingClientRect();
  const cachedTray = fx.trayDieRects.get(String(die.id));
  if (cachedTray) return cachedTray;
  const cached = fx.dieRects.get(String(die.id));
  if (cached) return cached;
  const trayDie = firstVisible(`#tray-${player} .die, #mobile-tray .die`);
  if (trayDie) return trayDie.getBoundingClientRect();
  const tray = firstVisible(`#tray-${player}, #mobile-tray`);
  return tray?.getBoundingClientRect() || null;
}

function findStrikeTargetRect(opponent, field, removedDice = []) {
  for (const removed of removedDice || []) {
    const exactDie = firstVisible(
      `.field[data-player="${opponent}"][data-field="${field}"] .die[data-die-id="${removed.id}"]`,
    );
    if (exactDie) return exactDie.getBoundingClientRect();
  }
  const matchingDie = firstVisible(
    `.field[data-player="${opponent}"][data-field="${field}"] .die`,
  );
  if (matchingDie) return matchingDie.getBoundingClientRect();
  return firstVisible(`.field[data-player="${opponent}"][data-field="${field}"]`)
    ?.getBoundingClientRect() || null;
}

function rememberDieRects() {
  document.querySelectorAll(".die[data-die-id]").forEach((element) => {
    if (element.closest(".strike-flyer-shell")) return;
    if (!isVisibleElement(element)) return;
    const id = element.dataset.dieId;
    if (!id) return;
    const rect = rectSnapshot(element);
    fx.dieRects.set(id, rect);
    if (element.closest(".tray-dice") || element.closest(".mobile-tray")) {
      fx.trayDieRects.set(id, rect);
    }
  });
}

function lockFor(duration) {
  fx.lockUntil = Math.max(fx.lockUntil, Date.now() + duration);
}

function markAnimation(duration) {
  fx.animatingUntil = Math.max(fx.animatingUntil, Date.now() + duration);
}

function scheduleFxRender() {
  if (fx.renderTimer) window.clearTimeout(fx.renderTimer);
  const delay = Math.max(0, fx.animatingUntil - Date.now() + 30);
  fx.renderTimer = window.setTimeout(() => {
    fx.renderTimer = null;
    if (Date.now() < fx.animatingUntil) {
      scheduleFxRender();
      return;
    }
    render();
  }, delay);
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
      fieldEl.classList.toggle("egg-target", isEggTargetLegal(player, field));
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
    if (room.streamerMode && !room.started && !game.result) {
      const host = room.players[0];
      const challenger = room.players[1];
      const canReady =
        player === 0 &&
        you.player === 0 &&
        host?.occupied &&
        challenger?.occupied &&
        challenger?.connected;
      els.trayControls[player].innerHTML = player === 0 && you.player === 0
        ? `
          <button class="tray-action ready-action"
            data-ready-player="0" ${canReady ? "" : "disabled"}>
            준비
          </button>
        `
        : "";
      continue;
    }

    const isCurrent = room.started && you.player === player && game.currentPlayer === player;
    const canEmote = room.started && you.player === player;
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
      <div class="emoticon-control">
        <button class="tray-action emoticon-toggle" data-emoticon-toggle data-player="${player}" ${
          canEmote ? "" : "disabled"
        }>이모티콘</button>
        ${renderEmoticonPicker(canEmote && state.emoticonPickerPlayer === player, [
          "pc-emoticon-picker",
          `emoticon-picker-player-${player}`,
        ])}
      </div>
    `;
  }
}

function renderEmoticonPicker(isOpen, extraClasses = []) {
  const classes = ["emoticon-picker", ...extraClasses].join(" ");
  return `
    <div class="${classes}" ${isOpen ? "" : "hidden"}>
      ${EMOTICONS.map(
        (item) => `
          <button class="emoticon-choice" type="button" data-emoticon-id="${item.id}" aria-label="${item.label}">
            <img src="${emoticonUrl(item.id)}" alt="" draggable="false" />
          </button>
        `,
      ).join("")}
    </div>
  `;
}

function renderStreamerQueue(room, you) {
  if (!els.streamerQueuePanel) return;
  if (!room.streamerMode) {
    els.streamerQueuePanel.hidden = true;
    els.streamerQueuePanel.classList.remove("is-mobile-open");
    if (els.streamerQueueToggle) els.streamerQueueToggle.hidden = true;
    state.streamerQueueOpen = false;
    return;
  }

  const waitingPlayers = room.waitingPlayers || [];
  els.streamerQueueCount.textContent = `${waitingPlayers.length}/${room.queueLimit || 0}`;
  if (els.streamerQueueToggle && els.streamerQueueToggleCount) {
    els.streamerQueueToggle.hidden = false;
    els.streamerQueueToggleCount.textContent = String(waitingPlayers.length);
    els.streamerQueueToggle.setAttribute(
      "aria-expanded",
      state.streamerQueueOpen ? "true" : "false",
    );
    els.streamerQueueToggle.setAttribute(
      "aria-label",
      state.streamerQueueOpen
        ? "대기자 목록 닫기"
        : `대기자 ${waitingPlayers.length}명 목록 열기`,
    );
  }
  els.streamerQueueList.innerHTML = waitingPlayers.length
    ? waitingPlayers
        .map(
          (waiting) => `
            <li>
              <span>${waiting.position}</span>
              <strong>${escapeHtml(waiting.name || "대기자")}</strong>
            </li>
          `,
        )
        .join("")
    : `<li><span>–</span><strong>대기자 없음</strong></li>`;

  const canUseWaitingEmoticon = Number.isInteger(you.queuePosition) && you.queuePosition > 0;
  els.waitingEmoticonControl.innerHTML = canUseWaitingEmoticon
    ? `
      <div class="waiting-emoticon-control">
        <button class="tray-action" type="button" data-waiting-emoticon-toggle>
          대기자 이모티콘
        </button>
        <div class="emoticon-picker waiting-emoticon-picker" ${
          state.waitingEmoticonPickerOpen ? "" : "hidden"
        }>
          ${EMOTICONS.map(
            (item) => `
              <button class="emoticon-choice" type="button"
                data-waiting-emoticon-id="${item.id}" aria-label="${item.label}">
                <img src="${emoticonUrl(item.id)}" alt="" draggable="false" />
              </button>
            `,
          ).join("")}
        </div>
      </div>
    `
    : "";
  els.streamerQueuePanel.classList.toggle("is-mobile-open", state.streamerQueueOpen);
  els.streamerQueuePanel.hidden = false;
}

function renderResult(room, game, you) {
  if (!game.result) {
    els.resultBanner.hidden = true;
    els.restart.textContent = "다시하기";
    els.kickOpponent.hidden = true;
    if (els.mobile.resultBanner) els.mobile.resultBanner.hidden = true;
    if (els.mobile.restart) els.mobile.restart.textContent = "다시하기";
    if (els.mobile.kickOpponent) els.mobile.kickOpponent.hidden = true;
    return;
  }
  const winnerText =
    game.result.winner === null ? "무승부!" : `${playerName(game.result.winner)} 승리!`;
  els.resultWinnerText.textContent = winnerText;
  const votes = room.rematchVotes || 0;
  const needed = room.rematchNeeded || 2;
  const restartText = votes > 0 && votes < needed ? `다시하기 (${votes}/${needed})` : "다시하기";
  els.restart.textContent = restartText;
  els.restart.disabled = you.player === null || you.player === undefined;
  const canKick =
    !room.randomMatch &&
    you.player === 0 &&
    Boolean(room.players?.[1]?.occupied);
  els.kickOpponent.hidden = !canKick;
  els.restart.parentElement?.classList.toggle("single-action", !canKick);
  els.resultBanner.hidden = false;
  if (els.mobile.resultBanner) {
    els.mobile.resultWinnerText.textContent = winnerText;
    els.mobile.restart.textContent = restartText;
    els.mobile.restart.disabled = you.player === null || you.player === undefined;
    els.mobile.kickOpponent.hidden = !canKick;
    els.mobile.resultBanner.hidden = false;
  }
}

function isGameInProgress() {
  const snapshot = state.snapshot;
  return Boolean(snapshot?.room.started && !snapshot.game.result);
}

function requestLeave() {
  if (state.snapshot?.you?.spectator) {
    returnToLobby("대기열에서 나갔습니다.");
    return;
  }
  if (isGameInProgress()) {
    state.leaveReserved = true;
    renderLeaveButtons(state.snapshot.room, state.snapshot.game);
    setStatus("나가기 예약중 · 승패가 결정되면 로비로 이동합니다.");
    return;
  }
  returnToLobby("로비로 돌아왔습니다.");
}

function renderLeaveButtons(room, game) {
  const reserved = Boolean(state.leaveReserved && room?.started && !game?.result);
  for (const button of [els.leave, els.mobile.leave]) {
    if (!button) continue;
    button.textContent = reserved ? "나가기 예약중" : "나가기";
    button.disabled = reserved;
    button.classList.toggle("leave-reserved", reserved);
  }
}

function maybeAutoLeaveAfterResult(game) {
  if (!state.leaveReserved || !game?.result || state.leaveAutoTimer) return;
  state.leaveAutoTimer = window.setTimeout(() => {
    if (state.leaveReserved) {
      returnToLobby("게임이 종료되어 로비로 돌아왔습니다.");
    }
  }, 650);
}

function renderClocks(room, game) {
  for (let player = 0; player < 2; player += 1) {
    const remaining = clockValues(player);
    const isClockPlayer = room.started && !game.result && room.clockPlayer === player;
    const spendingTurn = isClockPlayer && remaining.turn > 0;
    const spendingTotal = isClockPlayer && remaining.turn <= 0 && remaining.total > 0;

    if (els.turnClockValues[player]) {
      els.turnClockValues[player].textContent = formatClock(remaining.turn);
    }
    if (els.totalClockValues[player]) {
      els.totalClockValues[player].textContent = formatClock(remaining.total);
    }
    if (els.turnClockPanels[player]) {
      els.turnClockPanels[player].classList.toggle("active", spendingTurn);
      els.turnClockPanels[player].classList.toggle(
        "danger",
        spendingTurn && remaining.turn <= 5,
      );
    }
    if (els.totalClockPanels[player]) {
      els.totalClockPanels[player].classList.toggle("active", spendingTotal);
      els.totalClockPanels[player].classList.toggle(
        "danger",
        spendingTotal && remaining.total <= 15,
      );
    }
  }
}

function mobilePlayers(you) {
  const me = you?.player === 0 || you?.player === 1 ? you.player : 0;
  return { me, opponent: 1 - me };
}

function renderMobile(room, game, you) {
  if (!els.mobile?.myBoard) return;
  const { me, opponent } = mobilePlayers(you);
  if (els.mobile.roomCode) {
    els.mobile.roomCode.textContent = room.randomMatch
      ? "랜덤 매칭"
      : room.code;
  }
  renderMobilePlayerCards(room, game, me, opponent);
  renderMobileBoard(els.mobile.opponentBoard, game, opponent, "opponent", me);
  renderMobileScoreGrid(game, me, opponent);
  renderMobileBoard(els.mobile.myBoard, game, me, "mine", me);
  renderMobileTray(room, game, you, me);
  renderMobileActions(room, game, you, me);
  renderMobileClocks(room, game, me, opponent);
}

function renderMobilePlayerCards(room, game, me, opponent) {
  const players = [
    { key: "opponent", player: opponent, card: els.mobile.opponentCard },
    { key: "my", player: me, card: els.mobile.myCard },
  ];
  for (const item of players) {
    const avatar = item.key === "my" ? els.mobile.myAvatar : els.mobile.opponentAvatar;
    const name = item.key === "my" ? els.mobile.myName : els.mobile.opponentName;
    const stateLine = item.key === "my" ? els.mobile.myState : els.mobile.opponentState;
    const roomPlayer = room.players[item.player];
    avatar.className = `avatar ${item.key === "my" ? "avatar-green" : "avatar-red"}`;
    name.innerHTML = renderPlayerNameWithRank(roomPlayer || { name: DEFAULT_PLAYER_NAMES[item.player] });
    stateLine.innerHTML = renderPlayerStateLine(room, roomPlayer);
    item.card.classList.toggle(
      "is-turn",
      room.started && game.currentPlayer === item.player && game.phase !== "game_over",
    );
  }
}

function renderMobileBoard(container, game, player, side, me) {
  if (!container) return;
  container.innerHTML = [0, 1, 2]
    .map((field) => {
      const fieldKey = `${player}:${field}`;
      const classes = [
        "field",
        "mobile-field",
        `mobile-field-${side}`,
        isFieldLegal(player, field) ? "legal" : "",
        isEggTargetLegal(player, field) ? "egg-target" : "",
        fx.flickFields.has(fieldKey) ? "flick-hit" : "",
        fx.shieldFields.has(fieldKey) ? "shield-hit" : "",
      ]
        .filter(Boolean)
        .join(" ");
      return `
        <div class="${classes}" data-player="${player}" data-field="${field}" role="button" tabindex="0">
          ${renderMobileFieldSlots(game.boards[player][field], side, me)}${renderGhostDice(player, field, { mobileMe: me })}
        </div>
      `;
    })
    .join("");
}

function renderMobileScoreGrid(game, me, opponent) {
  if (!els.mobile.scoreGrid) return;
  els.mobile.scoreGrid.innerHTML = [0, 1, 2]
    .map((field) => {
      const topScore = game.scores[opponent][field];
      const bottomScore = game.scores[me][field];
      const arrowClass =
        topScore === bottomScore ? "" : topScore > bottomScore ? "up" : "down";
      const arrowText = topScore === bottomScore ? "–" : topScore > bottomScore ? "▲" : "▼";
      return `
        <div class="mobile-score-bridge">
          <span class="score-top">${topScore}</span>
          <span class="arrow ${arrowClass}">${arrowText}</span>
          <span class="score-bottom">${bottomScore}</span>
        </div>
      `;
    })
    .join("");
}

function renderMobileTray(room, game, you, me) {
  if (!els.mobile.tray) return;
  const isPlayer = you.player === 0 || you.player === 1;
  const isCurrent = room.started && isPlayer && game.currentPlayer === me && you.player === me;
  const isOpponentTurn = room.started && isPlayer && game.currentPlayer !== me;
  const dice = [];
  if ((isCurrent || isOpponentTurn) && game.phase !== "game_over") {
    if (game.phase === "select_die") dice.push(...game.rolledDice);
    if ((game.phase === "place_normal" || game.phase === "place_bonus") && game.heldDie) {
      dice.push(game.heldDie);
    }
  }

  if (dice.length) {
    const label = isOpponentTurn
      ? "상대 주사위"
      : game.phase === "select_die"
        ? "선택할 주사위"
        : "현재 주사위";
    const ownerOverride = isOpponentTurn ? 1 : 0;
    els.mobile.tray.innerHTML = dice
      .map((die, index) => {
        const clickable = !isOpponentTurn && isMyTurn() && game.phase === "select_die";
        return `
          <span class="mobile-tray-die-wrap">
            ${renderDie(die, {
              clickable,
              selectIndex: index,
              ownerOverride,
            })}
            <span class="mobile-tray-label">${label}</span>
          </span>
        `;
      })
      .join("");
    return;
  }

  if (!room.started) {
    els.mobile.tray.textContent =
      room.streamerMode && room.players[1]?.occupied
        ? "방송인의 준비 대기 중"
        : "상대 입장 대기 중";
    return;
  }
  if (game.result) {
    els.mobile.tray.textContent = "게임 종료";
    return;
  }
  els.mobile.tray.textContent =
    game.currentPlayer === me ? phaseText(game) : `${playerName(game.currentPlayer)} 차례`;
}

function renderMobileActions(room, game, you, me) {
  if (!els.mobile.actionRow) return;
  if (room.streamerMode && !room.started && !game.result) {
    const challenger = room.players[1];
    const canReady =
      you.player === 0 && challenger?.occupied && challenger?.connected;
    els.mobile.actionRow.innerHTML = you.player === 0
      ? `
        <button class="tray-action ready-action"
          data-ready-player="0" ${canReady ? "" : "disabled"}>
          준비
        </button>
      `
      : "";
    return;
  }

  const isCurrent = room.started && you.player === me && game.currentPlayer === me;
  const canEmote = room.started && you.player === me;
  const canTrick =
    isCurrent &&
    game.phase === "place_normal" &&
    !game.handTrickUsed[me] &&
    !game.result &&
    !isFxLocked();
  const canHold =
    isCurrent &&
    ["place_normal", "select_die"].includes(game.phase) &&
    !game.result &&
    !isFxLocked();
  els.mobile.actionRow.innerHTML = `
    <button class="tray-action" data-action="trick" data-player="${me}" ${
      canTrick ? "" : "disabled"
    }>타짜의 손놀림</button>
    <button class="tray-action danger" data-action="hold" data-player="${me}" ${
      canHold ? "" : "disabled"
    }>홀드</button>
    <div class="emoticon-control mobile-emoticon-control">
      <button class="tray-action emoticon-toggle" data-emoticon-toggle data-player="${me}" ${
        canEmote ? "" : "disabled"
      }>이모티콘</button>
      ${renderEmoticonPicker(canEmote && state.emoticonPickerPlayer === me, [
        "mobile-emoticon-picker",
      ])}
    </div>
  `;
}

function renderMobileClocks(room, game, me, opponent) {
  const pairs = [
    [
      me,
      clockValues(me),
      els.mobile.myTurnClock,
      els.mobile.myTotalClock,
      els.mobile.myTurnClockPanel,
      els.mobile.myTotalClockPanel,
    ],
    [
      opponent,
      clockValues(opponent),
      els.mobile.opponentTurnClock,
      els.mobile.opponentTotalClock,
      els.mobile.opponentTurnClockPanel,
      els.mobile.opponentTotalClockPanel,
    ],
  ];
  for (const [player, remaining, turnValue, totalValue, turnPanel, totalPanel] of pairs) {
    const isClockPlayer = room.started && !game.result && room.clockPlayer === player;
    const spendingTurn = isClockPlayer && remaining.turn > 0;
    const spendingTotal = isClockPlayer && remaining.turn <= 0 && remaining.total > 0;

    if (turnValue) turnValue.textContent = formatClock(remaining.turn);
    if (totalValue) totalValue.textContent = formatClock(remaining.total);
    if (turnPanel) {
      turnPanel.classList.toggle("active", spendingTurn);
      turnPanel.classList.toggle("danger", spendingTurn && remaining.turn <= 5);
    }
    if (totalPanel) {
      totalPanel.classList.toggle("active", spendingTotal);
      totalPanel.classList.toggle("danger", spendingTotal && remaining.total <= 15);
    }
  }
}

function clockValues(player) {
  const room = state.snapshot?.room;
  if (!room) return { turn: 15, total: 60 };
  let turn = Number(room.turnClocks?.[player] ?? room.turnTimeSeconds ?? 15);
  let total = Number(
    room.totalClocks?.[player] ?? room.clocks?.[player] ?? room.totalTimeSeconds ?? 60,
  );
  if (
    room.clockPlayer === player &&
    state.snapshot?.game?.result === null &&
    state.snapshot?.room?.started
  ) {
    const elapsed = Math.max(0, Date.now() - state.snapshotReceivedAt) / 1000;
    const turnSpent = Math.min(turn, elapsed);
    turn -= turnSpent;
    total -= Math.max(0, elapsed - turnSpent);
  }
  return {
    turn: Math.max(0, turn),
    total: Math.max(0, total),
  };
}

function formatClock(seconds) {
  const total = Math.ceil(Math.max(0, seconds));
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  return `${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
}

function renderStartBanner(room) {
  const banner = fx.startBanner;
  if (!banner || Date.now() > banner.until) {
    els.startBanner.hidden = true;
    delete els.startBanner.dataset.key;
    return;
  }

  if (els.startBanner.dataset.key !== banner.key) {
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
    els.startBanner.dataset.key = banner.key;
  }
  els.startBanner.hidden = false;
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

function isEggTargetLegal(player, field) {
  const snapshot = state.snapshot;
  if (!snapshot || !isMyTurn()) return false;
  if (isFxLocked()) return false;
  const { game } = snapshot;
  if (game.phase !== "place_normal" || !game.heldDie) return false;

  const current = game.currentPlayer;
  const opponent = 1 - current;
  if (player !== opponent) return false;
  if (game.boards[current][field].length >= 3) return false;

  return game.boards[opponent][field].some(
    (die) => die.value === game.heldDie.value && !die.shield,
  );
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

function renderMobileFieldDice(dice) {
  const parts = [];
  let index = 0;
  while (index < dice.length) {
    let end = index + 1;
    while (end < dice.length && dice[end].value === dice[index].value) end += 1;
    const group = dice.slice(index, end);
    if (group.length >= 2) {
      const type = group.length === 3 ? "triple" : "double";
      parts.push(`
        <span class="mobile-combo-group ${type}-group" aria-label="${type} combo">
          ${group.map((die) => renderDie(die)).join('<span class="mobile-combo-link" aria-hidden="true"></span>')}
        </span>
      `);
    } else {
      parts.push(renderDie(group[0]));
    }
    index = end;
  }
  return parts.join("");
}

function renderMobileFieldSlots(dice, side, me) {
  const slotOrder = side === "opponent" ? [2, 1, 0] : [0, 1, 2];
  const slots = [null, null, null];
  dice.forEach((die, index) => {
    const row = slotOrder[index];
    if (row !== undefined) slots[row] = { die, index };
  });

  const comboRows = new Set();
  const connectorRows = new Set();
  let index = 0;
  while (index < dice.length) {
    let end = index + 1;
    while (end < dice.length && dice[end].value === dice[index].value) end += 1;
    if (end - index >= 2) {
      const rows = [];
      for (let comboIndex = index; comboIndex < end; comboIndex += 1) {
        const row = slotOrder[comboIndex];
        if (row !== undefined) {
          rows.push(row);
          comboRows.add(row);
        }
      }
      const sortedRows = [...rows].sort((left, right) => left - right);
      for (let rowIndex = 0; rowIndex < sortedRows.length - 1; rowIndex += 1) {
        const row = sortedRows[rowIndex];
        if (sortedRows[rowIndex + 1] === row + 1) connectorRows.add(row);
      }
    }
    index = end;
  }

  return [0, 1, 2]
    .map((row) => {
      const slot = slots[row];
      const classes = [
        "mobile-die-slot",
        slot ? "filled" : "empty",
        comboRows.has(row) ? "combo-slot" : "",
        connectorRows.has(row) ? "combo-to-next" : "",
      ]
        .filter(Boolean)
        .join(" ");
      return `<span class="${classes}">${
        slot ? renderDie(slot.die, { ownerOverride: mobileVisualOwner(slot.die, me, side) }) : ""
      }</span>`;
    })
    .join("");
}

function renderGhostDice(player, field, options = {}) {
  return fx.ghosts
    .filter((ghost) => ghost.player === player && ghost.field === field)
    .map((ghost) =>
      renderDie(ghost.die, {
        extraClasses: ghost.extraClasses,
        ownerOverride:
          options.mobileMe === undefined
            ? undefined
            : mobileVisualOwner(ghost.die, options.mobileMe, player === options.mobileMe ? "mine" : "opponent"),
      }),
    )
    .join("");
}

function renderDie(die, options = {}) {
  const owner = options.ownerOverride ?? die.owner ?? 0;
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

function mobileVisualOwner(die, me, side = "mine") {
  if (!isMobileRoomView() || (me !== 0 && me !== 1)) return die?.owner ?? (side === "mine" ? 0 : 1);
  if (die?.owner === me) return 0;
  if (die?.owner === 0 || die?.owner === 1) return 1;
  return side === "mine" ? 0 : 1;
}

function mobileOwnerOverride(die, logicalPlayer) {
  const me = state.snapshot?.you?.player;
  if (!isMobileRoomView() || (me !== 0 && me !== 1)) return undefined;
  return mobileVisualOwner(die, me, logicalPlayer === me ? "mine" : "opponent");
}

function isMobileRoomView() {
  return document.body.classList.contains("in-room") && window.matchMedia("(max-width: 900px)").matches;
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

function startMobileDemo() {
  const die = (id, value, owner, shield = false) => ({ id, value, owner, shield });
  state.snapshot = {
    type: "snapshot",
    room: {
      code: "0000",
      started: true,
      randomMatch: true,
      ranked: true,
      rolloff: { rolls: [6, 3], winner: 0, rerolls: 0, ts: Date.now() / 1000 },
      players: [
        {
          index: 0,
          name: "앨리더",
          occupied: true,
          connected: true,
          stats: { score: 220, wins: 7, losses: 5, streak: -2, rank: 7 },
        },
        {
          index: 1,
          name: "으랏느랏",
          occupied: true,
          connected: true,
          stats: { score: 180, wins: 1, losses: 2, streak: 1, rank: 12 },
        },
      ],
      clocks: [56, 60],
      turnClocks: [8, 15],
      totalClocks: [56, 60],
      clockPlayer: 0,
      turnTimeSeconds: 15,
      totalTimeSeconds: 60,
      rematchVotes: 0,
      rematchNeeded: 2,
    },
    you: {
      clientId: state.clientId,
      player: 1,
      spectator: false,
      stats: { score: 180, wins: 1, losses: 2, streak: 1, rank: 12 },
    },
    game: {
      boards: [
        [
          [die(1, 4, 0), die(2, 2, 0), die(3, 1, 0)],
          [die(4, 2, 0), die(5, 2, 0)],
          [die(7, 1, 0), die(8, 3, 0), die(9, 5, 0)],
        ],
        [
          [die(10, 1, 1), die(11, 2, 1), die(12, 4, 1)],
          [die(13, 3, 1), die(15, 3, 1), die(14, 1, 1)],
          [die(16, 1, 1), die(17, 4, 1), die(18, 2, 1, true)],
        ],
      ],
      currentPlayer: 0,
      phase: "place_normal",
      handTrickUsed: [false, true],
      holding: [false, false],
      openingShieldPending: false,
      rolledDice: [],
      heldDie: die(19, 3, 0),
      result: null,
      scores: [
        [7, 6, 9],
        [7, 10, 7],
      ],
    },
    log: [],
  };
  state.snapshotReceivedAt = Date.now();
  els.roomCode.textContent = "랜덤 매칭";
  setRoomMode(true);
  setStatus("모바일 세로 UI 데모");
  render();
}

els.createRoom.addEventListener("click", () => {
  createRoom().catch((error) => setStatus(`방 생성 실패: ${error.message}`));
});

els.createStreamerRoom?.addEventListener("click", () => {
  createStreamerRoom().catch((error) =>
    setStatus(`방송인 모드 생성 실패: ${error.message}`),
  );
});

els.randomMatch.addEventListener("click", () => {
  randomMatch().catch((error) => setStatus(`랜덤 매칭 실패: ${error.message}`));
});

els.joinForm.addEventListener("submit", (event) => {
  event.preventDefault();
  connectRoom(els.roomCodeInput.value).catch((error) =>
    setStatus(`입장 실패: ${error.message}`),
  );
});

els.copyRoom.addEventListener("click", copyRoomCode);

els.leave.addEventListener("click", () => {
  requestLeave();
});

els.mobile.leave?.addEventListener("click", () => {
  requestLeave();
});

els.restart.addEventListener("click", sendRestart);
els.kickOpponent?.addEventListener("click", sendKickOpponent);

els.mobile.restart?.addEventListener("click", sendRestart);
els.mobile.kickOpponent?.addEventListener("click", sendKickOpponent);

els.mobile.resultLeave?.addEventListener("click", () => {
  returnToLobby("로비로 돌아왔습니다.");
});

els.soundToggle.addEventListener("click", () => {
  unlockSound();
  setSoundEnabled(!soundState.enabled || soundState.volume === 0);
  if (soundState.volume === 0) setSoundVolume(72);
});

els.soundVolume.addEventListener("input", () => {
  unlockSound();
  setSoundVolume(els.soundVolume.value);
});

document.addEventListener("click", (event) => {
  unlockSound();

  const streamerQueueToggle = event.target.closest("[data-streamer-queue-toggle]");
  if (streamerQueueToggle) {
    state.streamerQueueOpen = !state.streamerQueueOpen;
    requestRender();
    return;
  }

  const waitingEmoticonChoice = event.target.closest("[data-waiting-emoticon-id]");
  if (waitingEmoticonChoice) {
    state.waitingEmoticonPickerOpen = false;
    sendWaitingEmoticon(waitingEmoticonChoice.dataset.waitingEmoticonId);
    requestRender();
    return;
  }

  const waitingEmoticonToggle = event.target.closest("[data-waiting-emoticon-toggle]");
  if (waitingEmoticonToggle) {
    state.waitingEmoticonPickerOpen = !state.waitingEmoticonPickerOpen;
    requestRender();
    return;
  }

  const readyButton = event.target.closest("[data-ready-player]");
  if (readyButton) {
    if (!readyButton.disabled) sendReady();
    return;
  }

  const emoticonChoice = event.target.closest("[data-emoticon-id]");
  if (emoticonChoice) {
    sendEmoticon(emoticonChoice.dataset.emoticonId);
    return;
  }

  const emoticonToggle = event.target.closest("[data-emoticon-toggle]");
  if (emoticonToggle) {
    if (emoticonToggle.disabled) return;
    const player = Number(emoticonToggle.dataset.player);
    state.emoticonPickerPlayer = state.emoticonPickerPlayer === player ? null : player;
    requestRender();
    return;
  }

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
    const phase = state.snapshot.game.phase;
    if (phase === "place_normal" && isEggTargetLegal(player, fieldIndex)) {
      sendAction("place_normal", { field: fieldIndex });
      return;
    }
    if (!isFieldLegal(player, fieldIndex)) return;
    if (phase === "place_normal") sendAction("place_normal", { field: fieldIndex });
    if (phase === "place_bonus") {
      sendAction("place_bonus", { targetPlayer: player, field: fieldIndex });
    }
    return;
  }

});

els.nicknameInput.value = localStorage.getItem("tikatuka.nickname") || "";
setupSound();
updateMobileStageScale();
window.addEventListener("resize", updateMobileStageScale);
window.addEventListener("orientationchange", updateMobileStageScale);
window.visualViewport?.addEventListener("resize", updateMobileStageScale);
window.visualViewport?.addEventListener("scroll", updateMobileStageScale);
if (IS_MOBILE_DEMO) {
  startMobileDemo();
} else {
  setRoomMode(false);
  setStatus("");
  renderLobbyStatus();
  refreshStatus();
  window.setInterval(refreshStatus, 30000);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refreshStatus();
  });
}
window.setInterval(() => {
  if (!state.snapshot || els.gameShell.hidden) return;
  renderClocks(state.snapshot.room, state.snapshot.game);
  const { me, opponent } = mobilePlayers(state.snapshot.you);
  renderMobileClocks(state.snapshot.room, state.snapshot.game, me, opponent);
  sendTimeoutCheck();
}, 500);
