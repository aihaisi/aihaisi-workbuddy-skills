/* ============================================================
   iso-driver.js — 单变量隔离驱动（模板）
   ------------------------------------------------------------
   用途：画面里出现可疑的块/带/条纹时，判断它出自哪一环。
   做法：把本文件拼进单文件页面，用 URL hash 指定要关掉的那一项：

       file:///.../_iso.html#v=noGlitch

   页面 boot 完成后套用「原配方但关掉一个 pass/子项」的配方，
   让 app 自己的渲染循环继续跑，再用 --screenshot 逐变体截图。

   配套：
     scripts/splice_gltest.py        拼接
     scripts/iso_analyze.py          把截图按硬边指标排序

   ------------------------------------------------------------
   改造点（两处）：
     1) HOOK   —— 页面暴露的验证钩子名，需提供
                   state()  取 { canvas, passes[] }
                   apply(r) 套用配方
                   parse(t) 文本 → { recipe }
     2) PROMPT + VARIANTS —— 换成你要隔离的配方与开关
   ============================================================ */
(function () {
  var HOOK = window.__GLPROBE__ ? '__GLPROBE__' : (window.__PPFX__ ? '__PPFX__' : null);

  /* 用来生成"原配方"的自然语言 */
  var PROMPT = 'PUT YOUR PROMPT HERE';

  /* 每个变体：要改哪些配方字段。{} = 原配方不动。
     路径用点号，只有原本是数字的字段会被改（不会无中生有造字段）。 */
  var VARIANTS = {
    full:     {},
    noGlitch: { 'aberration.glitch': 0 },
    noAberr:  { 'aberration.amount': 0, 'aberration.glitch': 0 },
    noBloom:  { 'bloom.intensity': 0 },
    noGrain:  { 'grain.intensity': 0 },
    noScan:   { 'scanline.intensity': 0 },
    noHalf:   { 'halftone.mix': 0 },
    noEdge:   { 'edge.intensity': 0 },
    noVig:    { 'vignette.intensity': 0 },
    /* 只留最上游一环 —— 用来判断"异常是源图自带还是管线产生" */
    onlyGrade:{ 'aberration.amount': 0, 'aberration.glitch': 0, 'bloom.intensity': 0,
                'grain.intensity': 0, 'scanline.intensity': 0, 'halftone.mix': 0,
                'edge.intensity': 0, 'vignette.intensity': 0 }
  };

  function setPath(o, path, v) {
    var ks = path.split('.'), n = o;
    for (var i = 0; i < ks.length - 1; i++) { if (!n[ks[i]]) return; n = n[ks[i]]; }
    if (typeof n[ks[ks.length - 1]] === 'number') n[ks[ks.length - 1]] = v;
  }

  function mark(s) {
    var p = document.getElementById('__mk');
    if (!p) {
      p = document.createElement('pre');
      p.id = '__mk';
      p.style.cssText = 'position:fixed;left:0;bottom:0;z-index:99;margin:0;' +
                        'font:11px monospace;color:#0f0;background:#000;padding:2px 4px';
      document.body.appendChild(p);
    }
    p.textContent = s;
  }

  document.addEventListener('DOMContentLoaded', function () {
    setTimeout(function () {
      try {
        if (!HOOK) { mark('NO_HOOK'); return; }
        var S = window[HOOK];

        var m = /v=([A-Za-z]+)/.exec(location.hash || '');
        var name = (m && VARIANTS[m[1]]) ? m[1] : 'full';
        var ops = VARIANTS[name];

        var r = JSON.parse(JSON.stringify(S.parse(PROMPT).recipe));
        Object.keys(ops).forEach(function (k) { setPath(r, k, ops[k]); });
        r.name = name;

        S.apply(r);

        var st = S.state();
        mark('VARIANT=' + name +
             '  canvas=' + JSON.stringify(st.canvas) +
             '  passes=' + st.passes.map(function (p) { return p.id + (p.enabled ? '' : 'x'); }).join(',') +
             '  turns=' + JSON.stringify(ops));
      } catch (e) {
        mark('EXC ' + (e && e.message ? e.message : e));
      }
    }, 900);
  });
})();
