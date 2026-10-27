// dsh-plugin-boss-zhipin — registers the BOSS直聘 delivery skill as a bundled skill.
//
// The plugin imports nothing from the harness. It only consumes the `skills`
// service at apply time and returns the disposer from `ctx.skills.register()`
// through `ctx.effect()`, so unloading removes the contribution cleanly.
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

export const name = 'dsh-plugin-boss-zhipin'
export const inject = ['skills']

const packageRoot = dirname(fileURLToPath(import.meta.url))
const skillRoot = join(packageRoot, 'skill')

const DESCRIPTION =
  'BOSS直聘自动化投递（DSH 插件版）：三层循环（关键词进化 + 职位页串行投递），' +
  '通过 Kimi WebBridge 控制已登录浏览器，按用户画像逐条语义决策后投递，' +
  '支持环境自检、断点续传、每日目标检测与 HTML 汇报。'

/**
 * Remove the YAML frontmatter block. The body is what the model reads, so this
 * stays tolerant of CRLF and of block-scalar descriptions.
 * @param {string} text raw SKILL.md
 * @returns {string} instruction body
 */
export function stripFrontmatter(text) {
  const clean = text.replace(/^\uFEFF/, '')
  const match = /^---[ \t]*\r?\n[\s\S]*?\r?\n---[ \t]*(?:\r?\n|$)/.exec(clean)
  const body = match ? clean.slice(match[0].length) : clean
  return body.replace(/^(?:[ \t]*\r?\n)+/, '')
}

/**
 * @param {import('@deepseek-ai/cordis').Context} ctx
 */
export function apply(ctx) {
  const raw = readFileSync(join(skillRoot, 'SKILL.md'), 'utf8')
  const content = stripFrontmatter(raw)

  ctx.effect(() =>
    ctx.skills.register({
      name: 'boss-zhipin-deliver',
      source: 'bundled',
      description: DESCRIPTION,
      content,
      resourceBase: { kind: 'directory', path: skillRoot },
    }),
  )
}
