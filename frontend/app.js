const DEFAULT_PLAYER_NAMES = ["FrangGabriel", "레온하트 네리아"];
const SOUND_FILES = {
  roll: "./sound_samples/roll.m4a",
  place: "./sound_samples/place.m4a",
  egg: "./sound_samples/egg.m4a",
};

const DEMO_MODE = new URLSearchParams(window.location.search).get("demo");
const CUSTOMIZE_PREVIEW_TAB = new URLSearchParams(window.location.search).get("customize");
const IS_MOBILE_DEMO = DEMO_MODE === "mobile";
const IS_TIER_DEMO = DEMO_MODE === "tier";
const IS_TIER_LOBBY_DEMO = DEMO_MODE === "tier-lobby";
const IS_TOURNAMENT_DEMO = DEMO_MODE === "tournament";
const MOBILE_STAGE_WIDTH = 390;
const MOBILE_STAGE_HEIGHT = 844;
const DEFAULT_EMOTICONS = [
  { id: "gogo", label: "가자", src: "./emoticon/gogo.png", pack: "기본" },
  { id: "lol", label: "웃음", src: "./emoticon/lol.png", pack: "기본" },
  { id: "sad", label: "슬픔", src: "./emoticon/sad.png", pack: "기본" },
  { id: "stop", label: "멈춰", src: "./emoticon/stop.png", pack: "기본" },
  { id: "what", label: "뭐야", src: "./emoticon/what.png", pack: "기본" },
  { id: "whatwhat", label: "뭐뭐", src: "./emoticon/whatwhat.png", pack: "기본" },
];
const DEFAULT_EMOTICON_LOADOUT = DEFAULT_EMOTICONS.map((item) => item.id);
const EMOTICON_SLOT_COUNT = 6;
const BOARD_SKINS = [
  { id: "premium-wood", label: "우드" },
  { id: "casino-felt", label: "펠트" },
  { id: "neon-arcade", label: "네온" },
  { id: "pastel-cafe", label: "파스텔" },
  { id: "ice-crystal", label: "아이스" },
  { id: "dancheong-festival", label: "단청" },
];
const DEFAULT_BOARD_SKIN = "premium-wood";
const TITLE_CLASS_TOKEN = /^[a-z0-9-]+$/;
const TIER_LABELS = {
  bronze: "브론즈",
  silver: "실버",
  gold: "골드",
  platinum: "플레티넘",
  diamond: "다이아",
  master: "마스터",
};
const TIER_GRADE_LABELS = {
  1: "I",
  2: "II",
  3: "III",
  4: "IV",
  5: "V",
};

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
const CLIENT_ID_STORAGE_KEY = "tikatuka.clientId";
const NICKNAME_STORAGE_KEY = "tikatuka.nickname";
const BOARD_SKIN_STORAGE_KEY = "tikatuka.boardSkin";
const EMOTICON_LOADOUT_STORAGE_KEY = "tikatuka.emoticonLoadout";
const CLIENT_ID_MIGRATION_VERSION = "20260701-http-to-https";
const CLIENT_ID_MIGRATION_DONE_KEY = "tikatuka.clientIdMigrationDone";
const CLIENT_ID_MIGRATION_ATTEMPT_KEY = "tikatuka.clientIdMigrationAttempted";

applyClientIdMigrationFromHash();
bridgeClientIdBetweenHttpAndHttps();

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
  tournamentSetupOpen: false,
  tournamentHostParticipates: null,
  tournamentSize: null,
  tournamentTargetWins: null,
  tournamentManualSlots: [],
  tournamentManualKey: "",
  tournamentPickedId: null,
  tournamentDraggedId: null,
  boardSkin: initialBoardSkin(),
  customizeOpen: false,
  customizeTab: "board",
  customizeSelectedSlot: 0,
  emoticonCatalog: [...DEFAULT_EMOTICONS],
  emoticonLoadout: initialEmoticonLoadout(),
  emoticonDraftLoadout: initialEmoticonLoadout(),
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
  tournamentSeedUntil: 0,
  tournamentStartUntil: 0,
  tournamentAdvanceUntil: 0,
  tournamentChampionUntil: 0,
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
  titleCabinet: document.querySelector("#title-cabinet"),
  titleList: document.querySelector("#title-list"),
  titleUnequip: document.querySelector("#title-unequip-button"),
  boardSkinOptions: document.querySelector("#board-skin-options"),
  customizeOpen: document.querySelector("#customize-button"),
  customizeModal: document.querySelector("#customize-modal"),
  customizeTabs: document.querySelectorAll("[data-customize-tab]"),
  customizePanes: document.querySelectorAll("[data-customize-pane]"),
  customizeEmoticonSlots: document.querySelector("#customize-emoticon-slots"),
  customizeEmoticonCatalog: document.querySelector("#customize-emoticon-catalog"),
  customizeEmoticonCount: document.querySelector("#customize-emoticon-count"),
  leaderboard: document.querySelector("#leaderboard"),
  nicknameInput: document.querySelector("#nickname-input"),
  randomMatch: document.querySelector("#random-match-button"),
  createRoom: document.querySelector("#create-room-button"),
  createStreamerRoom: document.querySelector("#create-streamer-room-button"),
  createTournamentRoom: document.querySelector("#create-tournament-room-button"),
  createTournamentConfirm: document.querySelector("#create-tournament-confirm-button"),
  streamerQueueLimit: document.querySelector("#streamer-queue-limit"),
  tournamentSetup: document.querySelector("#tournament-setup"),
  joinForm: document.querySelector("#join-form"),
  roomCodeInput: document.querySelector("#room-code-input"),
  roomCode: document.querySelector("#room-code"),
  copyRoom: document.querySelector("#copy-room-button"),
  connectionStatus: document.querySelector("#connection-status"),
  friendlyRecord: document.querySelector("#friendly-record"),
  friendlyRecordScore: document.querySelector("#friendly-record-score"),
  leave: document.querySelector("#leave-button"),
  surrender: document.querySelector("#surrender-button"),
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
  tournamentPanel: document.querySelector("#tournament-panel"),
  tournamentSummary: document.querySelector("#tournament-summary"),
  tournamentStateText: document.querySelector("#tournament-state-text"),
  tournamentVersus: document.querySelector("#tournament-versus"),
  tournamentHostName: document.querySelector("#tournament-host-name"),
  tournamentParticipantCount: document.querySelector("#tournament-participant-count"),
  tournamentParticipantList: document.querySelector("#tournament-participant-list"),
  tournamentBracket: document.querySelector("#tournament-bracket"),
  tournamentControls: document.querySelector("#tournament-controls"),
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
    surrender: document.querySelector("#mobile-surrender-button"),
    resultBanner: document.querySelector("#mobile-result-banner"),
    resultWinnerText: document.querySelector("#mobile-result-winner-text"),
    restart: document.querySelector("#mobile-restart-button"),
    kickOpponent: document.querySelector("#mobile-kick-opponent-button"),
    resultLeave: document.querySelector("#mobile-result-leave-button"),
    waitingEmoticonStage: document.querySelector("#mobile-waiting-emoticon-stage"),
  },
};

