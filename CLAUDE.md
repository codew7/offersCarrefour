# Verificador de precios y ofertas · Carrefour Argentina

Herramienta local para chequear, sobre una lista de artículos, cuáles están en oferta
hoy en www.carrefour.com.ar y a qué precio.

**Usuario:** Alejandro. No es programador. Explicaciones concisas, en español, sin jerga innecesaria.

---

## Arquitectura (v3 — actual)

**Python busca, el HTML muestra.** Es un mini servidor local:

```
abrir-verificador.bat  →  verificador.py  →  http://127.0.0.1:8765
                              │                      │
                              │                      └─ sirve verificador-carrefour.html
                              └─ consulta carrefour.com.ar (sin navegador, sin CORS)
```

El navegador **nunca** habla con Carrefour: sólo con `127.0.0.1`, que es el mismo origen
que la página. Por eso el problema de CORS desapareció por completo.

### Archivos

| Archivo | Qué es |
|---|---|
| `abrir-verificador.bat` | **Punto de entrada.** Doble clic. Busca `py` y después `python`; si no hay ninguno explica cómo instalarlo. |
| `verificador.py` | Servidor + búsqueda + puntaje. Sólo biblioteca estándar (`http.server`, `urllib`, `json`, `unicodedata`). No instala nada. |
| `verificador-carrefour.html` | La pantalla. Lo sirve Python. Sin servidor detrás busca un `ultima-busqueda.json` al lado y, si lo encuentra, se abre en **modo lectura** (ver esa sección); si no, explica cómo encender el programa. |
| `articulos.txt` | Lista editable. Python la lee al arrancar y el botón "Guardar lista" la reescribe. Un artículo por línea; `#` al principio = comentario. |
| `categorias.txt` | Categorías marcadas en el explorador de ofertas. Lo escribe el botón "Guardar selección"; se puede editar a mano. Se crea recién la primera vez que guardás. |
| `ultima-busqueda.json` | **La última búsqueda de cada pantalla**, para no repetirla al volver a abrir. Lo escribe Python solo, al terminar cada búsqueda. Borrarlo a mano equivale a "Descartar". Es también el archivo que se sube al hosting junto al HTML para mirar desde el celular. Ver "Los resultados quedan guardados" y "Modo lectura". |
| `ultima-busqueda.js` | **El gemelo del anterior**, con el mismo contenido envuelto en `window.ULTIMA_BUSQUEDA = …`. Lo escribe Python al mismo tiempo. Existe sólo porque con doble clic (`file://`) el navegador no deja leer el `.json` pero sí un `<script>`. Ver "Modo lectura". |
| `CARRITO_OFERTA_JULIO2026.txt` | Lista original de julio 2026. Referencia, no la lee el programa. |
| `*.pdf` | Comprobantes sueltos, sin relación con esta herramienta. |

### Endpoints internos

| Ruta | Qué hace |
|---|---|
| `GET /` | Devuelve el HTML (lo lee del disco en cada pedido, así los cambios se ven al refrescar). |
| `GET /api/ping` | Sirve para que el HTML detecte si hay servidor detrás. |
| `GET /api/articulos` | Contenido de `articulos.txt`. |
| `POST /api/buscar` | `{linea}` → resultado de **un** artículo. El HTML las manda de a una para poder mostrar la barra de progreso. |
| `POST /api/guardar` | `{texto}` → reescribe `articulos.txt`. |
| `GET /api/categorias` | Árbol de categorías aplanado, para el explorador de ofertas. |
| `POST /api/ofertas` | `{cat, desde, paginas}` → un tramo de ofertas de esa categoría. |
| `GET /api/sesion` | Lo guardado de la última búsqueda: `{lista:{…}, ofertas:{…}}`. |
| `POST /api/sesion` | `{parte, datos}` → guarda **una** parte (`"lista"` u `"ofertas"`) y deja la otra como estaba. Con `datos:null` la borra. |
| `POST /api/salir` | Apaga el servidor. |

---

## La pantalla (rediseño v4)

Cuatro zonas, de arriba a abajo:

1. **Panel "Tu lista"**, plegable. Arranca abierto y **se pliega solo** al empezar a
   buscar; la cabecera queda como barra fina con el conteo de artículos. `Ctrl+Enter`
   dentro del textarea también dispara la búsqueda.
2. **Barra pegajosa** (`position:sticky`): 4 KPI + chips de filtro **con contador** +
   buscador de texto libre + el switch de Tarjeta / Cuenta Digital. Es HTML estático:
   `render()` sólo actualiza números y clases, nunca la reescribe. Por eso el buscador
   no pierde el foco mientras tipeás.
3. **Lista de tarjetas, una sola columna** (`.grid{grid-template-columns:1fr}`), con
   títulos de grupo entre medio. Cada tarjeta es a su vez una grilla de tres zonas:
   `.izq` (qué es: buscado, foto, nombre, promos, cartel de rendimiento), `.der`
   (cuánto sale: precios, cálculo de promo, cantidad y botón del carrito, sobre un
   panel gris) y `.pie` a todo lo ancho (alternativas y "Ajustar búsqueda").
   Abajo de 820 px se apilan solas.
4. **Barra flotante del carrito** (`#barraCarrito`, `position:fixed` abajo), oculta
   mientras no haya nada elegido.

Detalles que conviene no romper:

- **Progreso en vivo.** `render()` se llama después de cada artículo, así las tarjetas
  aparecen de a una. Los que faltan se dibujan como esqueletos (`.skel`) y la barra
  `#progreso` avanza arriba de todo.
- **Cada alternativa lleva su foto** (`.alt-thumb`, 40 px), igual que el principal
  (`.thumb`, 84 px). Sale del mismo `a.img` que ya mandaba Python; no hubo que tocar el
  backend.
- **Los artículos se consultan de a `EN_PARALELO_ART = 5`.** Un grupo de "corredores"
  que van tomando la siguiente línea libre (`corredor()` se llama a sí misma al terminar).
  El servidor de Python es `ThreadingHTTPServer`, así que aguanta el paralelo. Por eso
  cada resultado guarda `pos`: sin eso, las tarjetas quedaban en el orden en que
  contestó Carrefour y no en el de tu lista. Subir mucho ese número no ayuda: Carrefour
  empieza a demorar los pedidos.
