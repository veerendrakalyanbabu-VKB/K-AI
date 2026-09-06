/* Opt-in phone sky view. It uses device sensors locally and only requests a
   rounded location when the user explicitly opens the view. It is an aid for
   orientation, not a surveyed AR instrument. */
'use strict';
(function (root) {
  const R = 6378137, E2 = 0.00669437999014;
  function lookAngles(observer, target) {
    const lat = observer.lat * Math.PI / 180, lon = observer.lng * Math.PI / 180;
    const n = R / Math.sqrt(1 - E2 * Math.sin(lat) ** 2);
    const ox = (n + (observer.alt || 0)) * Math.cos(lat) * Math.cos(lon);
    const oy = (n + (observer.alt || 0)) * Math.cos(lat) * Math.sin(lon);
    const oz = (n * (1 - E2) + (observer.alt || 0)) * Math.sin(lat);
    const tlat = target.lat * Math.PI / 180, tlon = target.lng * Math.PI / 180;
    const tn = R / Math.sqrt(1 - E2 * Math.sin(tlat) ** 2), alt = target.alt_m || (target.altitude_km || 0) * 1000;
    const tx = (tn + alt) * Math.cos(tlat) * Math.cos(tlon), ty = (tn + alt) * Math.cos(tlat) * Math.sin(tlon), tz = (tn * (1 - E2) + alt) * Math.sin(tlat);
    const dx = tx - ox, dy = ty - oy, dz = tz - oz;
    const east = -Math.sin(lon) * dx + Math.cos(lon) * dy;
    const north = -Math.sin(lat) * Math.cos(lon) * dx - Math.sin(lat) * Math.sin(lon) * dy + Math.cos(lat) * dz;
    const up = Math.cos(lat) * Math.cos(lon) * dx + Math.cos(lat) * Math.sin(lon) * dy + Math.sin(lat) * dz;
    const horizontal = Math.hypot(east, north);
    return { azimuth: (Math.atan2(east, north) * 180 / Math.PI + 360) % 360, elevation: Math.atan2(up, horizontal) * 180 / Math.PI, distance_km: Math.hypot(horizontal, up) / 1000 };
  }
  let session = 0, stream = null, dialog = null, listener = null, timer = null;
  function stop() {
    session++;
    if (stream) stream.getTracks().forEach(t => t.stop());
    stream = null;
    if (listener && root.removeEventListener) root.removeEventListener('deviceorientationabsolute', listener, true);
    listener = null; if (timer) clearInterval(timer); timer = null;
    if (dialog && dialog.open) dialog.close();
    const video = dialog && dialog.querySelector('video'); if (video) video.srcObject = null;
  }
  function makeDialog() {
    if (dialog) return dialog;
    dialog = document.createElement('dialog'); dialog.className = 'sky-dialog';
    dialog.innerHTML = '<button class="close" aria-label="Close phone sky view">×</button><div class="sky-camera"><video autoplay muted playsinline></video><div class="sky-reticle">＋</div><div class="sky-labels"></div></div><p class="sky-status">Preparing permissions…</p><p class="muted">Approximate bearings from public records. Sensor accuracy varies by phone; no camera image or sensor data is uploaded.</p>';
    document.body.appendChild(dialog); dialog.querySelector('.close').onclick = stop; dialog.addEventListener('cancel', stop); return dialog;
  }
  async function open(getRecords, explore) {
    const token = ++session, d = makeDialog(); d.showModal(); const status = d.querySelector('.sky-status'), labels = d.querySelector('.sky-labels');
    if (!navigator.mediaDevices?.getUserMedia) { status.textContent = 'Camera access requires a secure HTTPS browser context.'; return; }
    try {
      if (typeof DeviceOrientationEvent !== 'undefined' && typeof DeviceOrientationEvent.requestPermission === 'function') await DeviceOrientationEvent.requestPermission();
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false });
      if (token !== session) { stream.getTracks().forEach(t => t.stop()); return; }
      d.querySelector('video').srcObject = stream;
      let heading = null;
      listener = e => { const h = Number.isFinite(e.webkitCompassHeading) ? e.webkitCompassHeading : (e.absolute && Number.isFinite(e.alpha) ? (360 - e.alpha) % 360 : null); if (h != null) heading = h; };
      root.addEventListener('deviceorientationabsolute', listener, true);
      if (navigator.geolocation) navigator.geolocation.getCurrentPosition(p => { if (token === session) { window.__kaiSkyLat = p.coords.latitude; window.__kaiSkyLng = p.coords.longitude; if (explore) explore(p.coords.latitude, p.coords.longitude); } }, () => {}, { enableHighAccuracy: false, maximumAge: 600000, timeout: 10000 });
      timer = setInterval(() => {
        const all = typeof getRecords === 'function' ? getRecords() : [], observer = { lat: Number(window.__kaiSkyLat) || 17.385, lng: Number(window.__kaiSkyLng) || 78.487, alt: 0 };
        const targets = all.filter(x => ['aviation', 'marine', 'space'].includes(x.layer) && Number.isFinite(x.lat) && Number.isFinite(x.lng)).map(x => ({ x, a: lookAngles(observer, x) })).filter(v => v.a.elevation > -5).sort((a, b) => a.a.distance_km - b.a.distance_km).slice(0, 12);
        status.textContent = heading == null ? 'Camera active · compass unavailable; showing bearing list' : 'Camera active · approximate compass overlay';
        labels.innerHTML = targets.map(v => '<span class="sky-target" style="--bearing:'+v.a.azimuth+'deg"><b>'+String(v.x.title || 'Target').replace(/[&<>]/g, '')+'</b><small>'+Math.round(v.a.azimuth)+'° · '+(v.a.elevation > 0 ? 'above horizon' : 'near horizon')+'</small></span>').join('') || '<span class="sky-empty">No nearby above-horizon targets in loaded feeds.</span>';
      }, 1000);
    } catch (err) { status.textContent = err && err.name === 'NotAllowedError' ? 'Permission denied. Use the browser camera and motion controls to enable this view.' : 'Phone sky view could not start on this device.'; if (stream) stream.getTracks().forEach(t => t.stop()); stream = null; }
  }
  root.KAISky = { open, stop, lookAngles };
  if (typeof module !== 'undefined') module.exports = { lookAngles };
})(typeof window !== 'undefined' ? window : globalThis);
