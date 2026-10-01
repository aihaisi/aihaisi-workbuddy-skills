#!/usr/bin/env node

/**
 * 微信公众号文章搜索工具
 * 通过搜狗微信搜索获取微信公众号文章
 */

const https = require('https');
const zlib = require('zlib');

/**
 * 说明：本脚本不依赖任何第三方 npm 包（不再使用 cheerio），
 * 所有 HTML 解析均由下方内置的轻量解析函数完成，
 * 以保证在内网 / 离线环境下也能直接运行，无需 npm install。
 */

// ---------------------------------------------------------------------------
// 内置的零依赖 HTML 解析工具（替代 cheerio，仅覆盖本脚本所需的最小能力）
// ---------------------------------------------------------------------------

const NAMED_ENTITIES = {
  ldquo: '\u201c', rdquo: '\u201d', lsquo: '\u2018', rsquo: '\u2019',
  hellip: '\u2026', mdash: '\u2014', ndash: '\u2013', middot: '\u00b7',
};

/** 去除 HTML 标签并反转义常见实体，返回纯文本 */
function htmlToText(html) {
  if (!html) return '';
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&(ldquo|rdquo|lsquo|rsquo|hellip|mdash|ndash|middot);/g, (_, n) => NAMED_ENTITIES[n])
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(Number(d)))
    .replace(/&#x([0-9a-fA-F]+);/g, (_, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * 从一段 HTML 中提取指定标签的所有区块内容（支持同名标签嵌套）。
 * @param {string} html
 * @param {string} tag - 如 'li'
 * @returns {string[]} 每个匹配标签的内部 HTML
 */
function extractBlocks(html, tag) {
  const blocks = [];
  const openRe = new RegExp(`<${tag}\\b[^>]*>`, 'gi');
  const openTag = new RegExp(`<${tag}\\b[^>]*>`, 'i');
  const closeTag = new RegExp(`</${tag}>`, 'i');
  let m;
  while ((m = openRe.exec(html)) !== null) {
    let depth = 1;
    let idx = openRe.lastIndex;
    const start = idx;
    while (depth > 0 && idx < html.length) {
      const rest = html.slice(idx);
      const nextOpen = rest.search(openTag);
      const nextClose = rest.search(closeTag);
      if (nextClose === -1) break;
      if (nextOpen !== -1 && nextOpen < nextClose) {
        depth++;
        idx += nextOpen + rest.match(openTag)[0].length;
      } else {
        depth--;
        if (depth === 0) {
          blocks.push(html.slice(start, idx + nextClose));
          idx += nextClose + rest.match(closeTag)[0].length;
          openRe.lastIndex = idx;
          break;
        }
        idx += nextClose + rest.match(closeTag)[0].length;
      }
    }
  }
  return blocks;
}

/**
 * 提取带指定 class 的第一个元素的内部 HTML（用于 p.txt-info / .s-p / .s2 等）。
 * tag 传 '*' 时对任意标签名匹配（class 可能挂在 span 或 div 上）。
 */
function extractByClass(html, tag, className) {
  const tagPat = tag === '*' ? '[a-zA-Z][a-zA-Z0-9]*' : tag;
  const re = new RegExp(`<(${tagPat})\\b[^>]*class=["'][^"']*\\b${className}\\b[^"']*["'][^>]*>`, 'i');
  const m = re.exec(html);
  if (!m) return null;
  const matchedTag = m[1];
  // 简单闭合匹配（本页面结构层级浅，取到对应 close 标签）
  const blocks = extractBlocks(html.slice(m.index), matchedTag);
  return blocks.length > 0 ? blocks[0] : html.slice(m.index + m[0].length);
}

/** 提取 <a> 的 href 与文本（取第一个 a） */
function extractFirstAnchor(html) {
  const m = /<a\b[^>]*href=["']([^"']*)["'][^>]*>([\s\S]*?)<\/a>/i.exec(html);
  if (!m) return null;
  return { href: m[1], text: htmlToText(m[2]) };
}

/** 提取所有 <script> 标签内的文本 */
function extractScriptText(html) {
  let text = '';
  for (const m of html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/gi)) {
    text += m[1] + '\n';
  }
  return text;
}