- **La franja de color de la tarjeta la pinta `.card.oferta::after`**, no un `border-left`
  (con `border-radius` queda mal). **Verde si es una oferta real, amarilla si es sólo por
  tarjeta/cuenta** (`soloPorTarjeta()`). El cartelito `.flag` sigue el mismo criterio:
  "OFERTA" (verde) vs "CON TARJETA" (amarillo). Misma paleta en `.off`, `.tag.of`,
  `.kpi.destacado` y `.promo.tarjeta.on`. **El rojo ya no se usa para ofertas**, sólo para
  coincidencia baja (`.m-baja`).
- La coincidencia **ya no se muestra** (ver más abajo); el `via` del backend tampoco:
  los dos viven en el `title` de la línea "Buscaste".

### Cualquier imagen se amplía al hacer click

Vale para **las dos pantallas**: el principal, cada alternativa y las tarjetas del
explorador de ofertas. Al tocar una miniatura se abre `#lightbox` (fondo oscuro, imagen
centrada); se cierra tocando afuera o con `Escape`.

Está resuelto con **un solo listener delegado en `document`** que filtra por
`img.thumb, img.alt-thumb`. Por eso funciona con las tarjetas que se dibujan después
—que son todas— sin tener que reconectar nada en cada `render()`. **No pasarlo a
listeners por imagen:** habría que reengancharlos en cada repintado.

### Precio con la promo de varias unidades aplicada

Cuando un producto tiene una promo del tipo **"2do al 70%", "3x2", "20% llevando 2"**,
el número grande de la tarjeta deja de ser el precio de una unidad suelta y pasa a ser
**el precio por unidad aprovechando la promo**. Al lado va tachado el precio de una sola
unidad, el `.off` con el ahorro, y abajo un cartel verde `.calc`:
"Llevando **2** pagás $1.300 · 2do al 70%".

- `leerPromo(texto)` traduce el texto de la promo a `{unidades, paga, corta}`, donde
  `paga` está medido en "precios de una unidad" (2do al 70% → llevás 2, pagás 1,3).
  Cubre cuatro formas: `NxM`, "Ndo al X%", "X% en la Nda unidad" y "X% llevando N".
- `promoUnitaria(p)` recorre `p.promos` (y `p.promosTarjeta` **sólo si el selector está
  prendido**) y devuelve la más conveniente, ya en pesos. `null` si no hay ninguna.
- `bloquePrecios(p)` decide qué mostrar; `porPrecio()` ordena por este precio efectivo,
  y las alternativas muestran lo mismo con un `.tag.pr` ("2x1", "2do al 70%") y el detalle
  en el `title`.
- El campo de cantidad del botón "Agregar al carrito" arranca en `unidades`, así el
  carrito queda armado para que la promo se active.

> **Los "X% off" a secas NO se recalculan.** Ese descuento ya viene aplicado en el `Price`
> que devuelve VTEX (`p.desc`); volver a restarlo sería descontar dos veces. `leerPromo()`
> sólo reconoce promos que dependen de llevar **más de una** unidad.

### "Usar éste": cambiar cuál es el producto principal

Cada fila del acordeón de alternativas tiene un botón `.btn-usar`. Al tocarlo, esa
alternativa y el principal **se intercambian de lugar** (el que estaba baja a la lista),
las alternativas se reordenan con `porPrecio()` y se vuelve a dibujar todo. No hay
consulta nueva a Carrefour: es puro reacomodo en memoria.

- Los `data-usar` (índice del artículo) y `data-alt` (índice dentro de `alternativas`) los
  lee `conectarTarjetas()`.
- Se marca `r.abierto = true` para que el acordeón **no se cierre** después del cambio;
  si no, el `open` depende sólo de `p.score < 0.8` y la lista se plegaba sola.
- El cambio afecta todo lo que se calcula desde el principal: grupo (oferta / regular),
  KPI, comparación de "cuánto rinde" y el botón del carrito.
- Lo que ya estaba marcado para el carrito **no se toca**: `seleccion` se indexa por
  `sku`, así que sigue contando aunque el producto pase a ser una alternativa.

### Cuánto rinde: precio por kilo / litro / unidad / metro

Los resultados de un mismo artículo vienen en presentaciones distintas (290 g vs 700 g vs
pack x 3), así que el precio suelto no alcanza para saber cuál conviene. Cada producto
muestra un `≈ $X por kilo` (`.xu`) al lado del precio, y **entre los resultados de ese
artículo se marca el que más rinde**.

- `medida(nombre)` lee el tamaño **del nombre del producto** — es lo único que manda
  Carrefour — y lo normaliza a kg / L / unidades / metros. Reconoce, en este orden:
  multipack (`3 x 250 g`), peso o volumen simple (`290 g`, `1,5 lt`, `473 ml`), metros
  (`30 m`) y unidades (`x 6`, `12 rollos`, `pack 24`).
- `porMedida(p)` divide por ese tamaño **el precio que se ve en pantalla**, o sea con la
  promo de varias unidades ya aplicada.
- `elQueRinde(lista, tipo)` compara **sólo lo que se mide igual**: kilos con kilos, litros
  con litros. Nunca compara un pack de 6 contra un frasco de 500 g.
- Si gana una alternativa, la tarjeta muestra un cartel azul `.rinde` con el nombre y el
  precio por medida, y esa alternativa queda resaltada (`.alt.rinde-mas`, `.tag.md.win`).
  Si el que gana es el principal, el cartel es verde (`.rinde.propio`).
- El cartel **sólo aparece si hay con qué comparar** (al menos una alternativa del mismo
  tipo de medida).

> Todo esto es **estimado** y por eso lleva `≈`: si el nombre no dice el tamaño, o lo dice
> raro, `medida()` devuelve `null` y el producto simplemente no participa. Nunca inventa.

### Carrito: se marca acá, se manda una sola vez

**Ésta fue la corrección de rendimiento.** La primera versión hacía que cada botón fuera
un link directo a `/checkout/cart/add`: un artículo = una navegación, y cada navegación
arrastra el checkout entero de VTEX (crear sesión, orderForm, redirect final al carrito).
Con 10 artículos eran 10 viajes lentos y 10 pestañas abiertas.

Ahora el flujo es:

1. **"Agregar al carrito" en la tarjeta no toca la red.** Sólo guarda el artículo en
   `seleccion` (un objeto en memoria, indexado por `sku`) y el botón pasa a
   `.btn-cart.puesto` → "✓ Agregado · quitar". Volver a tocarlo lo saca.
2. **Barra flotante `#barraCarrito`** (abajo, centrada, aparece sola cuando hay algo
   elegido): "N artículos listos", "Vaciar" y "Enviar al carrito de Carrefour".
3. **Un solo viaje.** `linkCarrito(items)` arma una única URL **repitiendo el trío
   `sku`/`qty`/`seller`** por cada artículo:

