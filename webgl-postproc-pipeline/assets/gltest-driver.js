/* ============================================================
   gltest-driver.js — 无头渲染验证驱动（模板）
   ------------------------------------------------------------
   用法：
     1) 页面暴露一个验证钩子（名字随意，改下面的 HOOK 常量即可）：
          window.__GLPROBE__ = {
            state():      { glOk, glFail, errors[], passes[{id,enabled,broken}], passCount, canvas:[w,h] }
            sig(recipe):  { px: [16*16 灰度], mean }   // 应用配方 → 渲染 → 16×16 下采样
            sourceSig():  { px, mean }                 // 原图在【同样裁切】下的同规格签名
          }
        sig() 里的采样必须和管线里的 cover 裁切一致，否则对比的是画面里两块不同区域，
        会产生"中性配方 ≠ 原图"的假警报。
     2) 用 scripts/splice_gltest.py 把本文件拼进单文件页面
     3) --dump-dom 取回结果，grep '^RESULT=' / '^DONE'

   页面侧钩子示例见项目 prompt-postfx/src/app.js 末尾的 window.__PPFX__。
   ============================================================ */
(function () {
  var HOOK = window.__GLPROBE__ ? '__GLPROBE__' : (window.__PPFX__ ? '__PPFX__' : null);

  function log(s) {
    var p = document.getElementById('__res');
    if (!p) {
      p = document.createElement('pre');
      p.id = '__res';
      p.style.cssText = 'position:absolute;left:-9999px;top:0';
      document.body.appendChild(p);
    }
    p.textContent += s + '\n';
  }

  function distinct(list) {
    var seen = {};
    list.forEach(function (v) { seen[v] = 1; });
    return Object.keys(seen).length;
  }

  document.addEventListener('DOMContentLoaded', function () {
    setTimeout(function () {
      try {
        if (!HOOK) { log('RESULT=FAIL reason=no_hook'); log('DONE'); return; }
        var S = window[HOOK];
        var st = S.state();

        log('GL_OK=' + st.glOk);
        log('GL_FAIL=' + (st.glFail || ''));
        log('CANVAS=' + JSON.stringify(st.canvas));
        log('ERRORS=' + JSON.stringify(st.errors));
        log('PASSES=' + JSON.stringify(st.passes));
        log('PASS_COUNT=' + st.passCount);

        var ok = st.glOk === true && st.errors.length === 0;

        /* --- 中性配方必须等于原图 --- */
        var neutral = S.sig(null);           // null = 保持当前（应为中性）状态
        var src = S.sourceSig();
        var drift = (neutral && src) ? Math.abs(neutral.mean - src.mean) : 999;
        log('NEUTRAL_MEAN=' + (neutral ? neutral.mean : 'null'));
        log('SOURCE_MEAN=' + (src ? src.mean : 'null'));
        log('NEUTRAL_DRIFT=' + drift.toFixed(2));
        log('NEUTRAL_IDENTITY=' + (drift <= 5 ? 'PASS' : 'FAIL'));
        ok = ok && drift <= 5;

        /* --- 不同预设必须出不同的图 --- */
        var CASES = ['test sentence one', 'test sentence two', 'test sentence three'];
        var means = [];
        CASES.forEach(function (t) {
          var g = S.sig(S.parse ? S.parse(t).recipe : undefined);
          means.push(g ? g.mean : null);
          log('SIG ' + t + ' -> ' + (g ? g.mean : 'null'));
        });
        var d = distinct(means);
        log('DISTINCT_MEANS=' + d + '/' + means.length);
        ok = ok && d >= means.length;

        log('RESULT=' + (ok ? 'PASS' : 'FAIL'));
        log('DONE');
      } catch (e) {
        log('EXCEPTION=' + (e && e.message ? e.message : e));
        log('RESULT=FAIL');
        log('DONE');
      }
    }, 600);
  });
})();
