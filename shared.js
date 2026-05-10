/* Saflow Advertising — shared.js */
(function(){
  // ── Active nav link ──
  const path = location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.nav-links a').forEach(a => {
    const href = (a.getAttribute('href') || '').split('/').pop();
    if(href === path || (path === '' && href === 'index.html')) a.classList.add('active');
  });

  // ── Mobile nav toggle ──
  const navToggle = document.getElementById('navToggle');
  const navLinks  = document.querySelector('.nav-links');
  if(navToggle && navLinks){
    navToggle.addEventListener('click', () => {
      const open = document.body.classList.toggle('nav-open');
      navToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    navLinks.querySelectorAll('a').forEach(a => a.addEventListener('click', () => {
      document.body.classList.remove('nav-open');
      navToggle.setAttribute('aria-expanded','false');
    }));
  }

  // ── Custom cursor (desktop only) ──
  const cursor = document.getElementById('cursor');
  const ring   = document.getElementById('cursorRing');
  let mx=0,my=0,rx=0,ry=0,rafId=null;
  // Use window to ensure we catch events even when hovering fixed elements
  window.addEventListener('mousemove', e => {
    mx = e.clientX; my = e.clientY;
    if(cursor){ cursor.style.transform = `translate(calc(${mx}px - 50%), calc(${my}px - 50%))`; }
  }, {passive:true});
  function animRing(){
    rx += (mx-rx)*0.12; ry += (my-ry)*0.12;
    if(ring){ ring.style.transform = `translate(calc(${Math.round(rx)}px - 50%), calc(${Math.round(ry)}px - 50%))`; }
    rafId = requestAnimationFrame(animRing);
  }
  animRing();
  document.querySelectorAll('a,button,.service-card,.topic-card,.market-chip,.teaser-card').forEach(el => {
    el.addEventListener('mouseenter', () => { if(ring){ ring.style.width='60px'; ring.style.height='60px'; ring.style.borderColor='rgba(119,166,247,.85)'; }});
    el.addEventListener('mouseleave', () => { if(ring){ ring.style.width='36px'; ring.style.height='36px'; ring.style.borderColor='rgba(119,166,247,.55)'; }});
  });

  // ── Scroll reveal ──
  const io = new IntersectionObserver(entries => {
    entries.forEach(e => { if(e.isIntersecting){ e.target.classList.add('visible'); io.unobserve(e.target); }});
  }, {threshold:.1});
  document.querySelectorAll('.reveal,.reveal-left').forEach(el => io.observe(el));

  // ── Count-up numbers ──
  const cio = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if(e.isIntersecting){
        const el = e.target, target = +el.dataset.target, dur = 1800;
        let start = null;
        function step(ts){ if(!start) start=ts; const p=Math.min((ts-start)/dur,1); el.textContent=Math.round((1-Math.pow(1-p,3))*target); if(p<1) requestAnimationFrame(step); }
        requestAnimationFrame(step);
        cio.unobserve(el);
      }
    });
  }, {threshold:.5});
  document.querySelectorAll('.count-up').forEach(c => cio.observe(c));

  // ── Nav border on scroll ──
  const nav = document.querySelector('nav');
  window.addEventListener('scroll', () => {
    if(nav) nav.style.borderBottomColor = window.scrollY > 50 ? 'rgba(255,255,255,.12)' : 'rgba(247,241,230,.10)';
  });

  // ── Smooth scroll for hash links ──
  document.querySelectorAll('a[href^="#"]').forEach(a => {
    a.addEventListener('click', e => {
      const t = document.querySelector(a.getAttribute('href'));
      if(t){ e.preventDefault(); t.scrollIntoView({behavior:'smooth',block:'start'}); }
    });
  });

  // ── Plan Builder (plan.html only) ──
  const planRoot = document.getElementById('planBuilder');
  if(planRoot){
    const state = { stage:'smb', region:'usa', channels:new Set(['google','meta']), spend:50000 };
    // Slider bounds — aligned to tier-card thresholds:
    // $300 (Lite) → $2k (Spark) → $10k (Launch) → $50k (Growth) → $200k (Scale) → $1M (Enterprise) → $2M
    const SPEND_MIN = 300, SPEND_MAX = 2000000;
    // Hourly rate ranges by region (USD/hr local agency, midpoint used) — researched 2024-25
    // Sources: Clutch.co 2025 (US/EU/Aus/India), PayScale 2024 (UK), Entasher 2025 (UAE).
    const regionRates = {
      usa:{lo:100, hi:150, label:'USA',       cite:'Clutch 2025'},
      uk: {lo:55,  hi:120, label:'UK',        cite:'PayScale 2024'},
      eu: {lo:55,  hi:108, label:'EU',        cite:'Clutch 2025'},
      uae:{lo:80,  hi:140, label:'UAE',       cite:'Entasher 2025'},
      aus:{lo:130, hi:250, label:'Australia', cite:'Clutch 2025'},
      ind:{lo:15,  hi:45,  label:'India',     cite:'Clutch 2025 (premium incl.)'}
    };
    // Estimated monthly hours per channel (Saflow side) — informational only
    const channelHours = { google:30, meta:30, seo:30, creative:20, analytics:10, brand:15, lifecycle:15 };
    // CAC and payback by stage — First Page Sage 2024-25 medians
    const stageCAC     = { startup:80,  smb:700,  mid:2500, ent:5500 };
    const stagePayback = { startup:6,   smb:5,    mid:12,   ent:20   };
    // Pure log slider mapping: position 0 → $300, position 1000 → $2M
    const SPEND_LOG_RATIO = Math.log(SPEND_MAX / SPEND_MIN);
    function posToSpend(p){
      const t = Math.max(0, Math.min(1000, +p)) / 1000;
      return Math.round(SPEND_MIN * Math.exp(t * SPEND_LOG_RATIO));
    }
    function spendToPos(s){
      s = Math.max(SPEND_MIN, Math.min(SPEND_MAX, +s || SPEND_MIN));
      return Math.round(1000 * Math.log(s / SPEND_MIN) / SPEND_LOG_RATIO);
    }
    // Saflow fee per recommended tier (added Lite tier for tiny clients)
    const tierFee   = { lite:300,  spark:1500, launch:3500, growth:6500, scale:12000, ent:25000 };
    // Tier nominal monthly delivery hours — used for market-rate comparison
    const tierHours = { lite:8,    spark:25,   launch:50,   growth:90,   scale:160,   ent:280 };
    const tierLabel = { lite:'Lite', spark:'Spark', launch:'Launch', growth:'Growth', scale:'Scale', ent:'Enterprise' };
    const tierWhy = {
      lite:'Side-projects, indie hackers — $100–$2k/mo ad spend, 1 channel.',
      spark:'Solo founders pre-PMF — one channel, lean spend.',
      launch:'Early-stage, 1–2 channels, validating the funnel.',
      growth:'SMBs spending $50k–$200k/mo with 2–4 active channels.',
      scale:'Mid-market with cross-channel coverage and dedicated PM.',
      ent:'Fortune 500 multi-region rollouts — bespoke scope.'
    };

    function pickTier(){
      const order = ['lite','spark','launch','growth','scale','ent'];
      // Spend-driven baseline (the dominant signal)
      let t = 'lite';
      const s = state.spend;
      if(s >= 1000000) t = 'ent';
      else if(s >= 200000) t = 'scale';
      else if(s >= 50000) t = 'growth';
      else if(s >= 10000) t = 'launch';
      else if(s >= 2000) t = 'spark';
      // Stage acts as a soft floor — an Enterprise prospect needs at least Scale-level scope
      const stageFloor = { startup:'lite', smb:'spark', mid:'growth', ent:'scale' };
      const floor = stageFloor[state.stage];
      if(floor && order.indexOf(t) < order.indexOf(floor)) t = floor;
      // Many channels active also bumps up
      const ch = state.channels.size;
      if(ch >= 4 && order.indexOf(t) < order.indexOf('growth')) t = 'growth';
      if(ch >= 6 && order.indexOf(t) < order.indexOf('scale')) t = 'scale';
      return t;
    }
    function fmt(n){
      if(n >= 1e6) return '$'+(n/1e6).toFixed(1).replace(/\.0$/,'')+'M';
      if(n >= 1000) return '$'+(n/1000).toFixed(n>=10000?0:1).replace(/\.0$/,'')+'k';
      return '$'+Math.round(n).toLocaleString();
    }
    function compute(){
      const tier = pickTier();
      const saflowFee = tierFee[tier];
      // Use the tier's nominal hours so the comparison is apples-to-apples
      // (a local agency would bill the same scope of work at their hourly rate).
      const hours = tierHours[tier];
      const r = regionRates[state.region];
      const marketRate = (r.lo + r.hi) / 2;
      const marketFee = Math.round(hours * marketRate);
      const annualSavings = Math.max(0, (marketFee - saflowFee) * 12);
      const cac = stageCAC[state.stage];
      // Saflow targets a 25% payback improvement vs typical
      const paybackMonths = (stagePayback[state.stage] * 0.75).toFixed(1);
      const newCustOld = state.spend > 0 ? Math.round((state.spend * 12) / cac) : 0;
      const cacNew = Math.round(cac * 0.72);
      const newCustNew = state.spend > 0 ? Math.round((state.spend * 12) / cacNew) : 0;
      return { tier, saflowFee, marketFee, annualSavings, paybackMonths, cacOld:cac, cacNew, newCustOld, newCustNew };
    }
    function render(){
      const r = compute();
      const t = document.getElementById('poTier'); if(t) t.textContent = tierLabel[r.tier];
      const w = document.getElementById('poWhy');  if(w) w.textContent = tierWhy[r.tier];
      const s = document.getElementById('poSaflow'); if(s) s.textContent = r.tier==='ent' ? 'Custom' : fmt(r.saflowFee)+'/mo';
      const m = document.getElementById('poMarket'); if(m) m.textContent = fmt(r.marketFee)+'/mo';
      const sv = document.getElementById('poSavings');
      // Honest framing: when savings <10% (mostly the India region), show insight instead of $0
      const savingPct = r.marketFee > 0 ? (r.annualSavings / (r.marketFee*12)) : 0;
      const insight = document.getElementById('poInsight');
      if(savingPct < 0.1 && state.region === 'ind'){
        if(sv) sv.innerHTML = '—<small>comparable</small>';
        if(insight){ insight.textContent = 'Saflow charges similar to local Indian rates — but adds global delivery, English-native production, and proven cross-border campaign ops.'; insight.style.display = 'block'; }
      } else {
        if(sv) sv.innerHTML = fmt(r.annualSavings)+'<small>/year</small>';
        if(insight){ insight.textContent = ''; insight.style.display = 'none'; }
      }
      const pb = document.getElementById('poPayback'); if(pb) pb.textContent = (r.paybackMonths==='—'?'—':r.paybackMonths+' months');
      const cta = document.getElementById('poCta');
      if(cta){
        const params = new URLSearchParams({
          tier: tierLabel[r.tier], region: regionRates[state.region].label,
          channels: Array.from(state.channels).join(','), spend: state.spend
        });
        cta.href = 'contact.html?'+params.toString();
      }
      // Tier-card highlight in the Packages grid (real-time match-to-recommendation)
      document.querySelectorAll('.tier-card[data-tier]').forEach(c => {
        c.classList.toggle('recommended', c.dataset.tier === r.tier);
      });
      // ROI bar chart updates
      const annualSpend = state.spend * 12;
      const setText = (id,v)=>{ const el=document.getElementById(id); if(el) el.textContent = v; };
      setText('roiSpend',  fmt(annualSpend));
      setText('roiSpend2', fmt(annualSpend));
      setText('roiCacOld', '$'+r.cacOld);
      setText('roiCacNew', '$'+r.cacNew);
      setText('roiCustOld', r.newCustOld.toLocaleString());
      setText('roiCustNew', r.newCustNew.toLocaleString());
      // Spend readouts (both slider readout label and number input)
      const sv2 = document.getElementById('planSpendVal');
      if(sv2) sv2.textContent = fmt(state.spend);
      const inputBox = document.getElementById('planSpendInput');
      if(inputBox && document.activeElement !== inputBox) inputBox.value = state.spend;
    }
    // Wire chips
    planRoot.querySelectorAll('.plan-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const g = chip.dataset.group, v = chip.dataset.value;
        if(g === 'channels'){
          if(state.channels.has(v)){ state.channels.delete(v); chip.classList.remove('active'); }
          else { state.channels.add(v); chip.classList.add('active'); }
        } else {
          state[g] = v;
          planRoot.querySelectorAll(`.plan-chip[data-group="${g}"]`).forEach(c => c.classList.toggle('active', c.dataset.value === v));
        }
        render();
      });
    });
    // Wire spend slider (exponential mapping: 0–1000 position → $100–$100k)
    const spendSlider = document.getElementById('planSpend');
    const spendInput  = document.getElementById('planSpendInput');
    if(spendSlider){
      spendSlider.addEventListener('input', () => {
        state.spend = posToSpend(+spendSlider.value);
        render();
      });
    }
    if(spendInput){
      spendInput.addEventListener('input', () => {
        const v = Math.max(SPEND_MIN, Math.min(SPEND_MAX, +spendInput.value || SPEND_MIN));
        state.spend = v;
        if(spendSlider) spendSlider.value = spendToPos(v);
        render();
      });
      // Re-clamp/format on blur if user typed something out of range
      spendInput.addEventListener('blur', () => { spendInput.value = state.spend; });
    }
    // Wire spend presets
    document.querySelectorAll('.plan-preset').forEach(b => {
      b.addEventListener('click', () => {
        state.spend = +b.dataset.spend;
        if(spendSlider) spendSlider.value = spendToPos(state.spend);
        if(spendInput)  spendInput.value  = state.spend;
        render();
      });
    });
    // Initialize slider position to match initial state.spend
    if(spendSlider) spendSlider.value = spendToPos(state.spend);
    if(spendInput)  spendInput.value  = state.spend;
    render();
  }

})();