```
/checkout/cart/add?sku=111&qty=2&seller=1&sku=222&qty=1&seller=1&sc=1
```

> **La forma con comas (`sku=111,222&qty=2,1`) NO funciona: devuelve HTTP 400.**
> Ya se probó. Los parámetros van repetidos, no en listas.

   Se abre con `window.open(url, "carritoCarrefour")`: **target con nombre fijo**, así
   siempre reutiliza la misma pestaña y la segunda vez la sesión de Carrefour ya está
   caliente.

Sigue sin haber `fetch` a carrefour.com.ar — es una navegación normal del navegador, así
que **no** reabre el problema de CORS.

- `parsear()` aporta `sku` (`items[0].itemId`) y `vendedor` (`sellers[0].sellerId`).
- La cantidad arranca en las unidades que activan la promo (`promoUnitaria`). Cambiarla
  después de marcar el artículo actualiza `seleccion` en el acto (`onchange`).
- `seleccion` se indexa por `sku`, no por índice de la lista: sobrevive a re-buscar un
  artículo y a los re-render.
- Estados apagados (`.btn-cart.no`): "Sin código para el carrito" cuando Carrefour no
  devolvió `itemId`, y "Sin stock online" cuando `disponible` es `false`.
- Las tarjetas sin resultado y las alternativas no tienen botón.

> **No volver al link por artículo.** Es el camino lento y ya se probó.

### El porcentaje de coincidencia no se muestra

Lo pidió el usuario: el puntaje **sigue funcionando igual** (agrupa, ordena, alimenta el
KPI "a revisar" y el filtro, y decide el `open` del acordeón de alternativas), pero no se
dibuja. Vive en el `title`: en la línea "Buscaste" de la tarjeta y en el nombre de cada
alternativa. Las clases `.match` / `.m-alta` / `.m-media` / `.m-baja` quedaron en el CSS
sin uso, por si se quiere volver atrás.

---

## Los resultados quedan guardados

Buscar es lento —la lista, un rato; el explorador de ofertas, minutos—, así que
**cerrar el navegador no cuesta otra vuelta entera**. Al terminar cada búsqueda la
pantalla le manda a Python lo que encontró y Python lo deja en `ultima-busqueda.json`,
en la carpeta del programa. Al volver a abrir, la pantalla se rearma sola.

**Guarda Python, no el navegador.** Se decidió así a propósito: sobrevive también a
cerrar la ventana negra, no depende del `localStorage` (que no aguanta miles de
ofertas) y el archivo se puede borrar a mano. Lo único que sigue viviendo en el
navegador es la **selección de categorías**, que es chica.

### El archivo

Un solo JSON con dos partes independientes, cada una con su marca de tiempo:

```json
{
  "lista":   { "texto": "…articulos.txt tal como estaba…",
               "resultados": [ … ], "guardado": "2026-08-13T10:32:11" },
  "ofertas": { "items": [ … ], "cats": "Almacén, Bebidas",
               "revisados": 4820, "guardado": "2026-08-13T09:05:40" }
}
```

- `guardar_sesion(parte, datos)` **reemplaza una parte y deja la otra como estaba**:
  volver a buscar la lista no borra las ofertas que tardaron minutos. Con `datos=None`
  esa parte se borra; si no queda ninguna, se borran los archivos.
- Se escribe en `<archivo>.tmp` y recién ahí se hace `os.replace()` (`_escribir_atomico`).
  Si el programa se corta en el medio, queda el archivo viejo entero y no uno a la mitad.
- Se escriben **dos** archivos con el mismo contenido, `.json` y `.js`. El segundo es para
  el modo lectura con doble clic; ver esa sección.
- Hay `SESION_LOCK` porque el servidor es threading.
- Si el archivo está corrupto, `leer_sesion()` devuelve `{}`: se arranca en blanco,
  nunca se rompe.

### En la pantalla

- `recuperarSesion()` corre al arrancar, **después** de `cargarArchivo()`: el textarea
  lo manda siempre `articulos.txt`; lo guardado sólo lo pisa si el archivo está vacío.
- Cada pantalla tiene su cartel `.guardado` (`#avisoGuardado` y `#ofAvisoGuardado`) con
  "Esto es lo **guardado hoy a las 10:32**", el botón **Buscar de nuevo** y el botón
  **Descartar** (que borra esa parte del archivo). Pasadas 24 horas el cartel se pone
  amarillo (`.viejo`) y avisa que los precios pueden haber cambiado.
- **El cartel se esconde al arrancar una búsqueda nueva**: sólo tiene sentido cuando lo
  que estás viendo salió del archivo.
- Las ofertas se guardan **aunque hayas cancelado**: lo que llegó, llegó.
- El chip de vigencia del encabezado se repinta al final de `recuperarSesion()`, porque
  restaurar las ofertas lo deja hablando de la pantalla que no estás mirando.

> El carrito (`seleccion`) **no** se guarda. Es una decisión de la que hay que acordarse
> si algún día parece un bug: al recuperar una búsqueda, los artículos marcados no vuelven.

---

## Modo lectura: la página sin Python (hosting / celular)

Se buscó en la computadora y después se quiere **mirar el resultado desde el celular**,
en el supermercado. Para eso alcanza con subir **dos archivos** a cualquier hosting
estático:

```
verificador-carrefour.html
ultima-busqueda.json        ← el que ya escribe Python en la carpeta
```

Nada más: ni Python, ni el `.bat`, ni `articulos.txt`. La página detecta sola que no hay
servidor y entra en **modo lectura**.

### El archivo gemelo `ultima-busqueda.js` — y por qué existe

**Con doble clic (`file://`) el navegador PROHÍBE leer el `.json` de al lado**, aunque
esté justo ahí:

```
Access to fetch at 'file:///…/ultima-busqueda.json' from origin 'null'
has been blocked by CORS policy: Cross origin requests are only supported
for protocol schemes: … http, https …
```

Es el mismo CORS de siempre, ahora sobre un archivo local. Pero **un `<script src>` sí
carga** desde `file://`. Por eso `guardar_sesion()` escribe **los dos archivos a la vez**,
con el mismo contenido:

| Archivo | Contenido | Para qué |
|---|---|---|
| `ultima-busqueda.json` | `{…}` | Lo que lee Python; lo que se sube a un hosting. |
| `ultima-busqueda.js` | `window.ULTIMA_BUSQUEDA = {…};` | Lo único que el navegador deja leer con doble clic. |