// 可配置 User-Agent 池（固定 20 个），每次请求随机选一个，避免固定 UA
const USER_AGENTS = [
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edg/123.0.0.0 Chrome/123.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edg/122.0.0.0 Chrome/122.0.0.0 Safari/537.36',
  'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
  'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
  'Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1',
  'Mozilla/5.0 (iPhone; CPU iPhone OS 16_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
  'Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1',
  'Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36',
  'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36',
  'Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36',
  'Mozilla/5.0 (Linux; Android 13; Mi 11) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36',
];

function getRandomUserAgent() {
  return USER_AGENTS[Math.floor(Math.random() * USER_AGENTS.length)];
}

const HEADERS = {
  'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
  'Accept-Encoding': 'identity',
  'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
  'Host': 'weixin.sogou.com',
  'Referer': 'https://weixin.sogou.com/',
};

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function decompressBody(buffer, contentEncoding) {
  if (!contentEncoding) return buffer;
  const encoding = String(contentEncoding).toLowerCase();
  try {
    if (encoding.includes('gzip')) return zlib.gunzipSync(buffer);
    if (encoding.includes('deflate')) return zlib.inflateSync(buffer);
    if (encoding.includes('br')) return zlib.brotliDecompressSync(buffer);
  } catch {
    // 解压失败时直接返回原始数据，避免影响主流程
  }
  return buffer;
}

/**
 * 统一的网络请求工具（仅 https），带超时与重试，可处理 gzip/deflate/br 解压。
 * @param {{
 *   url: string,
 *   method?: string,
 *   headers?: Object,
 *   timeoutMs?: number,
 *   retries?: number
 * }} options
 * @returns {Promise<{statusCode: number, headers: Object, body: Buffer}>}
 */
async function request(options) {
  const {
    url,
    method = 'GET',
    headers = {},
    timeoutMs = 15000,
    retries = 0,
  } = options;

  const lastErrorPrefix = `Request failed: ${method} ${url}`;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const result = await new Promise((resolve, reject) => {
        const urlObj = new URL(url);
        const reqOptions = {
          hostname: urlObj.hostname,
          path: urlObj.pathname + urlObj.search,
          method,
          headers,
        };

        const req = https.request(reqOptions, (res) => {
          const chunks = [];
          res.on('data', (chunk) => chunks.push(chunk));
          res.on('end', () => {
            const raw = Buffer.concat(chunks);
            const body = decompressBody(raw, res.headers['content-encoding']);
            resolve({
              statusCode: res.statusCode || 0,
              headers: res.headers,
              body,
            });
          });
        });

        req.on('error', reject);
        req.setTimeout(timeoutMs, () => {
          req.destroy();
          reject(new Error('Request timeout'));
        });
        req.end();
      });

      return result;
    } catch (e) {
      if (attempt >= retries) {
        throw new Error(`${lastErrorPrefix}: ${e.message}`);
      }
      await sleep(300 + attempt * 300);
    }
  }

  throw new Error(`${lastErrorPrefix}: unexpected`);
}

async function requestText(options) {
  const resp = await request(options);
  return {
    ...resp,
    text: resp.body.toString('utf-8'),
  };
}

/**
 * 从响应头中提取cookie
 * @param {Object} headers - HTTP响应头
 * @returns {string} cookie字符串
 */
function extractCookies(headers) {
  const cookies = [];
  const setCookieHeader = headers['set-cookie'];
  
  if (setCookieHeader) {
    setCookieHeader.forEach(cookie => {
      const cookieValue = cookie.split(';')[0];
      if (cookieValue) {
        cookies.push(cookieValue);
      }
    });
  }
  
  return cookies.join('; ');
}

