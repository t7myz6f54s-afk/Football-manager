/* Trophy Room — a procedural 3D club museum.
 * Lazy-loads three.min.js, builds the room + recognisable trophies per
 * competition, animates new wins, raycast selection -> onSelect(group data).
 * Falls back to a 2D "shelf" view when WebGL is unavailable.
 */
(function () {
  "use strict";
  let state = null;

  function loadScript(src) {
    return new Promise((res, rej) => {
      if (document.querySelector('script[data-src="' + src + '"]')) return res();
      const s = document.createElement("script");
      s.src = src; s.onload = () => res(); s.onerror = () => rej(new Error("load " + src));
      document.head.appendChild(s);
    });
  }
  function webglOK() {
    try { const c = document.createElement("canvas");
      return !!(window.WebGLRenderingContext && (c.getContext("webgl") || c.getContext("experimental-webgl"))); }
    catch (e) { return false; }
  }

  /* ------------------------------------------------------------ trophy specs
   * metal: 0 silver, 1 gold | ear: handle size 0..1 | profile: body shape
   * top: ornament (none|lion|star) | accent: ribbon colour
   */
  function specFor(code, ctype, tier) {
    switch (code) {
      case "UCL": return { metal: 0, ear: 1.0, profile: "ucl", top: "none", accent: 0x274690 };
      case "UEL": return { metal: 0, ear: 0.72, profile: "cup", top: "none", accent: 0x1f4fa8 };
      case "UECL": return { metal: 0, ear: 0.72, profile: "cup", top: "none", accent: 0x1d7a3e };
      case "ENG1": return { metal: 1, ear: 0, profile: "pl", top: "lion" };
      case "FACUP": return { metal: 0, ear: 0.95, profile: "facup", top: "none" };
      case "EFLCUP": return { metal: 0, ear: 0.66, profile: "cup", top: "none", accent: 0x8c1d40 };
      default:
        if (ctype === "league") return { metal: (tier || 9) <= 1 ? 1 : 0, ear: 0,
          profile: "league", top: (tier || 9) <= 1 ? "star" : "none" };
        return { metal: 0, ear: 0.78, profile: "cup", top: "none", accent: 0x274690 };
    }
  }

  const PROFILE = {
    // (r, y) pairs for the lathe; base at y=0, rim at the end
    ucl: [[0.055, 0], [0.145, 0.012], [0.16, 0.07], [0.075, 0.12], [0.062, 0.30],
      [0.10, 0.42], [0.21, 0.55], [0.30, 0.72], [0.335, 0.92], [0.345, 1.02], [0.31, 1.05]],
    pl: [[0.05, 0], [0.15, 0.01], [0.17, 0.07], [0.09, 0.11], [0.08, 0.22],
      [0.13, 0.30], [0.27, 0.42], [0.34, 0.56], [0.345, 0.66], [0.30, 0.68]],
    facup: [[0.055, 0], [0.15, 0.012], [0.155, 0.08], [0.07, 0.12], [0.058, 0.34],
      [0.09, 0.44], [0.17, 0.52], [0.26, 0.66], [0.28, 0.84], [0.27, 0.90]],
    cup: [[0.055, 0], [0.15, 0.012], [0.155, 0.075], [0.072, 0.11], [0.062, 0.30],
      [0.10, 0.40], [0.20, 0.52], [0.27, 0.68], [0.285, 0.86], [0.27, 0.92]],
    league: [[0.05, 0], [0.16, 0.01], [0.175, 0.08], [0.085, 0.12], [0.075, 0.26],
      [0.12, 0.34], [0.24, 0.46], [0.31, 0.62], [0.32, 0.78], [0.28, 0.80]]
  };

  /* ------------------------------------------------------------ canvas text */
  function makeCanvas(w, h) { const c = document.createElement("canvas"); c.width = w; c.height = h; return c; }
  function plateTexture(name, count, years, gold) {
    const c = makeCanvas(512, 176), x = c.getContext("2d");
    x.fillStyle = "#0d0f13"; x.fillRect(0, 0, 512, 176);
    const g = x.createLinearGradient(0, 0, 0, 176);
    g.addColorStop(0, "rgba(255,214,120,.16)"); g.addColorStop(1, "rgba(255,214,120,.02)");
    x.fillStyle = g; x.fillRect(0, 0, 512, 176);
    x.strokeStyle = gold ? "rgba(212,175,55,.8)" : "rgba(212,175,55,.45)"; x.lineWidth = 4;
    x.strokeRect(6, 6, 500, 164);
    x.textAlign = "center"; x.fillStyle = gold ? "#e8c96a" : "#cfd6e0";
    x.font = "900 40px Arial"; x.fillText(name.toUpperCase(), 256, 64);
    x.font = "700 26px Arial"; x.fillStyle = "#9aa3ad";
    x.fillText(count > 1 ? count + "× WINNER" : "WINNER", 256, 104);
    x.font = "600 24px Arial"; x.fillStyle = "#7d8590";
    x.fillText(years.slice(0, 6).join("  ·  "), 256, 144);
    const t = new THREE.CanvasTexture(c); t.anisotropy = 4; return t;
  }
  function wallTexture(clubName, colA) {
    const c = makeCanvas(1024, 384), x = c.getContext("2d");
    const bg = x.createLinearGradient(0, 0, 0, 384);
    bg.addColorStop(0, "#0a0c10"); bg.addColorStop(1, "#07080b");
    x.fillStyle = bg; x.fillRect(0, 0, 1024, 384);
    x.fillStyle = colA || "rgba(212,175,55,.9)"; x.fillRect(0, 150, 1024, 3);
    x.fillRect(0, 262, 1024, 3);
    x.textAlign = "center";
    x.fillStyle = "rgba(232,201,106,.95)"; x.font = "900 84px Arial";
    x.fillText("TROPHY ROOM", 512, 220);
    x.fillStyle = "rgba(154,163,173,.85)"; x.font = "700 34px Arial";
    x.fillText((clubName || "THE CLUB").toUpperCase(), 512, 300);
    const t = new THREE.CanvasTexture(c); t.anisotropy = 4; return t;
  }

  /* ------------------------------------------------------------ trophy build */
  function silverMat() { return new THREE.MeshStandardMaterial({ color: 0xc9ced6, metalness: 0.96, roughness: 0.16, envMapIntensity: 1.25 }); }
  function goldMat() { return new THREE.MeshStandardMaterial({ color: 0xd8ab3c, metalness: 1.0, roughness: 0.24, envMapIntensity: 1.3 }); }
  function darkMat() { return new THREE.MeshStandardMaterial({ color: 0x101216, metalness: 0.4, roughness: 0.5, envMapIntensity: 0.6 }); }

  function lathe(pts, mat, seg) {
    const v = pts.map(p => new THREE.Vector2(p[0], p[1]));
    const geo = new THREE.LatheGeometry(v, seg || 40);
    return new THREE.Mesh(geo, mat);
  }
  function starShape(r) {
    const s = new THREE.Shape();
    for (let i = 0; i < 10; i++) {
      const a = (i * Math.PI) / 5 - Math.PI / 2, rr = i % 2 ? r * 0.45 : r;
      const px = Math.cos(a) * rr, py = Math.sin(a) * rr;
      if (i === 0) s.moveTo(px, py); else s.lineTo(px, py);
    }
    s.closePath(); return s;
  }

  function buildTrophy(spec) {
    const g = new THREE.Group();
    const mat = spec.metal === 1 ? goldMat() : silverMat();
    const body = lathe(PROFILE[spec.profile] || PROFILE.cup, mat, 44);
    g.add(body);
    const topY = (PROFILE[spec.profile] || PROFILE.cup).slice(-1)[0][1];
    // handles / ears
    if (spec.ear > 0) {
      const big = spec.ear >= 0.9;
      const R = 0.16 * spec.ear + (big ? 0.05 : 0), tube = 0.034 * (0.7 + spec.ear * 0.5);
      const arc = big ? Math.PI * 1.25 : Math.PI * 0.95;
      const yb = spec.profile === "facup" || spec.profile === "ucl" ? topY - 0.16 : topY * 0.62;
      for (const side of [-1, 1]) {
        const h = new THREE.Mesh(new THREE.TorusGeometry(R, tube, 12, 26, arc), mat);
        h.position.set(side * (0.30 + R * 0.35), yb, 0);
        h.rotation.set(0, side * -0.35, Math.PI * (big ? 0.38 : 0.18));
        if (big) { h.scale.set(1, 1.18, 1); h.position.x = side * 0.30; }
        g.add(h);
      }
    }
    // accent ribbon under the bowl
    if (spec.accent !== undefined) {
      const rib = new THREE.Mesh(new THREE.TorusGeometry(0.185, 0.028, 10, 30),
        new THREE.MeshStandardMaterial({ color: spec.accent, metalness: 0.6, roughness: 0.35 }));
      rib.rotation.x = Math.PI / 2; rib.position.y = 0.16; g.add(rib);
    }
    // ornaments
    if (spec.top === "lion") {          // PL: lid + standing lion (simplified herald)
      const lid = new THREE.Mesh(new THREE.CylinderGeometry(0.30, 0.32, 0.035, 32), darkMat());
      lid.position.y = topY + 0.017; g.add(lid);
      const lion = new THREE.Group();
      const lbody = new THREE.Mesh(new THREE.ConeGeometry(0.075, 0.24, 10), mat); lbody.position.y = 0.15;
      const lhead = new THREE.Mesh(new THREE.SphereGeometry(0.062, 14, 12), mat); lhead.position.y = 0.31;
      const lcrown = new THREE.Mesh(new THREE.ConeGeometry(0.045, 0.07, 8), mat); lcrown.position.y = 0.39;
      const ltail = new THREE.Mesh(new THREE.TorusGeometry(0.07, 0.016, 8, 16, Math.PI * 1.3), mat);
      ltail.position.set(0, 0.08, -0.05); ltail.rotation.set(0.5, 0.4, 0.6);
      lion.add(lbody, lhead, lcrown, ltail); lion.position.y = topY + 0.03; g.add(lion);
    } else if (spec.top === "star") {   // top-flight league: five-point star
      const star = new THREE.Mesh(new THREE.ExtrudeGeometry(starShape(0.11),
        { depth: 0.03, bevelEnabled: false }), mat);
      star.position.set(0, topY + 0.05, -0.015); g.add(star);
    }
    g.userData.topY = topY;
    return g;
  }

  function buildPlinth(tall) {
    const g = new THREE.Group();
    const h = tall ? 1.12 : 0.92;
    const base = new THREE.Mesh(new THREE.CylinderGeometry(0.30, 0.34, h, 24),
      new THREE.MeshStandardMaterial({ color: 0x12141a, metalness: 0.35, roughness: 0.55, envMapIntensity: 0.7 }));
    base.position.y = h / 2; g.add(base);
    const band = new THREE.Mesh(new THREE.TorusGeometry(0.315, 0.012, 8, 40),
      new THREE.MeshStandardMaterial({ color: 0xb08d3c, metalness: 1, roughness: 0.35 }));
    band.rotation.x = Math.PI / 2; band.position.y = h * 0.5; g.add(band);
    const plate = new THREE.Mesh(new THREE.CylinderGeometry(0.32, 0.32, 0.03, 24),
      new THREE.MeshStandardMaterial({ color: 0xb08d3c, metalness: 1, roughness: 0.3, envMapIntensity: 1.1 }));
    plate.position.y = h + 0.015; g.add(plate);
    g.userData.h = h; return g;
  }

  function buildGlass(h, w, d) {
    const glass = new THREE.Mesh(new THREE.BoxGeometry(w, h, d),
      new THREE.MeshPhongMaterial({ color: 0x9fc4d8, transparent: true, opacity: 0.10,
        shininess: 160, specular: 0xbfd8e8, side: THREE.DoubleSide, depthWrite: false }));
    glass.position.y = h / 2;
    const edges = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(w, h, d)),
      new THREE.LineBasicMaterial({ color: 0xc9a545, transparent: true, opacity: 0.55 }));
    edges.position.y = h / 2;
    const g = new THREE.Group(); g.add(glass, edges); return g;
  }

  /* ------------------------------------------------------------ environment */
  function buildEnvironment(renderer, clubName, colA) {
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x05060a);
    scene.fog = new THREE.Fog(0x05060a, 9, 17);
    // image-based lighting from a tiny emissive "studio" scene
    const env = new THREE.Scene();
    env.background = new THREE.Color(0x07090d);
    function panel(w, h, hex, mul, pos, lookAt) {
      const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h),
        new THREE.MeshBasicMaterial({ color: new THREE.Color(hex).multiplyScalar(mul), side: THREE.DoubleSide }));
      m.position.copy(pos); m.lookAt(lookAt || new THREE.Vector3()); env.add(m);
    }
    panel(14, 3, 0xfff2d8, 2.6, new THREE.Vector3(0, 5, 0), new THREE.Vector3(0, 0, 0));      // warm ceiling
    panel(3, 6, 0x8fb4ff, 0.9, new THREE.Vector3(-8, 2, 0)); panel(3, 6, 0x8fb4ff, 0.9, new THREE.Vector3(8, 2, 0));
    panel(6, 2, 0xffd9a0, 1.4, new THREE.Vector3(0, 1.4, -8)); panel(6, 2, 0xffd9a0, 1.4, new THREE.Vector3(0, 1.4, 8));
    const pmrem = new THREE.PMREMGenerator(renderer);
    const envRT = pmrem.fromScene(env, 0.06);
    scene.environment = envRT.texture; pmrem.dispose();
    // polished floor
    const floor = new THREE.Mesh(new THREE.CircleGeometry(10.5, 48),
      new THREE.MeshStandardMaterial({ color: 0x0b0d12, metalness: 0.6, roughness: 0.3, envMapIntensity: 0.85 }));
    floor.rotation.x = -Math.PI / 2; scene.add(floor);
    // walls + gilded cove
    const wall = new THREE.Mesh(new THREE.CylinderGeometry(10.4, 10.4, 6.4, 48, 1, true),
      new THREE.MeshStandardMaterial({ color: 0x0a0c11, metalness: 0.2, roughness: 0.8, side: THREE.BackSide }));
    wall.position.y = 3.2; scene.add(wall);
    const cove = new THREE.Mesh(new THREE.TorusGeometry(9.9, 0.05, 8, 72),
      new THREE.MeshBasicMaterial({ color: 0xd9b45c }));
    cove.rotation.x = Math.PI / 2; cove.position.y = 4.1; scene.add(cove);
    // branding wall
    const brand = new THREE.Mesh(new THREE.PlaneGeometry(6.4, 2.4),
      new THREE.MeshBasicMaterial({ map: wallTexture(clubName, colA) }));
    brand.position.set(0, 2.9, -9.6); scene.add(brand);
    // lights
    scene.add(new THREE.AmbientLight(0x2a3040, 0.9));
    const spot = (x, z, color, intensity) => {
      const s = new THREE.SpotLight(color, intensity, 18, 0.62, 0.55, 1.4);
      s.position.set(x, 6.2, z); s.target.position.set(x * 0.25, 1.2, z * 0.25);
      scene.add(s, s.target); return s;
    };
    scene.add(spot(-4.5, -2, 0xfff0d0, 1.15), spot(4.5, -2, 0xfff0d0, 1.15));
    scene.add(spot(0, 4.6, 0xcfe2ff, 0.85), spot(-5.5, 4, 0xffe6b8, 0.7));
    // dust motes in the light
    const N = 140, pos = new Float32Array(N * 3);
    for (let i = 0; i < N; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 13; pos[i * 3 + 1] = Math.random() * 5 + 0.4; pos[i * 3 + 2] = (Math.random() - 0.5) * 13;
    }
    const dg = new THREE.BufferGeometry(); dg.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    const dust = new THREE.Points(dg, new THREE.PointsMaterial({ color: 0xd8c08a, size: 0.02,
      transparent: true, opacity: 0.5, blending: THREE.AdditiveBlending, depthWrite: false }));
    scene.add(dust);
    return { scene, dust };
  }

  /* ------------------------------------------------------------ 3D mode */
  async function mount3D(container, data, opts) {
    await loadScript("three.min.js");
    const club = opts.club || {};
    const W = () => container.clientWidth, H = () => container.clientHeight;
    const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
    renderer.setSize(W(), H());
    renderer.outputEncoding = THREE.sRGBEncoding;
    container.appendChild(renderer.domElement);
    const { scene, dust } = buildEnvironment(renderer, club.name, "rgba(212,175,55,.9)");
    const camera = new THREE.PerspectiveCamera(42, W() / H(), 0.1, 60);

    const groups = [];               // raycast targets
    const pickables = [];
    const groupsList = (data.groups || []).slice();
    // hero first (most recent win)
    groupsList.sort((a, b) => (b.last || 0) - (a.last || 0));
    const n = groupsList.length;
    groupsList.forEach((g, i) => {
      const spec = specFor(g.code, g.ctype, g.tier);
      const unit = new THREE.Group();
      const plinth = buildPlinth(i === 0);
      unit.add(plinth);
      const trophy = buildTrophy(spec);
      const s = 0.62;
      trophy.scale.setScalar(s);
      trophy.position.y = plinth.userData.h + 0.03;
      trophy.rotation.y = -unit.position.x * 0.02;
      unit.add(trophy);
      const glass = buildGlass(1.62, 0.86, 0.86); glass.position.y = plinth.userData.h + 0.02; unit.add(glass);
      const years = g.seasons.slice().reverse().map(x => x + "/" + String(x + 1).slice(2));
      const label = new THREE.Mesh(new THREE.PlaneGeometry(0.62, 0.21),
        new THREE.MeshBasicMaterial({ map: plateTexture(g.comp, g.count, years, spec.metal === 1) }));
      label.position.set(0, 0.62, plinth.userData.h + 0.02); label.rotation.x = -0.32;
      unit.add(label);
      // layout: hero centre, rest on two arcs
      if (i === 0) unit.position.set(0, 0, 0.6);
      else {
        const ring = i <= 6 ? 1 : 2;
        const idx = ring === 1 ? i - 1 : i - 7;
        const count = ring === 1 ? Math.min(n - 1, 6) : n - 7;
        const a = (idx / Math.max(1, count)) * Math.PI * 2 + (ring === 1 ? 0.5 : 0.25);
        const r = ring === 1 ? 3.35 : 5.5;
        unit.position.set(Math.sin(a) * r, 0, -Math.cos(a) * r + 0.9);
        unit.lookAt(0, 0, 2.4);
      }
      scene.add(unit);
      unit.userData.trophy = g;
      unit.userData.trophyMesh = trophy;
      unit.userData.spawn = (g.new_seasons && g.new_seasons.length) ? performance.now() : -1;
      unit.userData.phase = Math.random() * Math.PI * 2;
      groups.push(unit); pickables.push(unit);
    });

    // spotlight glow for brand-new trophies
    const glow = new THREE.PointLight(0xffd873, 0, 7, 2);
    scene.add(glow);

    // camera orbit (drag / pinch / wheel)
    const orbit = { theta: 0.0, phi: 1.12, radius: 7.6, tTheta: 0, tPhi: 1.12, tRadius: 7.6, auto: true, idle: 0 };
    let dragging = false, px = 0, py = 0, pinch = 0;
    const el = renderer.domElement;
    el.style.touchAction = "none";
    el.addEventListener("pointerdown", e => { dragging = true; orbit.auto = false; px = e.clientX; py = e.clientY; orbit.idle = 0; });
    window.addEventListener("pointermove", e => {
      if (!dragging) return;
      orbit.tTheta -= (e.clientX - px) * 0.005; orbit.tPhi -= (e.clientY - py) * 0.004;
      orbit.tPhi = Math.max(0.32, Math.min(1.42, orbit.tPhi)); px = e.clientX; py = e.clientY;
    });
    window.addEventListener("pointerup", e => {
      if (dragging && Math.abs(e.clientX - px) < 6 && Math.abs(e.clientY - py) < 6) pick(e);
      dragging = false; setTimeout(() => { orbit.idle = 0; }, 0);
    });
    el.addEventListener("wheel", e => { e.preventDefault();
      orbit.tRadius = Math.max(4.2, Math.min(11, orbit.tRadius + e.deltaY * 0.004)); orbit.auto = false; }, { passive: false });
    el.addEventListener("touchstart", e => { if (e.touches.length === 2)
      pinch = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY); }, { passive: true });
    el.addEventListener("touchmove", e => { if (e.touches.length === 2 && pinch) {
      const d = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
      orbit.tRadius = Math.max(4.2, Math.min(11, orbit.tRadius * (pinch / d))); pinch = d; orbit.auto = false; } }, { passive: true });
    function pick(e) {
      const r = el.getBoundingClientRect();
      const v = new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      const rc = new THREE.Raycaster(); rc.setFromCamera(v, camera);
      const hit = rc.intersectObjects(pickables, true);
      if (!hit.length) { if (opts.onDeselect) opts.onDeselect(); return; }
      let o = hit[0].object; while (o && !o.userData.trophy) o = o.parent;
      if (o && opts.onSelect) opts.onSelect(o.userData.trophy);
    }

    const clock = new THREE.Clock();
    let raf = 0, running = true;
    function frame() {
      if (!running) return;
      raf = requestAnimationFrame(frame);
      const t = clock.getElapsedTime();
      orbit.idle += 1;
      if (orbit.idle > 240) orbit.auto = true;
      if (orbit.auto) orbit.tTheta += 0.0009;
      orbit.theta += (orbit.tTheta - orbit.theta) * 0.08;
      orbit.phi += (orbit.tPhi - orbit.phi) * 0.08;
      orbit.radius += (orbit.tRadius - orbit.radius) * 0.08;
      camera.position.set(
        Math.sin(orbit.theta) * Math.sin(orbit.phi) * orbit.radius,
        Math.cos(orbit.phi) * orbit.radius,
        Math.cos(orbit.theta) * Math.sin(orbit.phi) * orbit.radius);
      camera.lookAt(0, 1.28, 0.4);
      dust.rotation.y = t * 0.008;
      glow.intensity = 0;
      for (const u of groups) {
        if (u.userData.spawn > 0) {
          const age = (performance.now() - u.userData.spawn) / 1000;
          if (age < 1.4) { const k = age / 1.4, e2 = 1 + Math.sin(k * Math.PI * 2.2) * 0.5 * (1 - k); u.scale.setScalar(Math.max(0.001, k * (1.6 - e2 * 0.6))); }
          else u.scale.setScalar(1);
          if (age < 4) { glow.position.copy(u.position).setY(1.9); glow.intensity = 1.6 * (1 - age / 4); }
        }
        const tr = u.userData.trophyMesh;            // trophy group
        if (tr && u.userData.spawn <= 0) tr.rotation.y = 0.12 * Math.sin(t * 0.4 + u.userData.phase);
      }
      renderer.render(scene, camera);
    }
    frame();
    const onVis = () => { if (document.hidden) { running = false; cancelAnimationFrame(raf); } else if (!running) { running = true; frame(); } };
    document.addEventListener("visibilitychange", onVis);
    let ro = null;
    if (typeof ResizeObserver !== "undefined") ro = new ResizeObserver(() => {
      if (!W() || !H()) return;
      renderer.setSize(W(), H()); camera.aspect = W() / H(); camera.updateProjectionMatrix();
    }); if (ro) ro.observe(container);
    state = { mode: "3d", destroy() {
      running = false; cancelAnimationFrame(raf); if (ro) ro.disconnect();
      document.removeEventListener("visibilitychange", onVis);
      scene.traverse(o => {
        if (o.geometry) o.geometry.dispose();
        if (o.material) { const ms = Array.isArray(o.material) ? o.material : [o.material];
          ms.forEach(m => { if (m.map) m.map.dispose(); m.dispose(); }); }
      });
      if (scene.environment) scene.environment.dispose();
      renderer.dispose();
      if (renderer.domElement.parentNode === container) container.removeChild(renderer.domElement);
      state = null;
    } };
    return state;
  }

  /* ------------------------------------------------------------ 2D fallback */
  function mount2D(container, data, opts) {
    const club = (data.club || {});
    const gold = c => c === "UCL" || c === "ENG1" || c === "UEL" || c === "UECL";
    const cups = (data.groups || []).slice().sort((a, b) => (b.last || 0) - (a.last || 0));
    const item = g => {
      const spec = specFor(g.code, g.ctype, g.tier);
      const c = spec.metal === 1 ? "#d8ab3c" : "#c9ced6";
      const c2 = spec.metal === 1 ? "#8a6a1d" : "#5d646e";
      const isNew = g.new_seasons && g.new_seasons.length;
      return `<div class="t2-item ${isNew ? "t2-new" : ""}" data-i="${g.comp_id}">
        <div class="t2-case"><div class="t2-cup" style="--c:${c};--c2:${c2};--h:${g.ctype === "league" ? 54 : 64}">
          <div class="t2-lid"></div><div class="t2-bowl"></div>
          ${spec.ear > 0 ? '<div class="t2-hl"></div><div class="t2-hr"></div>' : ""}
          <div class="t2-stem"></div><div class="t2-base"></div>
        </div></div>
        <div class="t2-plate"><b>${esc2(g.comp)}</b><span>${g.count > 1 ? g.count + "×" : ""} · ${g.seasons[g.seasons.length - 1]}/${String(g.seasons[g.seasons.length - 1] + 1).slice(2)}</span></div>
      </div>`;
    };
    container.innerHTML = `<div class="t2-wrap">
      <div class="t2-head"><div class="t2-kicker">THE MUSEUM</div>
        <h2>${esc2(club.name || "")} <span>Trophy Room</span></h2>
        <p>${data.total} trophy${data.total === 1 ? "" : "ies"} · ${club.league || ""}</p></div>
      ${cups.length ? `<div class="t2-shelf">${cups.map(item).join("")}</div>`
        : `<div class="t2-empty"><h3>The shelves await their first winner.</h3><p>Win a competition and its trophy will stand here, forever.</p></div>`}
    </div>`;
    container.querySelectorAll(".t2-item").forEach(el =>
      el.addEventListener("click", () => {
        const g = cups.find(x => String(x.comp_id) === el.dataset.i);
        if (g && opts.onSelect) opts.onSelect(g);
      }));
    function esc2(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, m => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[m])); }
    state = { mode: "2d", destroy() { container.innerHTML = ""; state = null; } };
    return state;
  }

  /* ------------------------------------------------------------ public API */
  window.TrophyRoom = {
    hasGL: webglOK,
    async mount(container, data, opts) {
      this.destroy();
      try {
        if (webglOK()) return await mount3D(container, data, opts);
        return mount2D(container, data, opts);
      } catch (e) {
        console.warn("Trophy Room 3D failed, using shelf view:", e.message);
        return mount2D(container, data, opts);
      }
    },
    destroy() { if (state && state.destroy) state.destroy(); },
    get active() { return !!state; }
  };
})();
