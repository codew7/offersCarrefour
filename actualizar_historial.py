# -*- coding: utf-8 -*-
"""
Actualiza historial-carrefour.json con los pedidos nuevos de tu cuenta,
usando TU navegador de siempre (Brave), con tu sesión y tus contraseñas.

Cómo funciona:
  1. Abre carrefour.com.ar en tu Brave, como cualquier link.
  2. Vos tocás el favorito "📥 Historial Carrefour" de la barra. Ese favorito
     corre en la página de Carrefour, con tu sesión, y baja un
     historial-carrefour.json a tu carpeta de Descargas.
  3. Este programa ve aparecer el archivo, suma los pedidos nuevos al historial
     de la carpeta del programa (no borra los viejos) y borra la descarga.

Por qué no se maneja Brave "por control remoto": desde 2025 Chrome y Brave no
dejan que un programa controle el perfil principal (el que tiene tus
contraseñas), para frenar a los programas que roban sesiones. El favorito es
la forma de usar ese perfil sin pasar por arriba de esa protección.

El código del favorito NO vive acá: se lee de verificador-carrefour.html
(<script id="hbCodigo">), así hay una sola copia.

Solo biblioteca estándar: no instala nada.
"""
import datetime
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import webbrowser

CARPETA = os.path.dirname(os.path.abspath(__file__))
HISTORIAL = os.path.join(CARPETA, "historial-carrefour.json")
PAGINA = os.path.join(CARPETA, "verificador-carrefour.html")
INICIO = "https://www.carrefour.com.ar/"

# Cosas propias del programa que no tienen que ir a la carpeta del proyecto.
DATOS = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"),
                     "verificador-carrefour")
FAVORITO_HTML = os.path.join(DATOS, "instalar-favorito.html")
FAVORITO_OK = os.path.join(DATOS, "favorito-instalado")   # se crea tras la 1ra importación

ESPERA = 15 * 60          # cuánto se espera a que toques el favorito
DESCARGA = re.compile(r"^historial-carrefour.*\.json$", re.I)