/**
 * 从搜狗视频页面获取cookie
 * @returns {Promise<{cookieStr: string, cookieObj: Object}>} cookie字符串与对象
 */
async function getSogouCookie() {
  try {
    const resp = await request({
      url: 'https://v.sogou.com/v?ie=utf8&query=&p=40030600',
      headers: {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Encoding': 'identity',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'User-Agent': getRandomUserAgent(),
      },
      timeoutMs: 10000,
      retries: 1,
    });

    const cookies = extractCookies(resp.headers);
    const cookieObj = {};
    if (cookies) {
      cookies.split('; ').forEach(cookie => {
        const [key, value] = cookie.split('=');
        if (key && value) {
          cookieObj[key.trim()] = value.trim();
        }
      });
    }

    return { cookieStr: cookies || '', cookieObj };
  } catch {
    return { cookieStr: '', cookieObj: {} };
  }
}

/**
 * 发起HTTP GET请求
 * @param {string} url - 请求URL
 * @param {string} cookieStr - cookie字符串（可选）
 * @returns {Promise<string>} 响应HTML内容
 */
async function httpGet(url, cookieStr = '') {
  const headers = {
    ...HEADERS,
    'User-Agent': getRandomUserAgent(),
  };
  if (cookieStr) {
    headers['Cookie'] = cookieStr;
  }

  const resp = await requestText({
    url,
    headers,
    timeoutMs: 30000,
    retries: 1,
  });

  return resp.text;
}

/**
 * 从搜狗搜索页 HTML 中解析文章列表
 * @param {string} html
 * @param {number} maxResults
 */
function parseArticlesFromSearchHtml(html, maxResults) {
  const articles = [];

  // 定位 ul.news-list 区块
  const newsListHtml = extractByClass(html, 'ul', 'news-list');
  if (!newsListHtml) return [];

  const liBlocks = extractBlocks(newsListHtml, 'li');
  for (const liHtml of liBlocks) {
    if (articles.length >= maxResults) break;
    const article = parseArticle(liHtml);
    if (article) {
      articles.push(article);
    }
  }

  return articles;
}

/**
 * 从HTML中提取跳转URL（处理JavaScript跳转或meta refresh）
 * @param {string} html - HTML内容
 * @returns {string|null} 跳转URL
 */