function getClientId() {
  const existing = localStorage.getItem(CLIENT_ID_STORAGE_KEY);
  if (existing) return existing;
  const created =
    crypto.randomUUID?.() ||
    `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  localStorage.setItem(CLIENT_ID_STORAGE_KEY, created);
  return created;
}

function normalizeBoardSkinId(value) {
  const skinId = String(value || "").trim();
  return BOARD_SKINS.some((skin) => skin.id === skinId) ? skinId : DEFAULT_BOARD_SKIN;
}

function initialBoardSkin() {
  const querySkin = new URLSearchParams(window.location.search).get("skin");
  return normalizeBoardSkinId(querySkin || localStorage.getItem(BOARD_SKIN_STORAGE_KEY));
}

function initialEmoticonLoadout() {
  const fallback = [...DEFAULT_EMOTICON_LOADOUT];
  try {
    const parsed = JSON.parse(localStorage.getItem(EMOTICON_LOADOUT_STORAGE_KEY) || "[]");
    if (!Array.isArray(parsed)) return fallback;
    const sanitized = [];
    for (const id of parsed) {
      const cleanId = String(id || "").trim();
      if (!/^[a-z0-9_-]{1,40}$/.test(cleanId) || sanitized.includes(cleanId)) continue;
      sanitized.push(cleanId);
      if (sanitized.length >= EMOTICON_SLOT_COUNT) break;
    }
    return sanitized.length ? sanitized : fallback;
  } catch {
    return fallback;
  }
}

function applyBoardSkin(skinId, options = {}) {
  const normalized = normalizeBoardSkinId(skinId);
  state.boardSkin = normalized;
  document.body.dataset.boardSkin = normalized;
  if (options.persist) {
    localStorage.setItem(BOARD_SKIN_STORAGE_KEY, normalized);
  }
  renderBoardSkinOptions();
}

function renderBoardSkinOptions() {
  document
    .querySelectorAll("[data-board-skin]")
    .forEach((button) => {
      const selected = button.dataset.boardSkin === state.boardSkin;
      button.classList.toggle("is-selected", selected);
      button.setAttribute("aria-pressed", selected ? "true" : "false");
    });
}

function catalogItems() {
  return state.emoticonCatalog?.length ? state.emoticonCatalog : DEFAULT_EMOTICONS;
}

function catalogMap() {
  return new Map(catalogItems().map((item) => [item.id, item]));
}

function normalizeEmoticonLoadout(loadout, catalog = catalogItems()) {
  const allowed = new Set(catalog.map((item) => item.id));
  const normalized = [];
  for (const id of loadout || []) {
    const cleanId = String(id || "").trim();
    if (!allowed.has(cleanId) || normalized.includes(cleanId)) continue;
    normalized.push(cleanId);
    if (normalized.length >= EMOTICON_SLOT_COUNT) break;
  }
  for (const id of DEFAULT_EMOTICON_LOADOUT) {
    if (!allowed.has(id) || normalized.includes(id)) continue;
    normalized.push(id);
    if (normalized.length >= EMOTICON_SLOT_COUNT) break;
  }
  for (const item of catalog) {
    if (normalized.includes(item.id)) continue;
    normalized.push(item.id);
    if (normalized.length >= EMOTICON_SLOT_COUNT) break;
  }
  return normalized.slice(0, EMOTICON_SLOT_COUNT);
}

function loadoutItems(loadout = state.emoticonLoadout) {
  const map = catalogMap();
  return normalizeEmoticonLoadout(loadout).map((id) => map.get(id)).filter(Boolean);
}

function findEmoticon(emoticon) {
  return catalogMap().get(String(emoticon || "").trim()) || null;
}

async function loadEmoticonCatalog() {
  try {
    const response = await fetch("./emoticon/catalog.json?v=20260707-emoticon-catalog-1", {
      cache: "no-cache",
    });
    if (!response.ok) throw new Error(await response.text());
    const data = await response.json();
    const items = Array.isArray(data.items)
      ? data.items
          .map((item) => ({
            id: String(item.id || "").trim(),
            label: String(item.label || item.id || "").trim(),
            src: String(item.src || "").trim(),
            pack: String(item.pack || "기타").trim(),
          }))
          .filter((item) => item.id && item.src)
      : [];
    if (items.length >= DEFAULT_EMOTICONS.length) {
      state.emoticonCatalog = items;
      state.emoticonLoadout = normalizeEmoticonLoadout(state.emoticonLoadout, items);
      state.emoticonDraftLoadout = normalizeEmoticonLoadout(state.emoticonLoadout, items);
    }
  } catch {
    state.emoticonCatalog = [...DEFAULT_EMOTICONS];
    state.emoticonLoadout = normalizeEmoticonLoadout(state.emoticonLoadout, state.emoticonCatalog);
    state.emoticonDraftLoadout = [...state.emoticonLoadout];
  }
  renderCustomize();
  requestRender();
}

function shouldRunClientIdMigration() {
  return (
    !IS_MOBILE_DEMO &&
    !IS_TIER_DEMO &&
    !IS_TIER_LOBBY_DEMO &&
    window.location.hostname === "tikatuka.duckdns.org"
  );
}

function isValidClientId(value) {
  return /^[a-zA-Z0-9_-]{6,120}$/.test(String(value || ""));
}

function normalizedStoredNickname(value) {
  return String(value || "")
    .trim()
    .replace(/\s+/g, " ")
    .slice(0, 16);
}

function applyClientIdMigrationFromHash() {
  if (!shouldRunClientIdMigration()) return false;
  const rawHash = window.location.hash.startsWith("#")
    ? window.location.hash.slice(1)
    : window.location.hash;
  if (!rawHash) return false;
  const params = new URLSearchParams(rawHash);
  const migratedClientId = params.get("tikatuka_client_id");
  const migratedNickname = normalizedStoredNickname(params.get("tikatuka_nickname"));
  const missingClientId = params.get("tikatuka_client_id_missing");
  let changed = false;

  if (isValidClientId(migratedClientId)) {
    localStorage.setItem(CLIENT_ID_STORAGE_KEY, migratedClientId);
    localStorage.setItem(CLIENT_ID_MIGRATION_DONE_KEY, CLIENT_ID_MIGRATION_VERSION);
    params.delete("tikatuka_client_id");
    changed = true;
  } else if (missingClientId) {
    localStorage.setItem(CLIENT_ID_MIGRATION_DONE_KEY, CLIENT_ID_MIGRATION_VERSION);
    params.delete("tikatuka_client_id_missing");
    changed = true;
  }
  if (migratedNickname) {
    localStorage.setItem(NICKNAME_STORAGE_KEY, migratedNickname);
    params.delete("tikatuka_nickname");
    changed = true;
  }

  if (changed) {
    const nextHash = params.toString();
    window.history.replaceState(
      null,
      "",
      `${window.location.pathname}${window.location.search}${nextHash ? `#${nextHash}` : ""}`,
    );
  }
  return changed;
}

function bridgeClientIdBetweenHttpAndHttps() {
  if (!shouldRunClientIdMigration()) return;
  const url = new URL(window.location.href);
  const isMigrationHop = url.searchParams.get("client_id_migrate") === "1";

  if (window.location.protocol === "http:") {
    const clientId = localStorage.getItem(CLIENT_ID_STORAGE_KEY);
    const nickname = normalizedStoredNickname(localStorage.getItem(NICKNAME_STORAGE_KEY));
    const target = new URL(window.location.href);
    target.protocol = "https:";
    target.searchParams.delete("client_id_migrate");
    target.searchParams.delete("_");
    const hashParams = new URLSearchParams();
    if (isValidClientId(clientId)) {
      hashParams.set("tikatuka_client_id", clientId);
    } else {
      hashParams.set("tikatuka_client_id_missing", "1");
    }
    if (nickname) {
      hashParams.set("tikatuka_nickname", nickname);
    }
    target.hash = hashParams.toString();
    localStorage.setItem(CLIENT_ID_MIGRATION_DONE_KEY, CLIENT_ID_MIGRATION_VERSION);
    window.location.replace(target.toString());
    return;
  }

  if (window.location.protocol !== "https:") return;
  if (isMigrationHop) {
    url.searchParams.delete("client_id_migrate");
    url.searchParams.delete("_");
    localStorage.setItem(CLIENT_ID_MIGRATION_DONE_KEY, CLIENT_ID_MIGRATION_VERSION);
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
    return;
  }
  if (localStorage.getItem(CLIENT_ID_MIGRATION_DONE_KEY) === CLIENT_ID_MIGRATION_VERSION) return;
  if (sessionStorage.getItem(CLIENT_ID_MIGRATION_ATTEMPT_KEY) === CLIENT_ID_MIGRATION_VERSION) return;
  sessionStorage.setItem(CLIENT_ID_MIGRATION_ATTEMPT_KEY, CLIENT_ID_MIGRATION_VERSION);

  const target = new URL(window.location.href);
  target.protocol = "http:";
  target.searchParams.set("client_id_migrate", "1");
  target.searchParams.set("_", Date.now().toString(36));
  target.hash = "";
  window.location.replace(target.toString());
}

function getNickname() {
  const nickname = els.nicknameInput.value.trim().replace(/\s+/g, " ");
  if (!nickname) {
    setStatus("사용할 닉네임을 입력해주세요.");
    els.nicknameInput.focus();
    return null;
  }
  const clipped = nickname.slice(0, 16);
  localStorage.setItem(NICKNAME_STORAGE_KEY, clipped);
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
    document.body.classList.remove("tournament-room");
    state.streamerQueueOpen = false;
    state.tournamentSetupOpen = false;
    state.tournamentManualSlots = [];
    state.tournamentManualKey = "";
    state.tournamentPickedId = null;
  }
  els.lobby.hidden = inRoom;
  els.gameShell.hidden = !inRoom;
  if (!inRoom) renderTournamentSetupControls();
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
  document.querySelectorAll(".tournament-seed-flyer").forEach((element) => element.remove());
  document.querySelectorAll(".tournament-advance-flyer").forEach((element) => element.remove());
  document.querySelectorAll(".tournament-champion-burst").forEach((element) => element.remove());
  document
    .querySelectorAll(".mobile-player-card.has-emoticon")
    .forEach((element) => element.classList.remove("has-emoticon"));
  fx.startBanner = null;
  fx.tournamentSeedUntil = 0;
  fx.tournamentStartUntil = 0;
  fx.tournamentAdvanceUntil = 0;
  fx.tournamentChampionUntil = 0;
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
  setStatus("스트리머 모드 방 만드는 중...");
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

async function createTournamentRoom() {
  unlockSound();
  const nickname = getNickname();
  if (!nickname) return;
  if (!isTournamentSetupComplete()) {
    setStatus("토너먼트 설정을 모두 선택해주세요.");
    renderTournamentSetupControls();
    return;
  }
  const size = state.tournamentSize;
  const targetWins = state.tournamentTargetWins;
  const hostParticipates = state.tournamentHostParticipates;
  setStatus("토너먼트 방 만드는 중...");
  const response = await fetch(apiUrl("/api/tournament-rooms"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      clientId: state.clientId,
      nickname,
      size,
      targetWins,
      hostParticipates,
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

async function equipTitle(titleId) {
  if (!titleId) return;
  setStatus("칭호 장착 중...");
  const response = await fetch(apiUrl("/api/titles/equip"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      clientId: state.clientId,
      titleId,
    }),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || "칭호를 장착할 수 없습니다.");
  }
  state.status = await response.json();
  renderLobbyStatus();
  setStatus("칭호를 장착했습니다.");
}

async function unequipTitle() {
  setStatus("칭호 장착 해제 중...");
  const response = await fetch(apiUrl("/api/titles/unequip"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      clientId: state.clientId,
    }),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || "칭호를 해제할 수 없습니다.");
  }
  state.status = await response.json();
  renderLobbyStatus();
  setStatus("칭호 장착을 해제했습니다.");
}

function renderLobbyStatus() {
  const onlineUsers = state.status?.onlineUsers ?? 0;
  const stats = state.status?.stats || { score: 0, wins: 0, losses: 0, streak: 0 };
  const lobbyStats = {
    ...stats,
    tier: stats.tier || { tier: "bronze", grade: 5, stars: 0 },
  };
  const leaderboard = state.status?.leaderboard || [];
  els.onlineUsers.textContent = `접속 ${onlineUsers}명`;
  els.myRating.innerHTML = `
    <div class="lobby-tier-header">
      <span>내 티어</span>
      <span class="tier-help-wrap">
        <button class="tier-help-button" type="button" aria-label="티어 시스템 설명">?</button>
        <span class="tier-help-tooltip" role="tooltip">
          <strong>티어 시스템</strong>
          <span>브론즈→실버→골드→플레티넘→다이아→마스터</span>
          <span>승리 +1별, 패배 -1별 · 등급 강등 없음</span>
          <span>3연승부터 +2별, 5연승부터 +3별</span>
          <span>내가 낮은 티어면 패배해도 별 보호</span>
          <span>마스터는 100점 시작 · 승리 +10~15점, 패배 -10점</span>
        </span>
      </span>
    </div>
    <div class="lobby-tier-main">
      ${tierBadge(lobbyStats)}
      <span class="lobby-tier-record">${stats.wins}승 / ${stats.losses}패</span>
    </div>
    <small>${lobbyStreakText(stats)}</small>
  `;
  renderTitleCabinet(stats);
  els.leaderboard.innerHTML = leaderboard.length
    ? leaderboard
        .map((entry, index) => {
          const entryName = escapeHtml(entry.name || "플레이어");
          return `
            <li class="${entry.clientId === state.clientId ? "is-me" : ""}">
              <span class="rank-no">${index + 1}</span>
              <strong title="${entryName}">${entryName}</strong>
              <em>${tierBadge(entry) || `${entry.score}점`}</em>
              <small>${entry.wins}승/${entry.losses}패</small>
            </li>
          `;
        })
        .join("")
    : `<li class="empty-ranking">아직 랭킹 기록이 없습니다.</li>`;
}

function lobbyStreakText(stats) {
  if (stats.streak > 0) return `${stats.streak}연승 중`;
  if (stats.streak < 0) return `${Math.abs(stats.streak)}연패 중`;
  return "연승 기록 없음";
}

function openCustomize(tab = state.customizeTab || "board") {
  state.customizeOpen = true;
  state.emoticonDraftLoadout = normalizeEmoticonLoadout(state.emoticonLoadout);
  state.customizeSelectedSlot = Math.min(
    Math.max(0, state.customizeSelectedSlot || 0),
    EMOTICON_SLOT_COUNT - 1,
  );
  setCustomizeTab(tab);
  renderCustomize();
}

function closeCustomize() {
  state.customizeOpen = false;
  if (els.customizeModal) els.customizeModal.hidden = true;
}

function setCustomizeTab(tab) {
  state.customizeTab = tab === "emoticon" ? "emoticon" : "board";
  renderCustomize();
}

function renderCustomize() {
  if (!els.customizeModal) return;
  els.customizeModal.hidden = !state.customizeOpen;
  els.customizeTabs?.forEach((button) => {
    const selected = button.dataset.customizeTab === state.customizeTab;
    button.classList.toggle("is-selected", selected);
    button.setAttribute("aria-selected", selected ? "true" : "false");
  });
  els.customizePanes?.forEach((pane) => {
    pane.hidden = pane.dataset.customizePane !== state.customizeTab;
  });
  renderBoardSkinOptions();
  renderCustomizeEmoticons();
}

function renderCustomizeEmoticons() {
  if (!els.customizeEmoticonSlots || !els.customizeEmoticonCatalog) return;
  const map = catalogMap();
  const draft = normalizeEmoticonLoadout(state.emoticonDraftLoadout);
  state.emoticonDraftLoadout = draft;
  if (state.customizeSelectedSlot >= draft.length) state.customizeSelectedSlot = 0;
  const equipped = new Set(draft);
  els.customizeEmoticonSlots.innerHTML = draft
    .map((id, index) => {
      const item = map.get(id) || DEFAULT_EMOTICONS[index] || DEFAULT_EMOTICONS[0];
      return `
        <button
          type="button"
          class="customize-emoticon-slot ${index === state.customizeSelectedSlot ? "is-selected" : ""}"
          data-customize-emoticon-slot="${index}"
          aria-pressed="${index === state.customizeSelectedSlot ? "true" : "false"}"
          title="${escapeHtml(item.label)}"
        >
          <span>${index + 1}</span>
          <img src="${escapeHtml(item.src)}" alt="" draggable="false" />
        </button>
      `;
    })
    .join("");

  const items = catalogItems();
  if (els.customizeEmoticonCount) {
    els.customizeEmoticonCount.textContent = `${items.length}개`;
  }
  els.customizeEmoticonCatalog.innerHTML = items
    .map((item) => {
      const isEquipped = equipped.has(item.id);
      const isActive = draft[state.customizeSelectedSlot] === item.id;
      return `
        <button
          type="button"
          class="customize-emoticon-option ${isEquipped ? "is-equipped" : ""} ${isActive ? "is-active" : ""}"
          data-customize-emoticon-id="${escapeHtml(item.id)}"
          draggable="true"
          title="${escapeHtml(`${item.pack || "기타"} · ${item.label}`)}"
        >
          <img src="${escapeHtml(item.src)}" alt="" loading="lazy" draggable="false" />
        </button>
      `;
    })
    .join("");
}

function setDraftEmoticonSlot(slotIndex, emoticonId) {
  const map = catalogMap();
  const slot = Math.min(Math.max(0, Number(slotIndex) || 0), EMOTICON_SLOT_COUNT - 1);
  if (!map.has(emoticonId)) return;
  const draft = normalizeEmoticonLoadout(state.emoticonDraftLoadout);
  const previousIndex = draft.indexOf(emoticonId);
  if (previousIndex >= 0 && previousIndex !== slot) {
    draft[previousIndex] = draft[slot];
  }
  draft[slot] = emoticonId;
  state.emoticonDraftLoadout = normalizeEmoticonLoadout(draft);
  state.customizeSelectedSlot = Math.min(slot + 1, EMOTICON_SLOT_COUNT - 1);
  renderCustomizeEmoticons();
}

function saveEmoticonLoadout() {
  state.emoticonLoadout = normalizeEmoticonLoadout(state.emoticonDraftLoadout);
  localStorage.setItem(EMOTICON_LOADOUT_STORAGE_KEY, JSON.stringify(state.emoticonLoadout));
  state.emoticonPickerPlayer = null;
  state.waitingEmoticonPickerOpen = false;
  closeCustomize();
  setStatus("이모티콘 설정을 저장했습니다.");
  requestRender();
}

function resetDraftEmoticonLoadout() {
  state.emoticonDraftLoadout = normalizeEmoticonLoadout(DEFAULT_EMOTICON_LOADOUT);
  state.customizeSelectedSlot = 0;
  renderCustomizeEmoticons();
}

function normalizeTournamentSize(value) {
  return [4, 8, 16].includes(Number(value)) ? Number(value) : 4;
}

function normalizeTournamentTargetWins(value) {
  return [1, 2, 3].includes(Number(value)) ? Number(value) : 1;
}

function normalizeTournamentHostParticipates(value) {
  if (value === true || value === "true") return true;
  if (value === false || value === "false") return false;
  return null;
}

function isTournamentSetupComplete() {
  return (
    state.tournamentHostParticipates !== null &&
    [4, 8, 16].includes(Number(state.tournamentSize)) &&
    [1, 2, 3].includes(Number(state.tournamentTargetWins))
  );
}

function tournamentFormatText(targetWins) {
  if (Number(targetWins) === 2) return "3판2선승";
  if (Number(targetWins) === 3) return "5판3선승";
  return "단판";
}

function setTournamentSize(size) {
  state.tournamentSize = normalizeTournamentSize(size);
  renderTournamentSetupControls();
}

function setTournamentTargetWins(targetWins) {
  state.tournamentTargetWins = normalizeTournamentTargetWins(targetWins);
  renderTournamentSetupControls();
}

function setTournamentHostParticipates(value) {
  state.tournamentHostParticipates = normalizeTournamentHostParticipates(value);
  renderTournamentSetupControls();
}

function renderTournamentSetupControls() {
  if (els.tournamentSetup) {
    els.tournamentSetup.hidden = !state.tournamentSetupOpen;
  }
  if (els.createTournamentRoom) {
    els.createTournamentRoom.setAttribute(
      "aria-expanded",
      state.tournamentSetupOpen ? "true" : "false",
    );
  }
  document.querySelectorAll("[data-tournament-size]").forEach((button) => {
    button.classList.toggle(
      "is-selected",
      Number(button.dataset.tournamentSize) === state.tournamentSize,
    );
  });
  document.querySelectorAll("[data-tournament-target-wins]").forEach((button) => {
    button.classList.toggle(
      "is-selected",
      Number(button.dataset.tournamentTargetWins) === state.tournamentTargetWins,
    );
  });
  document.querySelectorAll("[data-tournament-host-participates]").forEach((button) => {
    button.classList.toggle(
      "is-selected",
      normalizeTournamentHostParticipates(button.dataset.tournamentHostParticipates) ===
        state.tournamentHostParticipates,
    );
  });
  if (els.createTournamentConfirm) {
    els.createTournamentConfirm.disabled = !isTournamentSetupComplete();
  }
}

function toggleTournamentSetup(force) {
  state.tournamentSetupOpen =
    typeof force === "boolean" ? force : !state.tournamentSetupOpen;
  renderTournamentSetupControls();
  setStatus(state.tournamentSetupOpen ? "토너먼트 설정을 선택해주세요." : "");
}

function renderTitleCabinet(stats) {
  if (!els.titleList) return;
  const titles = Array.isArray(stats?.titles) ? stats.titles : [];
  if (els.titleUnequip) {
    els.titleUnequip.disabled = !stats?.title;
  }
  els.titleList.innerHTML = titles.length
    ? titles
        .map((title) => {
          const equipped = Boolean(title.equipped);
          return `
            <li>
              <button
                class="title-choice ${equipped ? "is-equipped" : ""}"
                type="button"
                data-title-id="${escapeHtml(title.id)}"
                ${equipped ? 'aria-pressed="true"' : 'aria-pressed="false"'}
              >
                ${titleBadge({ title })}
                <span>${equipped ? "장착중" : "클릭 장착"}</span>
              </button>
            </li>
          `;
        })
        .join("")
    : `<li class="empty-title">보유 칭호가 없습니다.</li>`;
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

function sendSurrender() {
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
    setStatus("서버와 연결되어 있지 않습니다.");
    return;
  }
  if (!isGameInProgress()) {
    setStatus("진행 중인 게임이 없습니다.");
    return;
  }
  const confirmed = window.confirm("이번 판을 항복하고 패배 처리할까요?");
  if (!confirmed) return;
  state.actionPending = false;
  state.ws.send(JSON.stringify({ type: "surrender" }));
  setStatus("항복 처리 중...");
}

function sendTournamentCommand(type, payload = {}) {
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
    setStatus("서버와 연결되어 있지 않습니다.");
    return;
  }
  state.ws.send(JSON.stringify({ type, ...payload }));
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
  document.body.classList.toggle("tournament-room", Boolean(room.tournamentMode));
  if (els.waitingEmoticonStage) {
    els.waitingEmoticonStage.hidden = !room.streamerMode;
  }
  if (els.mobile.waitingEmoticonStage) {
    els.mobile.waitingEmoticonStage.hidden = !room.streamerMode;
  }
  processFx(snapshot);
  els.roomCode.textContent = room.randomMatch ? "랜덤매칭" : room.code;
  els.copyRoom.hidden = Boolean(room.randomMatch);

  const waitText = room.tournamentMode
    ? tournamentStatusText(room, game)
    : room.started
      ? phaseText(game)
      : room.streamerMode && room.players[1]?.occupied
        ? "스트리머의 준비를 기다리는 중"
        : "상대 입장 대기 중";
  setStatus(
    state.leaveReserved && room.started && !game.result
      ? "나가기 예약중 · 종료 후 이동"
      : waitText,
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
  renderTournamentPanel(room, game, you);
  renderFriendlyRecord(room);
  maybeAutoLeaveAfterResult(game);
  rememberDieRects();
}

function renderFriendlyRecord(room) {
  const isFriendlyMatch =
    !room.randomMatch &&
    !room.tournamentMode &&
    Boolean(room.players?.[1]?.occupied);
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
  return statsLine;
}

function renderPlayerStatLine(stats) {
  if (!stats) return "";
  const tier = tierBadge(stats);
  const record = `${stats.wins}승 / ${stats.losses}패`;
  const recordText =
    stats.streak > 0
      ? `${record} · <span class="streak-win">${stats.streak}연승 중</span>`
      : stats.streak < 0
        ? `${record} · <span class="streak-loss">${Math.abs(stats.streak)}연패 중</span>`
        : record;
  return `${tier}<span class="player-state-record">${recordText}</span>`;
}

function tierBadge(stats) {
  const tier = stats?.tier;
  if (!tier) return "";
  const key = safeTierToken(tier.tier || tier.key || tier.name);
  if (!key) return "";
  const label = TIER_LABELS[key];
  const detail =
    key === "master"
      ? `${Math.max(0, Number(tier.points) || 0)}점`
      : `${TIER_GRADE_LABELS[Number(tier.grade) || 5] || "V"} ${tierStars(Number(tier.stars) || 0)}`;
  return `
    <span class="tier-badge tier-${key}" aria-label="${escapeHtml(`${label} ${detail}`)}">
      <span class="tier-badge-mark" aria-hidden="true"><span></span><span></span><span></span></span>
      <span class="tier-badge-label">${escapeHtml(label)}</span>
      <span class="tier-badge-detail">${escapeHtml(detail)}</span>
    </span>
  `;
}

function tierStars(stars) {
  const filled = Math.max(0, Math.min(5, Math.floor(stars)));
  return `${"★".repeat(filled)}${"☆".repeat(Math.max(0, 3 - filled))}`;
}

function safeTierToken(value) {
  const token = String(value || "").trim().toLowerCase().replace(/_/g, "-");
  return Object.hasOwn(TIER_LABELS, token) ? token : "";
}

function renderPlayerNameWithRank(roomPlayer) {
  const name = escapeHtml(roomPlayer?.name || "플레이어");
  const stats = roomPlayer?.stats;
  const title = titleBadge(stats);
  return `${title}<span class="player-name-text">${name}</span>`;
}

function titleBadge(stats) {
  const title = stats?.title;
  if (!title?.label) return "";
  const color = safeTitleToken(title.color, "gold");
  const effect = safeTitleToken(title.effect, "glow");
  const icon = titleIconMarkup(title);
  return `
    <span class="title-badge title-color-${color} title-effect-${effect}" aria-label="칭호 ${escapeHtml(title.label)}">
      ${icon}<span>${escapeHtml(title.label)}</span>
    </span>
  `;
}

function titleIconMarkup(title) {
  if (title?.icon === "duelist") {
    return `
      <span class="title-badge-duelist-die" aria-hidden="true">
        <span></span><span></span><span></span>
      </span>
    `;
  }
  if (title?.icon === "mirang") {
    return `
      <span class="title-badge-mirang-mark" aria-hidden="true">
        <svg viewBox="0 0 100 100" focusable="false">
          <path d="M36 14H80L63 40H92L63 66H83V87H18L42 59H10L36 14Z" />
        </svg>
      </span>
    `;
  }
  return title?.iconText
    ? `<span class="title-badge-icon">${escapeHtml(title.iconText)}</span>`
    : "";
}

function safeTitleToken(value, fallback) {
  const token = String(value || fallback).trim().toLowerCase().replace(/_/g, "-");
  return TITLE_CLASS_TOKEN.test(token) ? token : fallback;
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

  if (event.type === "tournament_seeded") {
    fx.tournamentSeedUntil = Date.now() + 4300;
    markAnimation(4300);
    window.setTimeout(() => showTournamentSeedFlyers(snapshot), 80);
    return;
  }

  if (event.type === "tournament_match_started") {
    fx.tournamentStartUntil = Date.now() + 1400;
    markAnimation(1400);
    return;
  }

  if (event.type === "tournament_match_finished") {
    const duration = 3600;
    fx.tournamentAdvanceUntil = Date.now() + duration;
    markAnimation(duration);
    window.setTimeout(() => showTournamentAdvanceFlyer(snapshot, event), 110);
    return;
  }

  if (event.type === "tournament_finished") {
    const duration = 4200;
    fx.tournamentChampionUntil = Date.now() + duration;
    markAnimation(duration);
    window.setTimeout(() => showTournamentChampionBurst(event), 80);
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

function showTournamentSeedFlyers(snapshot) {
  const tournament = snapshot?.room?.tournament;
  if (!snapshot?.room?.tournamentMode || !tournament || !els.tournamentBracket) return;
  if (els.tournamentPanel?.hidden) return;
  const targets = [
    ...els.tournamentBracket.querySelectorAll(
      ".tournament-round:first-child [data-tournament-target-id]:not([data-tournament-target-id=''])",
    ),
  ];
  if (!targets.length) return;

  const fallbackSource =
    els.tournamentParticipantList?.getBoundingClientRect() ||
    els.tournamentPanel.getBoundingClientRect();
  targets.forEach((target, index) => {
    const clientId = target.dataset.tournamentTargetId;
    const sourceElement = els.tournamentParticipantList?.querySelector(
      `[data-tournament-participant-id="${cssEscape(clientId)}"]`,
    );
    const sourceRect = sourceElement?.getBoundingClientRect() || fallbackSource;
    const targetRect = target.getBoundingClientRect();
    if (!targetRect.width || !targetRect.height) return;

    const flyer = document.createElement("div");
    flyer.className = "tournament-seed-flyer";
    flyer.textContent =
      target.querySelector("span")?.textContent?.trim().replace(/\s+/g, " ") ||
      sourceElement?.textContent?.trim().replace(/\s+/g, " ") ||
      "참가자";
    const width = Math.min(Math.max(targetRect.width, 120), 220);
    flyer.style.width = `${width}px`;
    flyer.style.left = `${sourceRect.left + sourceRect.width / 2 - width / 2}px`;
    flyer.style.top = `${sourceRect.top + sourceRect.height / 2 - targetRect.height / 2}px`;
    flyer.style.transitionDelay = `${index * 220}ms`;
    document.body.append(flyer);

    window.requestAnimationFrame(() => {
      flyer.classList.add("is-flying");
      flyer.style.left = `${targetRect.left + targetRect.width / 2 - width / 2}px`;
      flyer.style.top = `${targetRect.top + targetRect.height / 2 - targetRect.height / 2}px`;
    });

    window.setTimeout(() => {
      flyer.classList.add("is-done");
    }, index * 220 + 1180);
    window.setTimeout(() => {
      flyer.remove();
    }, index * 220 + 1900);
  });
}

function showTournamentAdvanceFlyer(snapshot, event) {
  const tournament = snapshot?.room?.tournament;
  if (!snapshot?.room?.tournamentMode || !tournament || !els.tournamentBracket) return;
  if (els.tournamentPanel?.hidden) return;

  const rounds = Array.isArray(tournament.rounds) ? tournament.rounds : [];
  const completedMatch = rounds
    .flat()
    .find((match) => match?.matchId && match.matchId === event.matchId);
  const winnerId = completedMatch?.winnerId;
  if (!completedMatch || !winnerId) return;

  const source = els.tournamentBracket.querySelector(
    `[data-tournament-match-id="${cssEscape(completedMatch.matchId)}"] [data-tournament-player-id="${cssEscape(
      winnerId,
    )}"]`,
  );
  const target = els.tournamentBracket.querySelector(
    `[data-tournament-round-index="${Number(completedMatch.roundIndex) + 1}"] [data-tournament-player-id="${cssEscape(
      winnerId,
    )}"]`,
  );
  const sourceRect = source?.getBoundingClientRect();
  const targetRect = target?.getBoundingClientRect();
  if (!sourceRect || !targetRect || !targetRect.width || !targetRect.height) return;

  const flyer = document.createElement("div");
  flyer.className = "tournament-advance-flyer";
  flyer.textContent = `🏆 ${event.winner || completedMatch.winnerName || "승자"}`;
  const width = Math.min(Math.max(sourceRect.width, targetRect.width, 150), 240);
  flyer.style.width = `${width}px`;
  flyer.style.left = `${sourceRect.left + sourceRect.width / 2 - width / 2}px`;
  flyer.style.top = `${sourceRect.top + sourceRect.height / 2 - targetRect.height / 2}px`;
  document.body.append(flyer);

  window.requestAnimationFrame(() => {
    flyer.classList.add("is-flying");
    flyer.style.left = `${targetRect.left + targetRect.width / 2 - width / 2}px`;
    flyer.style.top = `${targetRect.top + targetRect.height / 2 - targetRect.height / 2}px`;
  });

  window.setTimeout(() => {
    flyer.classList.add("is-done");
  }, 1700);
  window.setTimeout(() => {
    flyer.remove();
  }, 2450);
}

