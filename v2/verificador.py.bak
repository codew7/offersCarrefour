#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verificador de precios y ofertas · Carrefour Argentina
------------------------------------------------------
Levanta un mini servidor local y abre el navegador.
La busqueda la hace Python (sin CORS), la pantalla la hace el HTML.

Uso:  doble clic en abrir-verificador.bat
      o bien:  python verificador.py

Solo usa la biblioteca estandar de Python. No instala nada.
"""

import datetime
import json
import os
import re
import ssl
import sys
import threading
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CARPETA = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(CARPETA, "verificador-carrefour.html")
LISTA = os.path.join(CARPETA, "articulos.txt")
CATS = os.path.join(CARPETA, "categorias.txt")   # seleccion del explorador de ofertas
# Ultima busqueda hecha. Buscar es lento, asi que el resultado queda en disco y
# sobrevive tanto a cerrar el navegador como a cerrar la ventana negra.
SESION = os.path.join(CARPETA, "ultima-busqueda.json")
# El mismo contenido, envuelto como javascript. Existe por una sola razon: si
# abris el HTML con doble clic (file://) el navegador PROHIBE leer el .json de
# al lado, pero un <script src="..."> si carga. Con esto el modo lectura anda
# tambien sin servidor y sin hosting. Ver "Modo lectura" en CLAUDE.md.
SESION_JS = os.path.join(CARPETA, "ultima-busqueda.js")

PUERTO_PREFERIDO = 8765
BASE = "https://www.carrefour.com.ar"

# Coincidencia minima para que un producto se muestre (principal o alternativa).
# Todo lo que no la supere es ruido del buscador y se descarta.
UMBRAL_COINCIDENCIA = 0.20

# Un resultado tiene que compartir al menos esta cantidad de palabras con lo que
# buscaste. Si la linea tiene una sola palabra util, alcanza con esa.
MIN_PALABRAS = 2

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")

# Contexto SSL: si el sistema no tiene los certificados al dia, se degrada
# a una conexion sin verificar en vez de romper toda la herramienta.
try:
    CTX = ssl.create_default_context()
except Exception:
    CTX = ssl._create_unverified_context()

CACHE = {}
CACHE_LOCK = threading.Lock()


# ----------------------------------------------------------------------
# Consulta a Carrefour
# ----------------------------------------------------------------------
def pedir_json(url):
    cab = {
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-AR,es;q=0.9",
    }
    req = urllib.request.Request(url, headers=cab)
    try:
        with urllib.request.urlopen(req, timeout=25, context=CTX) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except ssl.SSLError:
        ctx2 = ssl._create_unverified_context()
        with urllib.request.urlopen(req, timeout=25, context=ctx2) as r:
            return json.loads(r.read().decode("utf-8", "replace"))


def buscar_inteligente(consulta):
    """Buscador real de la web. Entiende frases completas, acentos y sinonimos.
    Desde Python funciona perfecto; desde el navegador estaba bloqueado por CORS."""
    url = (BASE + "/api/io/_v/api/intelligent-search/product_search/"
           "?query=" + urllib.parse.quote(consulta) + "&count=20&page=1")
    d = pedir_json(url)
    if isinstance(d, dict):
        return d.get("products") or []
    return d if isinstance(d, list) else []


def buscar_legacy(token):
    """Catalogo publico. Es literal (una sola palabra), se usa como respaldo."""
    url = (BASE + "/api/catalog_system/pub/products/search"
           "?ft=" + urllib.parse.quote(token) + "&_from=0&_to=39")
    d = pedir_json(url)
    return d if isinstance(d, list) else []


def con_cache(clave, fn):
    with CACHE_LOCK:
        if clave in CACHE:
            return CACHE[clave]
    valor = fn()
    with CACHE_LOCK:
        CACHE[clave] = valor
    return valor


# ----------------------------------------------------------------------
# Normalizacion y puntaje de coincidencia
# ----------------------------------------------------------------------
IGNORAR = {
    "de", "del", "la", "el", "los", "las", "y", "con", "sin", "en", "un", "una",
    "por", "para", "al", "grs", "gr", "g", "ml", "cc", "unidades", "unidad",
    "uni", "x", "lt", "lts", "l", "kg",
}

# Palabras que describen el producto pero no sirven para consultar:
# son tan comunes que traen cualquier cosa.
GENERICAS = {
    "yogur", "yogurt", "leche", "queso", "papel", "arroz", "fideos", "sopa",
    "pure", "papas", "atun", "palitos", "salados", "hamburguesa", "hamburguesas",
    "salchichas", "jabon", "liquido", "rollo", "rollos", "cocina", "tapa",
    "tapas", "mozzarella", "crema", "cuartirolo", "entero", "entera",
    "descremado", "descremada", "clasico", "clasica", "natural", "cremoso",
    "cremosa", "bebible", "fritas", "doble", "carne", "instantanea",
    "instantaneo", "frutilla", "vainilla", "carolina", "pascualina", "lomitos",
    "fortificada", "endulzar", "aceite", "agua", "light", "sabor", "pack",
}


def norm(s):
    s = unicodedata.normalize("NFD", str(s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9\s.]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def tokens(s):
    return [t for t in norm(s).split(" ") if t and t not in IGNORAR and len(t) > 1]


def claves_busqueda(desc):
    """Palabras candidatas para el buscador literal, de mas distintiva a menos."""
    ts = [t for t in tokens(desc) if not re.fullmatch(r"[0-9.]+", t)]
    propias = sorted([t for t in ts if t not in GENERICAS], key=len, reverse=True)
    comunes = sorted([t for t in ts if t in GENERICAS], key=len, reverse=True)
    return (propias + comunes)[:3]


def texto_producto(prod):
    return " " + norm(prod["nombre"] + " " + prod["marca"]) + " "


def acierta(t, texto):
    """True si la palabra buscada aparece en el nombre/marca del producto.
    Las que llevan digitos (290, 1kg) se exigen enteras; el resto tolera
    plurales y clasico/clasica cayendo la ultima letra."""
    if any(c.isdigit() for c in t):
        return (" " + t) in texto or (t + " ") in texto
    return t in texto or (len(t) > 4 and t[:-1] in texto)


def palabras_en_comun(desc, prod):
    """Cuantas palabras DISTINTAS de lo que buscaste aparecen en el producto."""
    texto = texto_producto(prod)
    return sum(1 for t in set(tokens(desc)) if acierta(t, texto))


def puntaje(desc, prod):
    """0..1 segun cuanto coincide el producto con la descripcion pedida."""
    texto = texto_producto(prod)
    tq = tokens(desc)
    if not tq:
        return 0.0
    total = 0.0
    logrado = 0.0
    for t in tq:
        peso = 2.5 if any(c.isdigit() for c in t) else 1.0   # el gramaje distingue 290 de 500
        total += peso
        if acierta(t, texto):
            logrado += peso
    return logrado / total if total else 0.0


# ----------------------------------------------------------------------
# Parseo de la respuesta de VTEX
# ----------------------------------------------------------------------
def limpiar_promo(t):
    if not t:
        return ""
    t = re.sub(r"^PROMO[\s\-_]*", "", str(t), flags=re.I)
    t = re.split(r"-Reg-|_Reg_|-Gigante|_Gigante", t, flags=re.I)[0]
    t = re.sub(r"\b\d{1,2}\s*al\s*\d{1,2}(\.\d+)?\b", "", t, flags=re.I)
    return re.sub(r"\s{2,}", " ", t).strip(" -_")


def nombre_teaser(t):
    if not isinstance(t, dict):
        return ""
    return t.get("name") or t.get("Name") or t.get("<Name>k__BackingField") or ""


# Los "teasers" de VTEX no son todos promociones: vienen mezclados con medios de
# pago, cuotas y marcadores internos. Sin este filtro TODO parecia estar en oferta.
RUIDO_TEASER = re.compile(
    r"(a\s*vista|vista|vezes|cuota|installment|visa|mastercard|american\s*express|"
    r"cabal|naranja|maestro|mercadopago|prepaga|electron|vale\b|restrictionsbins|"
    r"percentualdiscount|nominaldiscount|k__backingfield)", re.I)

SENAL_PROMO = re.compile(
    r"(%|\boff\b|\bdto\b|descuento|rebaja|\d\s*(do|ro|to|da|ta|va)\s*al\b|"
    r"\b\dx\d\b|\b\dx\b|precio\s*especial|combinable|lleva\b|ahorr|promo)", re.I)


# Promos atadas a un medio de pago propio de Carrefour. No aplican a cualquiera,
# asi que viajan en una lista aparte y NO cuentan como oferta por defecto:
# el selector de la pantalla decide si suman o no.
MEDIO_CARREFOUR = re.compile(
    r"(tarj\w*\s*carrefour|carrefour\s*tarj\w*|cuenta\s*digital|"
    r"mi\s*carrefour|banco\s*de\s*servicios)", re.I)


def es_promo_real(nombre):
    if not nombre or len(nombre) < 3:
        return False
    if RUIDO_TEASER.search(nombre):
        return False
    return bool(SENAL_PROMO.search(nombre))


# ---- Vigencia de la campaña ("Ahorro Gigante", ofertas de almacén, etc.) ----
#
# El nombre crudo del teaser trae, al final, la campaña y sus fechas:
#
#   PROMO-2do al 70% ... CASANCREM-Reg-2-70-Gigante28 al 3.8
#                                           ^^^^^^^^^^^^^^^^
#                                           campaña   del 28 al 3/8
#
# Eso —y no PriceValidUntil, que suele estar clavado a un año vista— es la
# fecha real hasta cuando vale la oferta.
#
# El nombre de la campaña NO se busca contra una lista cerrada. Antes si
# ("gigante", "almacen", "feria"…) y el dia que Carrefour estreno una campaña
# con otro nombre el cartel de vigencia dejo de aparecer, sin avisar nada.
# Ahora se toma como campaña cualquier palabra pegada a las fechas, y lo unico
# que se exige de verdad son las fechas. Si no hay nombre, se llama "Ofertas".
_LETRAS = "A-Za-zÁÉÍÓÚÜÑáéíóúüñ"

CAMPANIA = re.compile(
    r"(?P<campania>[%s][%s ]{1,24}?)?\s*"
    r"(?P<d1>\d{1,2})(?:[./](?P<m1>\d{1,2}))?\s*al\s*"
    # Lo de abajo evita confundir un porcentaje con una fecha: "10 al 20.5%"
    # no es del 10 al 20 de mayo, es un descuento. (Va doble el simbolo de
    # porcentaje porque la plantilla se arma con el operador % de Python.)
    r"(?P<d2>\d{1,2})[./](?P<m2>\d{1,2})(?![\d%%])" % (_LETRAS, _LETRAS), re.I)

# Variante con el mes escrito: "Ahorro Gigante del 28 al 3 de agosto".
MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

CAMPANIA_MES = re.compile(
    r"(?P<campania>[%s][%s ]{1,24}?)?\s*(?:del\s*)?"
    r"(?P<d1>\d{1,2})(?:\s*de\s*(?P<mes1>%s))?\s*al\s*"
    r"(?P<d2>\d{1,2})\s*de\s*(?P<mes2>%s)"
    % (_LETRAS, _LETRAS, "|".join(MESES), "|".join(MESES)), re.I)

# Traducciones lindas de los nombres que Carrefour abrevia. Lo que no este aca
# se muestra tal cual vino, con la primera en mayuscula.
NOMBRE_CAMPANIA = {
    "gigante": "Ahorro Gigante",
    "almacen": "Ofertas de almacén",
    "ahorro": "Ahorro",
    "feria": "Feria",
    "semana": "Ofertas de la semana",
    "finde": "Ofertas de fin de semana",
    "super": "Súper ofertas",
    "mega": "Mega ofertas",
    "aniversario": "Aniversario",
    "black": "Black Friday",
    "hot": "Hot Sale",
    "cyber": "Cyber Monday",
    "navidad": "Navidad",
    "reyes": "Reyes",
}

# Palabras que aparecen pegadas a las fechas pero no son el nombre de nada.
NO_ES_CAMPANIA = {
    "del", "al", "de", "la", "el", "los", "las", "y", "con", "en", "por",
    "vig", "vigencia", "vigente", "valido", "validez", "hasta", "desde",
    "promo", "reg", "max", "maximo", "unidades", "unidad", "combinable",
    "off", "dto", "desc", "descuento", "lleva", "llevando", "x",
}


def _iso(dia, mes, hoy):
    """Arma AAAA-MM-DD deduciendo el año: si el mes ya pasó, es del año que viene."""
    anio = hoy.year
    if mes < hoy.month - 1:          # ej. hoy diciembre y la promo dice enero
        anio += 1
    try:
        return "%04d-%02d-%02d" % (anio, mes, dia)
    except Exception:
        return ""


def _nombre_campania(crudo):
    """Limpia el pedacito de texto que venia pegado a las fechas."""
    txt = re.sub(r"\s{2,}", " ", str(crudo or "")).strip(" -_")
    # Se tiran las palabras de relleno del final ("Gigante del" → "Gigante").
    palabras = [p for p in txt.split(" ") if p]
    while palabras and norm(palabras[-1]) in NO_ES_CAMPANIA:
        palabras.pop()
    while palabras and norm(palabras[0]) in NO_ES_CAMPANIA:
        palabras.pop(0)
    if not palabras:
        return "Ofertas"
    txt = " ".join(palabras)
    clave = norm(txt).split(" ")[0]
    return NOMBRE_CAMPANIA.get(clave, txt.strip().title())


def _mes_num(nombre):
    return MESES.get(norm(nombre), 0) if nombre else 0


def periodo_campania(crudo):
    """De un nombre de teaser sin limpiar → (campaña, desde, hasta) o ("", "", "").

    Se prueban las dos formas que usa Carrefour: fechas en numeros
    ("Gigante28 al 3.8") y con el mes escrito ("del 28 al 3 de agosto")."""
    texto = str(crudo or "")
    m = CAMPANIA.search(texto)
    if m:
        d2, m2 = int(m.group("d2")), int(m.group("m2"))
        d1 = int(m.group("d1"))
        m1 = int(m.group("m1")) if m.group("m1") else 0
    else:
        m = CAMPANIA_MES.search(texto)
        if not m:
            return "", "", ""
        d2, m2 = int(m.group("d2")), _mes_num(m.group("mes2"))
        d1 = int(m.group("d1"))
        m1 = _mes_num(m.group("mes1"))

    if not (1 <= d2 <= 31 and 1 <= m2 <= 12):
        return "", "", ""
    hoy = datetime.date.today()
    hasta = _iso(d2, m2, hoy)

    # Si no dijo el mes de arranque: el mismo que el de cierre, salvo que el dia
    # sea mayor (28 al 3 = arranca el mes anterior).
    if not m1:
        m1 = m2 if d1 <= d2 else (m2 - 1 or 12)
    desde = _iso(d1, m1, hoy) if 1 <= d1 <= 31 and 1 <= m1 <= 12 else ""

    return _nombre_campania(m.group("campania")), desde, hasta


def _vendible(of):
    """True si ese SKU se puede comprar de verdad: con stock y con precio."""
    if of.get("IsAvailable") is False:
        return False
    precio = of.get("Price")
    return bool((of.get("AvailableQuantity") or 0) > 0
                and isinstance(precio, (int, float)) and precio > 0)


def _oferta_de(it):
    sellers = (it or {}).get("sellers") or [{}]
    s = sellers[0] if sellers else {}
    return s, (s.get("commertialOffer") or {})


def parsear(p):
    items = p.get("items") or [{}]

    # Un producto puede tener varios SKU y que el primero este agotado. Se toma
    # el primero que SI se pueda comprar; si no hay ninguno, queda el primero
    # (y mas adelante el filtro de "vendible" lo descarta).
    it = items[0] if items else {}
    for cand in items:
        if _vendible(_oferta_de(cand)[1]):
            it = cand
            break
    sellers, of = _oferta_de(it)

    brutos = (of.get("Teasers") or of.get("teasers")
              or of.get("<Teasers>k__BackingField") or [])
    promos, promos_tarjeta, vistos = [], [], set()
    campania = desde = hasta = ""
    for t in brutos:
        crudo = nombre_teaser(t)
        if not hasta:
            campania, desde, hasta = periodo_campania(crudo)
        n = limpiar_promo(crudo)
        k = n.lower()
        if es_promo_real(n) and k not in vistos:
            vistos.add(k)
            if MEDIO_CARREFOUR.search(n):
                promos_tarjeta.append(n)
            else:
                promos.append(n)

    precio = of.get("Price")
    lista = of.get("ListPrice")
    precio = precio if isinstance(precio, (int, float)) and precio > 0 else None
    lista = lista if isinstance(lista, (int, float)) and lista > 0 else None
    desc = round((1 - precio / lista) * 100) if (precio and lista and lista > precio) else 0

    link = p.get("link") or ("/" + (p.get("linkText") or "") + "/p")
    if link.startswith("/"):
        link = BASE + link

    imgs = it.get("images") or []
    img = imgs[0].get("imageUrl") if imgs else ""

    # Datos que necesita el link /checkout/cart/add del boton "Al carrito".
    sku = str(it.get("itemId") or it.get("itemid") or "")
    vendedor = str(sellers.get("sellerId") or "1")

    return {
        "id": str(p.get("productId") or p.get("linkText") or link),
        "nombre": p.get("productName") or "(sin nombre)",
        "marca": p.get("brand") or "",
        "link": link,
        "sku": sku,
        "vendedor": vendedor,
        "img": img or "",
        "precio": precio,
        "lista": lista,
        "desc": desc,
        "promos": promos,
        "promosTarjeta": promos_tarjeta,
        # Vigencia de la campaña, leida del nombre del teaser ("Gigante28 al 3.8").
        "campania": campania,     # "Ahorro Gigante", "Ofertas de almacén", …
        "desde": desde,           # "AAAA-MM-DD" o ""
        "hasta": hasta,           # "AAAA-MM-DD" o ""
        "disponible": _vendible(of),
        # Las promos de Tarjeta / Cuenta Digital quedan afuera a proposito.
        # Si el selector de la pantalla esta activado, el HTML las suma.
        "enOferta": bool(promos) or desc > 0,
    }


def por_precio(lst):
    """Ofertas primero; dentro de cada grupo, de mas barato a mas caro.
    Los que no tienen precio quedan al final."""
    def clave(p):
        return (0 if p["enOferta"] else 1,
                0 if p["precio"] is not None else 1,
                p["precio"] if p["precio"] is not None else 0)
    return sorted(lst, key=clave)


# ----------------------------------------------------------------------
# Busqueda de un articulo de la lista
# ----------------------------------------------------------------------
# Separadores entre "lo que describe" y "lo que se busca".
# El "+" se exige CON espacios a los costados para no romper nombres reales
# tipo "pack 4+1" o "shampoo 2en1+acondicionador".
SEPARADOR = re.compile(r"\s*>\s*|\s+\+\s+")


def partir(linea):
    """'Descripcion completa > palabraclave'  ->  (descripcion, clave|None)
    Tambien vale ' + ' en lugar de '>'."""
    partes = SEPARADOR.split(linea, 1)
    if len(partes) == 2:
        return partes[0].strip(), partes[1].strip()
    return linea.strip(), None


def buscar_articulo(linea):
    desc, clave = partir(linea)
    if not desc:
        return {"linea": linea, "desc": linea, "via": "-", "principal": None,
                "alternativas": [], "error": "Linea vacia."}

    consulta = clave or desc
    acumulado = {}
    vias = []
    hubo_red = False
    error = None

    # 1) Buscador inteligente con la frase completa.
    try:
        crudos = con_cache("IS:" + consulta, lambda: buscar_inteligente(consulta))
        hubo_red = True
        if crudos:
            vias.append("buscador inteligente")
        for p in crudos:
            d = parsear(p)
            acumulado.setdefault(d["id"], d)
    except Exception as e:
        error = "Buscador inteligente: %s" % e

    def mejor_puntaje():
        return max([puntaje(desc, p) for p in acumulado.values()], default=0.0)

    # 2) Si no alcanzo, respaldo con el catalogo literal palabra por palabra.
    if mejor_puntaje() < 0.85:
        for k in ([norm(clave)] if clave else claves_busqueda(desc)):
            if not k:
                continue
            try:
                crudos = con_cache("LG:" + k, lambda k=k: buscar_legacy(k))
                hubo_red = True
                if crudos and ("catalogo (%s)" % k) not in vias:
                    vias.append("catalogo (%s)" % k)
                for p in crudos:
                    d = parsear(p)
                    acumulado.setdefault(d["id"], d)
            except Exception as e:
                error = error or ("Catalogo: %s" % e)
            if mejor_puntaje() >= 0.9:
                break

    if not hubo_red:
        return {"linea": linea, "desc": desc, "via": "-", "principal": None,
                "alternativas": [], "error": error or "No se pudo conectar con Carrefour."}

    crudos = list(acumulado.values())
    for p in crudos:
        p["score"] = round(puntaje(desc, p), 4)
        p["comunes"] = palabras_en_comun(desc, p)

    # Sin precio o sin stock online no sirve para comparar: se descarta antes
    # que nada, no llega a la pantalla ni como alternativa.
    vendibles = [p for p in crudos if p["disponible"] and p["precio"]]

    # Ademas, para entrar tiene que:
    #  1) compartir al menos MIN_PALABRAS palabras con lo que buscaste
    #     (si tu linea tiene una sola palabra, alcanza con esa),
    #  2) superar el umbral de coincidencia.
    minimo = min(MIN_PALABRAS, len(set(tokens(desc))))
    todos = [p for p in vendibles
             if p["comunes"] >= minimo and p["score"] > UMBRAL_COINCIDENCIA]

    if not todos:
        if vendibles:
            motivo = ("Ningún resultado comparte %d palabra%s con «%s» "
                      "(o quedó por debajo del %d%% de coincidencia)."
                      % (minimo, "s" if minimo > 1 else "", consulta,
                         round(UMBRAL_COINCIDENCIA * 100)))
        elif crudos:
            motivo = ("Lo que trajo «%s» está sin stock online o sin precio."
                      % consulta)
        else:
            motivo = "Sin resultados para «%s»." % consulta
        return {"linea": linea, "desc": desc, "via": " + ".join(vias) or "-",
                "principal": None, "alternativas": [], "error": motivo}

    # El PRINCIPAL es el mas exacto (mayor coincidencia), no el mas barato.
    orden = sorted(todos, key=lambda p: -p["score"])
    principal = orden[0]
    # El resto: ofertas primero y de mas barato a mas caro. Van TODAS: el
    # usuario pidio no recortar resultados. El acordeon ya tiene scroll propio.
    alternativas = por_precio(orden[1:])

    return {"linea": linea, "desc": desc, "via": " + ".join(vias) or "-",
            "principal": principal, "alternativas": alternativas, "error": None}


# ----------------------------------------------------------------------
# Explorador de ofertas (funcion aparte, no toca la lista de articulos)
#
# Usa el catalogo legacy porque acepta filtrar por categoria y ORDENAR POR
# DESCUENTO: con eso las primeras paginas de cada rubro ya son casi todas
# ofertas, y no hay que barrer el sitio entero.
# ----------------------------------------------------------------------
POR_PAGINA = 50          # el maximo que devuelve VTEX de una
# VTEX no deja pedir mas alla de los ~2500 primeros productos de una consulta:
# pasado ese punto devuelve error. Es el unico techo real que hay.
TOPE_VENTANA = 2500
PAGINAS_MAX = TOPE_VENTANA // POR_PAGINA
EN_PARALELO = 6          # paginas que se piden a la vez, para no tardar una eternidad


def arbol_categorias():
    """Departamentos y sus subcategorias, tal como los publica Carrefour."""
    return pedir_json(BASE + "/api/catalog_system/pub/category/tree/2")


def categorias_planas():
    arbol = con_cache("ARBOL", arbol_categorias)
    salida = []
    for dep in (arbol or []):
        if not dep.get("id"):
            continue
        salida.append({"id": dep.get("id"), "nombre": dep.get("name") or "",
                       "padre": None, "padreId": None})
        for hijo in (dep.get("children") or []):
            if not hijo.get("id"):
                continue
            salida.append({"id": hijo.get("id"), "nombre": hijo.get("name") or "",
                           "padre": dep.get("name") or "", "padreId": dep.get("id")})
    return salida


def rutas_categorias():
    """id -> camino completo de la categoria: "292/293" para una subcategoria,
    "292" para un departamento. Cacheado, igual que el arbol del que sale."""
    def armar():
        mapa = {}
        for c in categorias_planas():
            cid = str(c["id"])
            mapa[cid] = "%s/%s" % (c["padreId"], cid) if c.get("padreId") else cid
        return mapa
    return con_cache("RUTAS", armar)


def ruta_categoria(cat_id):
    """El fq=C: del catalogo legacy quiere el CAMINO ENTERO, no el id de la hoja.

    `fq=C:/293/` (sólo "Leches") devuelve [] sin avisar; hay que mandar
    `fq=C:/292/293/` ("Lácteos y productos frescos" › "Leches"). Por eso marcar
    una subcategoría no traía ninguna oferta y marcar el departamento sí.
    Si el id no está en el árbol, se manda tal cual: peor no puede salir."""
    cid = re.sub(r"\D", "", str(cat_id or ""))
    if not cid:
        return ""
    try:
        return rutas_categorias().get(cid, cid)
    except Exception:
        return cid          # sin árbol (Carrefour caído) se sigue como antes


# ---- Guardar y cargar la seleccion de categorias en categorias.txt ----
# Formato: una por linea, "id | nombre". El nombre es solo para que se pueda
# leer y editar a mano; lo que manda es el numero de adelante.
def leer_seleccion_cats():
    try:
        with open(CATS, "r", encoding="utf-8") as f:
            texto = f.read()
    except FileNotFoundError:
        return [], ""
    ids = []
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        cabeza = linea.split("|", 1)[0].strip()
        if cabeza:
            ids.append(cabeza)
    return ids, texto


def guardar_seleccion_cats(items):
    """items: [{id, nombre}] tal como los manda la pantalla."""
    lineas = ["# Categorías elegidas en el explorador de ofertas.",
              "# Una por línea: id | nombre.  Con # al principio se ignora.",
              ""]
    for it in (items or []):
        lineas.append("%s | %s" % (str(it.get("id", "")).strip(),
                                   str(it.get("nombre", "")).strip()))
    with open(CATS, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")
    return CATS


# ---- La ultima busqueda, guardada en la carpeta ----
# Buscar es lento (la lista, un rato; el explorador de ofertas, minutos), asi
# que cerrar el navegador no tiene por que costar otra vuelta entera. Al
# terminar cada busqueda la pantalla manda lo que encontro y esto lo deja en
# ultima-busqueda.json; al abrir de nuevo, la pantalla se rearma sola.
#
# Es un archivo comun de la carpeta: se puede borrar a mano para empezar de cero.
SESION_LOCK = threading.Lock()
PARTES_SESION = ("lista", "ofertas")


def leer_sesion():
    """Todo lo guardado: {"lista": {...}, "ofertas": {...}}. Si no hay, {}."""
    try:
        with open(SESION, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except FileNotFoundError:
        return {}
    except (ValueError, OSError):
        return {}          # archivo a medio escribir o ilegible: como si no hubiera


def _escribir_atomico(ruta, texto):
    """Se escribe en un temporal y recien ahi se reemplaza: si el programa se
    corta en el medio, queda el archivo viejo entero y no uno a la mitad."""
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(texto)
    os.replace(tmp, ruta)


def _borrar(ruta):
    try:
        os.remove(ruta)
    except OSError:
        pass


def _volcar_sesion(d):
    """Deja lo guardado en los dos archivos gemelos: el .json (que es el que
    lee este programa y el que se sube a un hosting) y el .js (que es el unico
    que el navegador deja leer cuando abris el HTML con doble clic)."""
    crudo = json.dumps(d, ensure_ascii=False)
    _escribir_atomico(SESION, crudo)
    _escribir_atomico(SESION_JS, "window.ULTIMA_BUSQUEDA = %s;\n" % crudo)


def sincronizar_js():
    """Al arrancar: si hay un .json de una version anterior y todavia no existe
    su .js, se genera. Asi el modo lectura funciona sin tener que rebuscar."""
    if os.path.exists(SESION) and not os.path.exists(SESION_JS):
        d = leer_sesion()
        if d:
            try:
                _volcar_sesion(d)
            except OSError:
                pass       # carpeta de solo lectura: se sigue igual, sin el gemelo


def guardar_sesion(parte, datos):
    """Reemplaza UNA parte ('lista' u 'ofertas') y deja la otra como estaba.
    Con datos=None esa parte se borra. Devuelve la marca de tiempo guardada."""
    if parte not in PARTES_SESION:
        raise ValueError("Parte desconocida: %r" % (parte,))

    with SESION_LOCK:
        d = leer_sesion()
        if datos is None:
            d.pop(parte, None)
            cuando = ""
        else:
            if not isinstance(datos, dict):
                raise ValueError("Los datos de la sesion tienen que ser un objeto.")
            datos = dict(datos)
            cuando = datetime.datetime.now().replace(microsecond=0).isoformat()
            datos["guardado"] = cuando
            d[parte] = datos

        if not d:
            _borrar(SESION)
            _borrar(SESION_JS)
            return cuando

        _volcar_sesion(d)
        return cuando


def pagina_categoria(cat_id, pagina):
    """Una tanda de productos de una categoria, los de mayor descuento primero."""
    ruta = ruta_categoria(cat_id)      # camino entero: sin eso las subcategorias vienen vacias
    if not ruta:
        return []
    desde = pagina * POR_PAGINA
    url = (BASE + "/api/catalog_system/pub/products/search"
           "?fq=C:/%s/&O=OrderByBestDiscountDESC&_from=%d&_to=%d"
           % (ruta, desde, desde + POR_PAGINA - 1))
    d = pedir_json(url)
    return d if isinstance(d, list) else []


def nombre_categoria(p):
    cats = p.get("categories") or []
    if not cats:
        return ""
    partes = [x for x in str(cats[0]).split("/") if x]
    return " › ".join(partes[-2:]) if partes else ""


def explorar_ofertas(cat_id, desde=0, paginas=EN_PARALELO):
    """Un TRAMO de la categoria: las paginas [desde, desde+paginas).

    Se devuelve de a tramos —y no la categoria entera de una— para que la
    pantalla pueda mostrar el avance y las ofertas vayan apareciendo en vez de
    dejar al usuario mirando una barra quieta. Las paginas del tramo se piden
    en paralelo, que es lo que hace que esto no tarde minutos.

    `fin` avisa que ya no hay mas: o Carrefour devolvio una pagina incompleta,
    o se llego al tope de VTEX (no deja pasar de los ~2500 primeros productos).

    Incluye las promos de Tarjeta / Cuenta Digital: la pantalla decide si las
    muestra o no, igual que en el resto de la herramienta."""
    try:
        desde = max(0, int(desde or 0))
        paginas = max(1, min(int(paginas or EN_PARALELO), EN_PARALELO))
    except (TypeError, ValueError):
        desde, paginas = 0, EN_PARALELO

    tanda = list(range(desde, min(desde + paginas, PAGINAS_MAX)))
    items, vistos = [], set()
    error = None
    fin = not tanda            # ya se paso del tope: no hay nada mas que mirar
    productos = 0

    if tanda:
        with ThreadPoolExecutor(max_workers=len(tanda)) as pool:
            futuros = [pool.submit(con_cache, "CAT:%s:%d" % (cat_id, g),
                                   lambda c=cat_id, g=g: pagina_categoria(c, g))
                       for g in tanda]

            for fut in futuros:
                try:
                    crudos = fut.result()
                except Exception as e:
                    error = error or ("Categoría %s: %s" % (cat_id, e))
                    fin = True
                    continue

                productos += len(crudos)
                # Una pagina incompleta significa que se acabo la categoria.
                if len(crudos) < POR_PAGINA:
                    fin = True

                for p in crudos:
                    d = parsear(p)
                    if not d["disponible"] or not d["precio"]:
                        continue
                    if not (d["enOferta"] or d["promosTarjeta"]):
                        continue
                    if d["id"] in vistos:
                        continue
                    vistos.add(d["id"])
                    d["cat"] = nombre_categoria(p)
                    d["score"] = 1.0          # aca no hay nada que "coincidir"
                    items.append(d)

        if tanda[-1] + 1 >= PAGINAS_MAX:
            fin = True

    return {"cat": cat_id, "items": items, "error": error, "fin": fin,
            "leidas": len(tanda), "productos": productos}


# ----------------------------------------------------------------------
# Servidor local
# ----------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass  # silencio: la consola queda limpia para los mensajes utiles

    def _responder(self, codigo, cuerpo, tipo="application/json; charset=utf-8"):
        if isinstance(cuerpo, str):
            cuerpo = cuerpo.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _json(self, obj, codigo=200):
        self._responder(codigo, json.dumps(obj, ensure_ascii=False))

    def _cuerpo(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    def do_GET(self):
        ruta = urllib.parse.urlparse(self.path).path

        if ruta in ("/", "/index.html", "/verificador-carrefour.html"):
            try:
                with open(HTML, "rb") as f:
                    return self._responder(200, f.read(), "text/html; charset=utf-8")
            except FileNotFoundError:
                return self._responder(500, "Falta verificador-carrefour.html en la carpeta.",
                                       "text/plain; charset=utf-8")

        if ruta == "/api/articulos":
            try:
                with open(LISTA, "r", encoding="utf-8") as f:
                    return self._json({"texto": f.read()})
            except FileNotFoundError:
                return self._json({"texto": ""})

        if ruta == "/api/ping":
            return self._json({"ok": True})

        if ruta == "/api/categorias":
            try:
                return self._json({"categorias": categorias_planas(), "error": None})
            except Exception as e:
                return self._json({"categorias": [], "error": str(e)})

        if ruta == "/api/sesion":
            try:
                return self._json(leer_sesion())
            except Exception as e:
                return self._json({"error": str(e)})

        if ruta == "/api/cats-guardadas":
            try:
                ids, texto = leer_seleccion_cats()
                return self._json({"ids": ids, "texto": texto, "archivo": CATS})
            except Exception as e:
                return self._json({"ids": [], "texto": "", "error": str(e)})

        return self._responder(404, "No existe", "text/plain; charset=utf-8")

    def do_POST(self):
        ruta = urllib.parse.urlparse(self.path).path
        datos = self._cuerpo()

        if ruta == "/api/buscar":
            linea = (datos.get("linea") or "").strip()
            try:
                return self._json(buscar_articulo(linea))
            except Exception as e:
                return self._json({"linea": linea, "desc": linea, "via": "-",
                                   "principal": None, "alternativas": [],
                                   "error": "Error inesperado: %s" % e})

        if ruta == "/api/ofertas":
            cat = datos.get("cat")
            try:
                return self._json(explorar_ofertas(cat, datos.get("desde"),
                                                   datos.get("paginas")))
            except Exception as e:
                return self._json({"cat": cat, "items": [], "fin": True,
                                   "leidas": 0, "productos": 0,
                                   "error": "Error inesperado: %s" % e})

        if ruta == "/api/sesion":
            try:
                cuando = guardar_sesion(datos.get("parte"), datos.get("datos"))
                return self._json({"ok": True, "guardado": cuando, "archivo": SESION})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)})

        if ruta == "/api/guardar-cats":
            try:
                arch = guardar_seleccion_cats(datos.get("cats"))
                return self._json({"ok": True, "archivo": arch})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)})

        if ruta == "/api/guardar":
            try:
                with open(LISTA, "w", encoding="utf-8") as f:
                    f.write(datos.get("texto") or "")
                return self._json({"ok": True, "archivo": LISTA})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)})

        if ruta == "/api/salir":
            self._json({"ok": True})
            threading.Thread(target=lambda: os._exit(0)).start()
            return

        return self._responder(404, "No existe", "text/plain; charset=utf-8")


def elegir_puerto():
    import socket
    for p in range(PUERTO_PREFERIDO, PUERTO_PREFERIDO + 20):
        s = socket.socket()
        try:
            s.bind(("127.0.0.1", p))
            s.close()
            return p
        except OSError:
            s.close()
    return 0


def main():
    if not os.path.exists(HTML):
        print("ERROR: falta 'verificador-carrefour.html' en", CARPETA)
        input("Enter para salir...")
        return

    sincronizar_js()      # que el modo lectura ande aunque no rebusques nada

    puerto = elegir_puerto()
    url = "http://127.0.0.1:%d/" % puerto
    servidor = ThreadingHTTPServer(("127.0.0.1", puerto), Handler)

    print("=" * 64)
    print(" Verificador de precios Carrefour")
    print("=" * 64)
    print(" Abriendo:", url)
    print(" Dejá esta ventana negra abierta mientras usás la herramienta.")
    print(" Para terminar: cerrá esta ventana o apretá Ctrl+C.")
    print("=" * 64)

    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nCerrando...")


if __name__ == "__main__":
    main()