function extractRedirectUrlFromHtml(html) {
  // 尝试匹配 meta refresh
  const metaMatch = html.match(/<meta[^>]*http-equiv=["']refresh["'][^>]*content=["']\d+;\s*url=([^"']+)["'][^>]*>/i);
  if (metaMatch) {
    return metaMatch[1];
  }
  
  // 尝试匹配 JavaScript 跳转
  const jsMatch = html.match(/location\.href\s*=\s*["']([^"']+)["']/i) || 
                  html.match(/location\s*=\s*["']([^"']+)["']/i) ||
                  html.match(/window\.location\s*=\s*["']([^"']+)["']/i);
  if (jsMatch) {
    return jsMatch[1];
  }

  // 尝试匹配“拼接 url 变量 + location.replace(url)”的跳转方式
  // 典型形态：
  //   var url = '';
  //   url += 'https://mp.';
  //   url += 'weixin.qq.com/...';
  //   window.location.replace(url)
  // 参考截图中的 Python 思路：re.findall("url\s*\+=\s*'([^']*)'") 后 join
  const urlParts = [];
  for (const m of html.matchAll(/url\s*\+=\s*'([^']*)'/g)) {
    urlParts.push(m[1]);
  }
  for (const m of html.matchAll(/url\s*\+=\s*"([^"]*)"/g)) {
    urlParts.push(m[1]);
  }
  if (urlParts.length > 0) {
    const joined = urlParts.join('');
    if (joined.includes('mp.weixin.qq.com')) {
      return joined;
    }
  }
  
  return null;
}

/**
 * 获取URL重定向后的真实地址（参考Python实现）
 * @param {string} url - 原始URL
 * @param {Object} cookieObj - cookie对象
 * @param {number} retries - 重试次数
 * @returns {Promise<string>} 重定向后的真实URL
 */
function getRealUrl(url, cookieObj = {}, retries = 3) {
  return new Promise((resolve) => {
    // 如果不是搜狗链接，直接返回原URL
    if (!url.includes('weixin.sogou.com')) {
      resolve(url);
      return;
    }

    (async () => {
      // 构建Cookie字符串
      const baseCookies = 'ABTEST=7|1716888919|v1; IPLOC=CN5101; ariaDefaultTheme=default; ariaFixed=true; ariaReadtype=1; ariaStatus=false';
      const snuid = cookieObj['SNUID'] || '';
      const cookieStr = snuid ? `${baseCookies}; SNUID=${snuid}` : baseCookies;

      const headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Encoding': 'identity',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Cookie': cookieStr,
        'User-Agent': getRandomUserAgent(),
      };

      for (let attempt = 0; attempt < retries; attempt++) {
        try {
          const resp = await request({
            url,
            headers,
            timeoutMs: 5000,
            retries: 0,
          });

          // 检查重定向（不跟随重定向，直接获取Location）
          if (resp.statusCode >= 300 && resp.statusCode < 400 && resp.headers.location) {
            const redirectUrl = resp.headers.location;
            if (redirectUrl.includes('mp.weixin.qq.com')) {
              resolve(redirectUrl);
              return;
            }
            resolve(url);
            return;
          }

          if (resp.statusCode === 200) {
            const html = resp.body.toString('utf-8');
            console.error(`  获取到HTML内容(长度: ${html.length})，尝试解析跳转URL...`);
            const redirectUrl = extractRedirectUrlFromHtml(html);
            if (redirectUrl && redirectUrl.includes('mp.weixin.qq.com')) {
              resolve(redirectUrl);
              return;
            }
            resolve(url);
            return;
          }
        } catch {
          // 忽略错误，进入重试
        }

        if (attempt < retries - 1) {
          await sleep(1000);
        }
      }

      resolve(url);
    })();
  });
}

function parseCliArgs(args) {
  let query = '';
  let num = 10;
  let output = '';
  let resolveRealUrl = false;
  let days = 0; // 客户端按 datetime 二次过滤的时间窗（天），0 表示不过滤

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '-n' || args[i] === '--num') {
      num = parseInt(args[i + 1]) || 10;
      i++;
    } else if (args[i] === '-o' || args[i] === '--output') {
      output = args[i + 1] || '';
      i++;
    } else if (args[i] === '-d' || args[i] === '--days') {
      days = parseInt(args[i + 1]) || 0;
      i++;
    } else if (args[i] === '-r' || args[i] === '--resolve-url') {
      resolveRealUrl = true;
    } else if (!args[i].startsWith('-')) {
      query = args[i];
    }
  }

  return { query, num, output, resolveRealUrl, days };
}

/**
 * 按 datetime 字段做客户端二次时间过滤（服务端无可用时间筛选）。
 * @param {Array} articles
 * @param {number} days - 保留最近 N 天内、有可解析 datetime 的文章；0 表示不过滤
 * @returns {{kept: Array, dropped: number, undated: number}}
 */
function filterByDays(articles, days) {
  if (!days || days <= 0) return { kept: articles, dropped: 0, undated: 0 };
  const cutoff = Date.now() - days * 24 * 60 * 60 * 1000;
  const kept = [];
  let dropped = 0;
  let undated = 0;
  for (const a of articles) {
    if (!a.datetime) { undated++; continue; }
    const t = new Date(a.datetime.replace(' ', 'T')).getTime();
    if (isNaN(t)) { undated++; continue; }
    if (t >= cutoff) kept.push(a); else dropped++;
  }
  return { kept, dropped, undated };
}

/**
 * 批量获取文章的真实URL
 * @param {Array} articles - 文章列表
 * @returns {Promise<Array>} 包含真实URL的文章列表
 */