function showTournamentChampionBurst(event) {
  if (!els.tournamentPanel || els.tournamentPanel.hidden) return;
  const burst = document.createElement("div");
  burst.className = "tournament-champion-burst";
  burst.innerHTML = `
    <span>🏆</span>
    <strong>${escapeHtml(event.winner || "우승자")} 우승!</strong>
    <em>TOURNAMENT WINNER</em>
  `;
  els.tournamentPanel.append(burst);
  window.requestAnimationFrame(() => {
    burst.classList.add("is-showing");
  });
  window.setTimeout(() => {
    burst.classList.add("is-hiding");
  }, 2800);
  window.setTimeout(() => {
    burst.remove();
  }, 3800);
}

function cssEscape(value) {
  if (window.CSS?.escape) return window.CSS.escape(String(value || ""));
  return String(value || "").replace(/["\\]/g, "\\$&");
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
  if (!findEmoticon(emoticon)) return;
  if (isMobileRoomView()) {
    showMobileEmoticon(player, emoticon);
    return;
  }
  showPcEmoticon(player, emoticon);
}

function showWaitingEmoticon(event) {
  if (!state.snapshot?.room?.streamerMode) return;
  if (!findEmoticon(event.emoticon)) return;
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
  return findEmoticon(emoticon)?.src || `./emoticon/${encodeURIComponent(emoticon)}.png`;
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
  if (game.phase === "place_normal") return "배치 차례";
  if (game.phase === "select_die") return "주사위 선택";
  if (game.phase === "place_bonus") return "보너스 배치";
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
    if (room.tournamentMode && !room.started && !game.result) {
      els.trayControls[player].innerHTML = "";
      continue;
    }

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
  const items = loadoutItems();
  return `
    <div class="${classes}" ${isOpen ? "" : "hidden"}>
      ${items.map(
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
              <strong>${titleBadge(waiting.stats)}${escapeHtml(waiting.name || "대기자")}</strong>
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
          ${loadoutItems().map(
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

function renderTournamentPanel(room, game, you) {
  if (!els.tournamentPanel) return;
  if (!room.tournamentMode || !room.tournament) {
    els.tournamentPanel.hidden = true;
    return;
  }

  const tournament = room.tournament;
  const participants = Array.isArray(tournament.participants)
    ? tournament.participants
    : [];
  const isHost = you.clientId === tournament.hostId;
  ensureTournamentManualSlots(tournament);
  const isSeeding = Date.now() < fx.tournamentSeedUntil;
  const isStarting = Date.now() < fx.tournamentStartUntil;
  const isAdvancing = Date.now() < fx.tournamentAdvanceUntil;
  const isChampion = Date.now() < fx.tournamentChampionUntil;

  els.tournamentPanel.hidden = false;
  els.tournamentPanel.dataset.size = String(tournament.size || 4);
  els.tournamentPanel.classList.toggle("is-seeding", isSeeding);
  els.tournamentPanel.classList.toggle("is-starting-match", isStarting);
  els.tournamentPanel.classList.toggle("is-advancing", isAdvancing);
  els.tournamentPanel.classList.toggle("is-champion", isChampion);
  els.tournamentSummary.textContent = `${tournament.size}인 · ${tournamentFormatText(
    tournament.targetWins,
  )}`;
  els.tournamentStateText.textContent = tournamentStatusText(room, game);
  els.tournamentHostName.innerHTML =
    titleBadge(participantStats(tournament, tournament.hostId)) +
    escapeHtml(tournament.hostName || "방장");
  els.tournamentParticipantCount.textContent = `${participants.length}/${tournament.size}`;
  renderTournamentVersus(room, tournament);
  renderTournamentParticipantList(tournament, isHost);
  renderTournamentBracket(tournament, isHost);
  renderTournamentControls(room, tournament, isHost);
}

function tournamentStatusText(room, game) {
  const tournament = room.tournament || {};
  if (tournament.status === "finished") {
    return `우승 ${tournament.winnerName || "확정"}`;
  }
  if (room.started && !game?.result) return phaseText(game);
  if (room.started && game?.result) return "방장이 시작을 누르면 다음 경기로 진행";
  if (tournament.seeded) return "배치 완료 · 시작 대기";
  const count = Array.isArray(tournament.participants)
    ? tournament.participants.length
    : 0;
  return `참가자 대기 중 ${count}/${tournament.size || 0}`;
}

function renderTournamentVersus(room, tournament) {
  const match = tournament.activeMatch || tournament.nextMatch;
  const players = match?.players || [];
  const names = players.map((player) => player?.name || "대기중");
  if (tournament.status === "finished") {
    els.tournamentVersus.textContent = `🏆 ${tournament.winnerName || "우승자"} 우승`;
    els.tournamentVersus.hidden = false;
    return;
  }
  if (!match || names.length < 2 || names.some((name) => !name || name === "대기중")) {
    els.tournamentVersus.hidden = true;
    return;
  }
  const score = Array.isArray(match.scores)
    ? ` · ${Number(match.scores[0]) || 0}:${Number(match.scores[1]) || 0}`
    : "";
  els.tournamentVersus.textContent = `${names[0]} VS ${names[1]}${score}`;
  els.tournamentVersus.hidden = false;
}

function renderTournamentParticipantList(tournament, isHost) {
  const participants = Array.isArray(tournament.participants)
    ? tournament.participants
    : [];
  const slots = tournamentDisplaySlots(tournament);
  const placed = new Set(slots.filter(Boolean));
  els.tournamentParticipantList.innerHTML = participants.length
    ? participants
        .map((participant, index) => {
          const clientId = participant.clientId || "";
          const classes = [
            participant.active ? "is-active" : "",
            placed.has(clientId) ? "is-placed" : "",
            state.tournamentPickedId === clientId ? "is-picked" : "",
          ]
            .filter(Boolean)
            .join(" ");
          return `
            <li
              class="${classes}"
              ${isHost ? 'draggable="true"' : ""}
              data-tournament-participant-id="${escapeHtml(clientId)}"
            >
              <span>${index + 1}</span>
              <strong>${titleBadge(participant.stats)}${escapeHtml(
                participant.name || "참가자",
              )}</strong>
            </li>
          `;
        })
        .join("")
    : `<li><span>–</span><strong>참가자 없음</strong></li>`;
}

function renderTournamentBracket(tournament, isHost) {
  const rounds = tournamentRoundsForDisplay(tournament);
  els.tournamentBracket.dataset.size = String(tournament.size || 4);
  els.tournamentBracket.innerHTML = rounds
    .map((round, roundIndex) => `
      <section
        class="tournament-round ${roundIndex === rounds.length - 1 ? "is-final-round" : ""}"
        data-tournament-round-index="${roundIndex}"
        style="--match-count: ${round.length}; --round-index: ${roundIndex};"
      >
        <h4>${tournamentRoundName({ ...tournament, rounds }, roundIndex)}</h4>
        <div class="tournament-round-matches">
          ${round
            .map((match) =>
              renderTournamentMatch(tournament, match, isHost, roundIndex === 0),
            )
            .join("")}
        </div>
      </section>
    `)
    .join("");
}

function tournamentRoundsForDisplay(tournament) {
  if (Array.isArray(tournament.rounds) && tournament.rounds.length) {
    return tournament.rounds.map((round) =>
      round.map((match) => ({ ...match, editable: false })),
    );
  }

  const slots = tournamentDisplaySlots(tournament);
  const rounds = [];
  let matchCount = Math.max(1, Math.floor(Number(tournament.size || 4) / 2));
  let roundIndex = 0;
  while (matchCount >= 1) {
    const round = [];
    for (let matchIndex = 0; matchIndex < matchCount; matchIndex += 1) {
      const firstSlot = matchIndex * 2;
      const playerIds =
        roundIndex === 0
          ? [slots[firstSlot] || null, slots[firstSlot + 1] || null]
          : [null, null];
      round.push({
        matchId: `preview-r${roundIndex}m${matchIndex}`,
        roundIndex,
        matchIndex,
        playerIds,
        slotIndexes: roundIndex === 0 ? [firstSlot, firstSlot + 1] : null,
        players: playerIds.map((clientId) => tournamentPlayerPayload(tournament, clientId)),
        scores: [0, 0],
        winnerId: null,
        completed: false,
        active: false,
        editable: roundIndex === 0,
        preview: true,
      });
    }
    rounds.push(round);
    matchCount = Math.floor(matchCount / 2);
    roundIndex += 1;
  }
  return rounds;
}

function tournamentPlayerPayload(tournament, clientId) {
  const participant = participantById(tournament, clientId);
  return participant
    ? {
        clientId,
        name: participant.name,
        stats: participant.stats,
      }
    : {
        clientId: null,
        name: "",
        stats: null,
      };
}

function renderTournamentMatch(tournament, match, isHost, isFirstRound) {
  const players = Array.isArray(match.players) ? match.players : [];
  const scores = Array.isArray(match.scores) ? match.scores : [0, 0];
  const editable = Boolean(match.editable && isFirstRound);
  return `
    <div
      class="tournament-match ${match.active ? "is-active" : ""} ${
        match.completed ? "is-completed" : ""
      } ${match.preview ? "is-preview" : ""}"
      data-tournament-match-id="${escapeHtml(match.matchId || "")}"
      data-tournament-round-index="${Number(match.roundIndex) || 0}"
      data-tournament-match-index="${Number(match.matchIndex) || 0}"
      style="--match-index: ${match.matchIndex};"
    >
      ${[0, 1]
        .map((index) => {
          if (editable) {
            return renderTournamentSlot(
              tournament,
              match.playerIds?.[index],
              match.slotIndexes?.[index] ?? match.matchIndex * 2 + index,
              isHost,
              match.matchIndex * 2 + index,
            );
          }
          const player = players[index] || {};
          const isWinner = match.winnerId && player.clientId === match.winnerId;
          const name = player.name || (match.preview ? "승자 대기" : "대기중");
          return `
            <div class="tournament-match-player ${player.clientId ? "" : "is-empty"} ${
              isWinner ? "is-winner" : ""
            }"
              data-tournament-target-id="${escapeHtml(player.clientId || "")}"
              data-tournament-player-id="${escapeHtml(player.clientId || "")}"
              style="--seed-index: ${match.matchIndex * 2 + index};">
              <span>${titleBadge(player.stats)}${escapeHtml(name)}</span>
              <strong class="tournament-match-score">${Number(scores[index]) || 0}</strong>
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderTournamentSlot(tournament, clientId, index, isHost, seedIndex = index) {
  const participant = participantById(tournament, clientId);
  const name = participant?.name || "여기로 드래그";
  return `
    <div
      class="tournament-slot ${clientId ? "" : "is-empty"}"
      data-tournament-slot-index="${index}"
      data-tournament-target-id="${escapeHtml(clientId || "")}"
      style="--seed-index: ${seedIndex};"
      role="button"
      tabindex="0"
    >
      <span>${participant ? `${titleBadge(participant.stats)}${escapeHtml(name)}` : escapeHtml(name)}</span>
      ${
        isHost && clientId
          ? `<button type="button" aria-label="슬롯 비우기" data-tournament-clear-slot="${index}">×</button>`
          : ""
      }
    </div>
  `;
}

function renderTournamentControls(room, tournament, isHost) {
  if (!isHost) {
    els.tournamentControls.innerHTML = `<p>방장이 대진 배치와 시작을 진행합니다.</p>`;
    return;
  }
  if (tournament.status === "finished") {
    els.tournamentControls.innerHTML = `<p>토너먼트가 종료되었습니다.</p>`;
    return;
  }
  const full = tournament.participants?.length === tournament.size;
  const manualFull = tournamentDisplaySlots(tournament).filter(Boolean).length === tournament.size;
  const controls = [];
  if (full && ["lobby", "seeded"].includes(tournament.status)) {
    controls.push(
      `<button type="button" data-tournament-random-seed>랜덤 배치</button>`,
    );
    controls.push(
      `<button type="button" data-tournament-manual-seed ${
        manualFull ? "" : "disabled"
      }>지정 배치 적용</button>`,
    );
  }
  if (tournament.canStart) {
    controls.push(
      `<button class="tournament-start-button" type="button" data-tournament-start>시작</button>`,
    );
  }
  if (!full) {
    controls.push(`<p>참가자 ${tournament.size}명이 모두 들어오면 배치할 수 있습니다.</p>`);
  }
  if (!controls.length) {
    controls.push(`<p>현재 경기가 진행 중입니다.</p>`);
  }
  els.tournamentControls.innerHTML = controls.join("");
}

function tournamentRoundName(tournament, roundIndex) {
  const totalRounds = tournament.rounds?.length || 1;
  if (roundIndex === totalRounds - 1) return "결승";
  if (roundIndex === totalRounds - 2) return "준결승";
  return `${roundIndex + 1}라운드`;
}

function ensureTournamentManualSlots(tournament) {
  const participantKey = (tournament.participants || [])
    .map((participant) => participant.clientId)
    .join("|");
  const seededKey = (tournament.slots || [])
    .map((slot) => slot.clientId || "")
    .join("|");
  const key = `${tournament.size}:${tournament.status}:${participantKey}:${seededKey}`;
  if (state.tournamentManualKey === key) return;
  const serverSlots = (tournament.slots || []).map((slot) => slot.clientId || null);
  state.tournamentManualSlots = serverSlots.length
    ? serverSlots
    : Array.from({ length: tournament.size }, () => null);
  state.tournamentManualKey = key;
  state.tournamentPickedId = null;
}

function tournamentDisplaySlots(tournament) {
  const seededSlots = (tournament.slots || []).map((slot) => slot.clientId || null);
  if (seededSlots.some(Boolean)) return seededSlots;
  if (state.tournamentManualSlots.length !== tournament.size) {
    state.tournamentManualSlots = Array.from({ length: tournament.size }, () => null);
  }
  return state.tournamentManualSlots;
}

function participantById(tournament, clientId) {
  if (!clientId) return null;
  return (tournament.participants || []).find((participant) => participant.clientId === clientId) || null;
}

function participantStats(tournament, clientId) {
  return participantById(tournament, clientId)?.stats || null;
}

function amTournamentHost() {
  const snapshot = state.snapshot;
  return Boolean(
    snapshot?.room?.tournamentMode &&
      snapshot.room.tournament?.hostId &&
      snapshot.you?.clientId === snapshot.room.tournament.hostId,
  );
}

function setTournamentSlot(clientId, index) {
  const tournament = state.snapshot?.room?.tournament;
  if (!amTournamentHost() || !tournament || !clientId || index < 0 || index >= tournament.size) return;
  const known = participantById(tournament, clientId);
  if (!known) return;
  const slots = [...tournamentDisplaySlots(tournament)];
  const currentIndex = slots.indexOf(clientId);
  if (currentIndex >= 0) slots[currentIndex] = null;
  slots[index] = clientId;
  state.tournamentManualSlots = slots;
  state.tournamentPickedId = null;
  requestRender();
}

function clearTournamentSlot(index) {
  const tournament = state.snapshot?.room?.tournament;
  if (!amTournamentHost() || !tournament || index < 0 || index >= tournament.size) return;
  const slots = [...tournamentDisplaySlots(tournament)];
  slots[index] = null;
  state.tournamentManualSlots = slots;
  requestRender();
}

function seedTournamentManual() {
  const tournament = state.snapshot?.room?.tournament;
  if (!tournament) return;
  const slots = tournamentDisplaySlots(tournament);
  if (slots.filter(Boolean).length !== tournament.size) {
    setStatus("참가자를 모든 슬롯에 배치해주세요.");
    return;
  }
  sendTournamentCommand("tournament_seed_manual", { slots });
}

function renderResult(room, game, you) {
  if (!game.result) {
    els.resultBanner.hidden = true;
    els.restart.hidden = false;
    els.restart.textContent = "다시하기";
    els.kickOpponent.hidden = true;
    if (els.mobile.resultBanner) els.mobile.resultBanner.hidden = true;
    if (els.mobile.restart) els.mobile.restart.hidden = false;
    if (els.mobile.restart) els.mobile.restart.textContent = "다시하기";
    if (els.mobile.kickOpponent) els.mobile.kickOpponent.hidden = true;
    return;
  }
  const winnerText =
    game.result.winner === null ? "무승부!" : `${playerName(game.result.winner)} 승리!`;
  els.resultWinnerText.textContent = winnerText;
  if (room.tournamentMode) {
    els.restart.hidden = true;
    els.kickOpponent.hidden = true;
    els.restart.parentElement?.classList.add("single-action");
    els.resultBanner.hidden = false;
    if (els.mobile.resultBanner) {
      els.mobile.resultWinnerText.textContent = winnerText;
      if (els.mobile.restart) els.mobile.restart.hidden = true;
      if (els.mobile.kickOpponent) els.mobile.kickOpponent.hidden = true;
      els.mobile.resultBanner.hidden = false;
    }
    return;
  }
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
  if (state.leaveReserved) {
    cancelLeaveReservation();
    return;
  }
  if (isGameInProgress()) {
    state.leaveReserved = true;
    renderLeaveButtons(state.snapshot.room, state.snapshot.game);
    setStatus("나가기 예약중 · 종료 후 이동");
    return;
  }
  returnToLobby("로비로 돌아왔습니다.");
}

function cancelLeaveReservation() {
  state.leaveReserved = false;
  if (state.leaveAutoTimer) window.clearTimeout(state.leaveAutoTimer);
  state.leaveAutoTimer = null;
  if (state.snapshot) {
    renderLeaveButtons(state.snapshot.room, state.snapshot.game);
  }
  setStatus("나가기 예약을 취소했습니다.");
}

function renderLeaveButtons(room, game) {
  const reserved = Boolean(state.leaveReserved && room?.started && !game?.result);
  const canSurrender = Boolean(
    room?.started &&
      !game?.result &&
      state.snapshot?.you?.player !== null &&
      state.snapshot?.you?.player !== undefined &&
      !state.snapshot?.you?.spectator,
  );
  for (const button of [els.surrender, els.mobile.surrender]) {
    if (!button) continue;
    button.hidden = !canSurrender;
    button.disabled = !canSurrender;
  }
  for (const button of [els.leave, els.mobile.leave]) {
    if (!button) continue;
    button.textContent = reserved ? "예약 취소" : canSurrender ? "나가기 예약" : "나가기";
    button.disabled = false;
    button.classList.toggle("leave-reserved", reserved);
    button.classList.toggle("leave-pending", canSurrender && !reserved);
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
      ? "랜덤매칭"
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
      room.tournamentMode
        ? tournamentStatusText(room, game)
        : room.streamerMode && room.players[1]?.occupied
        ? "스트리머의 준비 대기 중"
        : "상대 입장 대기 중";
    return;
  }
  if (game.result) {
    els.mobile.tray.textContent = "게임 종료";
    return;
  }
  els.mobile.tray.textContent =
    game.currentPlayer === me ? phaseText(game) : "상대 차례";
}

function renderMobileActions(room, game, you, me) {
  if (!els.mobile.actionRow) return;
  if (room.tournamentMode && !room.started && !game.result) {
    els.mobile.actionRow.innerHTML = "";
    return;
  }

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
          stats: {
            score: 220,
            wins: 7,
            losses: 5,
            streak: -2,
            rank: 7,
            tier: { tier: "gold", grade: 3, stars: 2 },
          },
        },
        {
          index: 1,
          name: "으랏느랏",
          occupied: true,
          connected: true,
          stats: {
            score: 180,
            wins: 1,
            losses: 2,
            streak: 1,
            rank: 12,
            tier: { tier: "diamond", grade: 1, stars: 1 },
          },
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
      stats: {
        score: 180,
        wins: 1,
        losses: 2,
        streak: 1,
        rank: 12,
        tier: { tier: "diamond", grade: 1, stars: 1 },
      },
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
  els.roomCode.textContent = "랜덤매칭";
  setRoomMode(true);
  setStatus("모바일 세로 UI 데모");
  render();
}

function startTierDemo() {
  startMobileDemo();
  state.snapshot.room.players[0].name = "듀얼따고싶다";
  state.snapshot.room.players[0].stats = {
    score: 388,
    wins: 42,
    losses: 18,
    streak: 5,
    rank: 4,
    tier: { tier: "gold", grade: 3, stars: 2 },
    title: {
      id: "duelist",
      label: "듀얼리스트",
      color: "blue",
      icon: "duelist",
      effect: "glow",
    },
  };
  state.snapshot.room.players[1].name = "가나다라마바사아자차카타파하";
  state.snapshot.room.players[1].stats = {
    score: 724,
    wins: 86,
    losses: 51,
    streak: -1,
    rank: 1,
    tier: { tier: "master", points: 145 },
    title: {
      id: "rank-top",
      label: "TOP 1",
      color: "gold",
      icon: "crown",
      iconText: "◆",
      effect: "shine",
    },
  };
  state.snapshot.you.player = 0;
  state.snapshot.you.stats = state.snapshot.room.players[0].stats;
  els.roomCode.textContent = "랜덤매칭";
  setStatus("티어 배지 인게임 데모");
  render();
}

function startTournamentDemo() {
  startMobileDemo();
  const participantNames = [
    "방장스트리머",
    "모코코장인",
    "행운의주사위",
    "토너먼트왕",
    "긴닉네임참가자테스트",
    "빠른손놀림",
    "실드믿는사람",
    "결승가자",
  ];
  const participants = participantNames.map((name, index) => ({
    clientId: index === 0 ? state.clientId : `demo-tournament-${index}`,
    name,
    active: index < 2,
    stats: {
      wins: 10 + index * 3,
      losses: 4 + index,
      streak: index % 3 === 0 ? 2 : 0,
      tier: index === 0
        ? { tier: "master", points: 128 }
        : { tier: ["gold", "platinum", "diamond", "silver"][index % 4], grade: (index % 5) + 1, stars: index % 3 },
      title:
        index === 0
          ? { id: "duelist", label: "듀얼리스트", color: "blue", icon: "duelist", effect: "glow" }
          : null,
    },
  }));
  const player = (index) => participants[index];
  const match = (roundIndex, matchIndex, first, second, options = {}) => ({
    matchId: `demo-r${roundIndex}m${matchIndex}`,
    roundIndex,
    matchIndex,
    players: [first === null ? null : player(first), second === null ? null : player(second)],
    scores: options.scores || [0, 0],
    winnerId: options.winner === null || options.winner === undefined
      ? null
      : player(options.winner).clientId,
    completed: Boolean(options.completed),
    active: Boolean(options.active),
  });

  const room = state.snapshot.room;
  room.code = "2468";
  room.randomMatch = false;
  room.ranked = false;
  room.tournamentMode = true;
  room.tournament = {
    size: 8,
    targetWins: 2,
    status: "playing",
    seeded: true,
    hostId: state.clientId,
    hostName: "방장스트리머",
    participants,
    slots: participants.map((participant) => ({ clientId: participant.clientId })),
    rounds: [
      [
        match(0, 0, 0, 1, { active: true, scores: [1, 0] }),
        match(0, 1, 2, 3),
        match(0, 2, 4, 5, { completed: true, winner: 5, scores: [0, 2] }),
        match(0, 3, 6, 7),
      ],
      [
        match(1, 0, null, null),
        match(1, 1, 5, null),
      ],
      [match(2, 0, null, null)],
    ],
    activeMatch: {
      players: [player(0), player(1)],
      scores: [1, 0],
    },
    nextMatch: null,
    canStart: false,
  };
  room.players[0].name = participantNames[0];
  room.players[0].stats = participants[0].stats;
  room.players[1].name = participantNames[1];
  room.players[1].stats = participants[1].stats;
  state.snapshot.you.player = 0;
  state.snapshot.you.stats = participants[0].stats;
  setStatus("토너먼트 모바일 UI 데모");
  render();
}

function startTierLobbyDemo() {
  setRoomMode(false);
  document.body.classList.toggle(
    "tier-help-demo",
    new URLSearchParams(window.location.search).get("help") === "1",
  );
  state.status = {
    onlineUsers: 128,
    stats: {
      score: 388,
      wins: 42,
      losses: 18,
      streak: 5,
      rank: 4,
      tier: { tier: "gold", grade: 2, stars: 2 },
      titles: [],
    },
    leaderboard: [
      {
        clientId: "sample-1",
        name: "가나다라마바사아자차카타파하",
        score: 724,
        wins: 86,
        losses: 51,
        tier: { tier: "master", points: 145 },
      },
      {
        clientId: state.clientId,
        name: "나",
        score: 388,
        wins: 42,
        losses: 18,
        tier: { tier: "gold", grade: 2, stars: 2 },
      },
      {
        clientId: "sample-3",
        name: "주사위조작했으니탈주추천",
        score: 251,
        wins: 30,
        losses: 26,
        tier: { tier: "silver", grade: 1, stars: 1 },
      },
    ],
  };
  renderLobbyStatus();
  setStatus("티어 로비 데모");
}

els.createRoom.addEventListener("click", () => {
  createRoom().catch((error) => setStatus(`방 생성 실패: ${error.message}`));
});

els.createStreamerRoom?.addEventListener("click", () => {
  createStreamerRoom().catch((error) =>
    setStatus(`스트리머 모드 생성 실패: ${error.message}`),
  );
});

els.createTournamentRoom?.addEventListener("click", () => {
  toggleTournamentSetup();
});

els.createTournamentConfirm?.addEventListener("click", () => {
  createTournamentRoom().catch((error) =>
    setStatus(`토너먼트 생성 실패: ${error.message}`),
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

els.surrender?.addEventListener("click", () => {
  sendSurrender();
});

els.mobile.leave?.addEventListener("click", () => {
  requestLeave();
});

els.mobile.surrender?.addEventListener("click", () => {
  sendSurrender();
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

els.titleUnequip?.addEventListener("click", () => {
  unlockSound();
  unequipTitle().catch((error) =>
    setStatus(`칭호 해제 실패: ${error.message}`),
  );
});

els.customizeOpen?.addEventListener("click", () => {
  unlockSound();
  openCustomize("board");
});

document.addEventListener("click", (event) => {
  unlockSound();

  const titleChoice = event.target.closest("[data-title-id]");
  if (titleChoice) {
    equipTitle(titleChoice.dataset.titleId).catch((error) =>
      setStatus(`칭호 장착 실패: ${error.message}`),
    );
    return;
  }

  const customizeSave = event.target.closest("[data-customize-emoticon-save]");
  if (customizeSave) {
    saveEmoticonLoadout();
    return;
  }

  const customizeReset = event.target.closest("[data-customize-emoticon-reset]");
  if (customizeReset) {
    resetDraftEmoticonLoadout();
    return;
  }

  const customizeClose = event.target.closest("[data-customize-close]");
  if (customizeClose) {
    closeCustomize();
    return;
  }

  const customizeTab = event.target.closest("[data-customize-tab]");
  if (customizeTab) {
    setCustomizeTab(customizeTab.dataset.customizeTab);
    return;
  }

  const customizeSlot = event.target.closest("[data-customize-emoticon-slot]");
  if (customizeSlot) {
    state.customizeSelectedSlot = Number(customizeSlot.dataset.customizeEmoticonSlot) || 0;
    renderCustomizeEmoticons();
    return;
  }

  const customizeEmoticon = event.target.closest("[data-customize-emoticon-id]");
  if (customizeEmoticon) {
    setDraftEmoticonSlot(
      state.customizeSelectedSlot,
      customizeEmoticon.dataset.customizeEmoticonId,
    );
    return;
  }

  const boardSkinButton = event.target.closest(".customize-board-skins button[data-board-skin]");
  if (boardSkinButton) {
    applyBoardSkin(boardSkinButton.dataset.boardSkin, { persist: true });
    setStatus(`보드판 스킨: ${boardSkinButton.textContent.trim()}`);
    return;
  }

  const tournamentHostParticipates = event.target.closest("[data-tournament-host-participates]");
  if (tournamentHostParticipates) {
    setTournamentHostParticipates(tournamentHostParticipates.dataset.tournamentHostParticipates);
    return;
  }

  const tournamentSize = event.target.closest("[data-tournament-size]");
  if (tournamentSize) {
    setTournamentSize(tournamentSize.dataset.tournamentSize);
    return;
  }

  const tournamentTargetWins = event.target.closest("[data-tournament-target-wins]");
  if (tournamentTargetWins) {
    setTournamentTargetWins(tournamentTargetWins.dataset.tournamentTargetWins);
    return;
  }

  const tournamentRandomSeed = event.target.closest("[data-tournament-random-seed]");
  if (tournamentRandomSeed) {
    sendTournamentCommand("tournament_seed_random");
    return;
  }

  const tournamentManualSeed = event.target.closest("[data-tournament-manual-seed]");
  if (tournamentManualSeed) {
    if (!tournamentManualSeed.disabled) seedTournamentManual();
    return;
  }

  const tournamentStart = event.target.closest("[data-tournament-start]");
  if (tournamentStart) {
    sendTournamentCommand("tournament_start");
    return;
  }

  const clearTournamentSlotButton = event.target.closest("[data-tournament-clear-slot]");
  if (clearTournamentSlotButton) {
    clearTournamentSlot(Number(clearTournamentSlotButton.dataset.tournamentClearSlot));
    return;
  }

  const tournamentSlot = event.target.closest("[data-tournament-slot-index]");
  if (tournamentSlot && state.tournamentPickedId && amTournamentHost()) {
    setTournamentSlot(
      state.tournamentPickedId,
      Number(tournamentSlot.dataset.tournamentSlotIndex),
    );
    return;
  }

  const tournamentParticipant = event.target.closest("[data-tournament-participant-id]");
  if (tournamentParticipant && amTournamentHost()) {
    state.tournamentPickedId =
      state.tournamentPickedId === tournamentParticipant.dataset.tournamentParticipantId
        ? null
        : tournamentParticipant.dataset.tournamentParticipantId;
    requestRender();
    return;
  }

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

document.addEventListener("dragstart", (event) => {
  const customizeEmoticon = event.target.closest("[data-customize-emoticon-id]");
  if (customizeEmoticon) {
    const emoticonId = customizeEmoticon.dataset.customizeEmoticonId;
    event.dataTransfer?.setData("application/x-tikatuka-emoticon", emoticonId);
    event.dataTransfer?.setData("text/plain", emoticonId);
    event.dataTransfer?.setDragImage?.(customizeEmoticon, 24, 24);
    return;
  }

  const participant = event.target.closest("[data-tournament-participant-id]");
  if (!participant) return;
  if (!amTournamentHost()) {
    event.preventDefault();
    return;
  }
  state.tournamentDraggedId = participant.dataset.tournamentParticipantId;
  event.dataTransfer?.setData("text/plain", state.tournamentDraggedId);
  event.dataTransfer?.setDragImage?.(participant, 12, 12);
});

document.addEventListener("dragover", (event) => {
  const customizeSlot = event.target.closest("[data-customize-emoticon-slot]");
  if (customizeSlot) {
    event.preventDefault();
    customizeSlot.classList.add("is-drop-target");
    return;
  }

  const slot = event.target.closest("[data-tournament-slot-index]");
  if (!slot || !state.tournamentDraggedId) return;
  event.preventDefault();
  slot.classList.add("is-drop-target");
});

document.addEventListener("dragleave", (event) => {
  const customizeSlot = event.target.closest("[data-customize-emoticon-slot]");
  if (customizeSlot) customizeSlot.classList.remove("is-drop-target");

  const slot = event.target.closest("[data-tournament-slot-index]");
  if (slot) slot.classList.remove("is-drop-target");
});

document.addEventListener("drop", (event) => {
  const customizeSlot = event.target.closest("[data-customize-emoticon-slot]");
  if (customizeSlot) {
    event.preventDefault();
    const emoticonId =
      event.dataTransfer?.getData("application/x-tikatuka-emoticon") ||
      event.dataTransfer?.getData("text/plain");
    customizeSlot.classList.remove("is-drop-target");
    setDraftEmoticonSlot(
      Number(customizeSlot.dataset.customizeEmoticonSlot),
      emoticonId,
    );
    return;
  }

  const slot = event.target.closest("[data-tournament-slot-index]");
  if (!slot) return;
  event.preventDefault();
  const clientId = event.dataTransfer?.getData("text/plain") || state.tournamentDraggedId;
  slot.classList.remove("is-drop-target");
  state.tournamentDraggedId = null;
  setTournamentSlot(clientId, Number(slot.dataset.tournamentSlotIndex));
});

document.addEventListener("dragend", () => {
  state.tournamentDraggedId = null;
  document
    .querySelectorAll(".customize-emoticon-slot.is-drop-target")
    .forEach((slot) => slot.classList.remove("is-drop-target"));
  document
    .querySelectorAll(".tournament-slot.is-drop-target")
    .forEach((slot) => slot.classList.remove("is-drop-target"));
});

els.nicknameInput.value = localStorage.getItem(NICKNAME_STORAGE_KEY) || "";
applyBoardSkin(state.boardSkin);
loadEmoticonCatalog();
renderTournamentSetupControls();
setupSound();
if (CUSTOMIZE_PREVIEW_TAB) {
  window.setTimeout(() => openCustomize(CUSTOMIZE_PREVIEW_TAB), 200);
}
updateMobileStageScale();
window.addEventListener("resize", updateMobileStageScale);
window.addEventListener("orientationchange", updateMobileStageScale);
window.visualViewport?.addEventListener("resize", updateMobileStageScale);
window.visualViewport?.addEventListener("scroll", updateMobileStageScale);
if (IS_MOBILE_DEMO) {
  startMobileDemo();
} else if (IS_TIER_DEMO) {
  startTierDemo();
} else if (IS_TOURNAMENT_DEMO) {
  startTournamentDemo();
} else if (IS_TIER_LOBBY_DEMO) {
  startTierLobbyDemo();
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
