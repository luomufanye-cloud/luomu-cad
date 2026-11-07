import { readFile } from 'node:fs/promises'
import { drawOpening, drawFurniture, wallGeometry, wallPoint, furnitureCatalog, openingCatalog } from './house_plan_upstream.mjs'
import { ComponentCanvas } from './component_canvas.mjs'

const templates = new Map(furnitureCatalog.flatMap(group=>group.items.map(item=>[item.key,{...item,group:group.group}])))

export function catalog() {
  return {openings: openingCatalog, furniture: [...templates.values()].map(item => {
    try {
      furnitureGeometry(item)
      return {...item, native_geometry:true}
    } catch(error) {
      return {...item, native_geometry:false, reason:error.message}
    }
  })}
}

export function furnitureGeometry(input) {
  const template = templates.get(input.key)
  if (!template) throw new Error('Unknown upstream furniture key '+input.key)
  const item = {...structuredClone(template), ...input}
  const canvas = new ComponentCanvas()
  canvas.translate(item.x || 0, item.y || 0)
  canvas.rotate((item.rot || 0)*Math.PI/180)
  canvas.scale(1,-1)
  drawFurniture(canvas,item,1)
  if (!canvas.entities.length) throw new Error('Upstream component produced no native geometry')
  return {id: input.id, key: item.key, name: template.name, entities: canvas.entities}
}

export function assemble(plan) {
  const geometry = wallGeometry(plan)
  const walls = [], openings = []
  const xy = point => [point.x,point.y]
  for (const wall of geometry.active) {
    wall.exteriorSide = wall.w.exterior_side
    for (const solid of wall.solids) {
      const start = Math.max(solid.s0,wall.mA ?? -Infinity)
      const end = Math.min(solid.s1,wall.mB ?? Infinity)
      if (end-start <= .5) continue
      walls.push({wall:wall.w.id, polygon:[xy(wallPoint(wall,start,-wall.ht)),xy(wallPoint(wall,end,-wall.ht)),
        xy(wallPoint(wall,end,wall.ht)),xy(wallPoint(wall,start,wall.ht))]})
    }
    for (const opening of wall.ops) {
      if (opening.s0 < (wall.mA ?? 0) || opening.s1 > (wall.mB ?? wall.len)) {
        throw new Error('Opening overlaps wall joint: '+opening.o.id)
      }
      const canvas = new ComponentCanvas()
      drawOpening(canvas,wall,opening.o,opening.s0,opening.s1,1,false)
      openings.push({id:opening.o.id,wall:wall.w.id,type:opening.o.type,
        jambs:[xy(wallPoint(wall,opening.s0,opening.o.side*wall.ht)),xy(wallPoint(wall,opening.s1,opening.o.side*wall.ht))],
        entities:canvas.entities})
    }
  }
  for (const joint of geometry.miters) walls.push({wall:joint.gs.map(g=>g.w.id).join('+'),polygon:joint.poly.map(xy)})
  return {walls,openings,furniture:(plan.furniture||[]).map(furnitureGeometry)}
}

if (process.argv[1]?.endsWith('house_components.mjs')) {
  const action = process.argv[2]
  if (action==='catalog') console.log(JSON.stringify(catalog()))
  else if (action==='build') console.log(JSON.stringify(assemble(JSON.parse(await readFile(process.argv[3],'utf8')))))
  else if (action==='probe') {
    const results = []
    for (const item of templates.values()) {
      try { results.push({key:item.key,name:item.name,ok:true,entities:furnitureGeometry(item).entities.length}) }
      catch(error) { results.push({key:item.key,name:item.name,ok:false,error:error.message}) }
    }
    console.log(JSON.stringify(results))
  } else throw new Error('Use catalog, build input.json, or probe')
}
