# Tic Tac Toe 3D (4×4×4) multijugador

Version web de tu Tic Tac Toe 3D original (el de Tkinter). Se juega en el
navegador, en tiempo real, contra otra persona por internet, usando
**Flask + Flask-SocketIO** en el backend.

El tablero es un cubo de 4×4×4 (64 casillas) y se gana alineando 4 fichas en
cualquiera de las **76 lineas posibles**: filas, columnas, "pilares"
verticales, diagonales de cada capa, y las 4 diagonales que cruzan todo el
cubo de esquina a esquina. Toda la logica de validacion y de detectar quien
gano vive en el servidor (el cliente solo dibuja), asi que no se puede hacer
trampa editando el navegador.

## Estructura

```
app.py                 backend Flask + Socket.IO (logica del juego)
templates/index.html   pagina unica (lobby + tablero)
static/style.css       estilos
static/client.js       cliente Socket.IO
requirements.txt       dependencias Python
Procfile                comando de arranque para Render
```

## Como se juega

1. Un jugador presiona **"Crear sala nueva"** → recibe un codigo de 4
   caracteres (ej. `GT5B`).
2. Comparte ese codigo con la otra persona.
3. El segundo jugador escribe el codigo en **"Unirse a una sala"**.
4. En cuanto los dos estan conectados empieza la partida. El primero en
   crear la sala siempre es `X`.
5. Cada capa del cubo (Z=0 a Z=3) se muestra como una grilla 4x4. Al pasar el
   mouse sobre una casilla se ve su coordenada `x,y,z` exacta.
6. Al ganar o empatar aparece un dialogo con boton de **revancha**: cuando
   ambos jugadores lo presionan, el tablero se reinicia sin salir de la sala.

## Correrlo en tu computadora

```bash
python3 -m venv venv
source venv/bin/activate        # en Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Abre `http://127.0.0.1:5000` en dos pestañas (o dos navegadores) para
probarlo vos mismo antes de invitar a alguien.

## Desplegar en Render (gratis)

1. Sube esta carpeta a un repositorio de GitHub.
2. En [render.com](https://render.com) → **New +** → **Web Service** →
   conecta el repositorio.
3. Configuracion:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn --worker-class eventlet -w 1 app:app`
     (ya esta en el `Procfile`, Render lo detecta solo)
   - **Instance Type**: Free esta bien para jugar entre pocas personas.
4. Deploy. Cuando termine, Render te da una URL publica
   (`https://tu-app.onrender.com`) — esa es la que compartes con quien
   quieras jugar.

### Version de Python (importante)

`eventlet` todavia no es compatible con Python 3.14, que es lo que Render usa
por defecto en builds nuevos. El archivo `runtime.txt` de este proyecto fija
la version a `python-3.12.7`, que si es compatible. Si Render no la respeta
sola, fijala a mano:

- En el dashboard del servicio → **Environment** → agrega la variable
  `PYTHON_VERSION` con el valor `3.12.7` → **Save Changes** (esto dispara un
  redeploy).

Si por algun motivo seguis viendo el error `class uri 'eventlet' invalid or
not found` despues de fijar la version, la alternativa sin dependencias
nativas es cambiar el **Start Command** a:

```
gunicorn --worker-class gthread --threads 4 -w 1 app:app
```

Esto hace que Socket.IO funcione por *long-polling* en vez de WebSockets
puros (un poco mas de latencia, imperceptible en un juego por turnos) y no
depende de `eventlet` en absoluto.

### Notas importantes sobre Render

- **Un solo worker (`-w 1`)**: el estado de las salas vive en memoria del
  proceso Python. Si usas mas de un worker/instancia, cada uno tendria su
  propia lista de salas y los jugadores podrian caer en procesos distintos.
  Con el plan Free esto no es problema porque solo corre una instancia.
- **`eventlet`** es necesario para que Flask-SocketIO maneje WebSockets
  correctamente bajo Gunicorn.
- **Plan Free "se duerme"**: si nadie usa la app por un rato, Render la pone
  a dormir y el primer acceso tarda unos segundos en despertarla — es
  normal, no es un error.
- Si en algun momento migras a multiples workers/instancias, vas a necesitar
  guardar el estado de las salas en algo compartido (Redis, por ejemplo) en
  vez de un diccionario en memoria.

## Diferencias con la version de escritorio

- La logica de "quien gano" se reescribio para revisar las 76 lineas
  ganadoras completas del cubo despues de cada jugada (mas simple y directa
  de auditar que el barrido de 13 direcciones relativas del script
  original, aunque el resultado es equivalente).
- El servidor es la unica fuente de verdad: valida turno, casilla libre y
  coordenadas antes de aceptar una jugada.
- Se agrego reconexion: si a alguien se le corta la conexion y vuelve a
  entrar con el mismo codigo de sala, retoma su simbolo (`X` u `O`) en la
  partida en curso.
