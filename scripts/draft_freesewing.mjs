// Executes upstream FreeSewing designs from an explicitly installed local module.
import { readFile, writeFile, mkdir, access } from 'node:fs/promises'
import { resolve, dirname } from 'node:path'
import { pathToFileURL } from 'node:url'
import { createHash } from 'node:crypto'

const [modulePath, exportName, settingsPath, outputPath] = process.argv.slice(2)
if (!outputPath) throw new Error('Usage: node draft_freesewing.mjs module.mjs Export settings.json output.svg')
const settingsText = await readFile(settingsPath, 'utf8')
const settings = JSON.parse(settingsText)
if (!settings.measurements || Object.values(settings.measurements).some(v => typeof v !== 'number' || !Number.isFinite(v) || v <= 0)) {
  throw new Error('Positive millimetre body measurements required')
}
if ([modulePath, settingsPath].some(p => resolve(p) === resolve(outputPath))) throw new Error('Output cannot overwrite input')
const module = await import(pathToFileURL(resolve(modulePath)).href)
const Pattern = module[exportName]
if (typeof Pattern !== 'function') throw new Error('Named FreeSewing design export required')
const pattern = new Pattern(settings)
const svg = pattern.draft().render()
const errors = [pattern.store, ...pattern.setStores].flatMap(store => store.logs.error)
if (errors.length || !svg.includes('<svg') || !svg.includes('<path')) throw new Error(JSON.stringify(errors))
const hash = value => createHash('sha256').update(value).digest('hex')
const reportPath = outputPath + '.json'
const request = { exportName, settings_sha256: hash(settingsText), module_sha256: hash(await readFile(modulePath)) }
let exists = true
try { await access(outputPath) } catch (error) { if (error.code === 'ENOENT') exists = false; else throw error }
if (exists) {
  const previous = JSON.parse(await readFile(reportPath, 'utf8'))
  if (JSON.stringify(previous.request) !== JSON.stringify(request) || hash(await readFile(outputPath)) !== previous.svg_sha256) {
    throw new Error('Existing output differs; choose a fresh output path')
  }
  console.log(JSON.stringify(previous))
} else {
  await mkdir(dirname(resolve(outputPath)), { recursive: true })
  await writeFile(outputPath, svg, { flag: 'wx' })
  const report = { request, design: module.about?.pkg, version: module.about?.version,
    svg_sha256: hash(svg), bytes: Buffer.byteLength(svg), draft_errors: errors,
    warnings: [pattern.store, ...pattern.setStores].flatMap(store => store.logs.warn),
    fit_verified: false, industrial_dxf_exchange_verified: false }
  await writeFile(reportPath, JSON.stringify(report, null, 2), { flag: 'wx' })
  console.log(JSON.stringify(report))
}