Los escribe `_volcar_sesion(d)` (un `json.dumps` y dos `_escribir_atomico`), y `guardar_sesion`
con `datos=None` **borra los dos**. `sincronizar_js()` corre al arrancar `main()` y genera
el `.js` si hay un `.json` de una versión anterior que todavía no lo tiene, así el modo
lectura funciona sin tener que rebuscar nada.

> El gemelo **duplica el tamaño en disco** (3 MB → 6 MB). Es a propósito y es el precio de
> que el doble clic funcione. Al hosting se puede subir sólo el `.json`.

### Cómo decide

En el arranque, si `/api/ping` falla (no hay Python), **antes** de dar por perdida la
pantalla se prueban las dos fuentes, **en este orden** y con rutas relativas a la página:

1. `leerScriptSesion()` — inyecta `<script src="ultima-busqueda.js">` y espera
   `window.ULTIMA_BUSQUEDA`. Es el que salva el doble clic.
2. `leerJsonSesion()` — `fetch("ultima-busqueda.json")`. Es el que salva el hosting
   donde subiste sólo dos archivos.

Alcanza con que ande uno (`leerArchivoSesion()` encadena el segundo en el `catch` del
primero).

| Ping | Archivo al lado | Qué pasa |
|---|---|---|
| ✅ | — | Normal de siempre: `cargarArchivo()` + `recuperarSesion()`. |
| ❌ | `.js` o `.json` con datos | **Modo lectura**: `entrarModoLectura(d)`. |
| ❌ | ninguno | El cartel `#sinServidor` (cómo encender el `.bat`, o abrir el JSON a mano). |

Las rutas son **relativas** a propósito: así funciona igual en la raíz del dominio que en
un subdirectorio. El `.json` va con `cache:"no-store"` y el `.js` con `?t=<ahora>`; si no,
el celular sigue mostrando lo de la semana pasada después de subir algo nuevo.

### Qué se apaga

`soloLectura` es la única bandera. `entrarModoLectura()`:

- Esconde lo que necesita al servidor: `btnGo`, `btnGuardar`, `btnRecargar`, el panel de
  categorías del explorador (`#ofPanelCats`) y los botones **Buscar de nuevo** /
  **Descartar** de los dos carteles `.guardado`. El textarea queda `readOnly`.
- `cajaRebuscar()` devuelve `""` y no se dibuja el `<details>` de "Ajustar búsqueda".
- `guardarSesion()`, `verificar()` y `buscarOfertas()` cortan al entrar; `vista()` no
  llama a `cargarCategorias()`.
- Cartel verde `#modoLectura` arriba de las pestañas, con la fecha de lo guardado (la
  más reciente de las dos partes).
- Si el JSON trae **sólo ofertas** (el caso normal), se abre directo en esa pestaña; la
  otra explica que ahí no hay nada guardado, en vez de quedar en blanco.

### Qué sigue funcionando

Todo lo que ya vivía en el navegador: filtros, orden, paginado, el selector de Tarjeta /
Cuenta Digital, el cálculo de promos de varias unidades, el precio por kilo/litro, "Usar
éste", ampliar imágenes y **el carrito** — el carrito es una navegación a
`carrefour.com.ar/checkout/cart/add`, no pasa por Python, así que desde el celular anda
igual.

### El botón "Abrir un ultima-busqueda.json…"

Última red: el cartel `#sinServidor` tiene un `<input type="file">` para elegir el JSON a
mano. Con el gemelo `.js` en la carpeta ya casi no hace falta, pero sirve si te pasaste el
archivo al celular por mail o WhatsApp, suelto y sin el HTML al lado.

> **Refactor que esto trajo:** `recuperarSesion()` se partió en `pintarSesion(d)` (rearma
> la pantalla con un JSON, venga de donde venga) y `recuperarSesion()` (lo pide a
> `/api/sesion`). Las dos fuentes tienen exactamente la misma forma, así que hay un solo
> camino de dibujo. `hayGuardado(d)` es el chequeo compartido de "¿esto tiene algo?".

---

## Pantalla 2: explorador de ofertas

Función **aparte y opcional**. Dos pestañas arriba de todo (`.tabs`): "Mi lista" y
"Explorar ofertas". No comparte nada con la lista de artículos: es para mirar qué hay
en oferta hoy, sin buscar nada en particular.

Sí comparte todo lo demás: el carrito, el selector de Tarjeta / Cuenta Digital, el
cálculo de promos de varias unidades y el precio por kilo/litro.

### De dónde salen los datos

Del **catálogo legacy**, porque es el único que deja filtrar por categoría y, sobre todo,
**ordenar por descuento**:

```
/api/catalog_system/pub/products/search?fq=C:/<catId>/&O=OrderByBestDiscountDESC&_from=0&_to=49
```

`explorar_ofertas(cat, desde, paginas)` devuelve **un tramo** de la categoría: las páginas
`[desde, desde+paginas)`, con `fin:true` cuando ya no hay más (página incompleta o tope de
VTEX, que no deja pasar de los ~2500 primeros productos de una consulta, `TOPE_VENTANA`).

Se devuelve de a tramos, y no la categoría entera de una, por dos motivos: la barra de
progreso puede moverse de verdad y las ofertas van apareciendo mientras baja. El navegador
encadena tramos hasta el `fin`. Dentro de cada tramo, las 6 páginas se piden **en
paralelo** con un `ThreadPoolExecutor` (`EN_PARALELO`) — eso es lo que evita que tarde
minutos. Como cada página va al `CACHE`, repetir la misma categoría después es instantáneo.

### La barra de progreso

No hay forma de saber cuántas páginas tiene una categoría antes de recorrerla, así que la
barra (`#ofCargando`) se arma con lo que sí se sabe:

- **Avanza por categorías terminadas**: cada una vale `100 / total`.
- **Dentro de la que está en curso**, se acerca al 90% de su porción sin llegar nunca
  (`1 - 0.72^tramos`). Nunca retrocede ni invade la porción siguiente.
- Debajo, los números reales: productos revisados, ofertas encontradas y segundos.
- **Rayas en movimiento** sobre la barra: un tramo puede tardar varios segundos y sin eso
  parecía colgado.
- Botón **Cancelar** (`ofCancelado`), que se mira entre tramo y tramo.

`pintarSeguido()` limita el redibujo a uno cada 500 ms: repintar 100 tarjetas en cada
tramo costaba más de lo que aportaba.

> **No volver a cortar por "ya no aparecen ofertas".** Se probó y estaba mal: una promo
> tipo "3x2" no baja el `Price`, así que el orden por descuento la manda al fondo y se
> perdían. Hay que barrer todo. Por lo mismo se sacó el selector de "cuánto mirar".

