// Service worker: lo que hace falta para que Android deje INSTALAR la página
// (ícono en la pantalla de inicio, abre sin barra del navegador).
//
// Estrategia: primero la red, y si no hay red, lo último que se guardó. Así
// siempre ves la búsqueda más nueva que subiste, y sin señal en el súper
// todavía abre con la anterior.
// Nunca se toca /api/ (eso es el Python de la computadora) ni nada de otro
// origen (las fotos de Carrefour, el carrito).
var CACHE = "ofertas-carrefour-v1";
var BASE = ["./verificador-carrefour.html", "./manifest.webmanifest",
            "./iconos/icono-192.png", "./iconos/icono-512.png"];

self.addEventListener("install", function(e){
  e.waitUntil(caches.open(CACHE).then(function(c){
    return Promise.all(BASE.map(function(u){ return c.add(u).catch(function(){}); }));
  }).then(function(){ return self.skipWaiting(); }));
});

self.addEventListener("activate", function(e){
  e.waitUntil(caches.keys().then(function(ks){
    return Promise.all(ks.filter(function(k){ return k !== CACHE; })
                         .map(function(k){ return caches.delete(k); }));
  }).then(function(){ return self.clients.claim(); }));
});

self.addEventListener("fetch", function(e){
  var req = e.request, url = new URL(req.url);
  if(req.method !== "GET" || url.origin !== location.origin || url.pathname.indexOf("/api/") !== -1) return;
  // "?t=123" (el .js de la sesión) se guarda sin la marca, así hay una sola copia.
  var clave = url.origin + url.pathname;
  e.respondWith(fetch(req).then(function(r){
    if(r && r.ok){
      var copia = r.clone();
      caches.open(CACHE).then(function(c){ c.put(clave, copia); });
    }
    return r;
  }).catch(function(){
    return caches.match(clave).then(function(r){
      return r || (req.mode === "navigate" ? caches.match("./verificador-carrefour.html") : r) || Response.error();
    });
  }));
});