async function resolveRealUrls(articles) {
  // 获取cookie用于解析URL
  const { cookieObj } = await getSogouCookie();
  
  console.error(`获取到 ${articles.length} 篇文章，开始解析真实URL...`);
  console.error('注意：搜狗微信有严格的反爬虫机制，可能无法获取真实URL');
  
  const results = [];
  let successCount = 0;
  let failCount = 0;
  
  for (let i = 0; i < articles.length; i++) {
    const article = articles[i];
    try {
      console.error(`[${i + 1}/${articles.length}] 解析: ${article.title.substring(0, 30)}...`);
      const realUrl = await getRealUrl(article.url, cookieObj);
      
      // 检查是否成功获取到真实URL（不是搜狗链接，也不是antispider页面）
      const isSuccess = !realUrl.includes('weixin.sogou.com') && !realUrl.includes('antispider');
      
      results.push({
        ...article,
        url: isSuccess ? realUrl : article.url,
        url_resolved: isSuccess
      });
      
      if (isSuccess) {
        successCount++;
      } else {
        failCount++;
      }
      
      // 添加延迟避免请求过快
      if (i < articles.length - 1) {
        await new Promise(resolve => setTimeout(resolve, 500 + Math.random() * 1000));
      }
    } catch (error) {
      console.error(`  解析失败: ${error.message}`);
      failCount++;
      results.push({
        ...article,
        url: article.url,
        url_resolved: false
      });
    }
  }
  
  console.error(`\n解析完成: 成功 ${successCount}, 失败 ${failCount}`);
  
  return results;
}

/**
 * 解析相对时间为绝对时间
 * @param {string} timeText - 时间文本（如"1天前"、"2小时前"、"30分钟前"）
 * @returns {Object} 包含datetime和dateText的对象
 */
function parseRelativeTime(timeText) {
  if (!timeText) return { datetime: '', dateText: '' };
  
  const now = new Date();
  let targetDate = new Date(now);
  
  // 匹配各种相对时间格式
  const dayMatch = timeText.match(/(\d+)天前/);
  const hourMatch = timeText.match(/(\d+)小时前/);
  const minuteMatch = timeText.match(/(\d+)分钟前/);
  
  if (dayMatch) {
    const days = parseInt(dayMatch[1]);
    targetDate.setDate(now.getDate() - days);
  } else if (hourMatch) {
    const hours = parseInt(hourMatch[1]);
    targetDate.setHours(now.getHours() - hours);
  } else if (minuteMatch) {
    const minutes = parseInt(minuteMatch[1]);
    targetDate.setMinutes(now.getMinutes() - minutes);
  } else {
    // 尝试匹配标准日期格式（如"2024-01-15"）
    const dateMatch = timeText.match(/(\d{4})-(\d{2})-(\d{2})/);
    if (dateMatch) {
      targetDate = new Date(
        parseInt(dateMatch[1]),
        parseInt(dateMatch[2]) - 1,
        parseInt(dateMatch[3])
      );
    } else {
      return { datetime: '', dateText: timeText };
    }
  }
  
  const datetime = targetDate.toISOString().slice(0, 19).replace('T', ' ');
  const dateText = `${targetDate.getFullYear()}年${String(targetDate.getMonth() + 1).padStart(2, '0')}月${String(targetDate.getDate()).padStart(2, '0')}日`;
  
  return { datetime, dateText };
}

/**
 * 将Date对象格式化为中国时区（UTC+8）的datetime字符串
 * @param {Date} date - Date对象
 * @returns {string} YYYY-MM-DD HH:mm:ss 格式的中国时间
 */
