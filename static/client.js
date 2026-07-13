(() => {
  const socket = io();

  // ---- estado local ----
  let mySymbol = null;
  let roomCode = null;
  let lastWinLine = [];

  // ---- referencias DOM ----
  const lobbyScreen = document.getElementById('lobby');
  const gameScreen = document.getElementById('game');
  const lobbyError = document.getElementById('lobby-error');

  const createNameInput = document.getElementById('create-name');
  const joinNameInput = document.getElementById('join-name');
  const joinCodeInput = document.getElementById('join-code');
  const btnCreate = document.getElementById('btn-create');
  const btnJoin = document.getElementById('btn-join');

  const roomCodeEl = document.getElementById('room-code');
  const btnCopy = document.getElementById('btn-copy');
  const btnLeave = document.getElementById('btn-leave');
  const turnDot = document.getElementById('turn-dot');
  const turnText = document.getElementById('turn-text');
  const chipX = document.getElementById('chip-x');
  const chipO = document.getElementById('chip-o');
  const nameX = document.getElementById('name-x');
  const nameO = document.getElementById('name-o');
  const youSymbolEl = document.getElementById('you-symbol');
  const coordReadout = document.getElementById('coord-readout');
  const layersEl = document.getElementById('layers');

  const overlay = document.getElementById('overlay');
  const overlayTitle = document.getElementById('overlay-title');
  const overlaySub = document.getElementById('overlay-sub');
  const btnRematch = document.getElementById('btn-rematch');
  const rematchStatus = document.getElementById('rematch-status');

  const cellIndex = (x, y, z) => z * 16 + y * 4 + x;

  // -------------------------------------------------------------
  // Construccion del tablero: 4 capas (Z=3..0) cada una con grilla 4x4
  // -------------------------------------------------------------
  function buildBoard() {
    layersEl.innerHTML = '';
    for (let z = 3; z >= 0; z--) {
      const layer = document.createElement('div');
      layer.className = 'layer';
      layer.dataset.z = z;

      const label = document.createElement('div');
      label.className = 'layer-label';
      label.innerHTML = `capa <b>Z=${z}</b>`;
      layer.appendChild(label);

      const grid = document.createElement('div');
      grid.className = 'grid4';
      for (let y = 0; y < 4; y++) {
        for (let x = 0; x < 4; x++) {
          const idx = cellIndex(x, y, z);
          const btn = document.createElement('button');
          btn.className = 'cell';
          btn.dataset.idx = idx;
          btn.dataset.x = x;
          btn.dataset.y = y;
          btn.dataset.z = z;
          btn.addEventListener('click', onCellClick);
          btn.addEventListener('mouseenter', () => {
            coordReadout.textContent = `x=${x}  y=${y}  z=${z}`;
          });
          grid.appendChild(btn);
        }
      }
      layer.appendChild(grid);
      layersEl.appendChild(layer);
    }
  }

  function onCellClick(e) {
    const btn = e.currentTarget;
    if (btn.disabled) return;
    const x = Number(btn.dataset.x);
    const y = Number(btn.dataset.y);
    const z = Number(btn.dataset.z);
    socket.emit('move', { x, y, z });
  }

  // -------------------------------------------------------------
  // Lobby
  // -------------------------------------------------------------
  btnCreate.addEventListener('click', () => {
    hideError();
    socket.emit('create_room', { name: createNameInput.value.trim() });
  });

  btnJoin.addEventListener('click', () => {
    hideError();
    const code = joinCodeInput.value.trim().toUpperCase();
    if (code.length !== 4) {
      showError('El codigo de sala tiene 4 caracteres.');
      return;
    }
    socket.emit('join_room_event', { roomCode: code, name: joinNameInput.value.trim() });
  });

  joinCodeInput.addEventListener('input', () => {
    joinCodeInput.value = joinCodeInput.value.toUpperCase();
  });

  function showError(msg) {
    lobbyError.textContent = msg;
    lobbyError.hidden = false;
  }
  function hideError() {
    lobbyError.hidden = true;
  }

  socket.on('create_room_ack', (res) => {
    if (!res.ok) { showError(res.error || 'No se pudo crear la sala.'); return; }
    enterGame(res.roomCode, res.symbol);
  });

  socket.on('join_room_ack', (res) => {
    if (!res.ok) { showError(res.error || 'No se pudo unir a la sala.'); return; }
    enterGame(res.roomCode, res.symbol);
  });

  function enterGame(code, symbol) {
    roomCode = code;
    mySymbol = symbol;
    roomCodeEl.textContent = code;
    youSymbolEl.textContent = symbol;
    lobbyScreen.hidden = true;
    gameScreen.hidden = false;
    buildBoard();
  }

  // -------------------------------------------------------------
  // Sala / salida
  // -------------------------------------------------------------
  btnLeave.addEventListener('click', () => {
    socket.emit('leave_room_event');
    window.location.reload();
  });

  btnCopy.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(roomCode);
      btnCopy.textContent = 'copiado';
      setTimeout(() => (btnCopy.textContent = 'copiar'), 1200);
    } catch (_) { /* portapapeles no disponible */ }
  });

  btnRematch.addEventListener('click', () => {
    socket.emit('request_rematch');
    btnRematch.disabled = true;
    rematchStatus.textContent = 'Esperando confirmacion del rival…';
  });

  // -------------------------------------------------------------
  // Estado del juego -> render
  // -------------------------------------------------------------
  socket.on('state', (state) => {
    renderPlayers(state);
    renderTurn(state);
    renderBoard(state);
    renderOverlay(state);
  });

  socket.on('rematch_requested', (data) => {
    if (data.by !== mySymbol) {
      rematchStatus.textContent = 'Tu rival pidio la revancha — presiona el boton para aceptar.';
    }
  });

  function renderPlayers(state) {
    const px = state.players.find((p) => p.symbol === 'X');
    const po = state.players.find((p) => p.symbol === 'O');
    nameX.textContent = px ? px.name : 'esperando…';
    nameO.textContent = po ? po.name : 'esperando…';
    chipX.classList.toggle('disconnected', !!px && !px.connected);
    chipO.classList.toggle('disconnected', !!po && !po.connected);
  }

  function renderTurn(state) {
    if (!state.started) {
      turnText.textContent = 'Esperando rival — comparte el codigo de sala';
      turnDot.className = 'turn-dot';
      return;
    }
    if (state.winner) {
      turnText.textContent = `Jugador ${state.winner} gano la partida`;
      turnDot.className = `turn-dot is-${state.winner.toLowerCase()}`;
      return;
    }
    if (state.draw) {
      turnText.textContent = 'Empate — tablero completo';
      turnDot.className = 'turn-dot';
      return;
    }
    const isYou = state.turn === mySymbol;
    turnText.textContent = isYou ? 'Tu turno' : `Turno de ${state.turn}`;
    turnDot.className = `turn-dot is-${state.turn.toLowerCase()}`;
  }

  function renderBoard(state) {
    lastWinLine = state.winLine || [];
    const cells = layersEl.querySelectorAll('.cell');
    const gameOver = !!(state.winner || state.draw);
    const canPlay = state.started && !gameOver && state.turn === mySymbol;

    cells.forEach((btn) => {
      const idx = Number(btn.dataset.idx);
      const value = state.board[idx];
      btn.textContent = value || '';
      btn.classList.toggle('mark-x', value === 'X');
      btn.classList.toggle('mark-o', value === 'O');
      btn.classList.toggle('win-cell', lastWinLine.includes(idx));
      btn.disabled = !canPlay || !!value;
    });
  }

  function renderOverlay(state) {
    const gameOver = !!(state.winner || state.draw);
    overlay.hidden = !gameOver;
    if (!gameOver) return;

    if (state.winner) {
      overlayTitle.textContent = state.winner === mySymbol ? 'Ganaste' : `Gano el jugador ${state.winner}`;
      overlaySub.textContent = 'Cuatro fichas alineadas en algun eje, plano o diagonal del cubo.';
    } else {
      overlayTitle.textContent = 'Empate';
      overlaySub.textContent = 'Las 64 casillas se llenaron sin ninguna linea completa.';
    }
    btnRematch.disabled = false;
    rematchStatus.textContent = '';
  }
})();