El árbol de categorías sale de `/api/catalog_system/pub/category/tree/2` y se aplana en
`categorias_planas()` (departamento + subcategorías), cacheado igual que todo lo demás.

### `fq=C:` quiere el CAMINO ENTERO, no el id de la subcategoría

**Éste fue un bug real y silencioso.** Marcar una subcategoría no traía ninguna oferta;
marcar el departamento madre sí. La causa: el catálogo legacy quiere el path completo de
la categoría, y con el id de la hoja solo devuelve `[]` **sin error ninguno**.

```
fq=C:/293/         → []          ← sólo "Leches"
fq=C:/292/293/     → 50 productos ← "Lácteos y productos frescos" › "Leches"
fq=C:/292/         → 50 productos ← el departamento, que sí funcionaba
```

Lo resuelve `ruta_categoria(id)`: busca el id en el árbol (ya cacheado) y devuelve
`"292/293"` para una subcategoría o `"292"` para un departamento. `rutas_categorias()`
arma ese mapa una sola vez (`con_cache("RUTAS", …)`). El navegador **sigue mandando sólo
el id**: la traducción es interna, así que no cambió ni el HTML ni `categorias.txt`.

> Si el id no está en el árbol se manda tal cual, y si Carrefour no responde el árbol se
> sigue como antes. Nunca rompe: en el peor caso vuelve al comportamiento viejo.

| Ruta | Qué hace |
|---|---|
| `GET /api/categorias` | Departamentos y subcategorías para el selector. |
| `POST /api/ofertas` | `{cat, desde, paginas}` → un tramo de la categoría, con `fin`. |

Un producto entra si es **vendible** (stock + precio) y tiene `enOferta` **o**
`promosTarjeta`. Las de tarjeta viajan siempre; **la pantalla decide si se ven**, con el
mismo `esOferta()` del resto: con el selector apagado desaparecen de la lista.

### La pantalla

- **Selector múltiple de categorías**: un panel de checkboxes agrupados por departamento
  (`.cats`, en columnas con `column-width`), con buscador, "Todas" y "Ninguna". Ver abajo.
- **No hay control de profundidad.** Siempre se trae todo lo que haya en las categorías
  marcadas; cuantas más marques, más tarda la primera vez.
- **Filtros que no vuelven a consultar** (todo en memoria): texto libre, descuento mínimo,
  y orden. **El orden por defecto es alfabético** (`nombre`); después están mayor
  descuento, menor precio y mejor precio por medida.
- **Se muestran todas las ofertas, paginadas de a 100** (`POR_PAGINA_OF`). No hay tope:
  el recorte es sólo de dibujo. Con más de 100 tarjetas con imagen el navegador se
  arrastra, y por eso existe el paginado; `refiltrarOfertas()` vuelve a la página 1 cada
  vez que tocás un filtro.
- **Botón "Agregar al carrito"** en cada tarjeta: es la misma `filaCarrito()` de la otra
  pantalla y suma a la misma barra flotante.
- **Un color por subcategoría en la franja izquierda.** `colorCat()` saca un tono de un
  hash del nombre (`hsl(H,62%,44%)`, saturación y luminosidad fijas para que ninguno
  quede ilegible) y lo pasa por la variable CSS `--franja`, que usan `.oc::after` y el
  rótulo `.oc-cat`. Sale de un hash y no de la posición, así el mismo rubro tiene siempre
  el mismo color entre búsquedas. Se usa la **subcategoría** (el último tramo de `p.cat`),
  que es lo que distingue una góndola de otra.
  Como la franja dejó de poder avisar "esto es sólo con Tarjeta", eso ahora lo dice el
  chip amarillo `.oc-tarj`.
- **Todas las tarjetas de una fila miden lo mismo** (`.oc{height:100%}` + el `stretch` que
  trae la grilla por defecto) y las promos junto con el botón viven en `.oc-pie`, que se
  pega abajo con `margin-top:auto`. Sin eso, un producto con promo de varias unidades
  quedaba más alto y las vecinas dejaban un hueco. **No poner `align-items:start` en
  `.of-grid`**: es justamente lo que rompía la alineación.

### El que más rinde de cada subcategoría: tarjeta amarilla

Dentro de cada subcategoría se marca **el que mejor precio por medida tiene** (por kilo,
litro, unidad o metro). Lo calcula `mejoresPorSubcategoria(lista)`, que reutiliza el mismo
`porMedida()` de la pantalla "Mi lista":

- Agrupa por **subcategoría + tipo de medida** (`subcategoria(p.cat) + "|" + pm.tipo`), así
  nunca compara un pack de 6 contra un frasco de 500 g ni litros contra kilos.
- **Sólo marca si el grupo tiene 2 o más productos.** Si no hay con qué comparar, no se
  destaca nada — mismo criterio que el cartel `.rinde` de "Mi lista".
- Se calcula **sobre todas las ofertas filtradas**, no sólo la página que se ve: la
  comparación es contra todo lo que estás mirando con los filtros puestos. `pintarOfertas()`
  lo llama una sola vez por render y le pasa el mapa (`id -> medida`) a cada tarjeta.
- Como usa `porMedida()`, compara el precio **con la promo de varias unidades ya aplicada**.
- Empate = gana el primero (la comparación es `<` estricto): un solo ganador por grupo.

