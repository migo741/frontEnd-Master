const CACHE='js-lab-legacy-v1';
self.addEventListener('install',event=>event.waitUntil((async()=>{
 const cache=await caches.open(CACHE);
 await cache.put(new URL('./api/config',self.location.href),new Response(JSON.stringify({schema:1,inventoryEnabled:true}),{headers:{'Content-Type':'application/json','X-Release-Id':'cached-api-v1'}}));
 await self.skipWaiting();
})()));
self.addEventListener('activate',event=>event.waitUntil(self.clients.claim()));
self.addEventListener('fetch',event=>{
 if(new URL(event.request.url).pathname.endsWith('/release/old/api/config'))
  event.respondWith(caches.open(CACHE).then(c=>c.match(event.request)));
});