# ----------------------------------------------------------------------
# Brave y la carpeta de Descargas
# ----------------------------------------------------------------------
def buscar_brave():
    bases = [os.environ.get(k) for k in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
    for b in filter(None, bases):
        c = os.path.join(b, "BraveSoftware", "Brave-Browser", "Application", "brave.exe")
        if os.path.exists(c):
            return c
    return shutil.which("brave")


def carpetas_descargas():
    """Donde puede caer el archivo: la carpeta que configuraste en Brave (si
    elegiste una) y la carpeta de Descargas de Windows."""
    salida = []
    prefs = os.path.join(os.environ.get("LOCALAPPDATA") or "", "BraveSoftware",
                         "Brave-Browser", "User Data", "Default", "Preferences")
    try:
        with open(prefs, "r", encoding="utf-8") as f:
            d = (json.load(f).get("download") or {}).get("default_directory")
        if d:
            salida.append(d)
    except (OSError, ValueError):
        pass
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
            v = winreg.QueryValueEx(k, "{374DE290-123F-4565-9164-39C4925E467B}")[0]
            salida.append(os.path.expandvars(v))
    except Exception:
        pass
    salida.append(os.path.join(os.path.expanduser("~"), "Downloads"))
    vistas, unicas = set(), []
    for c in salida:
        k = os.path.normcase(os.path.abspath(c))
        if k not in vistas and os.path.isdir(c):
            vistas.add(k)
            unicas.append(c)
    return unicas


def descargas_nuevas(desde):
    """historial-carrefour*.json bajados después de `desde` (marca de tiempo)."""
    hallados = []
    for c in carpetas_descargas():
        try:
            nombres = os.listdir(c)
        except OSError:
            continue
        for n in nombres:
            if not DESCARGA.match(n):
                continue
            ruta = os.path.join(c, n)
            try:
                if os.path.getmtime(ruta) >= desde:
                    hallados.append(ruta)
            except OSError:
                pass
    return sorted(hallados, key=os.path.getmtime)


def abrir(url):
    brave = buscar_brave()
    if brave:
        # Sin --user-data-dir: es tu Brave de siempre. Si ya está abierto, se
        # suma una pestaña a la ventana que tengas.
        subprocess.Popen([brave, url])
    else:
        webbrowser.open(url)


# ----------------------------------------------------------------------
# El favorito
# ----------------------------------------------------------------------
def codigo_favorito():
    with open(PAGINA, "r", encoding="utf-8") as f:
        m = re.search(r'<script type="text/plain" id="hbCodigo">(.*?)</script>', f.read(), re.S)
    if not m:
        raise RuntimeError("No encontré el código del favorito en verificador-carrefour.html")
    # Un favorito es una sola línea: se compacta y se codifica para la URL.
    codigo = " ".join(l.strip() for l in m.group(1).strip().splitlines())
    return "javascript:" + urllib.parse.quote(codigo, safe="(){}[];,=>!'.:/?&|*+-_")


def preparar_pagina_favorito():
    """Una página local con el botón para arrastrar a la barra de favoritos."""
    os.makedirs(DATOS, exist_ok=True)
    href = html.escape(codigo_favorito(), quote=True)
    pagina = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>Instalar favorito · Historial Carrefour</title>
<style>
 body{font-family:system-ui,Segoe UI,sans-serif;background:#f2f5f9;color:#1d2430;margin:0;padding:40px 16px}
 .caja{max-width:620px;margin:auto;background:#fff;border-radius:14px;padding:28px 30px;
       box-shadow:0 4px 18px rgba(0,40,90,.08);line-height:1.6}
 h1{font-size:21px;margin:0 0 6px;color:#004E9F}
 ol{padding-left:22px}
 .fav{display:inline-block;margin:14px 0 18px;background:#004E9F;color:#fff;font-weight:700;
      padding:12px 20px;border-radius:999px;text-decoration:none;font-size:16px;cursor:grab}
 .nota{color:#5b6675;font-size:13.5px}
</style></head><body><div class="caja">
<h1>Un solo paso, una sola vez</h1>
<p><b>Arrastrá este botón</b> hasta la barra de favoritos de Brave (la franja de abajo de la
dirección) y soltalo ahí:</p>
<a class="fav" href="%s" onclick="alert('No hay que tocarlo acá: arrastralo a la barra de favoritos.');return false;">📥 Historial Carrefour</a>
<ol>
 <li>Andá a la pestaña de <b>carrefour.com.ar</b> que se abrió al lado.</li>
 <li>Si no tenés la sesión iniciada, iniciala (Brave te completa la contraseña).</li>
 <li>Tocá el favorito <b>📥 Historial Carrefour</b> en la barra.</li>
 <li>Esperá el cartel "N pedidos exportados". La ventana negra hace el resto.</li>
</ol>
<p class="nota">Las próximas veces es sólo el paso 3. El favorito lee <b>tus pedidos</b> y baja
un archivo con los productos; tu contraseña y tus datos de pago no salen de Brave.
Si Brave te pregunta si permitís la descarga, decile que sí.</p>
</div></body></html>""" % href
    with open(FAVORITO_HTML, "w", encoding="utf-8") as f:
        f.write(pagina)
    return FAVORITO_HTML


# ----------------------------------------------------------------------
# Unir lo descargado con lo que ya había
# ----------------------------------------------------------------------
def leer(ruta):
    with open(ruta, "r", encoding="utf-8") as f:
        d = json.load(f)
    if not isinstance(d, dict) or not isinstance(d.get("pedidos"), list):
        raise ValueError("%s no tiene pedidos" % os.path.basename(ruta))
    return d["pedidos"]


def unir(nuevos):
    """Suma `nuevos` al historial de la carpeta. Lo nuevo pisa a lo viejo con el
    mismo número de pedido (por si cambió de estado). Devuelve
    (pedidos agregados, productos que no estaban, total de pedidos)."""
    try:
        viejos = leer(HISTORIAL)
    except FileNotFoundError:
        viejos = []
    por_id = {o.get("pedido"): o for o in viejos}
    agregados = sum(1 for o in nuevos if o.get("pedido") not in por_id)
    antes = {i.get("productId") for o in viejos for i in o.get("items") or []}
    for o in nuevos:
        por_id[o.get("pedido")] = o
    nuevos_prod = {i.get("productId") for o in nuevos for i in o.get("items") or []} - antes

    todos = sorted(por_id.values(), key=lambda o: str(o.get("fecha") or ""), reverse=True)
    d = {"exportado": datetime.datetime.now(datetime.timezone.utc).isoformat(), "pedidos": todos}
    tmp = HISTORIAL + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, HISTORIAL)    # si se corta en el medio, queda el archivo viejo entero
    return agregados, len(nuevos_prod), len(todos)


def importar_descargas(desde=None):
    """Suma al historial cualquier historial-carrefour*.json de Descargas que sea
    más nuevo que el historial de la carpeta, y borra la descarga. La usa
    también el verificador al tocar "Leer historial"."""
    if desde is None:
        try:
            desde = os.path.getmtime(HISTORIAL)
        except OSError:
            desde = 0
    total = [0, 0, 0]
    for ruta in descargas_nuevas(desde):
        try:
            a, p, t = unir(leer(ruta))
        except (OSError, ValueError):
            continue           # a medio bajar o no es nuestro: se deja como está
        total = [total[0] + a, total[1] + p, t]
        try:
            os.remove(ruta)
        except OSError:
            pass
    return total


# ----------------------------------------------------------------------
def fin(msj, codigo=0):
    print()
    print(msj)
    print()
    if codigo:
        input("Enter para cerrar...")
    sys.exit(codigo)


def main():
    print("=" * 64)
    print(" Actualizar historial de compras · Carrefour (con tu Brave)")
    print("=" * 64)

    inicio = time.time() - 2
    primera = not os.path.exists(FAVORITO_OK)

    abrir(INICIO)
    if primera:
        abrir("file:///" + preparar_pagina_favorito().replace("\\", "/"))
        print()
        print(" PRIMERA VEZ: en Brave se abrió una página que explica cómo poner")
        print(" el favorito \"📥 Historial Carrefour\" en tu barra. Es un solo paso.")
    print()
    print(" En la pestaña de carrefour.com.ar (con tu sesión iniciada)")
    print(" tocá el favorito  📥 Historial Carrefour  de la barra.")
    print()
    print(" Esperando la descarga... (se puede cancelar cerrando esta ventana)")

    limite = time.time() + ESPERA
    while time.time() < limite:
        # Se espera a que el archivo deje de crecer: Brave lo escribe de a poco.
        hallados = descargas_nuevas(inicio)
        if hallados:
            time.sleep(1.5)
            agregados, productos, total = importar_descargas(inicio)
            if total:
                os.makedirs(DATOS, exist_ok=True)
                open(FAVORITO_OK, "w").close()
                print()
                print("=" * 64)
                if agregados:
                    print(" Listo: %d pedido%s nuevo%s, %d producto%s que no tenías." % (
                        agregados, "" if agregados == 1 else "s", "" if agregados == 1 else "s",
                        productos, "" if productos == 1 else "s"))
                else:
                    print(" Listo: no hay pedidos nuevos desde la última vez.")
                print(" El historial tiene ahora %d pedidos." % total)
                print(" En el verificador, 'Lo que compro' ya los toma (o tocá 'Leer historial').")
                print("=" * 64)
                time.sleep(8)
                return
        time.sleep(1)
    fin("Pasaron %d minutos y no llegó ninguna descarga. Probá de nuevo." % (ESPERA // 60), 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        fin("Cancelado.", 1)
    except SystemExit:
        raise
    except Exception as e:
        fin("Algo salió mal: %s" % e, 1)