**Se muestra pintando la tarjeta entera de amarillo** (`.oc.mejor`: fondo amarillo suave
+ anillo `--amarillo`), no con un cartel. Al principio era un cartel de texto y el usuario
pidió cambiarlo por el color: se ve de un vistazo y no le suma otra línea a la tarjeta. El
detalle ("Mejor precio por litro entre los «Aguas minerales y de mesa» que estás viendo:
$733,79 por litro") vive en el `title` de la tarjeta.

> Ojo con el orden en el CSS: `.oc.mejor` y `.oc:hover` tienen la **misma especificidad**,
> así que `.oc.mejor` va después y necesita su propia regla `.oc.mejor:hover` para no
> comerse la sombra del hover.

> **El amarillo ahora significa dos cosas** según dónde esté: tarjeta amarilla = el que más
> rinde de su subcategoría; chip `.oc-tarj` amarillo = "sólo con Tarjeta". Son dos
> elementos distintos y conviven en la misma tarjeta sin pisarse.

### La selección de categorías se guarda en dos lados

La verdad vive en `elegidasCat` (objeto `id -> true`).

1. **En el navegador**, sola, en cada cambio: `localStorage["carrefour.categorias"]`
   con un array de ids. Es lo que hace que al volver a abrir esté todo como lo dejaste.
   Envuelto en `try/catch`: si el navegador no lo permite, simplemente no persiste.
2. **En `categorias.txt`**, sólo si tocás "Guardar selección". Formato legible y
   editable a mano, una por línea:

```
# Categorías elegidas en el explorador de ofertas.
# Una por línea: id | nombre.  Con # al principio se ignora.

18 | Almacén
21 | Bebidas › Vinos
```

   Lo escribe `guardar_seleccion_cats()` y lo lee `leer_seleccion_cats()`, que se queda
   con lo que hay **antes del `|`**. El nombre es sólo para que se entienda.

| Ruta | Qué hace |
|---|---|
| `POST /api/guardar-cats` | `{cats:[{id,nombre}]}` → reescribe `categorias.txt`. |
| `GET /api/cats-guardadas` | `{ids, texto}` leídos del archivo. |

**Departamento marcado = subcategorías de más.** `catsAConsultar()` saca del pedido toda
subcategoría cuyo `padreId` también esté marcado: los productos ya vienen adentro del
departamento y sería consultar dos veces lo mismo. Por eso `categorias_planas()` manda
`padreId` además del nombre del padre.

Como un producto puede estar en varias categorías, la acumulación en el navegador
**deduplica por `id`** antes de pintarlo.

### El carrito se identifica por SKU, no por posición

Para que `filaCarrito()` sirva en las dos pantallas, los botones dejaron de llevar el
índice del artículo: ahora llevan `data-cart="<sku>"` y hay un registro global
`catalogo` (sku → producto) que `conectarTarjetas()` consulta al clickear. **No volver a
indexar por posición**: en el explorador no existe tal cosa.

### El selector de Tarjeta está duplicado

Hay una copia en cada pantalla, pero la verdad es una sola variable (`incluirTarjeta`).
`setTarjeta(v)` actualiza los dos checkboxes, la clase `.on` de los dos labels, y rehace
lo que dependa de los precios efectivos en ambas vistas. (De paso: hasta acá la clase
`.on` del switch no la ponía nadie, así que el switch nunca se veía prendido.)

---

## Decisiones técnicas importantes

### 0. Sin filtro de código postal — se usa el catálogo general

**Se sacó a propósito.** Hasta la v4 existía una "región" de VTEX (resuelta a partir
de tu código postal) que se mandaba en cada pedido —`&regionId=` en el buscador
inteligente, cabecera `x-vtex-segment` en el resto— para que el stock y los precios
fueran los de tus sucursales. El usuario pidió eliminarlo: ahora todas las consultas
van sin región, contra el catálogo general de Carrefour, sin distinguir sucursal.

**No volver a agregarlo** salvo que el usuario lo pida explícitamente. Si vuelve a
hacer falta, la referencia era `resolver_region(cp)` / `aplicar_region(cp)` en
`verificador.py` (ya no existen) y el input de CP en la barra de pestañas del HTML.

### 1. Los dos buscadores de VTEX y por qué ahora se usan los dos

Carrefour AR corre sobre **VTEX**:

| Endpoint | Multi-palabra | CORS desde el navegador | Desde Python |
|---|---|---|---|
| `/api/io/_v/api/intelligent-search/product_search/?query=<q>` | ✅ Excelente | ❌ Bloqueado | ✅ **Principal** |
| `/api/catalog_system/pub/products/search?ft=<q>` (legacy) | ❌ Literal, con 2+ palabras devuelve `[]` | ✅ Permitido | ✅ **Respaldo** |

**Éste fue el cambio grande de la v3.** Mientras la búsqueda vivía en el navegador,
el intelligent-search era inservible:

```
Access to fetch at '...intelligent-search/product_search/?query=...'
from origin 'null' has been blocked by CORS policy:
No 'Access-Control-Allow-Origin' header is present
```

CORS es una regla **del navegador**, no del servidor de Carrefour. `urllib` la ignora,
así que desde Python el buscador bueno funciona perfecto.

> **No volver a poner llamadas a carrefour.com.ar en el JavaScript.** Ese camino ya se
> recorrió dos veces y termina en CORS. Todo lo de red va en `verificador.py`.

### 2. Estrategia de búsqueda (`buscar_articulo`)

1. **Intelligent-search con la frase completa.** Es lo que resuelve casi todo.
2. Si el mejor puntaje quedó **< 0.85**, refuerza con el **catálogo literal**, mandando
   una sola palabra fuerte por vez (`claves_busqueda()`), hasta 3, cortando apenas
   llega a **≥ 0.9**.
3. Une los dos conjuntos deduplicando por `productId`.

### El separador: `+` o `>`

```
Queso crema clásico 290 grs + casancrem
Queso crema clásico 290 grs > casancrem     (equivalente, sintaxis vieja)
```

- Izquierda = descripción, se usa para **puntuar y filtrar**.
- Derecha = **reemplaza** lo que se le consulta a Carrefour. Sirve cuando el nombre
  completo no encuentra nada.

Sin separador, se consulta la frase entera. **La mayoría de las líneas no lo necesitan.**

Lo parte `partir()` con la regex `SEPARADOR = \s*>\s*|\s+\+\s+`, un solo corte
(`split(..., 1)`). **El `+` exige espacios a los dos lados** justamente para no partir
nombres reales como "pack 4+1" o "2en1+acondicionador"; el `>` no los necesita porque no
aparece nunca en un nombre de producto.

En la pantalla la explicación vive en un `<details>` plegado (`.ayuda-mas`) debajo del
textarea, así el panel no arranca lleno de texto. Muestra el `+` como forma recomendada
y menciona el `>` al final.

Hay **caché en memoria** por consulta (`CACHE`, con lock porque el servidor es threading),
así repetir "krachitos" no vuelve a pegarle a la API. Se limpia al reiniciar.

### 3. Puntaje de coincidencia (`puntaje`)

Devuelve 0..1 comparando palabra por palabra contra `productName + brand`, normalizados
(minúsculas, NFD para separar tildes, sólo `a-z0-9`).

- El criterio de match está en `acierta(t, texto)`, **una sola función** que usan tanto
  `puntaje()` como `palabras_en_comun()`. Si se toca el matching, se toca ahí.
- Palabras con dígitos (290, 500, 1kg) pesan **2,5×** — distinguen presentaciones del
  mismo producto. Se exige match de palabra entera.
- El resto pesa 1 y admite match de raíz (cae la última letra si tiene >4), para tolerar
  plurales y clasico/clasica.

Semáforo (hoy sólo en el `title`): **≥0.8 alta** · **≥0.5 media** · **<0.5 baja**.

### 3b. Los filtros de entrada

Para que un producto llegue a la pantalla — como principal **o** como alternativa — tiene
que pasar los tres, en `buscar_articulo`:

| Filtro | Constante | Qué exige |
|---|---|---|
| **Vendible** | — | `disponible` **y** `precio`. Lo que no se puede comprar no sirve para comparar: se descarta antes que nada, tanto acá como en el explorador de ofertas. |
| **Palabras en común** | `MIN_PALABRAS = 2` | Compartir al menos 2 palabras distintas con lo que buscaste. Si tu línea tiene una sola palabra útil, alcanza con ésa (`min(MIN_PALABRAS, len(set(tokens(desc))))`). |
| **Coincidencia mínima** | `UMBRAL_COINCIDENCIA = 0.20` | Superar el 20% de puntaje. |

`palabras_en_comun(desc, prod)` cuenta palabras **distintas** (`set(tokens(desc))`) usando
`acierta()`, el mismo criterio de match que `puntaje()`: los tokens con dígitos se exigen
enteros, el resto tolera plural/género. Las palabras de `IGNORAR` (de, la, grs, ml, x…)
no cuentan, así que "de" y "con" no regalan coincidencias.

Los dos números viven cada uno en una línea de `verificador.py`. Si algo que debería
aparecer no aparece, bajar `MIN_PALABRAS` a 1 es lo primero que hay que probar.

Cuando ningún resultado pasa, la tarjeta cae en "sin resultados" y el mensaje distingue
los tres casos: no vino nada, vino pero está sin stock/sin precio, o vino vendible pero
no se parece lo suficiente. Cada producto viaja además con `comunes` (cuántas palabras
compartió), por si se quiere mostrar o depurar.

Como consecuencia, el estado "Sin stock online" de la tarjeta y el botón apagado del
carrito quedaron **inalcanzables**. Se dejaron en el código como red de seguridad por si
algún día se afloja este filtro.

El algoritmo está **duplicado a propósito**: la versión de Python (`puntaje`) es la que
manda; el JS sólo conserva `porPrecio()` para reordenar cuando tocás "Usar este".

### 4. Reglas de orden — las pidió explícitamente el usuario

**Los artículos en oferta van siempre arriba de todo.** En dos niveles:

- **Tarjetas principales:** grupo 1 = en oferta, grupo 2 = precio regular, grupo 3 = sin
  resultados, con un título por grupo. Dentro de cada grupo manda **`r.pos`**, la posición
  en tu lista — *no* el orden de `resultados`, que es el orden en que fueron llegando.
- **Alternativas de cada artículo:** ofertas primero; dentro de cada grupo, de más barata
  a más cara (`por_precio()` en Python, `porPrecio()` en JS). Sin precio queda último.
  **Van todas, sin recortar** (antes había un `[:25]`); el acordeón tiene su propio scroll.

El **principal** por defecto es **el que más rinde**, no el de mayor coincidencia. Python
sigue mandando como principal el de mejor puntaje, y el JS lo reemplaza en cuanto llega
la respuesta (`elegirPrincipal(r)`):

- Se compara contra `tipoDominante()`: la medida que más se repite entre los resultados
  del artículo, así no mide unidades contra gramos.
- Si nadie declara tamaño en el nombre, no hay con qué comparar y **queda el que eligió
  Python** (mayor coincidencia).
- Se vuelve a correr al prender/apagar el selector de Tarjeta, porque cambian los precios
  efectivos.
- **No pisa tu elección manual:** el botón "Usar éste" marca `r.manual = true` y desde ahí
  el automático no toca más esa tarjeta.

El puntaje de coincidencia sigue decidiendo qué entra (filtros) y qué sale por pantalla
cuando no hay medidas.

### 4b. Hasta cuándo valen las ofertas (chip del header)

La fecha sale de **la campaña**, no de `PriceValidUntil`. Ese campo de VTEX suele estar
clavado a un año vista y mentía; **se dejó de usar a propósito**.

Carrefour escribe la campaña y sus fechas al final del nombre crudo del teaser:

```
PROMO-2do al 70% Max 8 unidades Combinable CASANCREM-Reg-2-70-Gigante28 al 3.8
                                                              ^^^^^^^^^^^^^^^^
                                                      Ahorro Gigante, 28/7 al 3/8
```

`periodo_campania(crudo)` lo lee **antes** de que `limpiar_promo()` borre esa cola (la
regex que la borra es la misma que la reconoce). Devuelve `(campania, desde, hasta)` y
viaja en cada producto. El año se deduce: si el mes ya pasó, es del año que viene.
`NOMBRE_CAMPANIA` traduce la palabra clave a algo legible ("Gigante" → "Ahorro Gigante",
"Almacen" → "Ofertas de almacén"); lo que no esté en esa tabla se muestra tal cual vino.

> **El nombre de la campaña ya NO se busca contra una lista cerrada.** Ése fue el
> motivo de que el chip desapareciera: la regex vieja exigía una de seis palabras
> (`gigante|almacen|feria|semana|…`) y el día que Carrefour estrenó una campaña con
> otro nombre dejó de matchear, en silencio y sin error. Ahora **lo único que se exige
> son las fechas**; como campaña se toma cualquier palabra pegada a ellas, y si no hay
> ninguna útil se llama "Ofertas" (`NO_ES_CAMPANIA` descarta relleno tipo "del", "vig",
> "promo"). Si aparece otra redacción, lo que hay que tocar son las **fechas**, no una
> lista de nombres.

Se reconocen dos formas, en este orden:

| Regex | Ejemplo |
|---|---|
| `CAMPANIA` (números) | `…-Gigante28 al 3.8`, `Vig 28/07 al 03/08` |
| `CAMPANIA_MES` (mes escrito) | `Ahorro Gigante del 28 al 3 de agosto` |

El `(?![\d%%])` del final de `CAMPANIA` está para que un descuento no pase por fecha:
"10 al 20.5%" es un porcentaje, no del 10 al 20 de mayo. Va el símbolo duplicado porque
la plantilla se arma con el operador `%` de Python.

En la pantalla, `pintarVigencia()`:

- Agrupa por **campaña + fecha** y muestra la que más productos aporta, entre las ofertas
  que estás viendo. El resto va en el `title` del chip.
- Descarta lo **vencido** y lo que cae a más de `DIAS_CREIBLES = 60`.
- Si no sobrevive nada, el chip **no aparece**. Nunca se inventa una fecha.

Se recalcula en `render()`, en `pintarOfertas()` (sobre todas las filtradas, no sólo la
página que se ve) y al cambiar de pestaña.

### 5. Detección de oferta

`enOferta = bool(promos) or desc > 0`, donde:

- `promos` sale de `Teasers`, ya filtrados por `es_promo_real()` (2do al 50%, 3x2, 30% off…)
- `desc` es el % de rebaja entre `ListPrice` y `Price`

**Los precios rebajados (`desc > 0`) se muestran en verde** (`.precio.rebajado` y
`.alt .p.rebajado`), igual que el resto de los indicadores de oferta. Por eso el verde de
"alternativa más barata que el principal" se pasó a azul.

### 5b. Promos de medio de pago propio — selector, apagado por defecto

`MEDIO_CARREFOUR` separa los teasers de **Tarjeta Carrefour**, **Cuenta Digital
Carrefour**, "Mi Carrefour" y Banco de Servicios Financieros. Van en una lista aparte,
`promosTarjeta`, y **no** entran en `enOferta`.

La decisión final es del JS, no de Python: `esOferta(p)` devuelve
`p.enOferta || (incluirTarjeta && p.promosTarjeta.length)`. `incluirTarjeta` arranca en
`false` y lo cambia el checkbox "Contar Tarjeta / Cuenta Digital Carrefour" que está
junto a los chips de filtro.

Ventaja de resolverlo en el navegador: tildar el selector reagrupa, reordena y recalcula
los KPI **sin volver a consultar Carrefour**.

> **Todo uso de `enOferta` en el JS debe pasar por `esOferta()`.** Si aparece un
> `p.enOferta` suelto en el render, el selector deja de tener efecto en ese lugar.
> La única excepción legítima está dentro de la propia `esOferta()`.

**Los chips de estas promos sólo se dibujan cuando el selector está prendido** (en
amarillo). Con el selector apagado no aparecen de ninguna forma — ni grises ni con
"· no cuenta" — así que un artículo cuya única promo sea de tarjeta muestra
"Sin promociones activas". Lo pidió el usuario.

---

## Forma de la respuesta de VTEX

```
# legacy → lista al ras
[ { productId, productName, brand, link, linkText, items:[...] } ]

# intelligent-search → viene envuelto
{ "products": [ {...igual...} ], ... }

# adentro de cada producto
items: [ { images:[{imageUrl}],
           sellers:[ { commertialOffer: {
               Price, ListPrice, PriceWithoutDiscount, AvailableQuantity,
               Teasers: [ { name | Name | "<Name>k__BackingField" } ]
           } } ] } ]
```

### Stock: qué cuenta como "se puede comprar"

`_vendible(commertialOffer)` es **el único lugar** donde se decide, y exige las tres:

1. `IsAvailable` que no sea `False` (si el campo viene),
2. `AvailableQuantity > 0`,
3. `Price` numérico y mayor a cero.

Además, **un producto puede tener varios SKU y el primero estar agotado**. `parsear()`
recorre `items` y se queda con el primero vendible; sólo si ninguno lo es cae de nuevo en
`items[0]`, y ahí el filtro lo descarta. Antes miraba `items[0]` a secas y colaba
productos sin stock.

Detalles que muerden:

- Los teasers cambian de clave según el endpoint: `name` (intelligent-search),
  `Name` o **`<Name>k__BackingField`** (legacy, serialización de .NET).
  `nombre_teaser()` contempla los tres.
- Los nombres de promo traen basura interna:
  `"PROMO-2do al 70% Max 8 unidades Combinable CASANCREM-Reg-2-70-Gigante28 al 3.8"`.
  `limpiar_promo()` corta en `-Reg-` / `-Gigante` y saca el prefijo `PROMO-`.
- `Price: 0` significa no disponible → se trata como `None`.
- En el legacy `link` viene absoluto; en intelligent-search viene relativo.
  `parsear()` maneja los dos.
- Se manda `User-Agent` de navegador. Sin él la API puede rechazar el pedido.
- Si el sistema tiene los certificados desactualizados, `pedir_json()` reintenta con
  contexto SSL sin verificar en vez de romper todo.

---

## Limitaciones conocidas

- No hay filtro por código postal: los precios y el stock son los del catálogo general
  de Carrefour, no necesariamente los de una sucursal en particular (ver sección "0"
  más arriba).
- No incluye cupones personalizados de "Mi Carrefour" ni de la app.
- Sin login: no se ven precios ni promos exclusivas de cuenta.
- Requiere Python instalado (el `.bat` avisa y da el link si falta). Sólo **para buscar**:
  para mirar lo ya buscado alcanza con el HTML y el JSON (modo lectura).
- La ventana negra tiene que quedar abierta mientras se usa la herramienta.
- En modo lectura los precios son los del momento en que se hizo la búsqueda en la
  computadora: el celular no consulta nada, sólo lee el archivo que subiste.
- El envío al carrito usa la sesión del navegador. La **primera** vez sigue siendo lenta:
  Carrefour tiene que crear la sesión y el orderForm, y puede pedirte sucursal o método
  de entrega. Eso pasa una sola vez, no una por artículo.

---

## Cosas que ya se probaron y NO funcionaron

- **intelligent-search desde el navegador** (`file://`) → bloqueado por CORS. Fue el
  motivo de la v3.
- **`corsproxy.io` / `api.allorigins.win`** como proxy de respaldo → 403 y 408.
- **`chrome --disable-web-security`** → se le llegó a sugerir al usuario y lo rechazó,
  con razón: es inseguro. **No volver a proponerlo.**
- **Mandar la frase completa al endpoint legacy** → devuelve `[]`. Ése fue el origen del
  "funciona pero los resultados no son precisos" de la v1.
- **`/checkout/cart/add` con listas separadas por coma** (`sku=1,2&qty=1,1`) → **HTTP 400**.
  Hay que repetir `sku`/`qty`/`seller` una vez por artículo.
- **`fetch("ultima-busqueda.json")` con el HTML abierto por doble clic** (`file://`) →
  bloqueado por CORS, origen `null`, aunque el archivo esté en la misma carpeta. **No es
  un problema de ruta y no se arregla cambiándola.** La salida fue el gemelo
  `ultima-busqueda.js` cargado con `<script src>`, que sí está permitido.

## Ideas pendientes (no pedidas todavía)

- Total del carrito con cantidades, con y sin descuentos.
- Reconocer más redacciones de promo en `leerPromo()` (hoy son cuatro patrones).
- Comparación contra el precio estimado de `CARRITO_OFERTA_JULIO2026.txt`.
- Exportar el resultado a xlsx.
- Guardar un histórico para ver cómo evoluciona cada precio.
