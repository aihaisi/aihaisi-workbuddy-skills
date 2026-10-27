# Remotion 最小可用工程（本机实测通过 2026-10-09）

照抄这套就能跑。已在 Windows + Node 22.22.2 + Remotion 4.0.534 验证：
90 帧 1920×1080 输出 MP4 成功。

---

## 1. `package.json`

```json
{
  "name": "my-video",
  "private": true,
  "scripts": {
    "studio": "remotion studio src/index.ts",
    "render": "remotion render src/index.ts MyComp out/video.mp4"
  },
  "dependencies": {
    "@remotion/cli": "4.0.534",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "remotion": "4.0.534",
    "zod": "^3.22.3"
  },
  "devDependencies": {
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "typescript": "^5.8.2"
  }
}
```

安装（**必须绕开那个坏代理**）：

```bash
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy
npm config set proxy null && npm config set https-proxy null
npm install --no-audit --no-fund
```

⚠️ esbuild 的 postinstall 会报 `pid: 0` 错误、npm 退出码非 0 —— **正常现象**。
验证方式：`node_modules/@esbuild/win32-x64/esbuild.exe --version` 能打印版本即可继续。

---

## 2. `src/index.ts`

```ts
import { registerRoot } from "remotion";
import { RemotionRoot } from "./Root";

registerRoot(RemotionRoot);
```

---

## 3. `src/schema.ts` —— 参数契约（这条路最强的部分）

```ts
import { z } from "zod";

export const MySchema = z.object({
  headline: z.string().max(24),
  subtitle: z.string().max(40),
  data: z.array(z.object({
    k: z.string().max(8),
    v: z.number().min(0).max(100),
  })).min(2).max(10),
});

export type MyProps = z.infer<typeof MySchema>;
```

为什么值得单独写：**渲染前就拦住参数错误**，且 Remotion Studio 会据此自动生成编辑表单。
这是裸 HTML 路线给不了的。

---

## 4. `src/Root.tsx` —— 注册表

```tsx
import React from "react";
import { Composition } from "remotion";
import { MyComp } from "./MyComp";
import { MySchema } from "./schema";

export const RemotionRoot: React.FC = () => (
  <Composition
    id="MyComp"
    component={MyComp}
    durationInFrames={90}   // 90 帧 @ 30fps = 3 秒
    fps={30}
    width={1920}
    height={1080}
    schema={MySchema}
    defaultProps={{
      headline: "对比",
      subtitle: "示例字幕",
      data: [
        { k: "1990", v: 12 }, { k: "2000", v: 26 },
        { k: "2010", v: 41 }, { k: "2020", v: 58 },
      ],
    }}
  />
);
```

---

## 5. `src/MyComp.tsx` —— 组件骨架

```tsx
import React from "react";
import {
  AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig,
} from "remotion";
import type { MyProps } from "./schema";

const ease = Easing.out(Easing.cubic);   // 等价于 easeOutCubic

export const MyComp: React.FC<MyProps> = ({ headline, subtitle, data }) => {
  const frame = useCurrentFrame();            // ← 核心：帧号驱动，和裸 HTML 路线同一纪律
  const { width, height, fps } = useVideoConfig();

  // 帧窗口 → 进度 → 缓动，这一段和手写 Canvas 完全同构
  const titleT = interpolate(frame, [12, 60], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });

  return (
    <AbsoluteFill>
      <AbsoluteFill style={{
        background: "radial-gradient(circle at 50% 46%, #150E2C 0%, #0A0618 55%, #030109 100%)",
      }} />

      <div style={{
        position: "absolute", top: height * 0.055, left: 0, width: "100%",
        textAlign: "center",
        fontFamily: '"Noto Sans SC","Microsoft YaHei",sans-serif',
        fontSize: 132, fontWeight: 800, letterSpacing: "0.06em",
        background: "linear-gradient(178deg,#FFE3A8 0%,#FFD995 46%,#FFCFA4 100%)",
        WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent",
        opacity: titleT,
        transform: `translateY(${(1 - titleT) * 30}px)`,
      }}>{headline}</div>

      <div style={{
        position: "absolute", bottom: 96, left: 0, width: "100%",
        textAlign: "center",
        fontFamily: '"Noto Sans SC","Microsoft YaHei",sans-serif',
        fontSize: 56, fontWeight: 700, color: "#F9F1F2",
        textShadow: "0 2px 18px rgba(0,0,0,0.55)",
      }}>{subtitle}</div>
    </AbsoluteFill>
  );
};
```

---

## 6. 渲染

```bash
# 🔴 必须带 --browser-executable，否则 Remotion 会去下载它自己的 Chrome（国内会卡死）
./node_modules/.bin/remotion render src/index.ts MyComp out/video.mp4 \
  --browser-executable="C:\Program Files\Google\Chrome\Application\chrome.exe"

# 只出一张静帧 —— 调试排版最快的方式
./node_modules/.bin/remotion still src/index.ts MyComp out/frame.png --frame=75

# 预览
./node_modules/.bin/remotion studio src/index.ts
```

或写进 `remotion.config.ts` 省得每次传：

```ts
import { Config } from "@remotion/cli/config";
Config.setBrowserExecutable("C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe");
Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
```

---

## 7. 与 Canvas 路线的 API 对照

| 要做的事 | Remotion | 裸 Canvas |
|---|---|---|
| 拿帧号 | `useCurrentFrame()` | `setFrame(f)` 收到的 `f` |
| 帧窗口映射 | `interpolate(f,[a,b],[0,1],{extrapolateLeft:'clamp'})` | `seg(f,a,b)` = `clamp01((f-a)/(b-a))` |
| 缓动 | `Easing.out(Easing.cubic)` | `easeOutCubic(t)` |
| 四阶缓动 | `Easing.out(Easing.poly(4))` | `easeOutQuart(t)` |
| 画矩形 | `<div>` / `<rect>` | `ctx.fillRect()` |
| 渐变文字 | CSS `background-clip:text` | 要手动逐字裁切，麻烦 |
| 文字宽度 | 浏览器自动排版 | `ctx.measureText()` |
| 分层 | `<AbsoluteFill>` / `<Sequence>` | 手写 z 序 ctx 调用顺序 |

**结论：视觉配方可 1:1 互搬，痛点在排版** —— CSS 省事但字体度量不透明，
Canvas 可控但要自己算。选哪个看内容偏排版还是偏图形。