function formatChinaDateTime(date) {
  // 转换为中国时间（UTC+8）
  const chinaTime = new Date(date.getTime() + 8 * 60 * 60 * 1000);
  const year = chinaTime.getUTCFullYear();
  const month = String(chinaTime.getUTCMonth() + 1).padStart(2, '0');
  const day = String(chinaTime.getUTCDate()).padStart(2, '0');
  const hours = String(chinaTime.getUTCHours()).padStart(2, '0');
  const minutes = String(chinaTime.getUTCMinutes()).padStart(2, '0');
  const seconds = String(chinaTime.getUTCSeconds()).padStart(2, '0');
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
}

/**
 * 解析单篇文章
 * @param {string} liHtml - 单个 <li> 的内部 HTML
 * @returns {Object|null} 文章数据对象
 */
function parseArticle(liHtml) {
  try {
    // 获取标题和URL（h3 内的第一个 a）
    const h3Html = extractBlocks(liHtml, 'h3')[0] || '';
    const titleAnchor = extractFirstAnchor(h3Html || liHtml);
    if (!titleAnchor || !titleAnchor.text) return null;

    const title = titleAnchor.text;
    let url = titleAnchor.href || '';

    // 处理相对URL
    if (url.startsWith('/')) {
      url = `https://weixin.sogou.com${url}`;
    }

    // 获取概要（p.txt-info）
    const txtInfoHtml = extractByClass(liHtml, 'p', 'txt-info');
    const summary = txtInfoHtml ? htmlToText(txtInfoHtml) : '';

    // 获取日期和来源
    let datetime = '';
    let dateText = '';
    let source = '';
    let timeDescription = ''; // 原始时间文字描述（如"2小时前"）

    const sourceBoxHtml = extractByClass(liHtml, '*', 's-p');
    if (sourceBoxHtml) {
      // 找不到 .s2 时不取时间（计入 undated），避免从无关 script 误取数字
      const s2Html = extractByClass(sourceBoxHtml, '*', 's2') || '';
      const scriptText = extractScriptText(s2Html);
      const timestampMatch = scriptText.match(/(\d{10})/);

      if (timestampMatch) {
        const timestamp = parseInt(timestampMatch[1]) * 1000;
        const date = new Date(timestamp);
        datetime = formatChinaDateTime(date);
        dateText = `${date.getFullYear()}年${String(date.getMonth() + 1).padStart(2, '0')}月${String(date.getDate()).padStart(2, '0')}日`;

        // 计算相对时间描述
        const now = new Date();
        const diffMs = now - date;
        const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
        if (diffDays > 0) {
          timeDescription = `${diffDays}天前`;
        } else if (diffHours > 0) {
          timeDescription = `${diffHours}小时前`;
        } else {
          const diffMinutes = Math.floor(diffMs / (1000 * 60));
          timeDescription = diffMinutes > 0 ? `${diffMinutes}分钟前` : '刚刚';
        }
      } else {
        // 无时间戳，尝试从纯文本获取
        const timeText = htmlToText(s2Html);
        if (timeText) {
          timeDescription = timeText;
          const parsedTime = parseRelativeTime(timeText);
          datetime = parsedTime.datetime;
          dateText = parsedTime.dateText;
        }
      }

      // 获取来源公众号名称 - 优先 .all-time-y2，其次 a.account
      const sourceSpanHtml = extractByClass(sourceBoxHtml, '*', 'all-time-y2');
      if (sourceSpanHtml) {
        source = htmlToText(sourceSpanHtml);
      } else {
        const accountRe = /<a\b[^>]*class=["'][^"']*\baccount\b[^"']*["'][^>]*>([\s\S]*?)<\/a>/i;
        const am = accountRe.exec(sourceBoxHtml);
        if (am) source = htmlToText(am[1]);
      }
    }

    return {
      title,
      url,
      summary,
      datetime,
      date_text: dateText,
      date_description: timeDescription || dateText,
      source
    };
  } catch (error) {
    console.error('解析文章失败:', error.message);
    return null;
  }
}

/**
 * 搜索微信公众号文章
 * @param {string} query - 搜索关键词
 * @param {number} maxResults - 最大返回结果数（默认10，最大50）
 * @returns {Promise<Array>} 文章列表
 */
async function searchWechatArticles(query, maxResults = 10, resolveRealUrl = false, days = 0) {
  // 限制最大结果数
  maxResults = Math.min(maxResults, 50);

  // 若启用时间窗过滤，多抓几页以补足过滤后的数量（上限 50）
  const targetRaw = days > 0 ? Math.min(maxResults * 3, 50) : maxResults;

  const articles = [];
  let page = 1;
  const pagesNeeded = Math.ceil(targetRaw / 10);

  while (articles.length < targetRaw && page <= pagesNeeded) {
    try {
      // 先获取cookie
      const { cookieStr } = await getSogouCookie();
      
      // 构建搜索URL
      const encodedQuery = encodeURIComponent(query);
      const url = `https://weixin.sogou.com/weixin?query=${encodedQuery}&s_from=input&_sug_=n&type=2&page=${page}&ie=utf8`;

      const html = await httpGet(url, cookieStr);

      const remaining = targetRaw - articles.length;
      const parsed = parseArticlesFromSearchHtml(html, remaining);
      if (parsed.length === 0) break;
      articles.push(...parsed);

      page++;

      // 请求间隔（固化的反爬节流，避免连续请求触发限流）
      if (page <= pagesNeeded) {
        await new Promise(resolve => setTimeout(resolve, 1200 + Math.random() * 1200));
      }
    } catch (error) {
      console.error(`请求第${page}页失败:`, error.message);
      break;
    }
  }

  // 客户端按 datetime 二次时间过滤
  let result = articles;
  if (days > 0) {
    const { kept, dropped, undated } = filterByDays(articles, days);
    console.error(`时间窗过滤(最近${days}天): 抓取${articles.length}条 → 命中${kept.length}条，超窗丢弃${dropped}条，无日期跳过${undated}条`);
    if (kept.length === 0) {
      console.error('提示: 时间窗内无匹配文章。数据源按相关度排序、覆盖有限，该关键词近期可能确无收录；请如实告知用户，勿外推。');
    }
    result = kept;
  }

  result = result.slice(0, maxResults);
  
  // 如果需要解析真实URL
  if (resolveRealUrl && result.length > 0) {
    console.error('正在解析真实URL...');
    return await resolveRealUrls(result);
  }

  return result;
}

/**
 * 主函数 - 处理命令行参数
 */
async function main() {
  const args = process.argv.slice(2);

  const { query, num, output, resolveRealUrl, days } = parseCliArgs(args);
  
  if (!query) {
    console.log(`
微信公众号文章搜索工具（零第三方依赖，可离线运行）

用法:
  node search_wechat.js <关键词> [选项]

选项:
  -n, --num <数量>       返回结果数量（默认10，最大50）
  -d, --days <天数>      仅保留最近 N 天内、有可解析发布时间的文章（客户端过滤）
  -o, --output <文件>    输出JSON文件路径
  -r, --resolve-url      解析真实的微信文章URL（会额外请求每个链接）

示例:
  node search_wechat.js "人工智能" -n 20
  node search_wechat.js "ChatGPT" -n 10 -d 365
  node search_wechat.js "人工智能" -n 5 -r
`);
    process.exit(0);
  }
  
  try {
    console.error(`正在搜索: "${query}"...`);
    
    const articles = await searchWechatArticles(query, num, resolveRealUrl, days);
    
    const result = {
      query,
      total: articles.length,
      articles
    };
    
    const jsonOutput = JSON.stringify(result, null, 2);
    
    if (output) {
      const fs = require('fs');
      fs.writeFileSync(output, jsonOutput, 'utf-8');
      console.error(`结果已保存到: ${output}`);
    }
    
    console.log(jsonOutput);
  } catch (error) {
    console.error('搜索失败:', error.message);
    process.exit(1);
  }
}

// 导出模块供其他脚本使用
module.exports = {
  searchWechatArticles
};

// 如果直接运行此脚本
if (require.main === module) {
  main();
}
